"""Regenerate the team experiment registry and normalized results CSVs.

Add new runs to EXPERIMENTS after verifying their command/configuration and
artifacts. This script reads recorded outputs only; it never launches simulator.py.
"""

import csv
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent
TEAM_PATH = "experiment/results/team_experiments"

EXPERIMENTS = [
    {
        "id": "E01", "name": "DeepBoot baseline, small workload",
        "purpose": "DeepBoot small-workload baseline with AFE disabled.",
        "scheduler": "DeepBoot", "policy": "dp", "workload": "small.csv",
        "scale": "small", "nodes": "16", "gpus_per_node": "4",
        "afe": "0", "aiss": "1",
        "aryl": "0 (CLI default)", "infer_allocation": "ATS-I allocation; random_allocate=0 (CLI default)",
        "infer_mode": "ATS-I (INFER_SCHEDULER=1 default; ARYL=0)",
        "commit": "cc85a24b346cfac17603cdfc9f5018089ac59432",
        "status": "completed", "member": "UNKNOWN",
        "dir": "E01_deepboot_baseline", "report": "experiment_report.md",
        "summary": "E01_deepboot_baseline/summary.json",
        "gpu": "E01_deepboot_baseline/gpu.log",
        "analysis": "E01_deepboot_baseline/analysis.json",
        "runtime": 2069.55, "runtime_source": "E01_deepboot_baseline/runtime.txt; report says timestamp-derived estimate",
        "job_source": "E01_deepboot_baseline/summary.json",
        "gpu_capacity": 64,
        "notes": "Exit 0; 3,360 JCTs. No full execution log. Wall time is an interval estimate, not /usr/bin/time.",
        "metrics": "JCT by job; GPU counters; simulated clock; metric log (empty)",
        "config_source": "E01 report Sections 4, 6; launcher experiment/cmd/16node-4gpu/small/DeepBoot-small-ATSI.sh; simulator.py CLI defaults",
        "confidence": "HIGH for configuration; MEDIUM for runtime measurement",
    },
    {
        "id": "E02", "name": "DeepBoot small workload, AFE on",
        "purpose": "DeepBoot small-workload AFE-on run, intended counterpart to E01.",
        "scheduler": "DeepBoot",
        "policy": "dp (E02 launcher; exact executed invocation unrecorded)",
        "workload": "small.csv (all summary job names match small.csv)",
        "scale": "small", "nodes": "16 (E02 launcher; invocation unrecorded)", "gpus_per_node": "4 (E02 launcher; invocation unrecorded)",
        "afe": "1", "aiss": "1", "aryl": "0 (launcher omits flag; default if used)",
        "infer_allocation": "ATS-I path; random_allocate=0 (launcher omits flag; defaults if used)",
        "infer_mode": "INFER_SCHEDULER=1 (default if launcher used); runtime invocation unrecorded",
        "commit": "6772f554dd104d908328f63e4ab719184c6ff4d3",
        "status": "completed", "member": "UNKNOWN",
        "dir": "E02_deepboot_afe", "report": "",
        "summary": "E02_deepboot_afe/summary.json",
        "gpu": "E02_deepboot_afe/gpu.log",
        "analysis": "E02_deepboot_afe/analysis.json",
        "runtime": 1313.2016817, "runtime_source": "E02_deepboot_afe/runtime.txt (timing method not specified)",
        "job_source": "E02_deepboot_afe/summary.json",
        "gpu_capacity": 64,
        "notes": "Exit 0; 3,360 JCTs. E02 commit title and matching launcher support configuration, but no invocation record/full log proves that launcher was used. 64-GPU normalization is recorded in analysis; run_tail.log is partial.",
        "metrics": "JCT by job; GPU counters and analysis; simulated clock; metric log (empty); jobinfo",
        "config_source": "E02 commit d589451; matching launcher at experiment/cmd/16node-4gpu/small/DeepBoot-small-ATSI_AFE.sh; output commit.txt; simulator.py defaults; no command record",
        "confidence": "MEDIUM (launcher and commit metadata agree; actual executed flags not independently recorded)",
    },
    {
        "id": "E03", "name": "AFS small baseline, AFE off",
        "purpose": "AFS small-workload reference with AFE disabled.",
        "scheduler": "AFS", "policy": "afs", "workload": "small.csv",
        "scale": "small", "nodes": "16", "gpus_per_node": "4",
        "afe": "0", "aiss": "1",
        "aryl": "1", "infer_allocation": "Aryl-specific inference allocation",
        "infer_mode": "AISS lifecycle + Aryl-specific path (ARYL=1; INFER_SCHEDULER=1 default)",
        "commit": "6772f554dd104d908328f63e4ab719184c6ff4d3",
        "status": "completed", "member": "UNKNOWN",
        "dir": "E03_afs_baseline", "report": "report.md",
        "summary": "E03_afs_baseline/summary.json",
        "gpu": "E03_afs_baseline/gpu.log",
        "analysis": "E03_afs_baseline/analysis.json",
        "runtime": 527.80, "runtime_source": "E03_afs_baseline/times.txt and report.md",
        "job_source": "E03_afs_baseline/summary.json",
        "gpu_capacity": 64,
        "notes": "Exit 0; 3,360 JCTs. ARYL=1 differs from pure ATS-I behavior. execution.log is only a 200-line tail; report says full ~576 MB capture is local/not pushed.",
        "metrics": "JCT by job; GPU counters; simulated clock; metric log (empty)", "config_source": "E03 report and retained run metadata", "confidence": "HIGH",
    },
    {
        "id": "E04", "name": "DeepBoot workload scaling, middle workload",
        "purpose": "DeepBoot middle-workload scaling contrast against small workload.",
        "scheduler": "DeepBoot", "policy": "dp", "workload": "middle.csv",
        "scale": "middle", "nodes": "16", "gpus_per_node": "4",
        "afe": "0", "aiss": "1",
        "aryl": "0", "infer_allocation": "ATS-I allocation; random_allocate=0",
        "infer_mode": "ATS-I (INFER_SCHEDULER=1 default; ARYL=0)",
        "commit": "6772f554dd104d908328f63e4ab719184c6ff4d3",
        "status": "completed", "member": "UNKNOWN",
        "dir": "E04_deepboot_workload_scaling", "report": "report.md",
        "summary": "E04_deepboot_workload_scaling/simulator-output/summary.json",
        "gpu": "E04_deepboot_workload_scaling/simulator-output/gpu.log",
        "analysis": "E04_deepboot_workload_scaling/analysis.json",
        "runtime": 2526.66, "runtime_source": "E04_deepboot_workload_scaling/runtime.txt (/usr/bin/time -v)",
        "job_source": "E04_deepboot_workload_scaling/simulator-output/summary.json",
        "gpu_capacity": 64,
        "notes": "Exit 0; 16,160 JCTs (160 training, 16,000 inference). Complete compressed execution.log.gz is local and excluded from Git due to size. Inference rows differ from small workload; scaling contrast is descriptive.",
        "metrics": "JCT by job; GPU counters; simulated clock; metric log (empty)", "config_source": "E04 report, command.txt, run_e04.sh, environment.txt", "confidence": "HIGH",
    },
    {
        "id": "E05", "name": "Pollux small, AISS lifecycle",
        "purpose": "Pollux optimizer-path reference on small mixed workload.",
        "scheduler": "Pollux", "policy": "pollux", "workload": "small.csv",
        "scale": "small", "nodes": "16", "gpus_per_node": "4",
        "afe": "0", "aiss": "1",
        "aryl": "0", "infer_allocation": "Pollux optimizer inference path",
        "infer_mode": "Pollux optimizer path (INFER_SCHEDULER=0; REPAIR_TRAIN=0)",
        "commit": "cc85a24b346cfac17603cdfc9f5018089ac59432",
        "status": "completed", "member": "UNKNOWN",
        "dir": "E05_Pollux-small-ATSI", "report": "experiment_report.md",
        "summary": "E05_Pollux-small-ATSI/analysis-summary.json",
        "gpu": "E05_Pollux-small-ATSI/analysis-summary.json",
        "analysis": "E05_Pollux-small-ATSI/analysis-summary.json",
        "runtime": None, "runtime_source": "E05_Pollux-small-ATSI/run-metadata.json",
        "job_source": "E05_Pollux-small-ATSI/job-metrics.csv; analysis-summary.json",
        "gpu_capacity": 64,
        "notes": "Exit 0; 3,360 completed. Filename says ATSI but INFER_SCHEDULER=0 uses Pollux optimizer. Raw summary.json/gpu.log/metric.log and reported console.log are not in this folder; job-metrics.csv and analysis-summary.json are retained.",
        "metrics": "Per-job JCT; derived GPU utilization; optimization-time analysis", "config_source": "E05 report, command.txt, run-metadata.json", "confidence": "HIGH",
    },
    {
        "id": "E06", "name": "AFS small, AFE on",
        "purpose": "AFS AFE-on result, paired descriptively with E03.",
        "scheduler": "AFS", "policy": "afs", "workload": "small.csv",
        "scale": "small", "nodes": "16", "gpus_per_node": "4",
        "afe": "1", "aiss": "1",
        "aryl": "1", "infer_allocation": "Aryl-specific inference allocation",
        "infer_mode": "AISS lifecycle + Aryl-specific path (ARYL=1; INFER_SCHEDULER=1 default)",
        "commit": "cc85a24b346cfac17603cdfc9f5018089ac59432",
        "status": "completed", "member": "UNKNOWN",
        "dir": "E06_AFS-small-ATSI_AFE", "report": "experiment_report.md",
        "summary": "E06_AFS-small-ATSI_AFE/analysis-summary.json",
        "gpu": "E06_AFS-small-ATSI_AFE/analysis-summary.json",
        "analysis": "E06_AFS-small-ATSI_AFE/analysis-summary.json",
        "runtime": None, "runtime_source": "E06_AFS-small-ATSI_AFE/run-metadata.json",
        "job_source": "E06_AFS-small-ATSI_AFE/job-metrics.csv; analysis-summary.json",
        "gpu_capacity": 64,
        "notes": "Exit 0; 3,360 completed. ARYL=1 means this is not a pure ATS-I inference configuration. Raw simulator summary/gpu/metric logs and reported full console capture are absent from this folder.",
        "metrics": "Per-job JCT; derived GPU utilization", "config_source": "E06 report, command.txt, run-metadata.json", "confidence": "HIGH",
    },
    {
        "id": "E07", "name": "DeepBoot small, random inference allocation",
        "purpose": "DeepBoot inference random-allocation branch comparison.",
        "scheduler": "DeepBoot", "policy": "dp", "workload": "small.csv",
        "scale": "small", "nodes": "16", "gpus_per_node": "4",
        "afe": "0", "aiss": "1",
        "aryl": "0", "infer_allocation": "random_allocate=1",
        "infer_mode": "random_allocate=1 (INFER_SCHEDULER=1; ARYL=0)",
        "commit": "cc85a24b346cfac17603cdfc9f5018089ac59432",
        "status": "completed", "member": "UNKNOWN",
        "dir": "E07_DeepBoot-small-ATSI_RANDOM", "report": "experiment_report.md",
        "summary": "E07_DeepBoot-small-ATSI_RANDOM/analysis-summary.json",
        "gpu": "E07_DeepBoot-small-ATSI_RANDOM/analysis-summary.json",
        "analysis": "E07_DeepBoot-small-ATSI_RANDOM/analysis-summary.json",
        "runtime": None, "runtime_source": "E07_DeepBoot-small-ATSI_RANDOM/run-metadata.json",
        "job_source": "E07_DeepBoot-small-ATSI_RANDOM/job-metrics.csv; analysis-summary.json",
        "gpu_capacity": 64,
        "notes": "Exit 0; 3,360 completed. random_allocate selects a separate inference branch; report notes no explicit RNG/seed. Raw simulator summary/gpu/metric files and reported console log are absent from this folder.",
        "metrics": "Per-job JCT; derived GPU utilization", "config_source": "E07 report, command.txt, run-metadata.json", "confidence": "HIGH",
    },
]


