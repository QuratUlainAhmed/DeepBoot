"""Read-only instrumentation of the research scheduling code.

Each wrapper:
  1. copies (never mutates) selected inputs,
  2. calls the ORIGINAL method with the ORIGINAL arguments,
  3. records selected outputs / object attributes,
  4. returns the ORIGINAL return value unchanged.

The wrappers are installed on the classes in the dashboard process only
(monkey-patching at runtime). No research source file is edited, and the
equivalence test (dashboard/tests/test_equivalence.py) checks that a
wrapped run produces exactly the same results as the unmodified CLI.

What is captured:
  ATS-T (dp.py)          allocate_elastic inputs, knapsack weights/values,
                         chosen replica counts (max_value_dp), resulting alloc
  ATS-I (infer_scheduler) which branch placed each request (empty GPU,
                         SLEEP pod, reclaim from training), reclaimed
                         (training job, node) pairs, candidate counts and the
                         best remaining-SPEEDUP sum per reclaim
  RANDOM                 that the random_allocate path was taken
"""
from __future__ import annotations

import copy
import functools
from typing import Any, Dict, List

import numpy as np

from . import sim_bridge  # noqa: F401  (ensures repo root on sys.path)
import dp as dp_mod
import infer_scheduler as is_mod


class Recorder:
    """Collects decision records produced during one simulator step."""

    def __init__(self) -> None:
        self.records: List[Dict[str, Any]] = []
        self.active = False
        self._pending_atsi: Dict[str, Any] | None = None

    def start(self) -> None:
        self.records = []
        self._pending_atsi = None
        self.active = True

    def stop(self) -> List[Dict[str, Any]]:
        self.active = False
        out = self.records
        self.records = []
        return out

    def add(self, rec: Dict[str, Any]) -> None:
        if self.active:
            self.records.append(rec)


RECORDER = Recorder()
_INSTALLED = False


def _to_py(x):
    if isinstance(x, (np.integer,)):
        return int(x)
    if isinstance(x, (np.floating,)):
        return float(x)
    if isinstance(x, np.ndarray):
        return x.tolist()
    return x


# --------------------------------------------------------------------- ATS-T
def _wrap_allocate_elastic(orig):
    @functools.wraps(orig)
    def wrapper(self, prev_allocations, jobs, free_gpus):
        if not RECORDER.active:
            return orig(self, prev_allocations, jobs, free_gpus)
        job_meta = []
        for name, info in jobs.items():
            restarts = info.num_restarts
            age = info.age
            delay = 10  # mirrors the constant in dp.py:121, used only for display
            factor = max(age - restarts * delay, 0.0) / (age + delay)
            job_meta.append(
                {
                    "job": name,
                    "age": _to_py(age),
                    "num_restarts": _to_py(restarts),
                    "max_replicas": _to_py(info.max_replicas),
                    "prev_gpus": len(prev_allocations.get(name, [])),
                    "penalty_factor_derived": round(float(factor), 4),
                }
            )
        rec = {
            "kind": "ATS-T",
            "free_gpus_by_node": {int(k): int(v) for k, v in dict(free_gpus).items()},
            "capacity": int(sum(free_gpus.values())),
            "jobs": job_meta,
            "prev_alloc": {k: list(map(int, v)) for k, v in prev_allocations.items()},
        }
        self._dash_rec = rec
        result = orig(self, prev_allocations, jobs, free_gpus)
        rec["new_alloc"] = {k: list(map(int, v)) for k, v in result.items()}
        self._dash_rec = None
        RECORDER.add(rec)
        return result

    return wrapper


def _wrap_max_value_dp(orig):
    @functools.wraps(orig)
    def wrapper(self, ws, vs, m):
        ways = orig(self, ws, vs, m)
        rec = getattr(self, "_dash_rec", None)
        if RECORDER.active and rec is not None:
            rec["knapsack"] = {
                "capacity_m": int(m),
                "values": [[round(float(v), 4) for v in row] for row in vs[1:]],
                "chosen_replicas": [int(w) for w in ways],
            }
        return ways

    return wrapper


# --------------------------------------------------------------------- ATS-I
def _wrap_atsi(orig):
    @functools.wraps(orig)
    def wrapper(self, jobs, nodes, base_allocations, node_template, infer_pod_status):
        if not RECORDER.active:
            return orig(self, jobs, nodes, base_allocations, node_template, infer_pod_status)
        before = {k: list(map(int, v)) for k, v in base_allocations.items()}
        self._dash_rec = {"kind": "ATS-I", "branches": [], "reclaims": [], "aryl": bool(self.aryl)}
        result = orig(self, jobs, nodes, base_allocations, node_template, infer_pod_status)
        alloc = result[0]
        rec = self._dash_rec
        self._dash_rec = None
        placed = {}
        for name, a in alloc.items():
            if jobs[name].inference and list(map(int, a)) != before.get(name, []) and len(a) > 0:
                placed[name] = list(map(int, a))
        rec["placed"] = placed
        RECORDER.add(rec)
        return result

    return wrapper


