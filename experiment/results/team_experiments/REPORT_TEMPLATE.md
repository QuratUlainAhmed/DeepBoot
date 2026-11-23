# <EXPERIMENT_ID> — <Experiment title>

## Experiment ID/title

- **ID:** <ID>
- **Title:** <short descriptive title>
- **Status:** planned / running / completed / failed
- **Assigned team member:** <name or UNKNOWN>

## Objective

<Why is this experiment being run?>

## Research question

<One question the measurements can answer.>

## Hypothesis

<Expected result and rationale.>

## Configuration

| Parameter | Value | Evidence/source |
|---|---|---|
| Scheduler | | |
| Policy | | |
| Workload file and scale | | |
| Training jobs | | |
| Inference requests | | |
| Nodes | | |
| GPUs per node | | |
| AFE | | |
| AISS | | |
| Inference scheduling mode (`ARYL`, `INFER_SCHEDULER`, `random_allocate`) | | |
| Scheduling interval | | |
| Other relevant arguments/defaults | | |

## Environment

- OS/platform:
- Python/environment:
- Relevant dependency versions:
- Hardware or simulator resource assumptions:

## Git commit

- Branch:
- Source commit hash:
- Source changes made for this run: none / describe precisely

## Methodology

<Trace the execution path, job classification, and metric definitions. State whether this is a paired/controlled comparison and why.>

## Exact execution command

```text
<paste the exact command, including flags and output path>
```

## Runtime

| Item | Value | Evidence |
|---|---|---|
| Start/end time and timezone | | |
| Wall-clock runtime | | |
| Measurement method (`/usr/bin/time`, etc.) | | |
| Exit status | | |
| Simulated duration/horizon | | |

## Logs

- Full stdout/stderr path:
- `summary.json` path:
- `jobinfo.log` path:
- `gpu.log` path:
- `metric.log` path:
- Other output paths:
- Missing or truncated logs:

## Results

Report actual values with units and sample counts. Split training and inference JCTs. Use the project comparison framework's consistent definitions. Leave unavailable metrics blank or state “unavailable”; never substitute zero.

| Metric | Training | Inference | All jobs | Unit/source |
|---|---:|---:|---:|---|
| Completed jobs | | | | |
| Mean JCT | | | | |
| Median JCT | | | | |
| P95 JCT | | | | |
| Maximum JCT | | | | |

| GPU metric | Result | Unit/source |
|---|---:|---|
| Allocated GPU utilization mean | | |
| Real GPU utilization mean | | |
| Running GPU utilization mean | | |
| Throughput/goodput | | |
| Failed jobs (only if simulator emits this) | | |

## Interpretation

<Explain observed numerical patterns. Distinguish direct observations from explanations.>

## Limitations

<Configuration mismatches, model assumptions, missing metrics/logs, missing repeats, and other threats to validity.>

## Conclusion

<Answer the research question only to the extent supported by the results.>

## Reproducibility

1. <Check out the source commit and set up the environment.>
2. <Use the exact workload and confirm required traces.>
3. <Create a fresh output directory; do not overwrite existing outputs.>
4. <Run the exact command and record full logs/runtime.>
5. <Run analysis from the generated files and document metric definitions.>

## Generated files

| File | Purpose | Complete/preserved? |
|---|---|---|
| | | |
