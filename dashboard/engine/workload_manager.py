"""Workload loading, reduced demo scenarios, and job injection.

Workload rows use the repository CSV schema:
    name, time, application, num_replicas, batch_size, duration, num_task

Which fields the simulator actually reads (verified in simulator.py
Cluster.__init__, lines 458-498):
  * policy dp / pollux : name, application, time, duration
        (num_replicas and batch_size are IGNORED; ncf batch forced to 32768)
  * policy afs         : additionally num_replicas -> target_num_replicas,
                         batch_size -> target_batch_size
  * training jobs have no duration: they run until the application's
    trace-based convergence epoch (applications.py)
  * inference jobs: one replica, `duration` seconds of service; the
    `application` string (e.g. infer-yolov3-1) is the pod/app identity used
    for warm-pod reuse
"""
from __future__ import annotations

import os
from typing import Optional

import pandas

from .sim_bridge import REPO_ROOT, sim

WORKLOAD_DIR = os.path.join(REPO_ROOT, "experiment", "workload")
WORKLOAD_FILES = {
    "small": "small.csv",
    "middle": "middle.csv",
    "large": "large.csv",
    "pure_train": "pure_train.csv",
}
COLUMNS = ["name", "time", "application", "num_replicas", "batch_size", "duration", "num_task"]


def load_workload(scale: str) -> pandas.DataFrame:
    return pandas.read_csv(os.path.join(WORKLOAD_DIR, WORKLOAD_FILES[scale]))


def is_inference_name(name: str) -> bool:
    return str(name).startswith("inference")


def reduced_scenario(
    base: pandas.DataFrame,
    n_training: int = 8,
    inference_window_s: int = 1800,
    exclude_apps: tuple = ("imagenet",),
) -> pandas.DataFrame:
    """Real rows only: the first `n_training` training jobs by arrival time
    (optionally excluding very long applications), plus every inference row
    arriving within `inference_window_s` seconds. Rows are not altered and keep
    their original relative order."""
    tr_mask = ~base["name"].map(is_inference_name)
    training = base[tr_mask & ~base["application"].isin(exclude_apps)].sort_values("time").head(n_training)
    inference = base[~tr_mask & (base["time"] <= inference_window_s)]
    keep = set(training.index) | set(inference.index)
    return base.loc[sorted(keep)].reset_index(drop=True)


def describe(workload: pandas.DataFrame) -> dict:
    inf = workload["name"].map(is_inference_name)
    return {
        "rows": int(len(workload)),
        "training": int((~inf).sum()),
        "inference": int(inf.sum()),
        "training_apps": workload.loc[~inf, "application"].value_counts().to_dict(),
        "inference_apps": int(workload.loc[inf, "application"].nunique()),
        "last_arrival_s": int(workload["time"].max()) if len(workload) else 0,
    }


class InjectionError(ValueError):
    pass


def make_row(
    kind: str,
    name: str,
    application: str,
    time: int,
    duration: Optional[float] = None,
    num_replicas: int = 1,
    batch_size: int = 1,
) -> dict:
    """Build a workload row in the repository CSV schema."""
    if kind == "training":
        return {
            "name": name, "time": int(time), "application": application,
            "num_replicas": int(num_replicas), "batch_size": int(batch_size),
            "duration": 4.0, "num_task": -1,  # training rows in the CSVs carry duration=4.0, num_task=-1
        }
    return {
        "name": name, "time": int(time), "application": application,
        "num_replicas": 1, "batch_size": 1, "duration": float(duration), "num_task": 0,
    }


def inject_job(cluster, row: dict, policy: str):
    """Add one job to a running research Cluster.

    Mirrors Cluster.__init__ (simulator.py 458-498) for a single row and appends
    it, which is equivalent to appending this row to the end of the workload CSV:
      * the same Job constructor arguments per policy,
      * ncf target_batch_size = 32768 for dp/pollux/afs (as in __init__),
      * job.app = row['application'] (as in __init__ line 488),
      * job_dict and submit_time registration (as in __init__ 491-498).
    Additionally job.current_time is set to the cluster's current_time, which is
    the value every not-yet-submitted job already has (job.step advances idle
    jobs in lock-step) and which Cluster.step asserts.
    """
    name = row["name"]
    if name in cluster.job_dict:
        raise InjectionError(f"A job named '{name}' already exists.")
    if row["time"] <= cluster.clock:
        raise InjectionError(
            f"Arrival time {row['time']} must be later than the current simulated time "
            f"{cluster.clock} s (the simulator only reacts to future arrivals)."
        )
    app_key = sim.app_trans(row["application"])
    if app_key not in sim.APPLICATIONS:
        raise InjectionError(f"Unknown application '{row['application']}'.")
    is_inf = is_inference_name(name)
    if is_inf != app_key.startswith("infer"):
        raise InjectionError("Inference jobs must be named 'inference-*' and use an infer-* application.")

    app = sim.APPLICATIONS[app_key]
    if policy in ("dp", "pollux"):
        job = sim.Job(name, app, row["time"], duration=row["duration"])
        if job.application.name == "ncf":
            job.target_batch_size = 32768
    elif policy == "afs":
        job = sim.Job(name, app, row["time"], duration=row["duration"],
                      target_num_replicas=row["num_replicas"], target_batch_size=row["batch_size"])
        if job.application.name == "ncf":
            job.target_batch_size = 32768
    else:
        raise InjectionError(f"Injection not supported for policy '{policy}'.")

    job.app = row["application"]
    job.current_time = cluster.current_time
    cluster.jobs.append(job)
    cluster.job_dict[name] = job
    cluster.submit_time[job.submission_time] = job.duration
    return job
