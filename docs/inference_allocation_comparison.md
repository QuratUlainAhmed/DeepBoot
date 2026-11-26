# Controlled inference allocation comparison: ATS-I vs RANDOM

## Research question

Under the repository's established DeepBoot small-workload configuration, how does the `random_allocate` inference path compare with the default ATS-I inference allocation path when all other simulator settings are held constant?

This is a new controlled simulator experiment. It is not a reproduction of a paper figure.

## Policy verification

`--random_allocate 0` selects `InferScheduler.ATSI_infer_schedule()` in `InferScheduler.optimize()`. This is the default. It converts the existing placement to scheduler state, initializes inference/training/sleeping states, places available inference replicas, and invokes the ATS-I training-GPU scheduling logic. `ARYL=0` selects `schedule_training_gpu()` rather than the Aryl branch.

`--random_allocate 1` selects `InferScheduler.random_allocate()`. The implementation sorts nodes and jobs, retains allocations for already placed active inference jobs, and collects active unallocated inference jobs in a Python `set`. It walks that set and assigns each pending inference job the next GPU in the free-GPU list. It then retains as many previous training and sleeping-job placements as the remaining free GPUs allow. It does not randomly choose a node or GPU and does not call Python's `random` module or NumPy's random generator. The difference is a distinct allocation implementation, not just a label.

The set iteration order depends on Python's string hash seed. An unset `PYTHONHASHSEED` is selected per process, so different processes can produce different pending-job order. This experiment sets `PYTHONHASHSEED` to 11, 22, and 33 and matches each seed across policies. The ATS-I and `dp` paths contain no RNG calls; other sets in these paths are used for membership/de-duplication, sorted before use, or only logged. `pollux.py` does contain NumPy randomness in its genetic optimizer, but `policy=dp` bypasses that training path. Here, hash-seed differences change RANDOM inference assignments, which can indirectly change the GPUs left for training. This gives reproducible RANDOM assignment order for a given Python version and seed.

The flag only changes inference allocation calls through `InferScheduler.optimize()`. `policy=dp` remains the DeepBoot training scheduler and still runs on the fixed scheduling interval. RANDOM can therefore affect training indirectly: the inference ordering determines which GPUs are taken first, and `update_alloc()` retains only training placements that fit in the residual free-GPU capacity. Inference placement and training capacity may respond differently; interpret their separate metrics below.

## Controlled configuration

| Setting | Value |
|---|---|
| Workload | `experiment/workload/small.csv` (160 training jobs, 3,200 inference requests) |
| Training scheduler | `dp` (DeepBoot) |
| Cluster | 16 nodes × 4 GPUs (64 modeled GPUs) |
| Max nodes / autoscaling | 16 / disabled |
| AFE / AISS / ARYL | 0 / 1 / 0 |
| Inference scheduler | `INFER_SCHEDULER=1` |
| Training repair | `REPAIR_TRAIN=1` |
| Scheduling interval | 60 seconds |
| Protect time / scale | 30 seconds / 1.0 |
| Inference priority / interference | 1 / 0.0 |
| Python | Python 3.8.12, `pollux` environment |
| Simulator commit | `5a94a70227884c3c72cc772b7e3f221224affb06` |
| Branch | `experiment/inference-allocation-controlled` |
| Repetitions | 3 matched seeds: 11, 22, 33 |

Only `random_allocate` differs between policies. The RNG environment variable differs by repetition but is matched between the two policy runs within each seed pair.

## Commands, seeds, and run records

Each completed command is recorded verbatim in its run directory's `command.txt`; `run-metadata.json` records the commit, seed, start/end timestamps, exit code, runtime, and policy. Exact command files and successful output folders are linked in the run-records table below, under [`experiment/results/team_experiments/E08_infer_alloc_control/runs/`](../experiment/results/team_experiments/E08_infer_alloc_control/runs/).

The command template is:

```sh
PYTHONHASHSEED=<seed> /home/crazi-grace/miniforge3/envs/pollux/bin/python3.8 -u simulator.py \
  --workload experiment/workload/small.csv --AFE 0 --AISS 1 --ARYL 0 \
  --INFER_SCHEDULER 1 --REPAIR_TRAIN 1 --protect_time 30 --interference 0.0 \
  --interval 60 --min-nodes 16 --num-gpus 4 --random_allocate <0-or-1> \
  --policy dp --log_file 0 --output <unique-run-output-directory>
```

One initial seed-11 ATS-I launch was interrupted during startup before it produced result files; it is excluded from analysis. Its command is preserved in [`runs/ats_i_seed11/command.txt`](../experiment/results/team_experiments/E08_infer_alloc_control/runs/ats_i_seed11/command.txt), with the reason in `attempt-status.json`. The successful matched seed-11 ATS-I run is `runs/ats_i_seed11_r2/`.

## Raw results and summary

