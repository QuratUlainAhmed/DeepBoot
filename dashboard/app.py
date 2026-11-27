"""DeepBoot Interactive Scheduling Simulator — Home / simulation setup.

Run from the repository root:
    conda activate deepboot-dash
    streamlit run dashboard/app.py
"""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import streamlit as st  # noqa: E402

from dashboard.components import common, theme  # noqa: E402
from dashboard.components.workflow import COMPONENTS_DOT  # noqa: E402
from dashboard.data import paper_reference  # noqa: E402
from dashboard.engine import state_manager  # noqa: E402
from dashboard.engine.sim_bridge import POLICY_LABELS, SimConfig  # noqa: E402
from dashboard.engine.workload_manager import describe, load_workload, reduced_scenario  # noqa: E402

ctl = common.page("Home", "🛰️")

st.title("DeepBoot Interactive Scheduling Simulator")
st.markdown(
    "An interactive front-end to the **unmodified DeepBoot research simulator** "
    "(Chen et al., IEEE TPDS 2023). Every allocation, reclaim and rescale shown here was "
    "computed by the repository's own `simulator.py`, `dp.py` and `infer_scheduler.py`. "
    "The dashboard drives the simulator loop one step at a time and records what it decides.")
st.markdown(theme.badge("paper") + theme.badge("repo") + theme.badge("proto") + theme.badge("paperonly"),
            unsafe_allow_html=True)
st.caption("These provenance badges appear on every result. Paper values are read from figures. "
           "Repository experiments are the team's retained runs. Prototype results are runs made in this app.")

st.graphviz_chart(COMPONENTS_DOT, use_container_width=True)

st.subheader("Simulation setup")
st.caption("Creating a new simulation replaces the current one for everyone using this server (single active simulation).")
with st.form("setup"):
    c1, c2, c3 = st.columns(3)
    policy = c1.selectbox("Training scheduler (--policy)", list(POLICY_LABELS), format_func=POLICY_LABELS.get)
    afe = c1.toggle("AFE (--AFE 1)", value=False, help="Use the AFE rescale-delay model (applications.FIRST/NEXT_DELAY)")
    aiss = c1.toggle("AISS (--AISS 1)", value=True, help="Keep finished inference pods in PROTECT for warm reuse")
    infer_path = c2.radio("Inference allocation", ["ATS-I (--random_allocate 0)", "RANDOM (--random_allocate 1)"])
    aryl = c2.toggle("Aryl worker-level reclaim (--ARYL 1)", value=False)
    protect = c2.select_slider("Protection scale (--protect_times)", [0.0, 1.0, 2.0, 4.0], value=1.0)
    infer_sched = 1
    if policy == "pollux":
        infer_sched = int(c2.toggle("Use ATS-I between ticks (--INFER_SCHEDULER 1)", value=False,
                                    help="0 = NSGA-II also schedules inference on every event (as in E05)"))
    scale = c3.selectbox("Base workload", ["small", "middle", "large"])
    mode = c3.radio("Scenario", ["Reduced (interactive)", "Full trace"],
                    help="Reduced keeps real rows only: first N training jobs + inference arrivals in a window.")
    n_tr = c3.slider("Training jobs (reduced)", 2, 40, 8)
    win = c3.slider("Inference window, s (reduced)", 300, 7200, 1800, step=300)
    ex_img = c3.toggle("Exclude ImageNet (≈10 h jobs) from reduced", value=True)
    go = st.form_submit_button("Create simulation", type="primary")

if go:
    base = load_workload(scale)
    if mode.startswith("Reduced"):
        w = reduced_scenario(base, n_tr, win, ("imagenet",) if ex_img else ())
        label = f"Reduced {scale}.csv ({n_tr} training, inference ≤ {win} s)"
    else:
        w = base
        label = f"Full {scale}.csv trace"
    cfg = SimConfig(policy=policy, AFE=int(afe), AISS=int(aiss), ARYL=int(aryl),
                    random_allocate=int(infer_path.startswith("RANDOM")), protect_times=float(protect),
                    INFER_SCHEDULER=infer_sched, REPAIR_TRAIN=0 if policy == "pollux" else 1,
                    workload=f"{scale}.csv" if mode.startswith("Full") else f"reduced-{scale}.csv")
    state_manager.new_simulation(w, cfg, {"label": label, "base": scale})
    st.rerun()

ctl = state_manager.controller()
d = describe(ctl.initial_workload)
st.markdown(f"**Current:** {state_manager.store()['scenario'].get('label')} · {d['training']} training jobs, "
            f"{d['inference']} inference requests · last arrival {d['last_arrival_s']:,} s")
st.markdown(f'<div class="db-mono">{ctl.cfg.cli_flags()}</div>', unsafe_allow_html=True)
if ctl.cfg.policy == "pollux":
    st.info("Pollux's NSGA-II is unseeded and takes ≈1 s per decision, so runs are slower and not bit-reproducible.")

with st.expander("Known caveats of this reproduction (from docs/DEEPBOOT_PAPER_AND_EXPERIMENT_COMPARISON.md)"):
    for c in paper_reference.KNOWN_CAVEATS:
        st.markdown(f"- {c}")

st.subheader("Pages")
st.markdown(
    "1. **Cluster Overview**: the 16×4 GPU grid, current or replayed.\n"
    "2. **Job Management**: submit training and inference jobs; queues and status.\n"
    "3. **Interactive Simulation**: play, pause, step, run-until; event timeline.\n"
    "4. **ATS & AFE**: the inside of each decision (knapsack, reclaim search, rescale delay, pod lifecycle).\n"
    "5. **Performance Analytics**: metrics of this run or any repository experiment.\n"
    "6. **Experiment Comparison**: E01–E08, ablations, and paper figure values.")
