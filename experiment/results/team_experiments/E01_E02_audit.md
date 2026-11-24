# E01/E02 Configuration Audit

**Audit branch:** `audit/e01-e02-paper-alignment`  
**Scope:** verify the retained E01 and E02 runs; no simulator was run and no simulator source was changed.

## Findings

| Field | E01 | E02 |
|---|---|---|
| Scheduler/policy | DeepBoot / `dp` | DeepBoot / `dp` in the matching E02 launcher and E02 commit title; executed invocation was not captured |
| Workload | `experiment/workload/small.csv`; 3,360 rows (160 training, 3,200 inference) | Same; all 3,360 names in `summary.json` match the workload |
| Cluster | 16 nodes × 4 GPUs (64 total) | 16 × 4 in the matching E02 launcher; runtime execution cannot be independently proven |
| AFE / AISS | 0 / 1 | 1 / 1; stated in the E02 commit title and launcher |
| ARYL | 0; simulator CLI default, not passed in launcher | 0 if the matching launcher was used; it does not pass `--ARYL` |
| Inference path | `INFER_SCHEDULER=1`, ATS-I with standard allocation, assuming CLI defaults in the recorded command | `INFER_SCHEDULER=1`, standard ATS-I allocation if launcher was used; invocation record absent |
| Other settings | interval 60 s; `REPAIR_TRAIN=1`; `random_allocate=0`; `interference=0`; priority 1; protect time 30 s; protect scale 1.0; CLI defaults | Same values follow from the matching launcher plus parser defaults, but are not runtime-verified |
| Result status | Exit 0; 3,360 JCT entries | Exit 0 recorded; 3,360 JCT entries; run tail contains normal `schedule over` completion |
| Reproducibility | Configuration and command are documented; exact result timing/log capture is imperfect | Configuration can be reconstructed from the matching launcher, but exact run command/environment invocation cannot be proven from retained artifacts |

The CSV registry records E02 values with an explicit qualifier rather than presenting the launcher configuration as proven runtime fact. The tracked launcher is evidence of intended settings, not a run-time argument capture.

## Commands and execution flow

E01's report records this command at `E01_deepboot_baseline/experiment_report.md` lines 107–115:

```bash
conda run -n pollux python simulator.py \
  --workload ./experiment/workload/small.csv \
  --AFE 0 --AISS 1 --log_file 0 \
  --output ./experiment/results/reproduction/deepboot-small-atsi-16x4 \
  --min-nodes 16 --num-gpus 4 --policy dp
```

The E01 shell launcher at `experiment/cmd/16node-4gpu/small/DeepBoot-small-ATSI.sh` lines 1–19 corroborates policy, workload, AFE/AISS, and cluster values. E01's report notes that the listed output directory was used for the result. Its runtime estimate came from filesystem timestamps, not `/usr/bin/time`; a full stdout/stderr log was not retained.

For E02, commit `d5894519bfe255d1cc5700c09c4ede470f4d4034` (the E02 experiment branch commit) includes `experiment/cmd/16node-4gpu/small/DeepBoot-small-ATSI_AFE.sh`. Lines 1–17 set `AFE=1`, `AISS=1`, `policy=dp`, `small`, 16 nodes, and 4 GPUs/node, then launch `simulator.py`. The E02 output commit's `commit.txt` records source commit `6772f554dd104d908328f63c9f5018089ac59432`, and its subject says DeepBoot/small/AISS on/AFE on. However, E02 has no `command.txt`; the 200-line `run_tail.log` is not a full invocation log and does not contain the original shell command. The matching launcher therefore supplies a repeatable intended command, not proof of the exact command actually invoked.

The simulator parser in `simulator.py` lines 1169–1237 accepts policy `dp` and defines defaults: 16 nodes, 4 GPUs/node, interval 60, ARYL=0, AISS=1, AFE=0, `INFER_SCHEDULER=1`, `REPAIR_TRAIN=1`, `protect_times=1.0`, `random_allocate=0`, priority=1, protect time=30, and interference=0. The E02 launcher overrides AFE to 1. `simulator.py` lines 418–460 constructs a `Cluster` and one job per workload row for DeepBoot; lines 946–952 calculate completed-job JCT as completion minus submission time. Lines 1004–1027 produce GPU counters. The parser's `INFER_SCHEDULER` help text and implementation describe its scheduler behavior; defaults alone do not prove a missing run flag was omitted.

## Actual retained metrics

Values below are extracted from retained `summary.json`, `analysis.json`, `gpu.log`, and runtime metadata. Mean and percentiles use the existing normalized-results definitions (training/inference split by `inference-` name prefix; P95 uses linear/type-7 interpolation).