REGISTRY_FIELDS = [
    "Experiment ID", "Experiment name", "Purpose", "Scheduler", "Policy", "Workload",
    "Workload scale", "Number of nodes", "GPUs per node", "AFE", "AISS",
    "ARYL", "Inference allocation mode", "Inference scheduling mode", "Git commit", "Status",
    "Assigned team member", "Output directory", "Report path", "Notes",
    "Metrics available", "Configuration source", "Metadata confidence",
]

RESULT_FIELDS = [
    "Experiment ID", "Scheduler", "Policy", "Workload", "Cluster configuration",
    "Total jobs", "Training jobs", "Inference jobs", "Training mean JCT (s)",
    "Training median JCT (s)", "Training P95 JCT (s)", "Training maximum JCT (s)",
    "Inference mean JCT (s)", "Overall mean JCT (s)",
    "GPU utilization mean (allocated, %)", "Real GPU utilization mean (%)",
    "Running GPU utilization mean (%)", "Simulation duration (simulated s)",
    "Actual wall-clock runtime (s)", "Number of completed jobs", "Number of failed jobs",
    "Throughput/goodput", "JCT source", "GPU utilization source",
    "Simulation duration source", "Runtime source", "Job-count source",
    "Failed-job source", "Throughput/goodput source", "Notes/limitations",
]


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def read_jcts(exp, folder):
    if exp.get("summary"):
        summary_path = ROOT / exp["summary"]
        if summary_path.exists():
            summary = read_json(summary_path)
            if "jcts" in summary:
                jobs = summary["jcts"]
                return {
                    "all": list(jobs.values()),
                    "training": [v for n, v in jobs.items() if not n.startswith("inference-")],
                    "inference": [v for n, v in jobs.items() if n.startswith("inference-")],
                }, summary
    with (folder / "job-metrics.csv").open(newline="", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    classes = {
        key: [float(r["jct_seconds"]) for r in rows if r["class"] == key]
        for key in ("training", "inference")
    }
    classes["all"] = classes["training"] + classes["inference"]
    return classes, None


def mean(values):
    return sum(values) / len(values) if values else None


def percentile_linear(values, p):
    """NumPy default (linear/type-7) percentile without a NumPy dependency."""
    if not values:
        return None
    ordered = sorted(values)
    h = (len(ordered) - 1) * p / 100.0
    lo = int(h)
    hi = min(lo + 1, len(ordered) - 1)
    return ordered[lo] + (h - lo) * (ordered[hi] - ordered[lo])


def gpu_statistics(exp, folder):
    gpu_path = ROOT / exp["gpu"] if exp.get("gpu") else None
    if gpu_path and gpu_path.name == "gpu.log":
        gpu = read_json(gpu_path)
        capacity = exp.get("gpu_capacity")
        if not capacity:
            return {}, None
        result = {
            key: mean(gpu[key]) / capacity * 100
            for key in ("gpu_use", "real_gpu_use", "real_running_gpu_use")
        }
        return result, gpu["clock"][-1] if gpu.get("clock") else None
    analysis = read_json(folder / "analysis-summary.json")
    usage = analysis.get("gpu_utilization", {})
    result = {}
    for key in ("gpu_use", "real_gpu_use", "real_running_gpu_use"):
        if key in usage:
            result[key] = usage[key].get("mean_capacity_percent")
    return result, analysis.get("simulated_seconds")


def build_rows():
    registry_rows, result_rows = [], []
    for exp in EXPERIMENTS:
        folder = ROOT / exp["dir"]
        report = team_path(f"{exp['dir']}/{exp['report']}") if exp["report"] else ""
        registry_rows.append({
            "Experiment ID": exp["id"], "Experiment name": exp["name"],
            "Purpose": exp["purpose"],
            "Scheduler": exp["scheduler"], "Policy": exp["policy"],
            "Workload": exp["workload"], "Workload scale": exp["scale"],
            "Number of nodes": exp["nodes"], "GPUs per node": exp["gpus_per_node"],
            "AFE": exp["afe"], "AISS": exp["aiss"],
            "ARYL": exp["aryl"], "Inference allocation mode": exp["infer_allocation"],
            "Inference scheduling mode": exp["infer_mode"], "Git commit": exp["commit"],
            "Status": exp["status"], "Assigned team member": exp["member"],
            "Output directory": team_path(exp["dir"]), "Report path": report,
            "Notes": exp["notes"], "Metrics available": exp["metrics"],
            "Configuration source": exp["config_source"],
            "Metadata confidence": exp["confidence"],
        })

        classes, summary = read_jcts(exp, folder)
        gpu, sim_duration = gpu_statistics(exp, folder)
        training, inference, all_jobs = classes["training"], classes["inference"], classes["all"]
        workload_path = ROOT.parent.parent / "workload" / (exp["scale"] + ".csv")
        with workload_path.open(newline="", encoding="utf-8-sig") as f:
            workload_rows = list(csv.DictReader(f))
        total_jobs = len(workload_rows)
        workload_training = sum(not row["name"].startswith("inference-") for row in workload_rows)
        workload_inference = total_jobs - workload_training
        if summary is not None:
            completed = len(summary["jcts"])
            completed_source = exp["job_source"]
        else:
            analysis = read_json(folder / "analysis-summary.json")
            completed = analysis.get("job_count_completed")
            completed_source = exp["job_source"]

        def stat(vals, op):
            if not vals:
                return ""
            value = op(vals)
            return round(value, 6) if isinstance(value, float) else value

        if exp["id"] == "E05":
            runtime = read_json(folder / "run-metadata.json").get("runtime_seconds")
        elif exp["id"] == "E06":
            runtime = read_json(folder / "run-metadata.json").get("runtime_seconds")
        elif exp["id"] == "E07":
            runtime = read_json(folder / "run-metadata.json").get("runtime_seconds")
        else:
            runtime = exp["runtime"]

        result_rows.append({
            "Experiment ID": exp["id"], "Scheduler": exp["scheduler"], "Policy": exp["policy"],
            "Workload": exp["workload"],
            "Cluster configuration": (
                "16 nodes × 4 GPUs/node (launcher; invocation unverified)"
                if exp["id"] == "E02"
                else f"{exp['nodes']} nodes × {exp['gpus_per_node']} GPUs/node"
                if exp["nodes"].isdigit() and exp["gpus_per_node"].isdigit()
                else "UNKNOWN"
            ),
            "Total jobs": total_jobs, "Training jobs": workload_training, "Inference jobs": workload_inference,
            "Training mean JCT (s)": stat(training, mean),
            "Training median JCT (s)": stat(training, lambda x: percentile_linear(x, 50)),
            "Training P95 JCT (s)": stat(training, lambda x: percentile_linear(x, 95)),
            "Training maximum JCT (s)": stat(training, max),
            "Inference mean JCT (s)": stat(inference, mean),
            "Overall mean JCT (s)": stat(all_jobs, mean),
            "GPU utilization mean (allocated, %)": round(gpu["gpu_use"], 6) if gpu.get("gpu_use") is not None else "",
            "Real GPU utilization mean (%)": round(gpu["real_gpu_use"], 6) if gpu.get("real_gpu_use") is not None else "",
            "Running GPU utilization mean (%)": round(gpu["real_running_gpu_use"], 6) if gpu.get("real_running_gpu_use") is not None else "",
            "Simulation duration (simulated s)": sim_duration if sim_duration is not None else "",
            "Actual wall-clock runtime (s)": runtime if runtime is not None else "",
            "Number of completed jobs": completed if completed is not None else "",
            "Number of failed jobs": "", "Throughput/goodput": "",
            "JCT source": team_path(exp["job_source"]), "GPU utilization source": team_path(exp["gpu"]),
            "Simulation duration source": team_path(
                exp["gpu"] if Path(exp["gpu"]).name == "gpu.log" else exp["analysis"]),
            "Runtime source": team_path(exp["runtime_source"]),
            "Job-count source": f"experiment/workload/{exp['scale']}.csv; completed count: {team_path(completed_source)}",
            "Failed-job source": "Not emitted by simulator", "Throughput/goodput source":
                (team_path(exp["dir"] + "/metric.log") if (folder / "metric.log").exists()
                 else team_path(exp["dir"] + "/analysis-summary.json") + ": metric_log_values empty; unavailable"),
            "Notes/limitations": exp["notes"],
        })
    return registry_rows, result_rows


def write_csv(path, fields, rows):
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def team_path(path):
    return f"{TEAM_PATH}/{path}" if path else ""


if __name__ == "__main__":
    registry, results = build_rows()
    write_csv(ROOT / "experiment_registry.csv", REGISTRY_FIELDS, registry)
    write_csv(ROOT / "master_results.csv", RESULT_FIELDS, results)
    print(f"Wrote {len(registry)} completed registry rows and {len(results)} result rows.")
