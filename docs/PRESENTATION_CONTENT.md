# DeepBoot Reproduction & Extension: Presentation Content

Slide-by-slide content. Bullets are for the slides. "Presenter notes" hold the explanation. All numbers trace to `docs/DEEPBOOT_PAPER_AND_EXPERIMENT_COMPARISON.md` (cited as **Report §x**). Paper values marked ≈ were read from figures.

---

## Project overview (for slide 1 / abstract)
We reproduced and audited **DeepBoot** (IEEE TPDS 2023), a GPU-cluster scheduler that lends idle inference GPUs to elastic training jobs. Using the authors' simulator, our verified DeepBoot run reproduces the paper's small-workload training JCT (0.652 h vs ≈0.66 h) and makespan (18.1 h vs ≈18 h). Three controlled studies show:
- protecting warm inference pods cuts inference latency by 27%;
- the paper's GPU-level inference allocation beats the repository's "random" path by 5% in training JCT;
- Pollux's genetic optimizer is far slower per decision, but the simulator never charges that time.

We propose a restart-cost-aware training scheduler as our extension.

## Our research contribution (one paragraph)
We contribute three things:
1. An evidence-graded reproduction audit: every reported metric was recomputed from raw outputs, and paper values come from figures.
2. Two controlled ablations the paper does not report directly: AISS warm-pod reuse with its effect on inference latency, and ATS-I vs the implemented RANDOM path with matched hash seeds.
3. Identification of two implementation-level limitations, each with direct evidence. First, the training scheduler applies a constant 10-s restart penalty to every job, while ImageNet jobs restart about 200+ times each. Second, the simulator does not model scheduling latency.

The extension (R1) is **proposed, not yet implemented or evaluated**.

## Caveats to state during the talk
- Simulator results only: GPU utilisation figures are simulated counters, not hardware telemetry.
- Paper numbers come from reading figures (±≈0.02 h). The paper gives no data tables for the simulator.
- Most configurations ran once. Determinism is proven only for DeepBoot + ATS-I with AFE off.
- The paper's headline "38% vs baseline" is **not yet tested**: the baseline was not run.
- The workload files contain 2× the paper's stated inference ratio.
- E02 cannot be verified, and its rerun (E08) gives a different result.

---

### Slide 1: DeepBoot: Reproducing and Extending a Training-Inference GPU Scheduler
- **Main message:** we tested whether DeepBoot's claims hold in the authors' own simulator, and found where it can improve.
- **Bullets:**
  - Paper: Chen et al., IEEE TPDS 34(9), 2023
  - Method: authors' discrete-time simulator, 16 × 4 GPUs
  - 10 runs + 3 controlled studies
  - Outcome: partial reproduction plus a proposed extension
- **Visual:** title plus one-line result: "DeepBoot small: 0.652 h (ours) vs ≈0.66 h (paper)".
- **Presenter notes:** frame the talk as an audit, not a success story. We will say what matched, what did not, and what we could not test.
- **Sources:** paper p. 2553; Report §1.

### Slide 2: The Problem: Idle Inference GPUs, Queued Training Jobs
- **Main message:** separate training and inference clusters waste GPUs because their loads peak at different times.
- **Bullets:**
  - Inference clusters < 40% utilised (diurnal load)
  - Training jobs wait in queues for GPUs
  - Lending GPUs → frequent reclaiming → restarts cost 20–150 s
- **Visual:** two cluster boxes; arrow "lend idle GPUs" and arrow "reclaim on request".
- **Presenter notes:** cite Table I restart costs (e.g. ImageNet 149.5 s without AFE). Explain why frequent reclaiming makes restart cost dominant (Fig. 2: real GPU use far below allocated).
- **Sources:** paper pp. 2553–2555, Table I, Fig. 2.

### Slide 3: DeepBoot's Approach
- **Main message:** three mechanisms: ATS-T, ATS-I and AFE.
- **Bullets:**
  - **ATS-T:** group-knapsack allocation maximising Σ SPEEDUP, every 60 s
  - **ATS-I:** immediate GPU-level placement and reclaim; PROTECT state with 30–120 s protection
  - **AFE:** elastic restarts, so surviving replicas skip a full restart
