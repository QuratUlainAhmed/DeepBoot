import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

import numpy as np  # noqa: E402
import pandas  # noqa: E402
import plotly.graph_objects as go  # noqa: E402
import streamlit as st  # noqa: E402

from dashboard.components import common, theme  # noqa: E402
from dashboard.components.charts import allocation_area, cdf_figure, event_timeline, gpu_util_figure  # noqa: E402
from dashboard.data import experiment_loader as EL  # noqa: E402

ctl = common.page("Performance Analytics", "📈")
st.title("Performance Analytics")

UNAVAILABLE = "unavailable"


def fmt(v, nd=1):
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return UNAVAILABLE
    return f"{v:,.{nd}f}"


def pct(v, q):
    return float(np.percentile(v, q)) if len(v) else None


src = st.radio("Data source", ["This prototype run", "Repository experiment"], horizontal=True)

if src == "This prototype run":
    st.markdown(theme.badge("proto"), unsafe_allow_html=True)
    jt = ctl.job_table()
    c = ctl.cluster
    tr = jt[(jt["class"] == "training") & jt["jct_s"].notna()]["jct_s"].values
    inf = jt[(jt["class"] == "inference") & jt["jct_s"].notna()]["jct_s"].values
    gs = ctl.gpu_series()
    G = ctl.total_gpus()
    resc = [e.get("rescale_delay", 0) for e in ctl.events if e["type"].startswith("training-") and e.get("gpus_after", 0) > 0]
    oh = pandas.DataFrame([{"clock": t, "jobs": s[0], "wall_s": w} for t, s, w in c.optimize_history]) if c.optimize_history else None

    st.markdown(f"Simulated t = **{c.clock:,} s** · {'all jobs complete' if ctl.is_complete() else 'run in progress (values cover completed jobs only)'}")
    k = st.columns(4)
    k[0].metric("Training mean JCT (s)", fmt(np.mean(tr) if len(tr) else None), f"n={len(tr)} completed", delta_color="off")
    k[1].metric("Training P50 / P95 (s)", f"{fmt(pct(tr, 50), 0)} / {fmt(pct(tr, 95), 0)}")
    k[2].metric("Inference mean latency (s)", fmt(np.mean(inf) if len(inf) else None, 2), f"n={len(inf)}", delta_color="off")
    k[3].metric("Inference P95 latency (s)", fmt(pct(inf, 95), 1))
    k = st.columns(4)
    k[0].metric("Makespan (simulated h)", fmt(c.clock / 3600, 2) if ctl.is_complete() else UNAVAILABLE,
                "run not finished" if not ctl.is_complete() else None, delta_color="off")
    k[1].metric("Allocated / real GPU %", f"{fmt(100 * gs['gpu_use'].mean() / G) if len(gs) else UNAVAILABLE} / "
                f"{fmt(100 * gs['real_gpu_use'].mean() / G) if len(gs) else UNAVAILABLE}")
    k[2].metric("Training restarts (total)", int(jt.loc[jt["class"] == "training", "restarts"].sum()))
    k[3].metric("Modelled rescale overhead (job-s)", fmt(float(np.sum(resc)), 0) if resc else "0")
    k = st.columns(4)
    qw_t = jt[(jt["class"] == "training") & jt["queue_wait_s"].notna()]["queue_wait_s"]
    qw_i = jt[(jt["class"] == "inference") & jt["queue_wait_s"].notna()]["queue_wait_s"]
    k[0].metric("Training queue wait, mean (s)", fmt(qw_t.mean() if len(qw_t) else None))
    k[1].metric("Inference queue wait, mean (s)", fmt(qw_i.mean() if len(qw_i) else None, 2))
    k[2].metric("Scheduler wall time, total (s)", fmt(oh["wall_s"].sum(), 2) if oh is not None else UNAVAILABLE)
    k[3].metric("Training throughput / goodput", UNAVAILABLE)
    with st.expander("Metric definitions and sources"):
        st.markdown("""
- **JCT** = completion_time − submission_time (`Cluster.get_jcts`, simulator.py:946). Inference JCT includes queueing and any 6 s cold start, so it is the request latency.
- **GPU %** = mean of the 1-s counters `gpu_use` (all placed GPUs) and `real_gpu_use` (excluding placements in rescale delay) ÷ GPUs (`calculate_real_gpu_usage`, :1004). These are simulated counters, not hardware telemetry.
- **Restarts** = `Job.num_restarts`. **Rescale overhead** = sum of the modelled `rescale_time` assigned at each training reallocation (AFE or stop-resume model).
- **Queue wait**: training = first non-empty placement − submission. Inference = `start_execute_time` − submission.
- **Scheduler wall time** = `optimize_history` per scheduling call (`time.time()` around the policy/ATS-I call). This is real CPU time on this machine. It is **not** added to simulated time.
- **Makespan** = final simulated clock once all jobs complete.
- **Throughput/goodput**: unavailable. The simulator's per-step goodput/speedup collection is commented out (simulator.py, `simulate()`), and `metric.log` is always empty.
""")
    c1, c2 = st.columns(2)
    if len(gs) > 1:
        c1.plotly_chart(gpu_util_figure(gs, G, "GPU utilisation over time (simulated counters)"), use_container_width=True)
    if ctl.alloc_series:
        c2.markdown("**Training vs inference GPU allocation over time**")
        c2.plotly_chart(allocation_area(pandas.DataFrame(ctl.alloc_series), G), use_container_width=True)
    c1, c2 = st.columns(2)
    if len(tr) or len(inf):
        c1.plotly_chart(cdf_figure({"training": tr, "inference": inf}, "JCT (s), log scale", log_x=True)
                        .update_layout(title="JCT CDF"), use_container_width=True)
    done = jt[jt["jct_s"].notna() & (jt["class"] == "training")].sort_values("jct_s")
    if len(done):
        c2.plotly_chart(go.Figure(go.Bar(x=done["job"], y=done["jct_s"], marker_color="#3B82F6",
                                         hovertext=done["application"]))
                        .update_layout(title="Training JCT per job (s)", height=340), use_container_width=True)
    if oh is not None and len(oh):
        oh["path"] = np.where(oh["clock"] % ctl.cfg.interval == 0, "60 s tick (training policy)", "event (inference scheduler)")
        fig = go.Figure()
        for p, g in oh.groupby("path"):
            fig.add_trace(go.Scatter(x=g["clock"], y=g["wall_s"], mode="markers", name=p, marker=dict(size=5)))
        fig.update_layout(title="Scheduling overhead per decision (wall-clock s, this machine)", xaxis_title="Simulated time (s)",
                          height=320, legend=dict(orientation="h", y=-0.3))
        st.plotly_chart(fig, use_container_width=True)
    if ctl.events:
        st.plotly_chart(event_timeline(pandas.DataFrame(ctl.events)).update_layout(title="Scheduling event timeline"),
                        use_container_width=True)
