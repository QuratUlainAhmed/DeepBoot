# Team experiment tracking

## Files

- `experiment_registry.csv` records verified configuration and run status.
- `master_results.csv` contains normalized outcomes and source-file columns for each metric.
- `update_tracking.py` rebuilds both CSVs from the recorded outputs without invoking the simulator.
- `REPORT_TEMPLATE.md` is the shared report skeleton.
- `../../../docs/experiment_comparison.md` summarizes the current results and comparability limits.
- `plots/` contains charts generated from the master CSV.

## Updating the framework

1. Keep the raw outputs in a new, unique experiment folder. Preserve the exact command, source commit, runtime metadata, and stdout/stderr.
2. Verify configuration from the executed command, launcher, or output metadata. Mark unknown fields `UNKNOWN`; do not infer them from a folder or script filename.
3. Add the completed run's verified metadata to `EXPERIMENTS` in `update_tracking.py`. For new output formats, update the extraction logic explicitly and document any definition changes.
4. Run `python experiment/results/team_experiments/update_tracking.py` to regenerate the registry/results tables.
5. Regenerate plots with `conda run -n pollux python experiment/results/team_experiments/plots/generate_plots.py` and update `docs/experiment_comparison.md` using the report template.

Add a `planned` row only after the team has assigned an experiment ID, configuration, and owner. Launcher scripts are candidate configurations, not proof of a planned or completed run. The current inventory has no additional pending assignment recorded.

## Metric definitions

- A job's JCT is `completion_time - submission_time` from the simulator. Training jobs are rows whose job name does not start with `inference-`; for `job-metrics.csv`, use its `class` field.
- Median and P95 use the linear/type-7 percentile method (the default NumPy `percentile` convention). Overall mean includes both training and inference jobs and must not be substituted for training mean.
- GPU means are percentages of the 64 modeled GPUs: `gpu_use`, `real_gpu_use`, and `real_running_gpu_use`, each averaged across one-second simulation samples and divided by 64. They are simulator counters, not physical GPU telemetry. E02's stored percentage uses a 64-GPU denominator, but its actual node/GPU configuration was not independently recorded; treat it cautiously.
- Simulation duration is the final simulator clock/sample count, not wall runtime. Wall runtime is copied from run metadata or the report and its measurement method is noted per row.
- The simulator does not emit a failed-job count in these outputs. The master CSV leaves that value blank. Goodput/throughput arrays are empty in the available `metric.log`/analysis outputs and are therefore blank, not zero.
- `master_results.csv` cites source files per metric. E05–E07 retain per-job CSV and derived analysis summaries but not the raw simulator `summary.json`/`gpu.log` in their team folders; E01–E04 preserve those raw files.
