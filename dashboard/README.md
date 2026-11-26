# DeepBoot Interactive Scheduling Simulator

A Streamlit front-end that drives the **unmodified** DeepBoot research simulator
(`simulator.py`, `dp.py`, `infer_scheduler.py`, …) one scheduling step at a time.
It visualises what the simulator actually decides. Nothing is re-implemented.

## Run

```bash
# one-time: separate environment (the research `pollux` env is not touched)
mamba create -n deepboot-dash python=3.8.12 pip
~/miniforge3/envs/deepboot-dash/bin/python -m pip install -r dashboard/requirements-dashboard.txt

# launch (from anywhere; the script cd's to the repo root)
bash dashboard/run.sh                 # http://localhost:8501
bash dashboard/run.sh --server.port 8517
```

The default scenario is a **reduced `small.csv`**. It contains real rows only: the first 8 training jobs
(ImageNet excluded, since those jobs take about 10 h) and every inference request arriving in the first 1,800 s. It finishes in
about 2,500 simulated s and about 15–20 s of wall time. Choose a full trace on the Home page and use
**Run until… → Until all jobs complete** on the Interactive Simulation page. A full small trace takes
about 11–35 min of wall time, as the original CLI does.

## Pages

| Page | What it shows | Data source |
|---|---|---|
| Home (`app.py`) | Component diagram, simulation setup (policy and flags as CLI options), equivalent CLI command, caveats | — |
| 1 Cluster Overview | 16×4 GPU grid (live or replay), worker drill-down, per-job allocation | prototype run snapshots |
| 2 Job Management | Submit training/inference jobs (only fields the simulator reads), queue and status tables | prototype run |
| 3 Interactive Simulation | Start/Pause/Resume/Next step/Reset, speed, Run until, narration of each step, event log and timeline | prototype run |
| 4 ATS & AFE | ATS-T knapsack inputs/outputs, ATS-I branch and reclaim search, AFE delay model vs paper Table I, AISS pod lifecycle | instrumentation records |
| 5 Performance Analytics | JCT, latency, GPU %, allocation over time, restarts, rescale overhead, queue wait, scheduler overhead, makespan | prototype run **or** any repository experiment |
| 6 Experiment Comparison | E01–E07, E08-rerun, AISS-0/1, ATS-I vs RANDOM seeds; paper Fig. 9/11b/14 overlays; existing plots | raw result files + paper figure readings |