- **Visual:** three-box diagram; complexity note O(n·m²) vs NSGA-II O(k·p·n²·m²).
- **Presenter notes:** SPEEDUP = GOODPUT(current)/GOODPUT(initial), from Pollux. ATS-I picks PROTECT GPUs first (largest reuse count), then FREE, then reclaims the training GPU whose loss hurts SPEEDUP least.
- **Sources:** paper Sec. IV–V, Alg. 1–3, pp. 2558–2561; Report §3.

### Slide 4: System Architecture and GPU Lifecycle
- **Main message:** inference GPUs move through TRAIN → FREE → RUN → PROTECT.
- **Bullets:**
  - Training GPUs allocated first from the training cluster, then loaned from the inference cluster
  - Inference request: PROTECT → FREE → reclaim
  - Protect time = min(120, 30 + 15·reuse count) s
- **Visual:** Report §3.1 Mermaid diagram, plus the state machine from paper Fig. 7.
- **Presenter notes:** repository flag mapping: `--policy dp` = ATS-T; `--AISS` = PROTECT/warm-reuse lifecycle only (not the whole of ATS-I); `--AFE`; `--random_allocate`; `--ARYL`. Stress that "AISS" is a code flag that does not appear in the paper.
- **Sources:** paper Fig. 5, Fig. 7; Report §3.5.

### Slide 5: Paper's Experimental Setup
- **Main message:** 64 simulated GPUs, 160 Microsoft-trace training jobs, three inference loads.
- **Bullets:**
  - 16 workers × 4 GPUs (8 training + 8 inference)
  - Small / Middle / Large inference loads over 16 h
  - Baselines: Optimus, Tiresias, AFS, Pollux, Aryl; pure-train Pollux on 32 GPUs
  - Metric: average **training** JCT, makespan
- **Visual:** parameter table (Report §4.1).
- **Presenter notes:** the paper reports no repetitions or variance. The testbed (8 × 2 P40) is out of our scope.
- **Sources:** paper Sec. VII-A, pp. 2561–2562.

### Slide 6: What the Paper Reports
- **Main message:** DeepBoot ≈ Pollux on JCT, much faster to schedule; −38% vs baseline.
- **Bullets:**
  - Fig. 9: DeepBoot ≈0.66 / 0.77 / 1.04 h (S/M/L)
  - Pollux slightly better at S/M, worse at L
  - Fig. 11: Pollux decisions take seconds; makespan up to ≈74 h
  - Fig. 14: ATS-I < Aryl, Random
- **Visual:** redrawn Fig. 9 bar chart with "≈" labels.
- **Presenter notes:** all values are read from figures. We also note small internal inconsistencies: Fig. 13 vs Fig. 9 at middle scale, and the AFS ratios in the text vs the bars.
- **Sources:** paper Figs. 9, 11, 13, 14, pp. 2562–2564; Report §4.3.

### Slide 7: Our Reproduction Methodology
- **Main message:** same code, recorded commands, every metric recomputed from raw outputs.
- **Bullets:**
  - Simulator source identical to the authors' upstream
  - 16 × 4, 60-s interval, protection constants match the paper
  - Workload training mix matches Table I exactly
  - Discrepancy: inference count 20× (file) vs 10× (paper text)
- **Visual:** pipeline: workload CSV → simulator → summary.json/gpu.log → our recomputation.
- **Presenter notes:** mention the restart-delay mismatch (code ImageNet 35 s vs paper 149.5 s). Two authors' launchers omit `--policy` and silently run DeepBoot. Our E05 added it.
- **Sources:** Report §5, §7.2–7.3.

### Slide 8: Experiment Inventory
- **Main message:** 10 runs + 3 studies. Configuration confidence varies.
- **Bullets:**
  - DeepBoot: E01 (AFE off), E08 rerun (AFE on, verified), E04 (middle)
  - Comparators: E03/E06 AFS (Aryl reclaim), E05 Pollux
  - Studies: AISS 0/1; ATS-I vs RANDOM ×3 seeds; Pollux overhead
  - E02: provisional (command lost; rerun disagrees)
