import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from collections import Counter  # noqa: E402

import pandas  # noqa: E402
import plotly.graph_objects as go  # noqa: E402
import streamlit as st  # noqa: E402

from dashboard.components import common, theme  # noqa: E402
from dashboard.components.job_cards import narrate_decision  # noqa: E402
from dashboard.components.workflow import COMPONENTS_DOT, POD_LIFECYCLE_DOT  # noqa: E402
from dashboard.data.paper_reference import TABLE1_RESTART_S  # noqa: E402
from dashboard.engine.sim_bridge import sim  # noqa: E402

ctl = common.page("ATS & AFE", "🧠")
st.title("ATS-T · ATS-I · AFE · AISS")
st.markdown(theme.badge("proto") + theme.badge("paperonly"), unsafe_allow_html=True)
st.caption("Each panel shows inputs and outputs recorded from the real methods by read-only wrappers "
           "(dashboard/engine/instrumentation.py). The dashboard does not recompute any decision.")

DEC = ctl.decisions
t0, t1, t2, t3, t4 = st.tabs(["Workflow", "ATS-T (training)", "ATS-I (inference)", "AFE (rescaling)", "AISS (pod lifecycle)"])

with t0:
    st.graphviz_chart(COMPONENTS_DOT, use_container_width=True)
    st.markdown("""
| Component | In the paper | In this code | Controlled by |
|---|---|---|---|
| **ATS-T** | Group knapsack maximising Σ SPEEDUP, restart penalty (Alg. 1–2) | `dp.py` `allocate_elastic` + `max_value_dp`, runs every 60 s | `--policy dp` |
| **ATS-I** | PROTECT → FREE → reclaim min-ΔSPEEDUP GPU (Alg. 3) | `InferScheduler.ATSI_infer_schedule`: empty → SLEEP → reclaim (warm PROTECT reuse happens earlier, in `Job.step`) | `--random_allocate 0`, `--ARYL 0` |
| **AFE** | Elastic restart with Redis-synchronised state (Sec. V) | A smaller **rescale-delay number** only (`calculate_rescale_time`) | `--AFE` |
| **AISS** | (not a paper term) | Keep finished pods in PROTECT for warm reuse, or delete them | `--AISS` |
""")
    st.info("AISS is not 'ATS-I on/off'. With AISS=0, inference placement still uses ATS-I; only the warm-pod "
            "PROTECT lifecycle is removed.")

with t1:
    st.markdown("**ATS-T** runs at every 60 s tick when the policy is `dp`.")
    tt = [d for d in DEC if d["kind"] == "ATS-T"]
    if not tt:
        st.info("No ATS-T decision recorded yet (policy must be `dp`; advance past a 60 s tick with training jobs present).")
    else:
        clocks = [d["clock"] for d in tt]
        ck = st.select_slider("ATS-T decision at simulated t (s)", clocks, value=clocks[-1])
        d = [x for x in tt if x["clock"] == ck][-1]
        st.markdown(narrate_decision(d))
        ks = d.get("knapsack") or {}
        jobs = d.get("jobs") or []
        chosen = ks.get("chosen_replicas", [])
        rows = []
        for j, w in zip(jobs, chosen):
            rows.append({**j, "chosen_GPUs": w, "changed": j["prev_gpus"] != w})
        st.dataframe(pandas.DataFrame(rows), hide_index=True, use_container_width=True)
        st.caption("penalty_factor_derived = max(age − restarts·10, 0)/(age + 10), the formula at dp.py:121–128. "
                   "It is applied to every option whose GPU count differs from the current one. The paper's "
                   "Alg. 2 line 26 states the opposite condition (likely a typo in the paper).")
        vals = ks.get("values") or []
        if vals:
            width = max(len(v) for v in vals)
            z = [v + [None] * (width - len(v)) for v in vals]
            fig = go.Figure(go.Heatmap(z=z, x=[str(i + 1) for i in range(width)], y=[j["job"] for j in jobs],
                                       colorscale="Blues", colorbar=dict(title="value")))
            fig.add_trace(go.Scatter(x=[str(w) for w in chosen if w > 0], y=[j["job"] for j, w in zip(jobs, chosen) if w > 0],
                                     mode="markers", marker=dict(symbol="x", size=14, color="#F59E0B"), name="chosen"))
            fig.update_layout(title="Knapsack item values (rows = jobs, columns = GPUs), ✕ = chosen",
                              height=120 + 26 * len(jobs), xaxis_title="GPUs (weight)")
            st.plotly_chart(fig, use_container_width=True)
        c1, c2 = st.columns(2)
        fg = d.get("free_gpus_by_node", {})
        c1.plotly_chart(go.Figure(go.Bar(x=[f"w{k}" for k in fg], y=list(fg.values()), marker_color="#3B82F6"))
                        .update_layout(title=f"Capacity offered to ATS-T: {d.get('capacity')} GPUs (excl. inference pods)",
                                       height=300), use_container_width=True)
        before, after = d.get("prev_alloc", {}), d.get("new_alloc", {})
        rows = [{"job": j, "before": ", ".join(f"w{k}×{v}" for k, v in sorted(Counter(before.get(j, [])).items())) or "∅",
                 "after": ", ".join(f"w{k}×{v}" for k, v in sorted(Counter(after.get(j, [])).items())) or "∅"}
                for j in sorted(set(before) | set(after))]
        c2.markdown("**Placement before → after** (`replicas2allocation`, dp.py:61: unchanged jobs kept, "
                    "new replicas packed onto the fewest workers)")
        c2.dataframe(pandas.DataFrame(rows), hide_index=True, use_container_width=True)

