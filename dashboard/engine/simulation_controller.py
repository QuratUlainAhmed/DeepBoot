"""Step-wise driver for the unmodified research Cluster.

`SimulationController.advance_second()` is a line-for-line copy of ONE iteration
of the `while not simulator.all_complete()` loop in simulate()
(simulator.py lines 1095-1150, logging lines omitted):

    simulator.clock += 1
    real, running, use = simulator.calculate_real_gpu_usage()
    simulator.gpu_util_dict[...] append
    simulator.update_infer_pod_status()
    if not simulator.event_update(): continue
    interval = simulator.clock - previous_clock
    simulator.step(interval, args.interval)
    previous_clock = simulator.clock

Everything else in this file only OBSERVES state (copies of allocations, pod
states, job fields, and records from instrumentation.py) to build an event log
and snapshots for playback. The test suite verifies that a run through this
controller reproduces the CLI's summary.json and gpu.log exactly.
"""
from __future__ import annotations

import copy
import threading
import time
import traceback
from collections import Counter
from typing import Any, Dict, List, Optional

import pandas

from . import instrumentation
from .sim_bridge import SimConfig, apply_globals, build_cluster, sim
from .workload_manager import InjectionError, inject_job, is_inference_name

MAX_SNAPSHOTS = 20000


def _pod_table(cluster) -> Dict[str, Dict[str, Any]]:
    out = {}
    for app, pods in cluster.infer_pod_status.items():
        for pod, info in pods.items():
            out[pod] = {
                "app": app,
                "status": info.get("status"),
                "live_time": info.get("live_time"),
                "curr_job": info.get("curr_job"),
                "cache_times": info.get("cache_times", 0),
            }
    return out