- **Visual:** compact version of the Report §6 table with a confidence column.
- **Presenter notes:** two folders share the "E08" ID; we recommend renaming one. Single runs are deterministic only for dp + ATS-I + AFE off.
- **Sources:** Report §6; `experiment_registry.csv`.

### Slide 9: Paper vs Our Results
- **Main message:** DeepBoot reproduces closely; AFS and Pollux absolute values do not.
- **Bullets:**
  - DeepBoot small: **0.652 h vs ≈0.66 h**; makespan **18.1 vs ≈18 h**
  - Small → middle: **+17.0% vs ≈+17%**
  - AFS small: 0.74–0.80 h vs ≈0.93 h (unexplained; ARYL=1)
  - Pollux small: 0.663 h vs ≈0.55 h (unexplained; AFE status unknown)
- **Visual:** grouped bars, paper (hatched, "≈") vs ours, for DeepBoot S/M, AFS S, Pollux S.
- **Presenter notes:** separate numerical agreement from trend agreement. The middle-scale comparison uses our AFE-off run against the paper's AFE-on bar. The headline 38% claim is untested because we did not run the baseline.
- **Sources:** Report §8.1–8.2.

### Slide 10: AISS Ablation (Warm-Pod Protection)
- **Main message:** protection helps inference latency, not training JCT, at the small scale.
- **Bullets:**
  - Only `--AISS` changed (0 vs 1)
  - Inference mean JCT 10.78 → **7.84 s (−27%)**; no request slower
  - Training mean −0.8%; P50/P95 +3%; paired jobs 57 faster / 58 slower
  - Allocated GPU −2.4 pp with AISS on
- **Visual:** inference JCT CDF (`experiment/results/ablation/aiss/jct_cdf_inference.png`).
- **Presenter notes:** the mechanism comes from the code: AISS=0 deletes finished pods, so each request pays a 6-s cold start. AISS=1 is identical to E01, which confirms determinism. This is related to Fig. 13 but not the same, because Fig. 13 varies protection length. The paper never reports inference latency, so this is new information.
- **Sources:** Report §9.2; `docs/AISS_ablation_report.md`.

### Slide 11: ATS-I vs RANDOM Inference Allocation
- **Main message:** ATS-I gives 5% lower training JCT in all 3 matched pairs.
- **Bullets:**
  - Only `--random_allocate` differs; `PYTHONHASHSEED` 11/22/33 matched
  - Training mean **+124.7 s (+5.1%)** with RANDOM; inference +0.07 s
  - "RANDOM" in the code = hash-ordered first-fit, with **no RNG**
  - Same direction as paper Fig. 14 (≈+8%)
- **Visual:** paired dot plot, 3 seeds × 2 policies.
- **Presenter notes:** ATS-I results are identical across seeds (deterministic). RANDOM varies with Python set iteration order. Three pairs cannot establish statistical significance. E07, run unseeded, falls outside the controlled range.
- **Sources:** Report §9.3; `docs/inference_allocation_comparison.md`.

### Slide 12: Pollux Optimization Overhead
- **Main message:** NSGA-II is about 5–7× slower per decision, but the simulator does not charge that time.
- **Bullets:**
  - Pollux ≈0.68–1.0 s/decision vs DeepBoot ≈0.14 s (tick) and ≈0.007 s (inference)
  - Runs on every event (7,263 calls) instead of every 60 s
  - "86% of wall time" inflated by one 2,336-s call (likely a stall)
  - Optimizer time is **not added to simulated time**, so no makespan penalty appears
- **Visual:** log-scale bar chart of per-decision cost; a callout showing Pollux simulated makespan 19.6 h vs paper ≈26 h.
- **Presenter notes:** distinguish wall-clock optimizer time, total simulator runtime and simulated time. The per-decision cost agrees with Fig. 11(a). Fig. 11(b) cannot be reproduced with this code.
- **Sources:** Report §9.4, §7.3; `docs/pollux_overhead_investigation.md`; `simulator.py:616–685`.

### Slide 13: Key Findings
- **Main message:** DeepBoot's own result reproduces; comparative claims are only partly tested.
- **Bullets:**
  - Reproduced: DeepBoot small JCT and makespan; scaling trend
  - Agreed in trend: ATS-I > RANDOM; AFE reduces restart overhead
  - Not reproduced: AFE percentile gains (≈1.7× P95 in paper vs 1.03×)
  - Untested: 38% vs baseline, Optimus/Tiresias/Aryl, large workload
