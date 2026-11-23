import json, re, subprocess, os, platform
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

base = Path(__file__).resolve().parent
repo = base.parents[3]

def sh(*cmd):
    try:
        return subprocess.check_output(cmd, stderr=subprocess.DEVNULL).decode().strip()
    except Exception:
        return "unavailable"

summary = json.load((base / "summary.json").open())
gpu = json.load((base / "gpu.log").open())
jobs = json.load((base / "jobinfo.log").open())
times_lines = (base / "times.txt").read_text().splitlines()
exec_log = (base / "execution.log").read_text(errors="ignore")

iso = [l.strip() for l in times_lines if re.match(r"\d{4}-\d{2}-\d{2}T", l.strip())]
start_t = iso[0] if iso else "unavailable"
end_t = iso[-1] if len(iso) > 1 else "unavailable"
m = re.search(r"exit_code=(\d+)", "\n".join(times_lines))
exit_code = m.group(1) if m else "unavailable"
m = re.search(r"Elapsed \(wall clock\) time \(h:mm:ss or m:ss\): ([\d:.]+)", exec_log)
elapsed_str = m.group(1) if m else "unavailable"
m = re.search(r"Maximum resident set size \(kbytes\): (\d+)", exec_log)
max_rss = "%.2f GiB" % (int(m.group(1)) / 1024 / 1024) if m else "unavailable"

jcts = summary["jcts"]
train = {k: v for k, v in jcts.items() if "infer" not in k}
infer = {k: v for k, v in jcts.items() if "infer" in k}

def describe(values):
    v = np.asarray(list(values), dtype=float)
    return {"count": int(v.size), "mean_seconds": float(v.mean()),
            "p50_seconds": float(np.percentile(v, 50)), "p75_seconds": float(np.percentile(v, 75)),
            "p95_seconds": float(np.percentile(v, 95)), "max_seconds": float(v.max())}

ts, is_, als = describe(train.values()), describe(infer.values()), describe(jcts.values())
clock = np.asarray(gpu["clock"])
g = {k: np.asarray(gpu[k]) for k in ("gpu_use", "real_gpu_use", "real_running_gpu_use")}
gs = {"samples": int(clock.size), "clock_end": int(clock.max()),
      "allocated_mean_percent": float(g["gpu_use"].mean() / 64 * 100),
      "allocated_peak_percent": float(g["gpu_use"].max() / 64 * 100),
      "real_mean_percent": float(g["real_gpu_use"].mean() / 64 * 100),
      "real_running_mean_percent": float(g["real_running_gpu_use"].mean() / 64 * 100)}
analysis = {"all_jcts": als, "training_jcts": ts, "inference_jcts": is_, "gpu": gs,
            "submitted_jobs": len(jobs["submitted_jobs"])}
json.dump(analysis, (base / "analysis.json").open("w"), indent=2)

E1 = {"tmean": 2442.58125, "tp50": 984.0, "tp75": 1672.75, "tp95": 6751.5, "tmax": 43773.0,
      "imean": 7.835625, "ip95": 15.0, "imax": 18.0,
      "alloc": 94.42166, "real": 83.45856, "run": 83.67769}

def d(new, old):
    return "%+.1f%%" % ((new - old) / old * 100)

tv = np.sort(np.asarray(list(train.values()), dtype=float))
iv = np.sort(np.asarray(list(infer.values()), dtype=float))
fig, ax = plt.subplots(figsize=(8, 5))
ax.plot(tv / 60, np.arange(1, tv.size + 1) / tv.size, color="#c62828", linewidth=2, label="Training jobs")
ax.plot(iv / 60, np.arange(1, iv.size + 1) / iv.size, color="#1976d2", linewidth=1.5, label="Inference jobs")
ax.set_xlabel("JCT (minutes)"); ax.set_ylabel("CDF"); ax.set_title("AFS small-workload JCT distribution")
ax.grid(True, alpha=0.25); ax.legend(); fig.tight_layout(); fig.savefig(base / "jct_cdf.png", dpi=160); plt.close(fig)

