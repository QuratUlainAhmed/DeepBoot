"""Load the team's retained experiment outputs (read-only).

Provenance: every value returned here is computed from files under
experiment/results/. Nothing is hardcoded except the location of each run
folder and its descriptive label. Configuration is read from the registry CSV
or from the run's own command.txt.

Formulas (same as the team reports and docs/DEEPBOOT_PAPER_AND_EXPERIMENT_COMPARISON.md):
  JCT                = completion_time - submission_time      (summary.json "jcts")
  training / inference split by job name prefix "inference"
  P50 / P95          = linear interpolation (numpy default)
  GPU %              = mean(1-s counter) / (nodes x GPUs)
  makespan (sim.)    = last simulated clock in gpu.log, or analysis-summary simulated_seconds
"""
from __future__ import annotations

import json
import os
import re
import shlex
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Dict, List, Optional

import numpy as np
import pandas

from dashboard.engine.sim_bridge import REPO_ROOT

RESULTS = os.path.join(REPO_ROOT, "experiment", "results")
TEAM = os.path.join(RESULTS, "team_experiments")
REGISTRY = os.path.join(TEAM, "experiment_registry.csv")
DOCS = os.path.join(REPO_ROOT, "docs")


@dataclass
class Experiment:
    key: str
    label: str
    folder: str
    group: str
    config: Dict[str, str] = field(default_factory=dict)
    notes: str = ""
    report: Optional[str] = None
    plots: List[str] = field(default_factory=list)


def _parse_command(path: str) -> Dict[str, str]:
    if not os.path.exists(path):
        return {}
    txt = open(path, encoding="utf-8-sig").read().strip().splitlines()
    txt = [l for l in txt if "simulator.py" in l]
    if not txt:
        return {}
    toks = shlex.split(txt[0].replace("\\", "/"), posix=True)
    out = {}
    for i, t in enumerate(toks):
        if t.startswith("--") and i + 1 < len(toks) and not toks[i + 1].startswith("--"):
            out[t[2:]] = toks[i + 1]
    m = re.search(r"PYTHONHASHSEED=(\d+)", txt[0])
    if m:
        out["PYTHONHASHSEED"] = m.group(1)
    return out


def _pngs(folder: str) -> List[str]:
    if not os.path.isdir(folder):
        return []
    return sorted(os.path.join(folder, f) for f in os.listdir(folder) if f.endswith(".png"))


@lru_cache(maxsize=1)
def catalog() -> Dict[str, Experiment]:
    exps: Dict[str, Experiment] = {}
    reg = pandas.read_csv(REGISTRY)
    for _, r in reg.iterrows():
        folder = os.path.join(REPO_ROOT, r["Output directory"])
        cfg = {
            "policy": str(r["Policy"]).split(" ")[0],
            "workload": str(r["Workload scale"]),
            "nodes×GPUs": f"{r['Number of nodes']}×{r['GPUs per node']}",
            "AFE": str(r["AFE"]), "AISS": str(r["AISS"]), "ARYL": str(r["ARYL"]).split(" ")[0],
            "inference path": str(r["Inference scheduling mode"]),
            "commit": str(r["Git commit"])[:7],
            "metadata confidence": str(r["Metadata confidence"]),
        }
        exps[r["Experiment ID"]] = Experiment(
            key=r["Experiment ID"], label=f"{r['Experiment ID']} — {r['Experiment name']}",
            folder=folder, group="registry", config=cfg, notes=str(r["Notes"]),
            report=os.path.join(REPO_ROOT, r["Report path"]) if isinstance(r["Report path"], str) else None,
            plots=_pngs(folder),
        )

    # Runs that exist on disk but post-date the registry (see comparison report §6).
    e08 = os.path.join(TEAM, "E08_DeepBoot-small-ATSI_AFE")
    if os.path.isdir(e08):
        c = _parse_command(os.path.join(e08, "command.txt"))
        exps["E08-rerun"] = Experiment(
            "E08-rerun", "E08-rerun — DeepBoot small, AFE on (verified E02 rerun)", e08, "post-registry",
            {**c, "commit": open(os.path.join(e08, "git_commit.txt")).read().strip()[:7]},
            "Verified command. Does NOT reproduce E02 exactly (train mean 2,348 vs 2,375 s).",
            os.path.join(e08, "experiment_report.md"), _pngs(e08))
    for a in (0, 1):
        f = os.path.join(RESULTS, "ablation", "aiss", f"aiss-{a}")
        if os.path.isdir(f):
            exps[f"AISS-{a}"] = Experiment(
                f"AISS-{a}", f"AISS-{a} — DeepBoot small, AFE 0, AISS={a}", f, "AISS ablation",
                {"policy": "dp", "workload": "small", "AFE": "0", "AISS": str(a), "ARYL": "0",
                 "commit": open(os.path.join(RESULTS, "ablation", "aiss", "commit.txt")).read().strip()[:7]},
                "Only --AISS differs between the pair (run_ablation.sh).",
                os.path.join(DOCS, "AISS_ablation_report.md"), _pngs(os.path.join(RESULTS, "ablation", "aiss")))
    runs = os.path.join(TEAM, "E08_infer_alloc_control", "runs")
    if os.path.isdir(runs):
        for d in sorted(os.listdir(runs)):
            out = os.path.join(runs, d, "simulator-output")
            if d.endswith("_r2") and os.path.exists(os.path.join(out, "summary.json")):
                c = _parse_command(os.path.join(runs, d, "command.txt"))
                pol = "ATS-I" if d.startswith("ats_i") else "RANDOM"
                exps[f"IA-{d}"] = Experiment(
                    f"IA-{d}", f"Alloc study — {pol}, PYTHONHASHSEED={c.get('PYTHONHASHSEED', '?')}", out,
                    "inference-allocation study", c,
                    "Controlled ATS-I vs RANDOM study (docs/inference_allocation_comparison.md).",
                    os.path.join(DOCS, "inference_allocation_comparison.md"), [])
    return exps