with t2:
    ti = [d for d in DEC if d["kind"] in ("ATS-I", "RANDOM") and (d.get("placed") or d.get("reclaims"))]
    st.markdown("**ATS-I** runs on every non-tick event (arrivals, finishes, waiting requests). "
                "Warm reuse of a PROTECT/SLEEP pod of the same app happens before the scheduler, in `Job.step`. "
                "Those placements appear as `warm-reuse` events and not here.")
    if not ti:
        st.info("No inference placement recorded yet.")
    else:
        only_reclaim = st.toggle("Only decisions that reclaimed GPUs from training", value=False)
        if only_reclaim:
            ti = [d for d in ti if d.get("reclaims")]
        if not ti:
            st.info("No decision reclaimed GPUs from training yet.")
        else:
            clocks = [d["clock"] for d in ti]
            ck = st.select_slider("Inference decision at simulated t (s)", clocks, value=clocks[-1])
            d = [x for x in ti if x["clock"] == ck][-1]
            st.markdown(narrate_decision(d))
            c1, c2 = st.columns(2)
            c1.markdown("**Placed requests → worker**")
            c1.dataframe(pandas.DataFrame([{"request": k, "worker": v[0]} for k, v in (d.get("placed") or {}).items()]),
                         hide_index=True, use_container_width=True)
            if isinstance(d.get("reclaims"), list) and d["reclaims"]:
                c2.markdown("**GPUs reclaimed from training**")
                c2.dataframe(pandas.DataFrame(d["reclaims"]), hide_index=True, use_container_width=True)
            if isinstance(d.get("branches"), list):
                c2.markdown("**Branch taken** (`schedule_available_gpu` → `schedule_training_gpu`)")
                c2.dataframe(pandas.DataFrame(d["branches"]), hide_index=True, use_container_width=True)
        all_i = [d for d in DEC if d["kind"] == "ATS-I"]
        if all_i:
            agg = Counter()
            for x in all_i:
                for b in x.get("branches") or []:
                    agg[b["branch"]] += b["count"]
            warm = sum(1 for e in ctl.events if e["type"] == "warm-reuse")
            agg["warm pod reuse (Job.step)"] = warm
            st.plotly_chart(go.Figure(go.Bar(x=list(agg), y=list(agg.values()), marker_color="#F59E0B"))
                            .update_layout(title="How inference requests got a GPU (this run)", height=300),
                            use_container_width=True)

