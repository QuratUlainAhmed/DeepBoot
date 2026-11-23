"""Create comparison plots from master_results.csv (no simulator execution)."""

import csv
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np


HERE = Path(__file__).resolve().parent
MASTER = HERE.parent / "master_results.csv"
with MASTER.open(newline="", encoding="utf-8-sig") as f:
    rows = {row["Experiment ID"]: row for row in csv.DictReader(f)}


def number(row, field):
    value = row[field].strip()
    return float(value) if value else np.nan


plt.rcParams.update({
    "font.size": 10,
    "axes.titlesize": 12,
    "axes.labelsize": 10,
    "figure.titlesize": 14,
})

# Small workload JCT values share the same job class and JCT definitions.
# Configuration differences are retained in the figure subtitle/caption.
small_ids = ["E01", "E02", "E03", "E05", "E06", "E07"]
small_names = ["E01\nDeepBoot", "E02*\nDeepBoot AFE", "E03\nAFS", "E05\nPollux", "E06\nAFS AFE", "E07\nDP random"]
means = [number(rows[eid], "Training mean JCT (s)") for eid in small_ids]
colors = ["#3567a8", "#8294ad", "#d17a22", "#4c8c62", "#e1a23b", "#6b75ad"]
fig, ax = plt.subplots(figsize=(10.5, 5.3))
bars = ax.bar(small_names, means, color=colors, width=0.7)
ax.set_ylabel("Training mean JCT (seconds)")
fig.suptitle("Observed training JCT — small workload", y=0.98)
fig.text(0.5, 0.93, "Single runs with different scheduler/inference settings; descriptive only. E02 cluster/config metadata incomplete.",
         ha="center", va="center", fontsize=9)
ax.grid(axis="y", alpha=0.25)
ax.set_axisbelow(True)
ax.set_ylim(0, max(means) * 1.16)
for bar, val in zip(bars, means):
    ax.text(bar.get_x() + bar.get_width() / 2, val + max(means) * 0.015,
            f"{val:,.0f}", ha="center", va="bottom", fontsize=8)
fig.tight_layout(rect=(0, 0.11, 1, 0.88))
fig.savefig(HERE / "training_jct_small.png", dpi=170, bbox_inches="tight")
plt.close(fig)

# E02 excluded because its cluster shape was not independently verified.
gpu_ids = ["E01", "E03", "E05", "E06", "E07"]
gpu_labels = ["E01 DP", "E03 AFS", "E05 Pollux", "E06 AFS AFE", "E07 DP random"]
series = [
    ("Allocated", "GPU utilization mean (allocated, %)", "#3567a8"),
    ("Real", "Real GPU utilization mean (%)", "#d17a22"),
    ("Real running", "Running GPU utilization mean (%)", "#4c8c62"),
]
x = np.arange(len(gpu_ids))
width = 0.24
fig, ax = plt.subplots(figsize=(10.5, 5.3))
for i, (label, field, color) in enumerate(series):
    vals = [number(rows[eid], field) for eid in gpu_ids]
    ax.bar(x + (i - 1) * width, vals, width, label=label, color=color)
ax.set_xticks(x)
ax.set_xticklabels(gpu_labels)
ax.set_ylabel("Mean modeled GPU capacity (%)")
ax.set_ylim(0, 105)
fig.suptitle("Mean GPU counters — small workload, verified 16 × 4 runs", y=0.98)
fig.text(0.5, 0.93, "Simulator counters normalized to 64 GPUs; scheduling modes vary. E02 excluded: cluster configuration incomplete.",
         ha="center", va="center", fontsize=9)
ax.grid(axis="y", alpha=0.25)
ax.set_axisbelow(True)
ax.legend(frameon=False, ncol=3)
fig.tight_layout(rect=(0, 0.02, 1, 0.88))
fig.savefig(HERE / "gpu_utilization_small.png", dpi=170, bbox_inches="tight")
plt.close(fig)

# One scheduler/configuration at two workload scales; the inference traces are
# not nested, so the plot is explicitly an observed contrast, not causal proof.
scale_ids = ["E01", "E04"]
scale_labels = ["Small\n3,200 inference", "Middle\n16,000 inference"]
panels = [
    ("Training mean JCT", "Training mean JCT (s)"),
    ("Inference mean JCT", "Inference mean JCT (s)"),
    ("Allocated GPU utilization", "GPU utilization mean (allocated, %)"),
]
fig, axes = plt.subplots(1, 3, figsize=(11, 4.8))
for ax, (title, field) in zip(axes, panels):
    vals = [number(rows[eid], field) for eid in scale_ids]
    bars = ax.bar(scale_labels, vals, color=["#3567a8", "#d17a22"], width=0.62)
    ax.set_title(title)
    ax.grid(axis="y", alpha=0.25)
    ax.set_axisbelow(True)
    ax.set_ylim(0, max(vals) * 1.22 if max(vals) > 0 else 1)
    for bar, val in zip(bars, vals):
        ax.text(bar.get_x() + bar.get_width() / 2, val + max(vals) * 0.025,
                f"{val:,.1f}", ha="center", va="bottom", fontsize=8)
    if "utilization" in title:
        ax.set_ylabel("Percent of 64 modeled GPUs")
    else:
        ax.set_ylabel("Seconds")
fig.suptitle("DeepBoot small-to-middle workload contrast")
fig.text(0.5, 0.01,
         "Same DP/AFE/AISS/cluster settings and training rows; inference rows differ. One run per scale; descriptive only.",
         ha="center", fontsize=9)
fig.tight_layout(rect=(0, 0.07, 1, 0.93))
fig.savefig(HERE / "workload_scaling_e01_e04.png", dpi=170, bbox_inches="tight")
plt.close(fig)

print("Wrote training_jct_small.png, gpu_utilization_small.png, and workload_scaling_e01_e04.png")