The simulator outputs in each run folder are the source for this analysis. JCT is `completion_time - submission_time`. Training rows are names not starting with `inference-`; inference rows start with `inference-`. P95 uses NumPy's default linear percentile. GPU percentages are means of one-second simulator counters divided by 64 modeled GPUs; they are simulated values, not physical telemetry. Each `optimize_history` timing wraps one selected optimizer call: DeepBoot's training policy on the 60-second interval and the inference scheduler between intervals. The total therefore reflects both types of call and how many scheduling events occurred; it is not an isolated timing of `random_allocate()` or ATS-I alone.

## Repeated-run summary

| Metric | ATS-I (mean ± SD; range) | RANDOM (mean ± SD; range) | RANDOM − ATS-I |
|---|---:|---:|---:|
| Training mean JCT (s) | 2442.58 ± 0.00 (2442.58–2442.58) | 2567.24 ± 33.29 (2542.81–2605.16) | +124.66 |
| Training P95 JCT (s) | 6751.50 ± 0.00 (6751.50–6751.50) | 6583.52 ± 281.04 (6295.70–6857.25) | -167.98 |
| Inference mean JCT (s) | 7.84 ± 0.00 (7.84–7.84) | 7.90 ± 0.02 (7.88–7.93) | +0.07 |
| Inference P95 JCT (s) | 15.00 ± 0.00 (15.00–15.00) | 15.00 ± 0.00 (15.00–15.00) | +0.00 |
| Allocated GPU utilization (%) | 94.42 ± 0.00 (94.42–94.42) | 94.63 ± 0.05 (94.60–94.69) | +0.21 |
| Real GPU utilization (%) | 83.46 ± 0.00 (83.46–83.46) | 84.31 ± 0.21 (84.14–84.54) | +0.85 |
| Real running GPU utilization (%) | 83.68 ± 0.00 (83.68–83.68) | 84.53 ± 0.21 (84.36–84.77) | +0.85 |
| Training allocation restarts (count) | 1894.00 ± 0.00 (1894.00–1894.00) | 1755.67 ± 22.50 (1738.00–1781.00) | -138.33 |
| Training jobs with restarts (count) | 92.00 ± 0.00 (92.00–92.00) | 116.33 ± 3.06 (113.00–119.00) | +24.33 |
| Training rescale delay (job-s)  | 49612.00 ± 0.00 (49612.00–49612.00) | 46086.33 ± 313.21 (45780.00–46406.00) | -3525.67 |
| Simulator time advanced (s) | 71460.00 ± 0.00 (71460.00–71460.00) | 69560.00 ± 124.90 (69420.00–69660.00) | -1900.00 |
| Scheduling overhead mean/decision (s) | 0.0111 ± 0.0027 (0.0092–0.0142) | 0.0077 ± 0.0004 (0.0074–0.0081) | -0.0034 |
| Scheduling overhead P95/decision (s) | 0.0579 ± 0.0095 (0.0510–0.0688) | 0.0510 ± 0.0020 (0.0490–0.0530) | -0.0069 |
| Total scheduling overhead (s) | 81.07 ± 19.63 (67.48–103.58) | 55.80 ± 2.82 (54.13–59.06) | -25.27 |

## Raw per-run values

| Seed | Policy | Train mean JCT (s) | Train P95 (s) | Infer mean JCT (s) | Infer P95 (s) | Allocated / real / running GPU (%) | Training restarts / affected jobs | Training rescale delay (job-s) | Simulator seconds | Decisions | Mean scheduling cost (s) | Wall time (s) |
|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 11 | ats_i | 2442.58 | 6751.50 | 7.84 | 15.00 | 94.42 / 83.46 / 83.68 | 1894 / 92 | 49612 | 71460 | 7306 | 0.0142 | 1192.07 |
| 11 | random | 2542.81 | 6597.60 | 7.93 | 15.00 | 94.69 / 84.23 / 84.45 | 1781 / 119 | 46406 | 69600 | 7276 | 0.0081 | 667.20 |
| 22 | ats_i | 2442.58 | 6751.50 | 7.84 | 15.00 | 94.42 / 83.46 / 83.68 | 1894 / 92 | 49612 | 71460 | 7306 | 0.0099 | 701.38 |
| 22 | random | 2553.74 | 6295.70 | 7.91 | 15.00 | 94.60 / 84.14 / 84.36 | 1748 / 117 | 46073 | 69420 | 7274 | 0.0074 | 591.39 |
| 33 | ats_i | 2442.58 | 6751.50 | 7.84 | 15.00 | 94.42 / 83.46 / 83.68 | 1894 / 92 | 49612 | 71460 | 7306 | 0.0092 | 668.67 |
| 33 | random | 2605.16 | 6857.25 | 7.88 | 15.00 | 94.60 / 84.54 / 84.77 | 1738 / 113 | 45780 | 69660 | 7274 | 0.0075 | 593.32 |


## Exact run records

