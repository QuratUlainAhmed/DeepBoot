# E02 configuration audit

## Executive summary

**E02 did run, according to the retained artifacts:** its recorded exit code is 0, it has 3,360 job results and 65,280 GPU samples ([analysis.json L27](../experiment/results/team_experiments/E02_deepboot_afe/analysis.json#L27)), and it has start/end timestamps on 2026-11-23. This is evidence of a completed run, though it does not establish who launched it.

The exact command was **not retained**, and the logs are only a 200-line tail. The strongest candidate is the repository's `DeepBoot-small-ATSI_AFE.sh` launcher at the source revision recorded with E02. That candidate describes `dp`, `small.csv`, 16 nodes × 4 GPUs, AFE=1, and AISS=1. The launcher is not proof that it was the command actually used. The output log independently confirms 16 nodes, a 60-second interval, and `INFER_SCHEDULER=1`; the result job names exactly match the 3,360 names in `small.csv`. The GPU count per node, AFE/AISS values, ARYL/random-allocation settings, and actual simulator output path are not all independently established.

**Recommendation:** do not use E02 as a verified, controlled AFE comparison against E01. Its numbers may be retained as provisional descriptive results with the unknowns disclosed. If the team needs a defensible paired comparison, run a new, clearly identified replicate with a saved command and fresh output path; do not overwrite or relabel E02. No simulator run was performed for this audit.

## Recovered command

No exact executed command was recovered from the logs, Git history, or accessible shell histories. If the candidate launcher was used unchanged, its expanded command would have been:

```sh
nohup python3 simulator.py \
  --workload ./experiment/workload/small.csv \
  --AFE 1 --AISS 1 --log_file 0 \
  --output ./experiment/out/16node-4gpu/small/dp-small-AISS_AFE \
  --min-nodes 16 --num-gpus 4 --policy dp \
  > /dev/null 2>&1 &
```

This is a **reconstruction, not a confirmed invocation**. The launcher has no explicit `--ARYL`, `--INFER_SCHEDULER`, `--random_allocate`, or `--interval` arguments; the candidate's effective values for those flags therefore depend on defaults in the recorded source version. The original process may also have been launched with a modified command or script.

## Configuration and confidence

| Parameter | Best finding | Level | Evidence and limits |
|---|---|---|---|
| Scheduler / policy | `dp` (DeepBoot) | **INFERRED — likely** | The candidate launcher sets `policy=dp` ([launcher L4](../experiment/cmd/16node-4gpu/small/DeepBoot-small-ATSI_AFE.sh#L4)) and passes it to the simulator ([launcher L17](../experiment/cmd/16node-4gpu/small/DeepBoot-small-ATSI_AFE.sh#L17)). The run tail does not identify the selected policy. |
| Workload file | `experiment/workload/small.csv` | **INFERRED — strong** | E02's [summary.json L1](../experiment/results/team_experiments/E02_deepboot_afe/summary.json#L1) contains 3,360 distinct job names; an exact name-set comparison against [`small.csv`](../experiment/workload/small.csv#L1) found no missing or extra names. The candidate launcher selects `small.csv` ([launcher L9](../experiment/cmd/16node-4gpu/small/DeepBoot-small-ATSI_AFE.sh#L9), [launcher L12](../experiment/cmd/16node-4gpu/small/DeepBoot-small-ATSI_AFE.sh#L12)). The original `--workload` argument itself is absent. |
| Number of nodes | 16 | **CONFIRMED in run log** | The retained tail records `schedule_cost_dict` with `nodes: 16` ([run_tail.log L12](../experiment/results/team_experiments/E02_deepboot_afe/run_tail.log#L12)). |
| GPUs per node | 4 | **INFERRED — likely** | The candidate launcher sets 4 ([launcher L8](../experiment/cmd/16node-4gpu/small/DeepBoot-small-ATSI_AFE.sh#L8)); the tail also records 64 GPUs in use ([run_tail.log L20](../experiment/results/team_experiments/E02_deepboot_afe/run_tail.log#L20)) while reporting 16 nodes. No retained command or startup metadata directly records `--num-gpus 4`. |
| AFE | `1` | **INFERRED — likely** | E02's candidate launcher explicitly sets `AFE=1` ([launcher L2](../experiment/cmd/16node-4gpu/small/DeepBoot-small-ATSI_AFE.sh#L2)). The results commit title and registry describe AFE as on, but no retained run log prints the value. |
| AISS | `1` | **INFERRED — likely** | Candidate launcher value ([launcher L3](../experiment/cmd/16node-4gpu/small/DeepBoot-small-ATSI_AFE.sh#L3)); also described as on in the registry. No retained run log directly prints the value. |
| ARYL | `0` | **INFERRED — likely** | The candidate launcher does not pass `--ARYL`; the simulator default at the recorded source revision is 0 ([simulator.py L1189](../simulator.py#L1189)). A different command could have overridden it. |
| Inference scheduler | `INFER_SCHEDULER=1` | **CONFIRMED in run log** | The tail prints `infer scheduler: 1` ([run_tail.log L8](../experiment/results/team_experiments/E02_deepboot_afe/run_tail.log#L8)). The source describes the default mode as ATS-I ([simulator.py L46](../simulator.py#L46)); the candidate launcher leaves this flag at its default. |
| Inference allocation policy | Most likely ATS-I; `random_allocate=0` | **INFERRED — likely** | The candidate launcher does not pass `--random_allocate`; the recorded source default is 0 ([simulator.py L1207](../simulator.py#L1207)). The retained tail does not show the startup value, and cannot exclude an override. |
| Scheduling interval | 60 seconds | **CONFIRMED in run log** | The tail repeatedly records `interval: 60` ([run_tail.log L6](../experiment/results/team_experiments/E02_deepboot_afe/run_tail.log#L6)). This also matches the source default ([simulator.py L1178](../simulator.py#L1178)). |
| Other candidate flags | `log_file=0`; defaults likely `infer_priority=1`, `protect_time=30`, `interference=0.0`, `REPAIR_TRAIN=1`, `protect_times=1.0`, `max_nodes=None` | **INFERRED** | These are the candidate launcher's explicit `log_file` setting or defaults in `simulator.py` at the recorded source revision ([simulator.py L1176](../simulator.py#L1176), [simulator.py L1180](../simulator.py#L1180), [simulator.py L1182](../simulator.py#L1182), [simulator.py L1184](../simulator.py#L1184), [simulator.py L1201](../simulator.py#L1201), [simulator.py L1204](../simulator.py#L1204), [simulator.py L1210](../simulator.py#L1210)). Their actual runtime values are not in the retained tail. |
| E02 archive directory | `experiment/results/team_experiments/E02_deepboot_afe/` | **CONFIRMED** | The directory contains the retained summary, logs, analysis, and timing records and was added in commit `0671e57` (“Add E02 AFE experiment results”). This is the archive location, not proof of the simulator's `--output` argument. |
| Simulator output directory | Candidate: `experiment/out/16node-4gpu/small/dp-small-AISS_AFE` | **INFERRED — unverified** | That path is assembled by the candidate launcher ([launcher L11](../experiment/cmd/16node-4gpu/small/DeepBoot-small-ATSI_AFE.sh#L11), [launcher L13](../experiment/cmd/16node-4gpu/small/DeepBoot-small-ATSI_AFE.sh#L13)). The actual command/output path was not retained. |
| Execution time | 2026-11-23 12:43:36.6816690 to 13:05:30.0860951, +05:00; recorded runtime 1,313.2016817 s; exit code 0 | **CONFIRMED as recorded metadata** | [start_time.txt L1](../experiment/results/team_experiments/E02_deepboot_afe/start_time.txt#L1), [end_time.txt L1](../experiment/results/team_experiments/E02_deepboot_afe/end_time.txt#L1), and [runtime.txt L1](../experiment/results/team_experiments/E02_deepboot_afe/runtime.txt#L1). |
| Python environment | Python 3.8.10 | **CONFIRMED as recorded environment metadata** | [env.txt L1](../experiment/results/team_experiments/E02_deepboot_afe/env.txt#L1). No environment name or complete machine specification was recovered. |
| Source version | `6772f554dd104d908328f63e4ab719184c6ff4d3` | **CONFIRMED as recorded metadata** | [commit.txt L1](../experiment/results/team_experiments/E02_deepboot_afe/commit.txt#L1) records this hash. It resolves to `Add preliminary DeepBoot baseline experiment` (2026-11-22); the candidate launcher at that revision matches the current launcher. The run's branch name is **UNKNOWN**. |

## Evidence review

### Script, Git history, branches, and defaults

- The candidate script is [`DeepBoot-small-ATSI_AFE.sh`](../experiment/cmd/16node-4gpu/small/DeepBoot-small-ATSI_AFE.sh#L1). At source revision `6772f554dd104d908328f63e4ab719184c6ff4d3`, it selects AFE=1, AISS=1, `dp`, 16 nodes, 4 GPUs per node, and the small workload. Its output path is under `experiment/out/16node-4gpu/small/`.
- The E02 artifacts were added to Git by `0671e57` on 2026-11-23. That commit packages result files; it is not the run command. E02's `commit.txt` records the separate source revision `6772f554dd104d908328f63e4ab719184c6ff4d3`.
- The recorded source revision has the defaults cited above. Defaults explain what would happen if the candidate script was run unchanged; they do not prove that it was.
- Before this audit branch was created, the local repository had only `main` and `origin/main`; no E02-specific branch was available. Launcher history shows the candidate existed by the original simulator commit and remained unchanged at the recorded E02 revision. No alternate E02 launcher version or execution record was found.

### Logs, result files, and shell history

- E02 retains `summary.json`, `analysis.json`, `gpu.log`, `jobinfo.log`, `metric.log`, timing/environment files, and `run_tail.log`. The summary covers 3,360 jobs (160 training, 3,200 inference); the job-name set matches `small.csv`. The retained `run_tail.log` is only 200 lines and shows late-run state, including interval 60, inference scheduler 1, 16 nodes, and 64 GPUs in use. It does not show the startup command or all startup flags.
- The accessible PowerShell history has a generic `bash experiment/cmd/16node-4gpu/small/xxx.sh` entry, not an E02 command or the candidate script name. Its other matching simulator commands use AFE=0 and a different output path, so they cannot identify E02. The accessible Git Bash history contains no E02 launch command.
- The result registry itself marks E02's exact command, node/GPU configuration, and inference mode as unknown ([experiment_registry.csv L3](../experiment/results/team_experiments/experiment_registry.csv#L3)). It notes that the result has 3,360 jobs and that the GPU percentage normalization used 64 GPUs, without independently documenting the cluster shape.

## E07 folder requested for inspection

[`E07_DeepBoot-small-ATSI_RANDOM`](../experiment/results/team_experiments/E07_DeepBoot-small-ATSI_RANDOM) has a preserved command and run metadata, but it is a separate experiment and must not be used to fill E02's gaps. Its command explicitly uses AFE=0 and `--random_allocate 1`, and writes to `experiment/results/reproduction/DeepBoot-small-ATSI_RANDOM/simulator-output` ([command.txt L1](../experiment/results/team_experiments/E07_DeepBoot-small-ATSI_RANDOM/command.txt#L1)). Its metadata records a 2026-11-22 run at source commit `cc85a24b346cfac17603cdfc9f5018089ac59432` ([run-metadata.json L3](../experiment/results/team_experiments/E07_DeepBoot-small-ATSI_RANDOM/run-metadata.json#L3), [run-metadata.json L9](../experiment/results/team_experiments/E07_DeepBoot-small-ATSI_RANDOM/run-metadata.json#L9)). These settings differ from E02's likely AFE-on configuration. E07 is useful as an independently documented run, not as evidence of E02's command.

## Conflicts, remaining unknowns, and comparison decision

1. The E02 folder name, commit title, registry description, and candidate launcher suggest an AFE-on `dp` experiment. Only the title/registry and candidate launcher support AFE=1; the saved run log does not independently confirm it.
2. The candidate launcher suggests a 16×4 cluster and ATS-I-style inference scheduling, while the registry correctly leaves the E02 node/GPU shape and inference mode unknown. The tail confirms 16 nodes, interval 60, and `INFER_SCHEDULER=1`, but it does not establish GPUs per node, ARYL, or random-allocation overrides.
3. E07's explicit `random_allocate=1`, AFE=0 command is not compatible with the likely E02 setup. The shared `small.csv` workload and similar names do not make E07 a substitute.
4. The actual E02 invocation, actual simulator output path, run branch, and runtime values for flags absent from the tail remain **UNKNOWN**.

**Can E02 safely be used in the comparison report?** Not as a verified, controlled AFE-on counterpart to E01. The results can be reported provisionally as an archived run with the above caveats, but the AFE effect should not be attributed to this run until its effective configuration is established. The recorded result is evidence of a completed simulation, so a rerun is not needed merely to establish that results exist. A fresh replicate is necessary only if the comparison requires verified matching settings and the missing invocation cannot be recovered; preserve E02 and use a new unique output directory.

## Team message

E02 has saved results and a recorded successful run on 2026-11-23, so it was not simply an unrun folder. Its recorded source commit is `6772f554`, and the best-matching launcher points to a small-workload `dp`, AFE=1/AISS=1 run. However, the exact command and simulator output path are missing; only 16 nodes, 60-second scheduling, and `INFER_SCHEDULER=1` are confirmed by the partial log. E07 is a different AFE-off random-allocation run and cannot validate E02. Keep E02 as provisional descriptive data, not a controlled AFE comparison; if we need a defensible paired result, run a new replicate to a fresh folder and save the exact command/metadata. No rerun was done.
