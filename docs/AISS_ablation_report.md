# AISS Ablation: DeepBoot on the Small Workload (AISS=0 vs AISS=1)

## 1. Objective
Measure the effect of the AISS flag on the DeepBoot policy (`--policy dp`) with the small mixed workload on 16 nodes x 4 GPUs. Only `--AISS` differs between the two runs.

## 2. Configuration
| Parameter | Value |
|---|---|
| Policy | `dp` |
| AFE | 0 |
| AISS | 0 vs 1 |
| Workload | `experiment/workload/small.csv` (3360 jobs: 160 training, 3200 inference) |
| Cluster | 16 nodes x 4 GPUs (64 GPUs) |
| Code commit | `f1f7ada` (no scheduler or simulator changes versus E01's commit) |

Command (only `--AISS` changes):
```bash
python3 simulator.py --workload ./experiment/workload/small.csv --AFE 0 --AISS {0|1} --log_file 0 --output <dir> --min-nodes 16 --num-gpus 4 --policy dp
```
Both runs were launched together by `run_ablation.sh` and ran in parallel on one laptop (8 CPUs, 7 GB RAM).

## 3. What AISS does (from reading `simulator.py`)
With AISS=1, a finished inference pod enters a PROTECT state with a countdown, and a later inference job can reuse it without startup cost (lines 214, 533-549). With AISS=0, finished pods are removed immediately (lines 333, 549). This was read from the code, not verified by instrumenting the simulator.

## 4. Results
Full table (also in `aiss_ablation_results.csv`):

| Metric | AISS=0 | AISS=1 | Absolute change (1-0) | Relative change |
|---|---:|---:|---:|---:|
| Training JCT mean (s) | 2,463.32 | 2,442.58 | -20.74 | -0.8% |
| Training JCT P50 (s) | 959.00 | 984.00 | +25.00 | +2.6% |
| Training JCT P75 (s) | 1,618.75 | 1,672.75 | +54.00 | +3.3% |
| Training JCT P95 (s) | 6,527.35 | 6,751.50 | +224.15 | +3.4% |
| Training JCT max (s) | 45,877.00 | 43,773.00 | -2,104.00 | -4.6% |
| Inference JCT mean (s) | 10.78 | 7.84 | -2.94 | -27.3% |
| Inference JCT P50 (s) | 11.00 | 8.00 | -3.00 | -27.3% |
| Inference JCT P75 (s) | 13.00 | 11.00 | -2.00 | -15.4% |
| Inference JCT P95 (s) | 16.00 | 15.00 | -1.00 | -6.2% |
| Inference JCT max (s) | 52.00 | 18.00 | -34.00 | -65.4% |
| All-jobs JCT mean (s) | 127.56 | 123.78 | -3.79 | -3.0% |
| Jobs completed | 3,360 | 3,360 | 0 | 0.0% |
| Allocated GPUs mean (% of 64) | 96.78 | 94.42 | -2.36 | -2.4% |
| Real used GPUs mean (% of 64) | 84.46 | 83.46 | -1.00 | -1.2% |
| Real running GPUs mean (% of 64) | 84.55 | 83.68 | -0.88 | -1.0% |
| Peak GPUs, all three measures (%) | 100.00 | 100.00 | 0 | 0.0% |
| Simulated end clock (s) | 69,840 | 71,460 | +1,620 | +2.3% |

Per-job paired comparison (same job in both runs, AISS=1 minus AISS=0):

| Group | Jobs | Mean difference (s) | AISS=1 faster | AISS=1 slower | Equal |
|---|---:|---:|---:|---:|---:|
| Inference | 3200 | -2.94 | 1606 | 0 | 1594 |
| Training | 160 | -20.74 | 57 | 58 | 45 |

Plots: `jct_cdf_training.png`, `jct_cdf_inference.png`, `gpu_utilization_aiss.png`, `training_jct_stats.png` in `experiment/results/ablation/aiss/`.

## 5. Determinism check
The AISS=1 run uses the same configuration and code as E01. Compared job by job, all 3360 JCTs are identical (max difference 0 s). The simulation is therefore deterministic for this configuration, and a single run per setting is sufficient. The DeepBoot code path contains no random calls (`np.random` appears only in `pollux.py`). AISS=0 was not repeated.

## 6. Interpretation
- Inference jobs benefit from AISS=1: no inference job was slower, 1606 of 3200 were faster, and mean JCT fell by 27.3%. This is consistent with warm-pod reuse removing startup time, but the experiment did not isolate the mechanism.
- Training jobs show no clear effect. The mean is 0.8% lower with AISS=1, while P50, P75 and P95 are 2.6-3.4% higher, and the paired counts are split almost evenly (57 faster, 58 slower). The lower mean is driven by the longest job (max 43,773 s vs 45,877 s).
- Mean allocated GPU use is 2.4 points higher with AISS=0, and real used GPU is 1.0 point higher. The experiment does not explain why.
- AISS=1 ends 1,620 s of simulated time later than AISS=0. The cause was not investigated.

## 7. Limitations
- One run per setting. AISS=1 is shown to be deterministic by matching E01. AISS=0 is assumed to be deterministic from the code, not checked by repetition.
- One workload and one cluster size.
- Wall-clock time and peak memory were not recorded: `time_v.txt`, `start_time.txt` and `command.txt` were missing after the runs (see `RUN_NOTES.md`). The two runs shared the CPU.
- `metric.log` is empty in both runs, so goodput and speedup data are unavailable.
- The simulator is trace-driven, so pod startup and rescaling costs are modelled, not measured on real GPUs.

## 8. Reproducibility
1. Check out `f1f7ada`, then `conda activate pollux`.
2. `bash experiment/results/ablation/aiss/run_ablation.sh` (needs empty `aiss-0/` and `aiss-1/` folders; each run takes about an hour when run in parallel).
3. `python3 experiment/results/ablation/aiss/compare_aiss.py` regenerates the table, CSV, JSON and plots.

## 9. Files
`experiment/results/ablation/aiss/`: `run_ablation.sh`, `compare_aiss.py`, `RUN_NOTES.md`, `commit.txt`, `aiss_ablation_results.csv`, `aiss_comparison_table.md`, `aiss_analysis.json`, four PNG plots, and `aiss-0/`, `aiss-1/` (simulator outputs).
