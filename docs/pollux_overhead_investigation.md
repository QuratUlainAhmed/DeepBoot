# Pollux optimization-time investigation

Branch: `investigation/pollux-overhead`. Date: 2026-11-24.
Status: code trace and comparison with E01/E02/E03 complete. E05's raw per-call data is not in the repo, so some questions stay open (section 7). No simulator code was changed and no experiment was rerun.

## 1. The anomaly

E05 (Pollux, small workload, `--INFER_SCHEDULER 0`) reports 7,263 optimizer decisions averaging 0.997 s, with P95 1.253 s, max 2,335.784 s and a sum of 7,241.665 s, against a whole-run wall time of 8,424.1 s (86%; `experiment_report.md` line 59 and `run-metadata.json` line 5 `runtime_seconds`; from the start and end timestamps in `run-metadata.json`, 2026-11-22 19:35:22 to 21:55:46 +05:00, so any machine suspend would be included). Sources: `E05_Pollux-small-ATSI/experiment_report.md` lines 7 and 117; `analysis-summary.json` (optimization block starts at line 153). `docs/experiment_comparison.md` lines 101, 138 and 143 call this notable and recommend investigating it with per-decision data.

E05's actual command (`E05_Pollux-small-ATSI/command.txt`): `--policy pollux --workload experiment/workload/small.csv --AFE 0 --AISS 1 --log_file 0 --INFER_SCHEDULER 0 --min-nodes 16 --REPAIR_TRAIN 0 --num-gpus 4`, with no `--interval`, so the default 60 s applies (`simulator.py` line 1178; E05 report line 33). It ran on `C:\Users\HP` (conda env `pollux`) at commit `cc85a24`.

## 2. Exact metric

- Wall-clock `time.time()` before and after the scheduling-policy call: `simulator.py` lines 616 (`t1`) and 649 (`t2`). `optimize_time = round(t2 - t1, 3)` at line 651, so values have 1 ms resolution.
- It times only the policy call. Autoscaling, `job.step` and the rest of the loop are outside it.
- Each call appends `(clock, states.shape, optimize_time)` to `optimize_history` (line 684, `states.shape = (num_jobs, num_nodes)`). It is written to `jobinfo.log` via `current_log` (line 711). Each call also logs `optimize time` (line 669), and a second per-call record goes into the in-memory `schedule_cost_dict` (lines 656-661; whether it is written out was not checked).
- It is a per-call value. Means, P95 and sums are computed afterwards by analysis scripts, not by the simulator.
- Because it is wall-clock, a machine suspend or stall during a call would be counted as optimizer time.

## 3. Code path

1. `Simulator.step(seconds, interval)` (`simulator.py` line 566) calls the policy between lines 616 and 649. `interval` is `args.interval` (line 1131).
2. If `INFER_SCHEDULER` is true (default 1, line 1198), the full `policy.optimize` runs only when `self.clock % interval == 0` (lines 619-628). All other events go to `infer_scheduler.optimize` (lines 630-637).
3. If `INFER_SCHEDULER` is false (E05), `policy.optimize` runs on every call (lines 639-647). Inference scheduling therefore happens inside the timed Pollux call: `pollux.py` defines `_sleep_alloc_update` (line 132) and `_infer_alloc_update` (line 160), which touch `problem.infer_pods`. Both are cheap loops over `base_alloc` that re-apply existing inference and sleep-pod allocations (lines 132-166); they are not part of the NSGA-II search itself. Inference jobs enter the search through the decision vector instead (item 6).
4. Which events call `step` is decided by `event_update` (`simulator.py` line 1029, called at line 1120, where `continue` skips the step when it returns False). Its first case fires on `clock % interval == 0` (lines 1030-1033). Case 2 (line 1037, logged as `case2 job finish`) fires when `submit_time[clock] > 0`. `submit_time` is filled with each job's submission time (line 500) and with inference jobs' `evaluate_finish_time` (lines 226 and 702-703), so this case fires at submissions and inference finishes, not only at training completion; the log label is misleading. Case 3 fires when an inference job has been submitted but has no placement and some inference pod is `SLEEP`, or `PROTECT` for a waiting app. With 3,200 inference rows in `small.csv`, submissions plausibly explain most of the roughly 6,100 non-tick events (not verified).
5. `PolluxPolicy.optimize` (`pollux.py` line 168) builds a `Problem` (line 235) and runs NSGA-II (`NSGA2` at line 257, `pop_size=my_pop_size=50` at line 35, `("n_gen", my_pop_size)` at line 265): 50 generations of 50 candidates, about 2,500 evaluations per call.
6. `simulator.py` line 1081 sets `policy.sched_train = INFER_SCHEDULER`. In `pollux.py` lines 251-255, with `sched_train` false the initial population is sampled over all jobs (inference pods included), not just training rows; lines 268-269 reshape the result accordingly. In `Problem.__init__`, the training-only filter (`pollux.py` lines 380-388) runs only when `sched_train` is true, and `n_var = self._base_state.size` (line 458). So in E05 the decision vector covers all jobs (training, inference and sleep pods) x nodes, while with `INFER_SCHEDULER=1` it covers training jobs only. Lines 614-617 also add sleep and inference terms to the objective when `sched_train` is false. Inference scheduling is therefore part of the timed Pollux call in E05. The actual vector size per call depends on the job count and was not measured. Note also that `simulator.py` line 1079 sends any unrecognized `--policy` value to Pollux; the default is `dp` (line 1172).
7. Naming caveat: the `--INFER_SCHEDULER` help string (lines 1198-1199) says 1 means using Pollux for inference, which contradicts the code and the comment at line 46. This report follows the code.
8. `Pollux-small-ATSI.sh` sets `policy=pollux` but its simulator command does not pass `--policy`, so run as committed it would run the default policy `dp` (`--policy` default, `simulator.py` line 1172), not Pollux. E05's `command.txt` does pass `--policy pollux`, and its other flags match the script. The script sends console output to `./logs/Pollux-small-AISS_worepair.log`, but E05 was launched directly with `python -u` (no log redirect in `command.txt`) and wrote to `experiment\results\reproduction\Pollux-small-ATSI\simulator-output`, so that log probably does not exist.