fig, ax = plt.subplots(figsize=(10, 5))
ax.plot(clock / 3600, g["gpu_use"] / 64 * 100, linewidth=0.8, color="#455a64", label="Allocated GPUs")
ax.plot(clock / 3600, g["real_gpu_use"] / 64 * 100, linewidth=0.8, color="#1565c0", label="Real used GPUs")
ax.plot(clock / 3600, g["real_running_gpu_use"] / 64 * 100, linewidth=0.8, color="#ef6c00", label="Real running GPUs")
ax.set_ylim(0, 105); ax.set_xlabel("Simulated time (hours)"); ax.set_ylabel("GPU utilization (%)")
ax.set_title("AFS small-workload GPU utilization"); ax.grid(True, alpha=0.25); ax.legend(ncol=3)
fig.tight_layout(); fig.savefig(base / "gpu_utilization.png", dpi=160); plt.close(fig)

labels = ["Mean", "P50", "P75", "P95", "Max"]
vals = np.asarray([ts["mean_seconds"], ts["p50_seconds"], ts["p75_seconds"], ts["p95_seconds"], ts["max_seconds"]]) / 60
fig, ax = plt.subplots(figsize=(8, 5))
bars = ax.bar(labels, vals, color=["#546e7a", "#1976d2", "#7b1fa2", "#ef6c00", "#c62828"])
ax.set_ylabel("Training JCT (minutes)"); ax.set_title("AFS small-workload training JCT summary")
ax.grid(axis="y", alpha=0.25)
for b, v in zip(bars, vals):
    ax.text(b.get_x() + b.get_width() / 2, b.get_height(), "%.1f" % v, ha="center", va="bottom", fontsize=9)
fig.tight_layout(); fig.savefig(base / "training_jct_summary.png", dpi=160); plt.close(fig)

commit = sh("git", "-C", str(repo), "rev-parse", "HEAD")
branch = sh("git", "-C", str(repo), "rev-parse", "--abbrev-ref", "HEAD")
files = sorted(os.listdir(base))
cmd = ("python3 simulator.py --policy afs --workload ./experiment/workload/small.csv --AFE 0 --AISS 1 "
       "--ARYL 1 --log_file 0 --output experiment/results/team_experiments/E03_afs_baseline "
       "--min-nodes 16 --num-gpus 4")
dirn = "higher" if ts["mean_seconds"] > E1["tmean"] else "lower"