Every result carries a provenance badge: **Paper (approx.)**, **Repository experiment** or
**Prototype run**. Paper-only mechanisms (for example AFE's Redis sync) are labelled
"Paper-described, not implemented".

## Architecture

```
dashboard/
  app.py, pages/1..6_*.py        Streamlit UI
  engine/
    sim_bridge.py                imports the research code; sets its module globals exactly as
                                 simulator.py's __main__ does; builds policy + Cluster exactly as simulate()
    simulation_controller.py     advance_second() = one iteration of simulate()'s loop (verbatim);
                                 next_event / run_until / inject / reset; event log + snapshots
    instrumentation.py           read-only wrappers around ATS-T / ATS-I / RANDOM methods
    workload_manager.py          real-row reduced scenarios; job injection mirroring Cluster.__init__
    state_manager.py             one server-wide simulation (st.cache_resource) + per-session UI state
  components/                    GPU grid, Plotly charts, Graphviz diagrams, narration, theme
  data/experiment_loader.py      loads team results from experiment/results (read-only)
  data/paper_reference.py        paper figure values (approximate, labelled)
  tests/                         pytest suite (see Validation)
```

### Integration points (how the dashboard talks to the simulator)

1. **Configuration.** `sim_bridge.apply_globals()` assigns `simulator.AISS/AFE/ARYL/INFER_SCHEDULER/
   REPAIR_TRAIN/RANDOM_ALLOCATE/PROTECT_TIMES/NUM_NODE/args`. This is necessary because these are module globals
   set only under `__main__`, and the import-time defaults differ from the CLI (e.g. `ARYL=True` on import, `0` on the CLI).
   The flags are re-applied before every mutation.
2. **Stepping.** `SimulationController.advance_second()` copies one iteration of the loop in
   `simulate()` (simulator.py 1095–1150): clock +1, GPU counters, `update_infer_pod_status()`,
   `event_update()`, `Cluster.step()`.
3. **Observation.** The controller diffs `cluster.allocations`, `infer_pod_status`, `finish_job_set` and
   job fields around each step. It never writes them.
4. **Decision internals.** `instrumentation.install()` wraps `DeepBoot.allocate_elastic`,
   `DeepBoot.max_value_dp`, `InferScheduler.ATSI_infer_schedule`, `_schedule_empty_or_sleep_gpu`,
   `_schedule_training_gpu` (and their Aryl variants), `_get_job_speedups` and `random_allocate`. Each wrapper
   calls the original with the original arguments and returns its result unchanged.
5. **Job submission.** `workload_manager.inject_job()` builds the `Job` with the same constructor arguments
   `Cluster.__init__` uses for the active policy, and registers it in `jobs`, `job_dict` and `submit_time`.
   This is equivalent to appending the row to the workload CSV. Only future arrivals are accepted.

### Modifications to existing research files

**None.** No file outside `dashboard/` was changed (`git status` shows only `dashboard/`). The wrappers
are installed at runtime inside the dashboard process only. The CLI, the `experiment/cmd` scripts and
the `pollux` environment are untouched. Outputs under `experiment/` are only read.

## Validation

`PYTHONHASHSEED=11 ~/miniforge3/envs/deepboot-dash/bin/python -m pytest dashboard/tests -q`
→ **23 passed, 1 xfailed** (about 3.5 min).

| Test | What it proves |
|---|---|
| `test_equivalence` × 7 | For dp ATS-I AFE 0/1, AISS 0, RANDOM, ARYL, protect×2 and AFS: the instrumented controller produces **identical** `summary.json` JCTs and `gpu.log` to the unmodified `python simulator.py`, run in the original `pollux` env. |
| AFS case (xfail) | On the tiny test scenario the **unmodified CLI itself crashes** (assertion in `applications.get_throughput`). The controller raises the same exception type, and the UI shows it with a traceback and blocks further stepping. |
| `test_injected_job_equals_csv_row` | A training or inference job submitted mid-run gives identical results to the same row in the CSV. |
| `test_reset…` | Reset restores t=0 and removes injected jobs; a replay is identical. |
| `test_instrumentation_matches_actual_allocations` | Recorded knapsack choices equal the GPU counts actually applied. Reclaimed jobs exist. |
| `test_snapshots_never_overcommit` | No worker ever shows more than 4 GPUs; the breakdown sums match. |
| `test_experiment_loader…` | Loaders reproduce the verified report values (E01 2,442.58 s, E08-rerun 2,348.03 s, AISS-0 10.78 s, E05 GPU source fallback). |
| `test_pages` | Every page renders headless without exceptions. *Next step* advances the real simulator. A training submission reaches `Cluster.jobs`. |

Manual check in Chrome: Home, Cluster Overview, Interactive Simulation (playback), ATS & AFE
and Experiment Comparison rendered and updated from live simulator state.

## Known limitations

- **One simulation per server.** The research flags are process-wide globals; a lock serialises access.
- **No GPU identity in the simulator.** Per-worker counts are exact. Slot order in the grid is illustrative.
- **Playback** replays snapshots of states that were actually reached; it does not interpolate. Snapshots are capped at 20,000.
- **Scheduler wall time** is measured on this machine and, as in the original code, is **not** part of simulated time.
- **Unavailable metrics:** throughput/goodput (collection disabled in `simulate()`, `metric.log` empty). Queue wait for
  repository runs (start times not retained). GPU time series for E05–E07 (raw `gpu.log` not retained).
- **Pollux** (NSGA-II) is unseeded and takes about 1 s per decision. When selected, `REPAIR_TRAIN=0` is used to mirror E05.
- **AFE** is modelled only as a delay. The paper's synchronisation steps are shown as paper-only.
- Paper values are read from figures (±≈0.02 h). See `docs/DEEPBOOT_PAPER_AND_EXPERIMENT_COMPARISON.md` for all caveats.
