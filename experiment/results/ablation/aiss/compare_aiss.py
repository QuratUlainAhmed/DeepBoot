import csv, json
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

base = Path(__file__).resolve().parent
repo = base.parents[3]
E01_SUMMARY = repo / "experiment/results/team_experiments/E01_deepboot_baseline/summary.json"
NGPU = 64


def describe(values):
    v = np.asarray(list(values), dtype=float)
    return {"count": int(v.size), "mean": float(v.mean()), "p50": float(np.percentile(v, 50)),
            "p75": float(np.percentile(v, 75)), "p95": float(np.percentile(v, 95)), "max": float(v.max())}


def load(a):
    d = base / f"aiss-{a}"
    r = {}
    r["summary"] = json.load((d / "summary.json").open())
    r["gpu"] = json.load((d / "gpu.log").open())
    ex = d / "exit_status.txt"
    r["exit"] = ex.read_text().strip() if ex.exists() else "unavailable"
    metric = d / "metric.log"
    r["metric_empty"] = (not metric.exists()) or ('"clock": []' in metric.read_text())
    jc = r["summary"]["jcts"]
    r["train"] = {k: v for k, v in jc.items() if "infer" not in k}
    r["infer"] = {k: v for k, v in jc.items() if "infer" in k}
    g = r["gpu"]
    r["clock"] = np.asarray(g["clock"])
    r["alloc"] = np.asarray(g["gpu_use"]) / NGPU * 100
    r["real"] = np.asarray(g["real_gpu_use"]) / NGPU * 100
    r["run"] = np.asarray(g["real_running_gpu_use"]) / NGPU * 100
    return r


R = {a: load(a) for a in (0, 1)}
T = {a: describe(R[a]["train"].values()) for a in (0, 1)}
I = {a: describe(R[a]["infer"].values()) for a in (0, 1)}
A = {a: describe(R[a]["summary"]["jcts"].values()) for a in (0, 1)}

rows = []
def add(name, v0, v1):
    rows.append((name, v0, v1))

for k, label in [("mean", "mean"), ("p50", "P50"), ("p75", "P75"), ("p95", "P95"), ("max", "max")]:
    add(f"Training JCT {label} (s)", T[0][k], T[1][k])
for k, label in [("mean", "mean"), ("p50", "P50"), ("p75", "P75"), ("p95", "P95"), ("max", "max")]:
    add(f"Inference JCT {label} (s)", I[0][k], I[1][k])
add("All-jobs JCT mean (s)", A[0]["mean"], A[1]["mean"])
add("Jobs completed (count)", A[0]["count"], A[1]["count"])
for key, label in [("alloc", "Allocated GPUs"), ("real", "Real used GPUs"), ("run", "Real running GPUs")]:
    add(f"{label} mean (% of {NGPU})", float(R[0][key].mean()), float(R[1][key].mean()))
    add(f"{label} peak (% of {NGPU})", float(R[0][key].max()), float(R[1][key].max()))
add("Simulated end clock (s)", float(R[0]["clock"].max()), float(R[1]["clock"].max()))


def fmt(v):
    return "unavailable" if v is None else f"{v:,.2f}"


def change(v0, v1):
    if v0 is None or v1 is None:
        return "n/a", "n/a"
    ab = v1 - v0
    rel = "n/a" if v0 == 0 else f"{ab / v0 * 100:+.1f}%"
    return f"{ab:+,.2f}", rel


