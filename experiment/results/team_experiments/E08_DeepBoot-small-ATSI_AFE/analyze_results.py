import csv
import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parent
OUT = ROOT / "simulator-output"
summary = json.loads((OUT / "summary.json").read_text(encoding="utf-8"))
jobinfo = json.loads((OUT / "jobinfo.log").read_text(encoding="utf-8"))
gpu = json.loads((OUT / "gpu.log").read_text(encoding="utf-8"))
metrics = json.loads((OUT / "metric.log").read_text(encoding="utf-8"))
workload = pd.read_csv(ROOT.parents[3] / "experiment" / "workload" / "small.csv")
jcts = summary["jcts"]
training = {k: float(v) for k, v in jcts.items() if not k.startswith("inference-")}
inference = {k: float(v) for k, v in jcts.items() if k.startswith("inference-")}


def stats(values):
    arr = np.asarray(list(values), dtype=float)
    if not len(arr):
        return {"count": 0}
    return {
        "count": int(len(arr)),
        "mean_seconds": float(np.mean(arr)),
        "median_seconds": float(np.median(arr)),
        "p95_seconds": float(np.percentile(arr, 95)),
        "min_seconds": float(np.min(arr)),
        "max_seconds": float(np.max(arr)),
    }


records = {j["name"]: j for j in jobinfo["submitted_jobs"]}
train_records = [j for j in records.values() if not j["name"].startswith("inference-")]
restart_vals = [int(j["num_restarts"] or 0) for j in train_records]
delay_vals = [float(j["delay_time"] or 0) for j in train_records]
restarts_by_app = {}
for j in train_records:
    app = j["name"].rsplit("-", 1)[0]
    restarts_by_app.setdefault(app, []).append(int(j["num_restarts"] or 0))

by_app = {}
for name, value in training.items():
    app = name.rsplit("-", 1)[0]
    by_app.setdefault(app, []).append(value)
per_app = {app: stats(vals) for app, vals in sorted(by_app.items())}

clocks = np.asarray(gpu["clock"], dtype=float)
capacity = int(jobinfo["num_nodes"]) * 4
series = {}
for key in ["gpu_use", "real_gpu_use", "real_running_gpu_use"]:
    vals = np.asarray(gpu[key], dtype=float)
    series[key] = {
        "mean_gpus": float(vals.mean()),
        "mean_capacity_percent": float(vals.mean() / capacity * 100),
        "peak_gpus": int(vals.max()),
        "peak_capacity_percent": float(vals.max() / capacity * 100),
    }

history = jobinfo.get("optimize_history", [])
schedule_costs = [float(x[2]) for x in history]
all_jcts = [float(x) for x in jcts.values()]

report = {
    "workload_csv_rows": int(len(workload)),
    "workload_last_submission_seconds": int(workload["time"].max()),
    "job_count_completed": len(jcts),
    "training_jct": stats(training.values()),
    "inference_jct": stats(inference.values()),
    "all_jobs_jct": stats(all_jcts),
    "training_jobs_by_application": per_app,
    "training_restarts_by_application": {
        app: {"jobs": len(vals), "total": int(sum(vals)), "mean": float(np.mean(vals)), "max": int(max(vals))}
        for app, vals in sorted(restarts_by_app.items())
    },
    "training_restart_count": {
        "mean": float(np.mean(restart_vals)) if restart_vals else None,
        "median": float(np.median(restart_vals)) if restart_vals else None,
        "p95": float(np.percentile(restart_vals, 95)) if restart_vals else None,
        "total": int(sum(restart_vals)),
        "jobs_with_restart": int(sum(x > 0 for x in restart_vals)),
        "jobs_count": int(len(restart_vals)),
        "max": int(max(restart_vals)) if restart_vals else None,
    },
    "training_rescale_delay_seconds": {
        "mean_per_job": float(np.mean(delay_vals)) if delay_vals else None,
        "total_job_seconds": float(np.sum(delay_vals)),
    },
    "gpu_samples": int(len(clocks)),
    "simulated_seconds": float(clocks[-1] if len(clocks) else 0),
    "cluster_capacity_gpus": capacity,
    "gpu_utilization": series,
    "scheduling_optimization": {
        "decision_count": len(schedule_costs),
        "mean_wall_seconds": float(np.mean(schedule_costs)) if schedule_costs else None,
        "p95_wall_seconds": float(np.percentile(schedule_costs, 95)) if schedule_costs else None,
        "max_wall_seconds": float(np.max(schedule_costs)) if schedule_costs else None,
        "sum_wall_seconds": float(np.sum(schedule_costs)) if schedule_costs else None,
    },
    "metric_log_values": metrics,
}
(ROOT / "analysis-summary.json").write_text(json.dumps(report, indent=2), encoding="utf-8")

with (ROOT / "job-metrics.csv").open("w", newline="", encoding="utf-8") as f:
    writer = csv.writer(f)
    writer.writerow(["job", "class", "application", "jct_seconds", "restarts", "rescale_delay_seconds"])
    for name, value in jcts.items():
        rec = records.get(name, {})
        cls = "inference" if name.startswith("inference-") else "training"
        app = name.rsplit("-", 1)[0] if cls == "training" else "-".join(name.split("-")[1:-1])
        writer.writerow([name, cls, app, value, rec.get("num_restarts"), rec.get("delay_time")])

fig, axes = plt.subplots(1, 2, figsize=(12, 4.6))
window = 300
for key, label in [("gpu_use", "Allocated"), ("real_gpu_use", "Not rescaling"), ("real_running_gpu_use", "Running")]:
    vals = pd.Series(gpu[key], dtype=float).rolling(window, min_periods=1).mean()
    axes[0].plot(clocks / 3600.0, vals / capacity * 100, label=label, linewidth=1.1)
axes[0].set_title("GPU utilization (5-minute rolling mean)")
axes[0].set_xlabel("Simulated time (hours)")
axes[0].set_ylabel("Cluster capacity used (%)")
axes[0].set_ylim(0, 105)
axes[0].grid(alpha=0.25)
axes[0].legend(frameon=False)

for values, label in [(training.values(), "Training"), (inference.values(), "Inference")]:
    arr = np.sort(np.asarray(list(values), dtype=float))
    if len(arr):
        y = np.arange(1, len(arr) + 1) / len(arr)
        axes[1].plot(arr, y, label=f"{label} (n={len(arr)})")
axes[1].set_title("Job completion time distribution")
axes[1].set_xscale("log")
axes[1].set_xlabel("JCT (seconds)")
axes[1].set_ylabel("Cumulative fraction")
axes[1].grid(alpha=0.25)
axes[1].legend(frameon=False)
fig.tight_layout()
fig.savefig(ROOT / "gpu-utilization-and-jct.png", dpi=180)
print(json.dumps(report, indent=2))
