# Size- and Progress-Aware ATS-I GPU Reclaiming

## What was happening before

The original ATS-I inference scheduler considered candidate GPUs to reclaim from
training tasks. For each candidate, it estimated the remaining training jobs'
speedups and selected the candidate with the largest **unweighted sum** of
speedups (`InferScheduler._schedule_training_gpu`). This accounts for a GPU's
immediate throughput impact, but does not explicitly include a training job's
restart cost, previous restarts, or accumulated execution time.

In the recorded E08 experiment, four ImageNet jobs accounted for about 38.5% of
the sum of training JCTs and had 872 of the 1,798 recorded training allocation
restarts. This is a reason to test whether explicit protection based on
interruption cost and job progress helps; it is not proof by itself that the
unweighted ATS-I objective caused those outcomes.

## What changed

ATS-I can now optionally apply a priority multiplier to each training job's
speedup before it compares GPU-reclaim candidates:

```text
P_i = (alpha * C_i_norm
     + beta  * R_i_norm
     + gamma * E_i_norm) / (alpha + beta + gamma)

weighted_speedup_i = speedup_i * (1 + strength * P_i)
```

The normalized inputs are:

- `C_i`: estimated restart cost in GPU-seconds: the modeled restart delay in
  seconds multiplied by the number of GPUs currently allocated to the job
  (at least one for a not-yet-allocated job).
- `R_i`: number of previous training allocation restarts.
- `E_i`: accumulated active training execution time in seconds.

Each component is divided by its maximum among the current training jobs; an
all-zero component remains zero. `P_i` is therefore between zero and one for
non-negative configuration weights. A higher score makes removing one of that
job's GPUs more costly to the ATS-I objective, while still allowing reclaiming
if it is the least harmful feasible choice.

Restart delay uses `NEXT_DELAY` when AFE is enabled and
`APPLICATIONS_DELAY` otherwise. This is a model-based estimate, not a live
measurement of restart cost.

## Configuration and preserving the baseline

The feature is **off by default** to preserve previous experiment behavior.
Enable it explicitly for ATS-I inference scheduling:

```text
--size_aware_scheduling 1
```

Defaults when enabled:

| Argument | Default | Meaning |
|---|---:|---|
| `--size_aware_alpha` | 0.4 | Weight of estimated restart cost |
| `--size_aware_beta` | 0.3 | Weight of previous restart count |
| `--size_aware_gamma` | 0.3 | Weight of accumulated active execution time |
| `--size_aware_strength` | 0.5 | Maximum relative speedup multiplier increase |

Weights must be non-negative and at least one must be positive. Strength must
be non-negative. Existing commands omit these flags and retain the original
unweighted ATS-I behavior. The feature applies to the ATS-I path, not the
separate random-allocation path or the periodic DeepBoot DP training allocator.

## Exact source changes

- `utils.py`: add restart count, modeled restart-delay, and current replica
  fields to `JobInfo`, retaining defaults for existing callers. Accumulated
  active runtime was already available as `JobInfo.run_time`.
- `simulator.py`: populate those fields from each live training job, use the
  simulator's AFE/non-AFE restart-delay model, validate the new CLI options,
  and pass them to the cluster's inference scheduler.
- `infer_scheduler.py`: calculate normalized priority multipliers and apply
  them to per-job speedups used when ATS-I compares GPU-reclaim candidates.
- `tests/test_size_aware_inference_scheduler.py`: test priority formation,
  reclaim preference, and unchanged weights with the feature disabled.

No workload, experiment script, or existing result artifact was changed.

## Validation and limitations

Run the focused tests with:

```powershell
python -m unittest tests.test_size_aware_inference_scheduler
```

The feature is an experiment, not a claim that the heuristic is optimal. The
weights and strength require sensitivity analysis. Current normalization is
relative to the jobs active at each scheduling decision, so priority values
can shift as the workload changes. The modeled restart delay is approximate,
and active execution time is used as the accumulated-progress proxy. Compare
enabled and disabled ATS-I runs using the same workload, commit, and settings;
report training mean/tail JCT, inference latency, restarts, and utilization
together so protecting training jobs does not hide an inference regression.
