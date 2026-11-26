import json
from pathlib import Path

import numpy as np


HERE = Path(__file__).resolve().parent
RUNS = HERE / "runs"
SEEDS = (11, 22, 33)
POLICIES = ("ats_i", "random")


def describe(values):
    arr = np.asarray(list(values), dtype=float)
    return {
        "count": int(arr.size),
        "mean": float(arr.mean()),
        "p95": float(np.percentile(arr, 95)),
        "max": float(arr.max()),
    }


def analyze(run_dir):
    output = run_dir / "simulator-output"
    summary = json.loads((output / "summary.json").read_text(encoding="utf-8"))
    gpu = json.loads((output / "gpu.log").read_text(encoding="utf-8"))
    info = json.loads((output / "jobinfo.log").read_text(encoding="utf-8"))
    metadata = json.loads((run_dir / "run-metadata.json").read_text(encoding="utf-8"))
    jcts = summary["jcts"]
    train = [v for k, v in jcts.items() if not k.startswith("inference-")]
    infer = [v for k, v in jcts.items() if k.startswith("inference-")]
    training_jobs = [j for j in info["submitted_jobs"] if not j["name"].startswith("inference-")]
    restarts = [int(j.get("num_restarts") or 0) for j in training_jobs]
    delays = [float(j.get("delay_time") or 0) for j in training_jobs]
    capacity = int(info["num_nodes"]) * 4
    timings = [float(item[2]) for item in info.get("optimize_history", [])]
    metrics = {
        "training_count": len(train),
        "training_mean_jct_s": describe(train)["mean"],
        "training_p95_jct_s": describe(train)["p95"],
        "inference_count": len(infer),
        "inference_mean_jct_s": describe(infer)["mean"],
        "inference_p95_jct_s": describe(infer)["p95"],
        "gpu_allocated_pct": float(np.mean(gpu["gpu_use"]) / capacity * 100),
        "gpu_real_pct": float(np.mean(gpu["real_gpu_use"]) / capacity * 100),
        "gpu_real_running_pct": float(np.mean(gpu["real_running_gpu_use"]) / capacity * 100),
        "training_restarts_total": int(np.sum(restarts)),
        "training_jobs_with_restarts": int(np.count_nonzero(restarts)),
        "training_rescale_delay_total_s": float(np.sum(delays)),
        "scheduling_decisions": len(timings),
        "scheduling_mean_s": float(np.mean(timings)) if timings else None,
        "scheduling_p95_s": float(np.percentile(timings, 95)) if timings else None,
        "scheduling_total_s": float(np.sum(timings)) if timings else None,
        "simulated_seconds": int(gpu["clock"][-1]),
        "completed_jobs": len(jcts),
    }
    return {"metadata": metadata, "metrics": metrics}


records = {}
for seed in SEEDS:
    records[seed] = {}
    for policy in POLICIES:
        run_dir = RUNS / f"{policy}_seed{seed}_r2"
        records[seed][policy] = analyze(run_dir)

metric_names = list(records[SEEDS[0]]["ats_i"]["metrics"])
summary = {}
for policy in POLICIES:
    summary[policy] = {}
    for name in metric_names:
        values = [records[seed][policy]["metrics"][name] for seed in SEEDS]
        values = [v for v in values if v is not None]
        if not values or not all(isinstance(v, (int, float)) for v in values):
            summary[policy][name] = None
            continue
        arr = np.asarray(values, dtype=float)
        summary[policy][name] = {
            "mean": float(arr.mean()),
            "sd": float(arr.std(ddof=1)) if len(arr) > 1 else 0.0,
            "min": float(arr.min()),
            "max": float(arr.max()),
        }

paired_differences = {}
for name in metric_names:
    differences = [records[s]["random"]["metrics"][name] - records[s]["ats_i"]["metrics"][name]
                   for s in SEEDS]
    if all(isinstance(v, (int, float)) for v in differences):
        paired_differences[name] = {
            "mean_random_minus_ats_i": float(np.mean(differences)),
            "paired_differences": differences,
        }