## 4. Comparison with other runs

Per-call data exists only for E01 (DeepBoot `dp`), E02 (DeepBoot `dp`, AFE on) and E03 (AFS, `ARYL=1`). E04, E06 and E07 have no `jobinfo.log` in the repo. Calls are split by `clock % 60 == 0` (full policy) vs other events (inference scheduler), following lines 619-637. This table is generated from the `optimize_history` in each run's `jobinfo.log`; the E05 row comes from its report, since E05's raw data is not retained.


| Run | Path | Calls | Mean (s) | P95 (s) | Max (s) | Sum (s) |
|---|---|---|---|---|---|---|
| E01 | all calls | 7306 | 0.0286 | 0.164 | 0.411 | 209.1 |
| E01 | full policy (clock%60==0) | 1191 | 0.1414 | 0.234 | 0.411 | 168.4 |
| E01 | other events (inference scheduler) | 6115 | 0.0067 | 0.017 | 0.142 | 40.7 |
| E02 | all calls | 7202 | 0.0209 | 0.138 | 0.262 | 150.2 |
| E02 | full policy (clock%60==0) | 1088 | 0.1127 | 0.185 | 0.262 | 122.6 |
| E02 | other events (inference scheduler) | 6114 | 0.0045 | 0.012 | 0.047 | 27.6 |
| E03 | all calls | 7487 | 0.0064 | 0.016 | 1.345 | 47.9 |
| E03 | full policy (clock%60==0) | 1374 | 0.0135 | 0.031 | 1.345 | 18.6 |
| E03 | other events (inference scheduler) | 6113 | 0.0048 | 0.012 | 0.148 | 29.3 |
| E05 | Pollux, every event (from its report) | 7263 | 0.997 | 1.253 | 2335.784 | 7241.665 |

Observations (arithmetic from the table and the reports):

- E01 has 1,191 full-policy calls. That equals its last clock 71,460 divided by 60. E02 has 1,088, which is 65,280 divided by 60. DeepBoot runs the full policy once per 60 s tick and the cheap scheduler otherwise.
- E05 ended at 70,500 s, i.e. 1,175 ticks. If it also had one call per tick, about 6,088 of its 7,263 calls fell on non-interval events. Under `INFER_SCHEDULER=1` those events use the cheap scheduler, but E05 runs the full NSGA-II on them. This is inferred, since E05's per-call data is not retained.
- E05 vs E01 full-policy calls: 7,263 / 1,191 = 6.1x more calls; mean 0.997 / 0.1414 = 7.05x per call (4.8x if the one 2,335.8 s call is removed: 4,905.9 s over 7,262 calls is about 0.68 s). The two factors multiply to about 43x on the sum (7,241.7 / 168.4).
- In E01, full-policy cost rises with the number of jobs in the call: about 0.062 s at 3 jobs, 0.138 s at 10, 0.192 s at 20, 0.306 s at 26 (the trend is noisy in E02).
- Share of wall time: E01 209.1 s of about 2,069.6 s (about 10%; its runtime is a timestamp estimate); E02 150.2 s of 1,313.2 s (about 11%); E05 7,241.7 s of 8,424.1 s (86%). Time outside the timed call is about 1,182 s for E05 and about 1,163 s for E02. That is suggestive only, because the machines and timers differ.