| Seed | Policy | Exact command | Output directory | Wall time (s) |
|---:|---|---|---|---:|
| 11 | ats_i | [command.txt](../experiment/results/team_experiments/E08_infer_alloc_control/runs/ats_i_seed11_r2/command.txt) | [simulator-output/](../experiment/results/team_experiments/E08_infer_alloc_control/runs/ats_i_seed11_r2/simulator-output/) | 1192.07 |
| 11 | random | [command.txt](../experiment/results/team_experiments/E08_infer_alloc_control/runs/random_seed11_r2/command.txt) | [simulator-output/](../experiment/results/team_experiments/E08_infer_alloc_control/runs/random_seed11_r2/simulator-output/) | 667.20 |
| 22 | ats_i | [command.txt](../experiment/results/team_experiments/E08_infer_alloc_control/runs/ats_i_seed22_r2/command.txt) | [simulator-output/](../experiment/results/team_experiments/E08_infer_alloc_control/runs/ats_i_seed22_r2/simulator-output/) | 701.38 |
| 22 | random | [command.txt](../experiment/results/team_experiments/E08_infer_alloc_control/runs/random_seed22_r2/command.txt) | [simulator-output/](../experiment/results/team_experiments/E08_infer_alloc_control/runs/random_seed22_r2/simulator-output/) | 591.39 |
| 33 | ats_i | [command.txt](../experiment/results/team_experiments/E08_infer_alloc_control/runs/ats_i_seed33_r2/command.txt) | [simulator-output/](../experiment/results/team_experiments/E08_infer_alloc_control/runs/ats_i_seed33_r2/simulator-output/) | 668.67 |
| 33 | random | [command.txt](../experiment/results/team_experiments/E08_infer_alloc_control/runs/random_seed33_r2/command.txt) | [simulator-output/](../experiment/results/team_experiments/E08_infer_alloc_control/runs/random_seed33_r2/simulator-output/) | 593.32 |

The complete numeric extraction is saved in [`comparison-results.json`](../experiment/results/team_experiments/E08_infer_alloc_control/comparison-results.json). Raw `summary.json`, `gpu.log`, and `jobinfo.log` remain in each run's `simulator-output/` directory.

## Interpretation

ATS-I produced identical JCT and GPU-counter values for all three hash seeds, while its measured scheduling time varied. That is consistent with a deterministic placement path for this configuration; wall-clock optimizer timings naturally varied. RANDOM increased training mean JCT in each matched pair by 100.23, 111.16, and 162.57 seconds (mean +124.66 seconds, about +5.1%). Inference mean JCT increased by only 0.04–0.09 seconds across the pairs (mean +0.07 seconds, about +0.9%), and inference P95 stayed at 15 seconds. Training P95 did not move consistently: it fell for seeds 11 and 22 and rose for seed 33. Its mean across the three runs is 168 seconds lower, but that average does not establish a reliable tail-latency improvement with only three seeds.

RANDOM's mean real GPU utilization was 0.85 percentage points higher, while training mean JCT was also higher. The source explains how these outcomes can coexist: RANDOM assigns pending inference jobs by set order from the free-GPU list, then retains training placements that fit in the residual capacity; ATS-I instead builds a placement state and runs its inference/training scheduling steps. The RANDOM path does not optimize training placements for job characteristics. The seed-to-seed changes in training JCT and utilization match the set-order sensitivity in that code path. Utilization is a capacity counter, so the higher value alone does not imply lower JCT.

The recorded training restart count was lower under RANDOM (mean 1,756 vs 1,894), but more training jobs had at least one recorded restart (116 vs 92). Recorded aggregate rescale delay was also lower (46,086 vs 49,612 job-seconds). These are simulator counters and describe a different allocation-change pattern; they do not contradict the higher training mean JCT. RANDOM's measured scheduler overhead was lower by 0.0034 seconds per decision on average and 25.27 seconds total. Per-decision timing covers whichever optimizer the simulator called: DeepBoot at 60-second intervals and the inference scheduler between those intervals. Total time also depends on the number of scheduling decisions; RANDOM runs advanced about 1,900 fewer simulated seconds and averaged about 31 fewer decisions. The simpler `random_allocate()` path is consistent with lower per-decision cost, but this is not an isolated microbenchmark of that function.

## Limitations

- This is a simulator experiment on one workload and one cluster shape; it does not establish the paper's results or behavior at other scales.
- RANDOM is not an RNG-driven sampler. Its variation here comes from Python set iteration order under explicitly controlled hash seeds.
- Three seeds provide a small exploratory sample. Reported standard deviations describe these three runs and are not confidence intervals or significance tests.
- GPU utilization and scheduler wall times are simulator counters/timers. They are not physical GPU measurements.
- JCT differences may arise from inference ordering and the corresponding residual GPU capacity available to training jobs, as determined by the implementation described above.
- `metric.log` goodput/speedup arrays are empty in this simulator configuration; those metrics are unavailable.

## Conclusion

For this controlled small-workload configuration, RANDOM had a higher training mean JCT (about 5.1%) in all three matched runs and slightly higher inference mean JCT, with no change in inference P95. Training P95 was seed-sensitive and did not show a consistent direction. RANDOM used more modeled GPU capacity and less scheduler time, but that did not translate into lower training mean JCT. The evidence supports ATS-I for training mean JCT in this setup; the three-seed experiment does not establish statistical significance or a general result beyond this workload.