with t3:
    st.markdown(f"AFE is **{'ON' if ctl.cfg.AFE else 'OFF'}** in this run.")
    st.markdown(theme.badge("paperonly") + " The paper's AFE steps (new Pod sync flags, rank-0 save state, "
                "Redis-coordinated reload, deadlock fallback; Sec. V–VI) are **not simulated**. The simulator models AFE only "
                "as a shorter rescale delay, during which the job makes no training progress.", unsafe_allow_html=True)
    st.markdown("""
**Rescale delay model** (`Job.reallocate`, simulator.py:376; `calculate_rescale_time`, :339):
- AFE off: every allocation change costs `APPLICATIONS_DELAY[app]` (full stop-resume).
- AFE on: first start → `FIRST_DELAY`; shrink → `NEXT_DELAY`; grow → `NEXT + (FIRST−NEXT)·added/new_total`; same size but moved → `FIRST_DELAY`.
""")
    rows = []
    for app in ["cifar10", "yolov3", "imagenet", "bert", "deepspeech2", "ncf"]:
        p = [v for k, v in TABLE1_RESTART_S.items() if k.startswith(app)][0]
        rows.append({"application": app, "code: full restart (s)": sim.APPLICATIONS_DELAY[app],
                     "code: AFE shrink (s)": sim.NEXT_DELAY[app], "paper Table I w/o AFE (s)": p[0],
                     "paper Table I w/ AFE (s)": p[1]})
    st.dataframe(pandas.DataFrame(rows), hide_index=True, use_container_width=True)
    st.caption("Code values from applications.py:284–322. Paper values from Table I, p. 2554, measured on the authors' testbed.")
    tr = [e for e in ctl.events if e["type"].startswith("training-") and e.get("gpus_after", 0) > 0]
    if tr:
        df = pandas.DataFrame(tr)
        st.markdown(f"**Rescaling events in this run: {len(df)}**, total modelled delay **{df['rescale_delay'].sum():,.0f} job-s**")
        fig = go.Figure(go.Scatter(x=df["clock"], y=df["rescale_delay"], mode="markers",
                                   marker=dict(size=8, color=df["gpus_after"] - df["gpus_before"], colorscale="RdBu",
                                               colorbar=dict(title="ΔGPUs")),
                                   hovertext=df["job"] + ": " + df["detail"], hoverinfo="text"))
        fig.update_layout(xaxis_title="Simulated time (s)", yaxis_title="Modelled rescale delay (s)", height=320)
        st.plotly_chart(fig, use_container_width=True)
        st.dataframe(df[["clock", "type", "job", "gpus_before", "gpus_after", "rescale_delay", "detail"]].iloc[::-1],
                     hide_index=True, use_container_width=True, height=280)
    else:
        st.info("No training rescaling recorded yet.")

with t4:
    st.markdown(f"AISS is **{'ON' if ctl.cfg.AISS else 'OFF'}** · protection scale ×{ctl.cfg.protect_times}")
    st.graphviz_chart(POD_LIFECYCLE_DOT, use_container_width=True)
    st.markdown("Protection time = `min(30 + 15·reuse_count, 120) × protect_times` s "
                "(`calculate_protect_time`, simulator.py:72). This matches the paper's t_p,min = 30, interval = 15, "
                "t_p,max = 120 (p. 2562). Warm reuse is per **application id** (e.g. `infer-yolov3-1`).")
    pods = ctl.snapshots[-1]["pods"]
    if pods:
        st.dataframe(pandas.DataFrame([{"pod": k, **v} for k, v in pods.items()]), hide_index=True, use_container_width=True)
    pe = [e for e in ctl.events if e["type"] in ("pod-state", "pod-removed", "warm-reuse")]
    if pe:
        c = Counter(e["type"] if e["type"] != "pod-state" else e["detail"].split(": ")[-1] for e in pe)
        st.plotly_chart(go.Figure(go.Bar(x=list(c), y=list(c.values()), marker_color="#A855F7"))
                        .update_layout(title="Pod lifecycle transitions observed", height=300), use_container_width=True)