def _find(folder: str, name: str) -> Optional[str]:
    for cand in (os.path.join(folder, name), os.path.join(folder, "simulator-output", name)):
        if os.path.exists(cand):
            return cand
    return None


def _pct(v, q):
    return float(np.percentile(np.asarray(v, float), q)) if len(v) else float("nan")


@lru_cache(maxsize=64)
def job_jcts(key: str) -> Optional[pandas.DataFrame]:
    """Per-job JCT table with columns job, class, application, jct_s, restarts (if known)."""
    e = catalog()[key]
    s = _find(e.folder, "summary.json")
    if s:
        jcts = json.load(open(s))["jcts"]
        df = pandas.DataFrame({"job": list(jcts), "jct_s": list(jcts.values())})
        df["class"] = np.where(df["job"].str.startswith("inference"), "inference", "training")
        df["application"] = df["job"].str.replace(r"^inference-", "", regex=True).str.rsplit("-", n=1).str[0]
        jl = _find(e.folder, "jobinfo.log")
        if jl:
            try:
                rec = json.load(open(jl))
                rs = {j["name"]: (j["num_restarts"] or 0) for j in rec["submitted_jobs"]}
                df["restarts"] = df["job"].map(rs)
            except Exception:
                pass
        return df
    m = _find(e.folder, "job-metrics.csv")
    if m:
        df = pandas.read_csv(m).rename(columns={"jct_seconds": "jct_s"})
        return df[[c for c in ["job", "class", "application", "jct_s", "restarts", "rescale_delay_seconds"] if c in df]]
    return None


@lru_cache(maxsize=64)
def gpu_series(key: str) -> Optional[pandas.DataFrame]:
    e = catalog()[key]
    g = _find(e.folder, "gpu.log")
    if not g:
        return None
    d = json.load(open(g))
    return pandas.DataFrame({k: d[k] for k in ("clock", "gpu_use", "real_gpu_use", "real_running_gpu_use")})


@lru_cache(maxsize=64)
def analysis_summary(key: str) -> Optional[dict]:
    e = catalog()[key]
    a = _find(e.folder, "analysis-summary.json")
    return json.load(open(a)) if a else None


def summary_metrics(key: str, total_gpus: int = 64) -> Dict[str, object]:
    """Headline metrics with a 'source' note. Missing values are None (shown as unavailable)."""
    out: Dict[str, object] = {"experiment": key}
    df = job_jcts(key)
    if df is not None:
        for cls in ("training", "inference"):
            v = df.loc[df["class"] == cls, "jct_s"].values
            out[f"{cls} mean JCT (s)"] = float(np.mean(v)) if len(v) else None
            out[f"{cls} P50 JCT (s)"] = _pct(v, 50) if len(v) else None
            out[f"{cls} P95 JCT (s)"] = _pct(v, 95) if len(v) else None
            out[f"{cls} jobs"] = int(len(v))
        if "restarts" in df:
            out["training restarts (total)"] = float(df.loc[df["class"] == "training", "restarts"].fillna(0).sum())
    g = gpu_series(key)
    a = analysis_summary(key)
    if g is not None:
        for col, lab in (("gpu_use", "allocated GPU %"), ("real_gpu_use", "real GPU %"), ("real_running_gpu_use", "real-running GPU %")):
            out[lab] = 100.0 * g[col].mean() / total_gpus
        out["makespan (simulated h)"] = g["clock"].iloc[-1] / 3600.0
        out["GPU source"] = "gpu.log (raw)"
    elif a:
        gu = a.get("gpu_utilization", {})
        out["allocated GPU %"] = gu.get("gpu_use", {}).get("mean_capacity_percent")
        out["real GPU %"] = gu.get("real_gpu_use", {}).get("mean_capacity_percent")
        out["real-running GPU %"] = gu.get("real_running_gpu_use", {}).get("mean_capacity_percent")
        out["makespan (simulated h)"] = (a.get("simulated_seconds") or 0) / 3600.0 or None
        out["GPU source"] = "analysis-summary.json (raw gpu.log not retained)"
    if a and a.get("scheduling_optimization"):
        so = a["scheduling_optimization"]
        out["sched. decisions"] = so.get("decision_count")
        out["sched. mean wall (s)"] = so.get("mean_wall_seconds")
        out["sched. max wall (s)"] = so.get("max_wall_seconds")
    if a and a.get("training_rescale_delay_seconds"):
        out["training rescale delay (job-s)"] = a["training_rescale_delay_seconds"].get("total_job_seconds")
    return out


def optimize_history(key: str) -> Optional[pandas.DataFrame]:
    """Per-decision scheduler wall time from jobinfo.log optimize_history, if retained."""
    e = catalog()[key]
    jl = _find(e.folder, "jobinfo.log")
    if not jl:
        return None
    rec = json.load(open(jl))
    h = rec.get("optimize_history") or []
    if not h:
        return None
    return pandas.DataFrame([{"clock": c, "jobs": s[0], "nodes": s[1], "wall_s": t} for c, s, t in h])