result = {"per_seed": records, "summary": summary, "paired_differences": paired_differences}
(HERE / "comparison-results.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")


def fmt_stat(stat, digits=2):
    return f"{stat['mean']:.{digits}f} ± {stat['sd']:.{digits}f} ({stat['min']:.{digits}f}–{stat['max']:.{digits}f})"


rows = [
    ("Training mean JCT (s)", "training_mean_jct_s", 2),
    ("Training P95 JCT (s)", "training_p95_jct_s", 2),
    ("Inference mean JCT (s)", "inference_mean_jct_s", 2),
    ("Inference P95 JCT (s)", "inference_p95_jct_s", 2),
    ("Allocated GPU utilization (%)", "gpu_allocated_pct", 2),
    ("Real GPU utilization (%)", "gpu_real_pct", 2),
    ("Real running GPU utilization (%)", "gpu_real_running_pct", 2),
    ("Training allocation restarts (count)", "training_restarts_total", 2),
    ("Training jobs with restarts (count)", "training_jobs_with_restarts", 2),
    ("Training rescale delay (job-s) ", "training_rescale_delay_total_s", 2),
    ("Simulator time advanced (s)", "simulated_seconds", 2),
    ("Scheduling overhead mean/decision (s)", "scheduling_mean_s", 4),
    ("Scheduling overhead P95/decision (s)", "scheduling_p95_s", 4),
    ("Total scheduling overhead (s)", "scheduling_total_s", 2),
]
lines = ["| Metric | ATS-I (mean ± SD; range) | RANDOM (mean ± SD; range) | RANDOM − ATS-I |",
         "|---|---:|---:|---:|"]
for label, key, digits in rows:
    ats = summary["ats_i"][key]
    rnd = summary["random"][key]
    delta = paired_differences[key]["mean_random_minus_ats_i"]
    lines.append(f"| {label} | {fmt_stat(ats, digits)} | {fmt_stat(rnd, digits)} | {delta:+.{digits}f} |")