R = f"""# E03: AFS Baseline (Small Workload, AISS On, AFE Off)

## 1. Objective
Run the repository's AFS scheduler (`--policy afs`) on the small mixed training/inference workload with ATS-I (AISS) enabled and AFE disabled, and record JCT and GPU-utilization results. Results are compared with the DeepBoot baseline (E01).

## 2. Configuration
| Parameter | Value |
|---|---|
| Policy | `afs` |
| AFE | 0 (off) |
| AISS | 1 (on) |
| ARYL | 1 (value used by the repository's AFS scripts) |
| Workload | `experiment/workload/small.csv` |
| Jobs completed | {als['count']} ({ts['count']} training, {is_['count']} inference) |
| Cluster | 16 nodes x 4 GPUs (64 GPUs) |

**Deviation from the repository scripts:** no script matches "AFS, small, AISS on, AFE off". `AFS-small.sh` has AISS=0 and `AFS-small-ATSI_AFE.sh` has AFE=1. The simulator was run directly with the command in section 4, with no source changes. This choice has not been confirmed by the team.

## 3. Environment
| Item | Value |
|---|---|
| Branch | `{branch}` |
| Git commit | `{commit}` |
| Python | {platform.python_version()} |
| Conda env | `pollux` |
| OS | WSL2 Ubuntu on Windows |
| Peak memory | {max_rss} |

## 4. Execution
```bash
{cmd}
```
| Item | Value |
|---|---|
| Start | {start_t} |
| End | {end_t} |
| Wall-clock runtime | {elapsed_str} |
| Exit status | {exit_code} |

`execution.log` holds only the last 200 lines. The full log was 576 MB (the simulator prints every job's JCT repeatedly), so it is kept locally and not pushed.

## 5. Results
### JCT
| Metric | E03 (AFS) | E01 (DeepBoot) | Difference |
|---|---:|---:|---:|
| Training mean JCT (s) | {ts['mean_seconds']:.2f} | {E1['tmean']:.2f} | {d(ts['mean_seconds'], E1['tmean'])} |
| Training P50 (s) | {ts['p50_seconds']:.2f} | {E1['tp50']:.2f} | {d(ts['p50_seconds'], E1['tp50'])} |
| Training P75 (s) | {ts['p75_seconds']:.2f} | {E1['tp75']:.2f} | {d(ts['p75_seconds'], E1['tp75'])} |
| Training P95 (s) | {ts['p95_seconds']:.2f} | {E1['tp95']:.2f} | {d(ts['p95_seconds'], E1['tp95'])} |
| Training max (s) | {ts['max_seconds']:.0f} | {E1['tmax']:.0f} | {d(ts['max_seconds'], E1['tmax'])} |
| Inference mean JCT (s) | {is_['mean_seconds']:.2f} | {E1['imean']:.2f} | {d(is_['mean_seconds'], E1['imean'])} |
| Inference P95 (s) | {is_['p95_seconds']:.2f} | {E1['ip95']:.2f} | {d(is_['p95_seconds'], E1['ip95'])} |
| Inference max (s) | {is_['max_seconds']:.2f} | {E1['imax']:.2f} | {d(is_['max_seconds'], E1['imax'])} |
| All-jobs mean JCT (s) | {als['mean_seconds']:.2f} | 123.78 | {d(als['mean_seconds'], 123.78)} |

### GPU utilization (percent of 64 GPUs, mean over {gs['samples']} samples)
| Measure | E03 (AFS) | E01 (DeepBoot) |
|---|---:|---:|
| Allocated | {gs['allocated_mean_percent']:.2f}% | {E1['alloc']:.2f}% |
| Real used | {gs['real_mean_percent']:.2f}% | {E1['real']:.2f}% |
| Real running | {gs['real_running_mean_percent']:.2f}% | {E1['run']:.2f}% |

Peak allocated GPUs: {gs['allocated_peak_percent']:.1f}%. Simulated time: {gs['clock_end']} s ({gs['clock_end']/3600:.2f} h).

![JCT CDF](jct_cdf.png)
![GPU utilization](gpu_utilization.png)
![Training JCT summary](training_jct_summary.png)

## 6. Interpretation
- Mean training JCT was {ts['mean_seconds']:.1f} s ({ts['mean_seconds']/60:.1f} min), {dirn} than E01's {E1['tmean']:.1f} s ({d(ts['mean_seconds'], E1['tmean'])}).
- Training P95 was {ts['p95_seconds']/60:.1f} min and max {ts['max_seconds']/3600:.2f} h, against a median of {ts['p50_seconds']/60:.1f} min.
- Inference JCT: mean {is_['mean_seconds']:.1f} s, max {is_['max_seconds']:.0f} s.
- Mean allocated utilization was {gs['allocated_mean_percent']:.1f}% and real used {gs['real_mean_percent']:.1f}%.

## 7. Limitations
- Single run on one workload; no variance estimate.
- Differs from E01 in more than the policy (ARYL=1 here vs default 0 in E01, and a different Git commit), so differences cannot be attributed to the scheduler alone.
- The AISS=1 choice was not confirmed by the team.
- The simulator is trace-driven; rescaling and restart costs are modelled, not measured.
- `metric.log` is empty, so goodput/speedup data is unavailable.

## 8. Reproducibility
1. Clone the repo and check out `{commit}`.
2. `conda env create -f environment.yaml && conda activate pollux`
3. Run the command in section 4 with an empty output folder.
4. `python3 make_report.py` from the output folder regenerates `analysis.json`, the plots and this report.

## 9. Files
""" + "\n".join("- `%s`" % f for f in files) + "\n"
(base / "report.md").write_text(R)
print(json.dumps(analysis, indent=2))
print("\nreport.md written to", base / "report.md")