else:
    st.markdown(theme.badge("repo"), unsafe_allow_html=True)
    cat = EL.catalog()
    key = st.selectbox("Experiment", list(cat), format_func=lambda k: cat[k].label)
    e = cat[key]
    st.markdown(f'<div class="db-mono">{" · ".join(f"{k}={v}" for k, v in e.config.items())}</div>', unsafe_allow_html=True)
    if e.notes and e.notes != "nan":
        st.caption(e.notes)
    m = EL.summary_metrics(key)
    show = {k: (fmt(v, 2) if isinstance(v, (int, float)) else (v if v is not None else UNAVAILABLE)) for k, v in m.items() if k != "experiment"}
    for k_ in ["training throughput / goodput", "queue wait"]:
        show[k_] = UNAVAILABLE
    st.dataframe(pandas.DataFrame([show]).T.rename(columns={0: "value"}), use_container_width=True)
    st.caption("Recomputed from the run's raw files (summary.json / gpu.log / job-metrics.csv / analysis-summary.json). "
               "Queue wait is unavailable because per-job start times are not retained in these outputs. "
               "Goodput is unavailable because metric.log is empty in every run.")
    g = EL.gpu_series(key)
    c1, c2 = st.columns(2)
    if g is not None:
        c1.plotly_chart(gpu_util_figure(g, 64, "GPU utilisation over time"), use_container_width=True)
    else:
        c1.info("GPU time series unavailable: the raw gpu.log was not retained for this run (summary values only).")
    df = EL.job_jcts(key)
    if df is not None:
        c2.plotly_chart(cdf_figure({c_: df.loc[df["class"] == c_, "jct_s"].values for c_ in ("training", "inference")},
                                   "JCT (s), log scale", log_x=True).update_layout(title="JCT CDF"), use_container_width=True)
        per_app = df[df["class"] == "training"].groupby("application")["jct_s"].agg(["count", "mean", "median", "max"]).round(1)
        if "restarts" in df:
            per_app["restarts"] = df[df["class"] == "training"].groupby("application")["restarts"].sum()
        st.markdown("**Training JCT by application**: the 4 ImageNet jobs dominate the mean in small-workload runs.")
        st.dataframe(per_app, use_container_width=True)
    oh = EL.optimize_history(key)
    if oh is not None:
        oh["path"] = np.where(oh["clock"] % 60 == 0, "60 s tick", "event")
        fig = go.Figure()
        for p, gg in oh.groupby("path"):
            fig.add_trace(go.Scatter(x=gg["clock"], y=gg["wall_s"], mode="markers", name=p, marker=dict(size=4)))
        fig.update_layout(title="Scheduling overhead per decision (wall-clock s, original machine)", height=320)
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.caption("Per-decision scheduling timings are unavailable for this run (jobinfo.log not retained).")