class SimulationController:
    def __init__(self, workload: pandas.DataFrame, cfg: SimConfig, label: str = "") -> None:
        instrumentation.install()
        self.lock = threading.RLock()
        self.cfg = cfg
        self.label = label
        self.initial_workload = workload.copy()
        self.injected_rows: List[dict] = []
        self.reset()

    # ------------------------------------------------------------------ setup
    def reset(self) -> None:
        with self.lock:
            self.cluster = build_cluster(self.initial_workload.copy(), self.cfg)
            self.previous_clock = 0
            self.events: List[Dict[str, Any]] = []
            self.snapshots: List[Dict[str, Any]] = []
            self.alloc_series: List[Dict[str, Any]] = []
            self.decisions: List[Dict[str, Any]] = []
            self.wall_time_s = 0.0
            self.steps_executed = 0
            self.injected_rows = []
            self.playing = False
            self.error = None
            self._take_snapshot([])  # state before any job arrives

    def _ensure_globals(self) -> None:
        # Module globals are process-wide; re-apply before every mutation so a
        # second controller (e.g. a test) can never leak its flags into this one.
        apply_globals(self.cfg)

    # ------------------------------------------------------------- core loop
    def advance_second(self) -> Optional[Dict[str, Any]]:
        """One iteration of simulate()'s loop. Returns a step record if the
        simulator executed a scheduling step (event_update() True), else None."""
        c = self.cluster
        c.clock += 1
        real_gpu_util, real_running_gpu_util, gpu_util = c.calculate_real_gpu_usage()
        c.gpu_util_dict["clock"].append(c.clock)
        c.gpu_util_dict["real_gpu_use"].append(real_gpu_util)
        c.gpu_util_dict["real_running_gpu_use"].append(real_running_gpu_util)
        c.gpu_util_dict["gpu_use"].append(gpu_util)
        c.update_infer_pod_status()
        if not c.event_update():
            return None
        interval = c.clock - self.previous_clock

        before_alloc = {k: list(v) for k, v in c.allocations.items()}
        before_finished = set(c.finish_job_set)
        instrumentation.RECORDER.start()
        n_hist = len(c.optimize_history)
        t0 = time.perf_counter()
        c.step(interval, sim.args.interval)
        self.wall_time_s += time.perf_counter() - t0
        records = instrumentation.RECORDER.stop()

        step_rec = self._describe_step(interval, before_alloc, before_finished, records, n_hist)
        self.previous_clock = c.clock
        self.steps_executed += 1
        return step_rec

    def is_complete(self) -> bool:
        return self.cluster.all_complete()

    def blocked(self) -> bool:
        """True when the run cannot advance: finished, or the research code raised."""
        return self.error is not None or self.is_complete()

    def _fail(self, exc: BaseException) -> None:
        # The research simulator raised mid-step; its state may be partially
        # updated, so further stepping is refused until reset().
        self.error = {"type": type(exc).__name__, "message": str(exc)[:500],
                      "clock": self.cluster.clock, "traceback": traceback.format_exc()[-4000:]}
        self.playing = False

    def next_event(self, max_seconds: int = 10**7) -> Optional[Dict[str, Any]]:
        """Advance until the simulator executes its next scheduling step."""
        with self.lock:
            self._ensure_globals()
            if self.error is not None:
                return None
            pods_before = _pod_table(self.cluster)
            start = self.cluster.clock
            try:
                while not self.is_complete() and self.cluster.clock - start < max_seconds:
                    rec = self.advance_second()
                    if rec is not None:
                        rec["events"] = self._pod_events(pods_before) + rec["events"]
                        self._commit(rec)
                        return rec
            except Exception as exc:  # surfaced in the UI, never swallowed
                self._fail(exc)
            return None

    def run_until(self, target_clock: Optional[int] = None, wall_budget_s: float = 5.0) -> int:
        """Advance until target_clock (None = completion) or the wall budget is
        spent. Returns the number of scheduling steps executed. Can be called
        repeatedly to continue (used by the 'Run until' control)."""
        n = 0
        deadline = time.perf_counter() + wall_budget_s
        with self.lock:
            self._ensure_globals()
            while not self.blocked():
                if target_clock is not None and self.cluster.clock >= target_clock:
                    break
                if time.perf_counter() > deadline:
                    break
                pods_before = _pod_table(self.cluster)
                try:
                    rec = self.advance_second()
                except Exception as exc:
                    self._fail(exc)
                    break
                if rec is not None:
                    rec["events"] = self._pod_events(pods_before) + rec["events"]
                    self._commit(rec)
                    n += 1
        return n

    def inject(self, row: dict):
        with self.lock:
            if self.error is not None:
                raise InjectionError("The simulation stopped with an error; reset it first.")
            self._ensure_globals()
            job = inject_job(self.cluster, row, self.cfg.policy)
            self.injected_rows.append(dict(row))
            self.events.append(
                {"clock": self.cluster.clock, "type": "submitted",
                 "job": row["name"], "detail": f"submitted via dashboard; arrives at t={row['time']} s"}
            )
            return job

    # ------------------------------------------------------------ observation
    def _pod_events(self, before: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
        after = _pod_table(self.cluster)
        clock = self.cluster.clock
        evs = []
        for pod, info in before.items():
            if pod not in after:
                evs.append({"clock": clock, "type": "pod-removed", "job": pod,
                            "detail": f"inference pod {pod} ({info['app']}) deleted (AISS=0 lifecycle or sleep pod released)"})
            elif after[pod]["status"] != info["status"]:
                evs.append({"clock": clock, "type": "pod-state", "job": pod,
                            "detail": f"pod {pod} ({info['app']}): {info['status']} → {after[pod]['status']}"})
        return evs

    def _describe_step(self, interval, before_alloc, before_finished, records, n_hist) -> Dict[str, Any]:
        c = self.cluster
        clock = c.clock
        is_tick = clock % self.cfg.interval == 0
        if self.cfg.INFER_SCHEDULER:
            path = f"{self.cfg.policy}.optimize (training tick)" if is_tick else (
                "InferScheduler.random_allocate" if self.cfg.random_allocate else "InferScheduler (ATS-I)")
        else:
            path = f"{self.cfg.policy}.optimize (every event; INFER_SCHEDULER=0)"
        evs: List[Dict[str, Any]] = []

        for job in c.jobs:
            if self.previous_clock < job.submission_time <= clock:
                kind = "inference" if job.inference else "training"
                evs.append({"clock": clock, "type": "arrival", "job": job.name,
                            "detail": f"{kind} job arrives ({job.app}, t_submit={job.submission_time})"})

        for job in c.jobs:
            if job.inference and job.use_cache and job.start_execute_time is not None \
                    and self.previous_clock < job.start_execute_time <= clock:
                evs.append({"clock": clock, "type": "warm-reuse", "job": job.name,
                            "detail": f"reuses warm pod {job.pod_name} (no cold start) — Job.step, AISS lifecycle"})

        after_alloc = c.allocations
        for name in sorted(set(before_alloc) | set(after_alloc)):
            a0, a1 = before_alloc.get(name, []), list(after_alloc.get(name, []))
            if Counter(a0) == Counter(a1):
                continue
            job = c.job_dict.get(name)
            if job is None:
                continue
            fmt = lambda a: "{" + ", ".join(f"w{k}:{v}" for k, v in sorted(Counter(a).items())) + "}" if a else "∅"
            if job.inference:
                evs.append({"clock": clock, "type": "inference-placement" if a1 else "inference-release",
                            "job": name, "detail": f"{fmt(a0)} → {fmt(a1)}"})
            else:
                if not a0 and a1:
                    t = "training-start"
                elif a0 and not a1:
                    t = "training-released" if job.completion_time is not None else "training-preempted"
                elif len(a1) > len(a0):
                    t = "training-scale-up"
                elif len(a1) < len(a0):
                    t = "training-scale-down"
                else:
                    t = "training-migrate"
                mode = "AFE" if self.cfg.AFE else "stop-resume"
                detail = f"{len(a0)}→{len(a1)} GPUs {fmt(a0)} → {fmt(a1)}"
                if a1:
                    detail += f"; modelled rescale delay {job.rescale_time} s ({mode}); restarts={job.num_restarts}"
                evs.append({"clock": clock, "type": t, "job": name, "detail": detail,
                            "rescale_delay": job.rescale_time if a1 else 0, "gpus_before": len(a0), "gpus_after": len(a1)})

        for name in sorted(set(c.finish_job_set) - before_finished):
            job = c.job_dict[name]
            evs.append({"clock": clock, "type": "completion", "job": name,
                        "detail": f"completed; JCT = {job.completion_time - job.submission_time:.0f} s"})

        opt = c.optimize_history[n_hist:] if len(c.optimize_history) > n_hist else []
        cost = opt[-1][2] if opt else None
        rec = {"clock": clock, "interval": interval, "tick": is_tick, "path": path,
               "optimize_wall_s": cost, "decisions": records, "events": evs}
        return rec

    def _alloc_breakdown(self) -> Dict[str, int]:
        c = self.cluster
        pods = _pod_table(c)
        out = {"training": 0, "training_rescaling": 0, "inference_running": 0,
               "inference_protect": 0, "inference_sleep": 0}
        for name, alloc in c.allocations.items():
            if not alloc:
                continue
            job = c.job_dict[name]
            if job.inference:
                st = pods.get(name, {}).get("status", "RUNNING")
                key = {"PROTECT": "inference_protect", "SLEEP": "inference_sleep"}.get(st, "inference_running")
                out[key] += len(alloc)
            else:
                key = "training_rescaling" if job.current_rescale_time > 0 or job.rescale_time > 0 else "training"
                out[key] += len(alloc)
        return out

    def _take_snapshot(self, events) -> None:
        c = self.cluster
        snap = {
            "clock": c.clock,
            "allocations": {k: list(v) for k, v in c.allocations.items() if v},
            "pods": _pod_table(c),
            "breakdown": self._alloc_breakdown(),
            "rescaling": sorted(j.name for j in c.jobs if not j.inference and j.placement
                                and (j.current_rescale_time > 0 or j.rescale_time > 0)),
            "events": events,
        }
        self.snapshots.append(snap)
        if len(self.snapshots) > MAX_SNAPSHOTS:
            del self.snapshots[1:len(self.snapshots) - MAX_SNAPSHOTS + 1]

    def _commit(self, rec: Dict[str, Any]) -> None:
        self.events.extend(rec["events"])
        for d in rec["decisions"]:
            self.decisions.append({"clock": rec["clock"], **d})
        bd = self._alloc_breakdown()
        self.alloc_series.append({"clock": rec["clock"], **bd})
        self._take_snapshot(rec["events"])
        self.last_step = rec

    # -------------------------------------------------------------- read API
    def job_table(self) -> pandas.DataFrame:
        c = self.cluster
        rows = []
        for job in c.jobs:
            if job.completion_time is not None and job.completion_time <= c.clock:
                status = "completed"
            elif job.submission_time > c.clock:
                status = "not yet arrived"
            elif job.placement:
                if not job.inference and (job.rescale_time > 0):
                    status = "rescaling"
                else:
                    status = "running"
            else:
                status = "pending"
            alloc = c.allocations.get(job.name, [])
            first_alloc = next((t for t, _, cur in job.placement_update_history if cur), None)
            rows.append({
                "job": job.name,
                "class": "inference" if job.inference else "training",
                "application": job.app,
                "status": status,
                "submitted_s": job.submission_time,
                "gpus": len(alloc),
                "workers": ",".join(f"w{k}×{v}" for k, v in sorted(Counter(alloc).items())),
                "restarts": job.num_restarts if job.num_restarts is not None else 0,
                "epoch": job.epoch if not job.inference else None,
                "rescale_left_s": job.rescale_time if not job.inference else None,
                "queue_wait_s": (job.start_execute_time - job.submission_time) if job.inference and job.start_execute_time is not None
                else ((first_alloc - job.submission_time) if first_alloc is not None else None),
                "completion_s": job.completion_time,
                "jct_s": (job.completion_time - job.submission_time) if job.completion_time is not None and job.completion_time <= c.clock else None,
                "injected": job.name in {r["name"] for r in self.injected_rows},
            })
        return pandas.DataFrame(rows)

    def gpu_series(self) -> pandas.DataFrame:
        d = self.cluster.gpu_util_dict
        return pandas.DataFrame({"clock": d["clock"], "gpu_use": d["gpu_use"],
                                 "real_gpu_use": d["real_gpu_use"], "real_running_gpu_use": d["real_running_gpu_use"]})

    def total_gpus(self) -> int:
        return self.cfg.min_nodes * self.cfg.num_gpus