Not an apples-to-apples comparison:

- Different algorithms (NSGA-II vs `dp` vs AFS), and different call frequency (every event vs once per 60 s tick).
- E05 uses `--REPAIR_TRAIN 0` and `INFER_SCHEDULER=0`; E01 uses the defaults (`REPAIR_TRAIN` 1, `INFER_SCHEDULER` 1). E03 uses `ARYL=1`.
- Different machine for E05 (`C:\Users\HP`). E02 ran on Windows with Python 3.8.10. The hardware of E01 and E03 is not recorded.
- Commits: E01 and E05 `cc85a24`; E02 and E03 `6772f55` (`experiment_registry.csv`).

## 5. Explanations, ranked by evidence

1. **Confirmed by code; E05's call split inferred: E05 runs the full optimizer on every event.** Lines 639-647 vs 619-637; the 1,191 = 71,460/60 and 1,088 = 65,280/60 counts. Total calls are similar across runs (E01 7,306; E02 7,202; E03 7,487; E05 7,263), and the non-tick calls in E01, E02 and E03 are almost identical (6,115, 6,114, 6,113), so the event counts look comparable. E01, E02 and E03 send only the tick events to the full policy, while E05 sends all of them. This accounts for about 6x of the total gap.
2. **Confirmed by code, magnitude from data: NSGA-II is heavier per call.** 50 x 50 evaluations per call (`pollux.py` lines 35 and 265). Measured about 0.68 s (excluding the outlier) vs 0.14 s for dp: about 4.8x to 7x.
3. **Confirmed by code, size not measured: the decision vector is larger in E05.** `pollux.py` lines 251-255 and 268-269 (`sched_train` false). `Problem.__init__` (lines 380-388, 458) confirms it: all jobs x nodes instead of training jobs x nodes. Its per-call effect on cost is not measured.
4. **Hypothesis: the 2,335.8 s call is a stall, not computation.** It is about 5,700 times E01's maximum and about 1,900 times E05's own P95, and the timer is wall-clock. It cannot be located without E05's raw data. Without it the sum would be 4,905.9 s.
5. **Hypothesis: machine and configuration differences** (hardware, `REPAIR_TRAIN`) add to E05's cost. Unmeasured.

## 6. Is the anomaly genuine and comparable?

- Genuine: Pollux's per-call cost is clearly higher than DeepBoot's dp, even without the outlier, and its total optimizer time is large.
- Not comparable as reported: "86% of wall time" and "unusually expensive" combine call frequency, algorithm cost, a possible stall and different hardware. The headline figure depends on the single outlier.

## 7. Unknowns

- When and why the 2,335.8 s call happened (needs E05's raw `jobinfo.log` or console log, which was never pushed; line 669 logs every call's `optimize time`).
- Pollux's per-call cost as a function of job count.
- Total cost of Pollux with `INFER_SCHEDULER=1` (full optimizer only on ticks).
- Machine specs for E01, E03 and E05; the effect of `REPAIR_TRAIN` on Pollux (the flag does reach Pollux: `simulator.py` line 1082 sets `policy.repair_train` and `pollux.py` line 245 copies it into the `Problem`, overriding the default `True` at line 342; whether `dp.py` reads it was not checked, so its effect on E01 is unknown).
- How the roughly 6,100 non-tick events split between case 2 and case 3 of `event_update` (`simulator.py` lines 1029-1062). The triggers are traced in section 3, but the events were not counted by case.
- Which command produced E05 (the committed script omits `--policy`, `command.txt` includes it), and whether the `simulator-output` folder named in E05 `command.txt` (it should hold `jobinfo.log`) or any console log still exists on the machine that ran it. Line 669 logs every call's `optimize time` to the console.

## 8. Recommended next step

1. Ask the person who ran E05 (machine `C:\Users\HP`) for `experiment\results\reproduction\Pollux-small-ATSI\simulator-output\jobinfo.log`. It was read by `analyze_results.py` but never pushed, and holds the per-call `optimize_history`. With it we can place the 2,335.8 s call and compute cost vs job count without any new run.
2. The two code questions (`Problem.__init__` and `event_update`) are now traced in sections 3 and 5. What remains is counting the non-tick events by trigger case, which also needs the per-call log.
3. If the data stays unavailable, propose a minimal profiling run for team approval: Pollux, small workload, otherwise identical to E05 but `INFER_SCHEDULER=1`, recording `time.process_time()` beside wall time. It would write to a fresh output folder and change no existing results.

## 9. Research direction

Plausibly yes. E05's report (line 117) says the overhead is consistent with the paper's concern about NSGA-II cost at scale; this has not been checked against the paper and should be before it is cited. A controlled test would match `INFER_SCHEDULER`, machine and interval, and vary workload size (small vs middle).