lines = ["| Metric | AISS=0 | AISS=1 | Absolute change (1-0) | Relative change |", "|---|---:|---:|---:|---:|"]
with (base / "aiss_ablation_results.csv").open("w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["metric", "aiss_0", "aiss_1", "absolute_change", "relative_change"])
    for name, v0, v1 in rows:
        ab, rel = change(v0, v1)
        lines.append(f"| {name} | {fmt(v0)} | {fmt(v1)} | {ab} | {rel} |")
        w.writerow([name, v0, v1, ab, rel])
table_md = "\n".join(lines)

paired = {}
for grp in ("train", "infer"):
    common = sorted(set(R[0][grp]) & set(R[1][grp]))
    d = np.asarray([R[1][grp][k] - R[0][grp][k] for k in common], dtype=float)
    paired[grp] = {"jobs_in_both": len(common),
                   "mean_diff_aiss1_minus_aiss0_s": float(d.mean()),
                   "aiss1_faster": int((d < 0).sum()), "aiss1_slower": int((d > 0).sum()),
                   "equal": int((d == 0).sum())}

det = {"e01_summary_found": E01_SUMMARY.exists()}
if E01_SUMMARY.exists():
    e01 = json.load(E01_SUMMARY.open())["jcts"]
    cur = R[1]["summary"]["jcts"]
    same_keys = set(e01) == set(cur)
    diffs = [abs(e01[k] - cur[k]) for k in set(e01) & set(cur)]
    det.update({"same_job_set": same_keys, "jobs_compared": len(diffs),
                "jobs_with_different_jct": int(sum(1 for x in diffs if x != 0)),
                "max_abs_jct_difference_s": float(max(diffs)) if diffs else None,
                "identical_to_E01": bool(same_keys and all(x == 0 for x in diffs))})

analysis = {"training": T, "inference": I, "all": A, "paired": paired, "determinism_vs_E01": det,
            "exit_status": {a: R[a]["exit"] for a in (0, 1)},
            "metric_log_empty": {a: R[a]["metric_empty"] for a in (0, 1)}}
json.dump(analysis, (base / "aiss_analysis.json").open("w"), indent=2)
(base / "aiss_comparison_table.md").write_text(table_md + "\n")

col = {0: "#c62828", 1: "#1565c0"}
for grp, title, fn in [("train", "Training JCT CDF", "jct_cdf_training.png"),
                       ("infer", "Inference JCT CDF", "jct_cdf_inference.png")]:
    fig, ax = plt.subplots(figsize=(8, 5))
    for a in (0, 1):
        v = np.sort(np.asarray(list(R[a][grp].values()), dtype=float))
        ax.plot(v / (60 if grp == "train" else 1), np.arange(1, v.size + 1) / v.size,
                color=col[a], linewidth=1.8, label=f"AISS={a}")
    ax.set_xlabel("JCT (minutes)" if grp == "train" else "JCT (seconds)")
    ax.set_ylabel("CDF"); ax.set_title(f"{title}: AISS=0 vs AISS=1"); ax.grid(True, alpha=0.25); ax.legend()
    fig.tight_layout(); fig.savefig(base / fn, dpi=160); plt.close(fig)

fig, axes = plt.subplots(2, 1, figsize=(10, 7), sharex=True)
for ax, key, label in [(axes[0], "alloc", "Allocated GPUs (%)"), (axes[1], "run", "Real running GPUs (%)")]:
    for a in (0, 1):
        ax.plot(R[a]["clock"] / 3600, R[a][key], linewidth=0.6, color=col[a], alpha=0.8, label=f"AISS={a}")
    ax.set_ylim(0, 105); ax.set_ylabel(label); ax.grid(True, alpha=0.25); ax.legend()
axes[1].set_xlabel("Simulated time (hours)")
fig.suptitle("GPU utilization: AISS=0 vs AISS=1"); fig.tight_layout()
fig.savefig(base / "gpu_utilization_aiss.png", dpi=160); plt.close(fig)

labels = ["Mean", "P50", "P75", "P95", "Max"]
keys = ["mean", "p50", "p75", "p95", "max"]
x = np.arange(len(labels)); wd = 0.38
fig, ax = plt.subplots(figsize=(8, 5))
for i, a in enumerate((0, 1)):
    ax.bar(x + (i - 0.5) * wd, [T[a][k] / 60 for k in keys], wd, color=col[a], label=f"AISS={a}")
ax.set_xticks(x); ax.set_xticklabels(labels); ax.set_ylabel("Training JCT (minutes)")
ax.set_title("Training JCT summary: AISS=0 vs AISS=1"); ax.grid(axis="y", alpha=0.25); ax.legend()
fig.tight_layout(); fig.savefig(base / "training_jct_stats.png", dpi=160); plt.close(fig)

print(table_md)
print()
print(json.dumps({k: analysis[k] for k in ("paired", "determinism_vs_E01", "exit_status", "metric_log_empty")}, indent=2))
print("\nWrote results CSV, table, analysis JSON and 4 PNG files in", base)