| Metric | E01 | E02 | Evidence / caveat |
|---|---:|---:|---|
| Completed JCT entries | 3,360 | 3,360 | `summary.json`; equals small workload row count |
| Training / inference jobs | 160 / 3,200 | 160 / 3,200 | workload file and summary job names |
| Training mean JCT (s) | 2,442.58125 | 2,374.625 | `summary.json` |
| Training median JCT (s) | 984 | 956.5 | `summary.json` JCT values |
| Training P95 JCT (s) | 6,751.5 | 6,913.2 | linear/type-7 percentile of training JCT |
| Training max JCT (s) | 43,773 | 41,148 | `summary.json` |
| Inference mean JCT (s) | 7.835625 | 7.8084375 | `summary.json` |
| Overall mean JCT (s) | 123.775893 | 120.513988 | Includes inference jobs; dominated by their count |
| Mean allocated GPU utilization (%) | 94.42166 | 94.69164 | E02 analysis reports normalization against 64 GPUs; E02 dimensions are launcher-backed, not runtime verified |
| Mean real GPU utilization (%) | 83.45856 | 90.63412 | Same caveat for E02 denominator/configuration |
| Mean real-running GPU utilization (%) | 83.67769 | 90.87319 | Same caveat for E02 denominator/configuration |
| Simulation clock end (s) | 71,460 | 65,280 | GPU timeline/analysis simulated time; not wall time |
| Wall-clock runtime (s) | 2,069.55 | 1,313.2016817 | E01 timestamp interval estimate; E02 runtime file does not identify timing method |
| Goodput/speedup | unavailable | unavailable | Metric logs exist but are empty; do not interpret as zero |
| Failed jobs | unavailable | unavailable | Not emitted in these retained artifacts |

These one-run results are descriptive. E01/E02 do not establish a causal AFE effect: E02 invocation flags and runtime setup are not fully recorded, and neither run has repeated trials. E02's raw GPU counters and stored 64-GPU normalized percentages can be reported with this provenance caveat; avoid treating them as a fully verified matched-cluster comparison.

## Missing metadata and recovery attempts

| Missing/uncertain item | E01 | E02 | Recovery result |
|---|---|---|---|
| Original shell invocation | Report contains an exact command; checked against launcher | No command file; checked E02 commit tree, matching launcher, partial log and result artifacts | E01 recoverable from report. E02 exact runtime invocation unavailable; launcher is reproducible proxy only. |
| Full stdout/stderr | Missing | Only `run_tail.log` (partial) | Not recoverable from committed Git history or result files. |
| Cluster and policy values as executed | Exact command/report and launcher agree | Launcher says `dp`, 16×4; no invocation record | High confidence for E01; medium for E02. Do not present E02 as independently verified. |
| ARYL/inference scheduling flags | Not explicit in command; CLI defaults make 0/1 if omitted | Not explicit in launcher; same defaults if omitted | Defaults recovered from source; omission at runtime is not independently recorded for E02. |
| E02 timing method | N/A | Runtime value and timestamps exist; method absent | E02 `runtime.txt` records exit 0 and 1,313.2016817 seconds; `env.txt` records Python 3.8.10 and package pins. Exact timing wrapper cannot be recovered. |
| Team member/owner | Not recorded in experiment metadata | Not recorded in experiment metadata | UNKNOWN; no attribution inferred from commit author. |
| Failures/goodput | Not emitted/empty metric log | Not emitted/empty metric log | Unavailable, not zero. |

## Environment and provenance

- E01 report identifies source commit `cc85a24b346cfac17603cdfc9f5018089ac59432`, Conda environment `pollux`, Python 3.8.12, NumPy 1.21.4, pandas 1.3.2, pymoo 0.5.0, SciPy 1.7.2, and Matplotlib 3.4.3. These are values recorded in the E01 report, not independently recreated in this audit.
- E02 `commit.txt` records `6772f554dd104d908328f63c9f5018089ac59432`. `env.txt` records Python 3.8.10, NumPy 1.21.4, pandas 1.3.2, pymoo 0.5.0, SciPy 1.7.2, and Matplotlib 3.4.3 among the pinned packages.
- The E02 branch commit is `d5894519bfe255d1cc5700c09c4ede470f4d4034`; the result-artifact commit is `0671e57c3c8f32033bc8eccd9a02dd4990dff7ea`.
- Current audit branch was created from `main` at `f1f7ada`; no E01/E02 outputs were edited.

## Follow-up coordination

The current team investigation state is tracked separately in [`follow_up_tracking.csv`](follow_up_tracking.csv). The repository has an E01/E07 baseline-versus-random comparison already; this does not replace a teammate's requested matched investigation. No names or new findings were present in the repository at audit time, so owners remain UNKNOWN and the three investigations remain open.