def _wrap_empty_or_sleep(orig, aryl: bool):
    @functools.wraps(orig)
    def wrapper(self, gpus, is_sleep=False):
        before = getattr(self, "remain_infer_tasks", 0)
        out = orig(self, gpus, is_sleep)
        rec = getattr(self, "_dash_rec", None)
        if RECORDER.active and rec is not None:
            n = before - self.remain_infer_tasks
            if n > 0:
                rec["branches"].append(
                    {
                        "branch": ("SLEEP pod GPU" if is_sleep else "empty GPU")
                        + (" (Aryl order)" if aryl else ""),
                        "count": int(n),
                    }
                )
        return out

    return wrapper


def _wrap_schedule_training_gpu(orig, aryl: bool):
    @functools.wraps(orig)
    def wrapper(self):
        before = getattr(self, "remain_infer_tasks", 0)
        n_cases_before = len(getattr(self, "best_cases", []) or [])
        train_names = [n for n, t in zip(self._jobs.keys(), self.training) if t]
        node_keys = list(self._nodes.keys())
        pre_state = np.array(self.training_state, copy=True)
        out = orig(self)
        rec = getattr(self, "_dash_rec", None)
        if RECORDER.active and rec is not None:
            n = before - self.remain_infer_tasks
            if n > 0:
                rec["branches"].append(
                    {"branch": "reclaim from training" + (" (Aryl worker-level)" if aryl else ""), "count": int(n)}
                )
            if not aryl:
                for case in (self.best_cases or [])[n_cases_before:]:
                    j_idx, n_idx = np.argwhere(case == 1)[0]
                    rec["reclaims"].append(
                        {"training_job": train_names[int(j_idx)], "node": int(node_keys[int(n_idx)])}
                    )
            else:
                diff = pre_state - self.training_state
                for j_idx, n_idx in np.argwhere(diff > 0):
                    rec["reclaims"].append(
                        {
                            "training_job": train_names[int(j_idx)],
                            "node": int(node_keys[int(n_idx)]),
                            "gpus": int(diff[j_idx, n_idx]),
                        }
                    )
        return out

    return wrapper


def _wrap_get_job_speedups(orig):
    @functools.wraps(orig)
    def wrapper(self, states):
        sp = orig(self, states)
        rec = getattr(self, "_dash_rec", None)
        if RECORDER.active and rec is not None and len(states) > 0:
            totals = np.sum(sp, axis=1)
            rec.setdefault("reclaim_search", []).append(
                {"candidates": int(len(states)), "best_remaining_speedup_sum": round(float(np.max(totals)), 4)}
            )
        return sp

    return wrapper


def _wrap_random(orig):
    @functools.wraps(orig)
    def wrapper(self, jobs, nodes, prev_allocations, infer_pod_status):
        if not RECORDER.active:
            return orig(self, jobs, nodes, prev_allocations, infer_pod_status)
        before = {k: list(map(int, v)) for k, v in prev_allocations.items()}
        result = orig(self, jobs, nodes, prev_allocations, infer_pod_status)
        placed = {
            n: list(map(int, a))
            for n, a in result[0].items()
            if jobs[n].inference and len(a) > 0 and list(map(int, a)) != before.get(n, [])
        }
        RECORDER.add({"kind": "RANDOM", "placed": placed})
        return result

    return wrapper


def install() -> None:
    """Install wrappers once per process (idempotent)."""
    global _INSTALLED
    if _INSTALLED:
        return
    D = dp_mod.DeepBoot
    D.allocate_elastic = _wrap_allocate_elastic(D.allocate_elastic)
    D.max_value_dp = _wrap_max_value_dp(D.max_value_dp)
    I = is_mod.InferScheduler
    I.ATSI_infer_schedule = _wrap_atsi(I.ATSI_infer_schedule)
    I._schedule_empty_or_sleep_gpu = _wrap_empty_or_sleep(I._schedule_empty_or_sleep_gpu, False)
    I._aryl_schedule_empty_or_sleep_gpu = _wrap_empty_or_sleep(I._aryl_schedule_empty_or_sleep_gpu, True)
    I._schedule_training_gpu = _wrap_schedule_training_gpu(I._schedule_training_gpu, False)
    I._aryl_schedule_training_gpu = _wrap_schedule_training_gpu(I._aryl_schedule_training_gpu, True)
    I._get_job_speedups = _wrap_get_job_speedups(I._get_job_speedups)
    I.random_allocate = _wrap_random(I.random_allocate)
    _INSTALLED = True