- **Visual:** three-column table: Reproduced / Trend only / Not reproduced or untested.
- **Presenter notes:** AFE's mean gain (≈4%) comes almost entirely from 4 ImageNet jobs, which make up ≈40% of total training JCT.
- **Sources:** Report §8, §10, §13.

### Slide 14: Identified Limitation: Restart-Blind Training Scheduler
- **Main message:** ATS-T penalises every reallocation with a constant 10 s, regardless of the job.
- **Bullets:**
  - `dp.py:121`: `delay = 10` for every application
  - Modelled restart cost: 18–103 s without AFE
  - ImageNet: ≈200–230 restarts **per job**; 4 jobs ≈ 40% of total training JCT
  - Restart overhead is the paper's own core motivation
- **Visual:** bar chart of restarts per job by application (E01: ImageNet ≈229, YOLOv3 ≈62, others ≤ 17).
- **Presenter notes:** this is a code-level observation backed by raw restart counts. That an improvement exists is a **hypothesis**.
- **Sources:** Report §8.3, §11 (R1); `dp.py:111–148`; E01 `jobinfo.log`.

### Slide 15: Proposed Improvement: Restart-Cost-Aware ATS-T
- **Main message:** make the knapsack penalty reflect each job's real rescale cost.
- **Bullets:**
  - Replace the constant 10 s with the per-application expected rescale cost (AFE-aware)
  - Optional: minimum dwell time / hysteresis before resizing again
  - Local change to `dp.py` (≈10–20 lines)
  - Status: **proposed, not implemented**
- **Visual:** formula: f = (age − restarts · d_app)/(age + d_app), with d_app = FIRST/NEXT_DELAY.
- **Presenter notes:** secondary contribution (R2): latency-aware simulation, so that scheduler speed affects simulated outcomes. This is needed to test the paper's main argument against Pollux.
- **Sources:** Report §11, §12.4.

### Slide 16: Evaluation Plan
- **Main message:** controlled, seeded, metric-complete evaluation against verified baselines.
- **Bullets:**
  - Baselines: E01 (AFE off) and E08 (AFE on), unchanged code
  - 3 `PYTHONHASHSEED`s; small, then middle workload
  - Metrics: training mean/P50/P95, ImageNet JCT, restarts, rescale delay, real GPU %, inference latency
  - First: run the missing pure-train baseline (`--policy pollux`, 8 × 4) and an AFE=1 determinism check
- **Visual:** experiment matrix table.
- **Presenter notes:** success criterion: fewer restarts and lower P95/ImageNet JCT without worse median JCT. Report all seeds, not only means.
- **Sources:** Report §12.3–12.4.

### Slide 17: Conclusion and Future Work
- **Main message:** a partial but honest reproduction, with a concrete, evidence-based extension.
- **Bullets:**
  - DeepBoot's small-scale numbers reproduce in the authors' simulator
  - Our studies add inference-latency and allocation evidence the paper lacks
  - Simulator gaps: no decision latency; restart costs and workload ratio differ from the paper
  - Next: baseline run → restart-aware ATS-T → latency-aware simulation
- **Visual:** roadmap arrow with three steps.
- **Presenter notes:** end with what is still unknown: the 38% claim, AFS/Pollux absolute gaps, E02 vs E08.
- **Sources:** Report §13.

---

## Backup slides (for viva questions)
- **B1, Metric definitions:**
  - JCT = completion − submission.
  - Training-only mean is used, because overall mean is 95% inference rows.
  - `gpu_use` = allocated share; `real_gpu_use` = excluding rescaling placements. Both match the paper's definitions (p. 2555) and both are simulated.
- **B2, Paper/implementation discrepancy list:** Report §7.3 and §4.3 (inconsistencies).
- **B3, E02 vs E08:** same end clock (65,280 s) but training mean 2,374.6 vs 2,348.0 s; hypotheses in Report §9.1.
- **B4, Why the AFS/Pollux numbers differ from the paper:** candidate causes listed; none verified (Report §8.1).