raw = ["| Seed | Policy | Train mean JCT (s) | Train P95 (s) | Infer mean JCT (s) | Infer P95 (s) | Allocated / real / running GPU (%) | Training restarts / affected jobs | Training rescale delay (job-s) | Simulator seconds | Decisions | Mean scheduling cost (s) | Wall time (s) |",
       "|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
for seed in SEEDS:
    for policy in POLICIES:
        record = records[seed][policy]
        m = record["metrics"]
        wall = record["metadata"]["runtime_seconds"]
        raw.append(f"| {seed} | {policy} | {m['training_mean_jct_s']:.2f} | {m['training_p95_jct_s']:.2f} | "
                   f"{m['inference_mean_jct_s']:.2f} | {m['inference_p95_jct_s']:.2f} | "
                   f"{m['gpu_allocated_pct']:.2f} / {m['gpu_real_pct']:.2f} / {m['gpu_real_running_pct']:.2f} | "
                   f"{m['training_restarts_total']} / {m['training_jobs_with_restarts']} | "
                   f"{m['training_rescale_delay_total_s']:.0f} | {m['simulated_seconds']} | {m['scheduling_decisions']} | "
                   f"{m['scheduling_mean_s']:.4f} | {wall:.2f} |")

tables_text = "\n".join([
    "## Repeated-run summary", "", *lines, "", "## Raw per-run values", "", *raw, ""
])
(HERE / "comparison-tables.md").write_text(tables_text, encoding="utf-8")

run_records = [
    "| Seed | Policy | Exact command | Output directory | Wall time (s) |",
    "|---:|---|---|---|---:|",
]
for seed in SEEDS:
    for policy in POLICIES:
        run_name = f"{policy}_seed{seed}_r2"
        record = records[seed][policy]
        relative = f"../experiment/results/team_experiments/E08_infer_alloc_control/runs/{run_name}"
        run_records.append(
            f"| {seed} | {policy} | [command.txt]({relative}/command.txt) | "
            f"[simulator-output/]({relative}/simulator-output/) | {record['metadata']['runtime_seconds']:.2f} |"
        )

interpretation = (
    "ATS-I produced identical JCT and GPU-counter values for all three hash seeds, while its measured scheduling time varied. "
    "That is consistent with a deterministic placement path for this configuration; wall-clock optimizer timings naturally varied. "
    "RANDOM increased training mean JCT in each matched pair by 100.23, 111.16, and 162.57 seconds (mean +124.66 seconds, about +5.1%). "
    "Inference mean JCT increased by only 0.04–0.09 seconds across the pairs (mean +0.07 seconds, about +0.9%), and inference P95 stayed at 15 seconds. "
    "Training P95 did not move consistently: it fell for seeds 11 and 22 and rose for seed 33. Its mean across the three runs is 168 seconds lower, "
    "but that average does not establish a reliable tail-latency improvement with only three seeds.\n\n"
    "RANDOM's mean real GPU utilization was 0.85 percentage points higher, while training mean JCT was also higher. The source explains how these "
    "outcomes can coexist: RANDOM assigns pending inference jobs by set order from the free-GPU list, then retains training placements that fit in "
    "the residual capacity; ATS-I instead builds a placement state and runs its inference/training scheduling steps. The RANDOM path does not optimize "
    "training placements for job characteristics. The seed-to-seed changes in training JCT and utilization match the set-order sensitivity in that "
    "code path. Utilization is a capacity counter, so the higher value alone does not imply lower JCT.\n\n"
    "The recorded training restart count was lower under RANDOM (mean 1,756 vs 1,894), but more training jobs had at least one recorded restart "
    "(116 vs 92). Recorded aggregate rescale delay was also lower (46,086 vs 49,612 job-seconds). These are simulator counters and describe a "
    "different allocation-change pattern; they do not contradict the higher training mean JCT. RANDOM's measured scheduler overhead was lower by "
    "0.0034 seconds per decision on average and 25.27 seconds total. Per-decision timing covers whichever optimizer the simulator called: DeepBoot "
    "at 60-second intervals and the inference scheduler between those intervals. Total time also depends on the number of scheduling decisions; RANDOM "
    "runs advanced about 1,900 fewer simulated seconds and averaged about 31 fewer decisions. The simpler `random_allocate()` path is consistent with "
    "lower per-decision cost, but this is not an isolated microbenchmark of that function."
)
conclusion = (
    "For this controlled small-workload configuration, RANDOM had a higher training mean JCT (about 5.1%) in all three matched runs and "
    "slightly higher inference mean JCT, with no change in inference P95. Training P95 was seed-sensitive and did not show a consistent direction. "
    "RANDOM used more modeled GPU capacity and less scheduler time, but that did not translate into lower training mean JCT. The evidence supports "
    "ATS-I for training mean JCT in this setup; the three-seed experiment does not establish statistical significance or a general result beyond this workload."
)
report_path = HERE.parents[3] / "docs" / "inference_allocation_comparison.md"
report = report_path.read_text(encoding="utf-8")
results_start = report.index("## Repeated-run summary")
results_end = report.index("The complete numeric extraction")
generated = tables_text + "\n\n## Exact run records\n\n" + "\n".join(run_records) + "\n\n"
report = report[:results_start] + generated + report[results_end:]
interpretation_start = report.index("## Interpretation\n\n") + len("## Interpretation\n\n")
interpretation_end = report.index("\n\n## Limitations", interpretation_start)
report = report[:interpretation_start] + interpretation + report[interpretation_end:]
conclusion_start = report.index("## Conclusion\n\n") + len("## Conclusion\n\n")
report = report[:conclusion_start] + conclusion + "\n"
report_path.write_text(report, encoding="utf-8")
print(HERE / "comparison-tables.md")
