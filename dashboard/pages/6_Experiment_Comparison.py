import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

import numpy as np  # noqa: E402
import pandas  # noqa: E402
import plotly.graph_objects as go  # noqa: E402
import streamlit as st  # noqa: E402

from dashboard.components import common, theme  # noqa: E402
from dashboard.components.charts import cdf_figure, gpu_util_figure  # noqa: E402
from dashboard.components.theme import COLORS  # noqa: E402
from dashboard.data import experiment_loader as EL  # noqa: E402
from dashboard.data import paper_reference as PR  # noqa: E402

ctl = common.page("Experiment Comparison", "🧪")
st.title("Experiment Comparison")
st.markdown(theme.badge("paper") + theme.badge("repo") + theme.badge("proto"), unsafe_allow_html=True)

cat = EL.catalog()
IA_A = [k for k in cat if k.startswith("IA-ats")]
IA_R = [k for k in cat if k.startswith("IA-random")]
PRESETS = {
    "Schedulers on small (descriptive only)": (["E01", "E08-rerun", "E03", "E06", "E05"],
        "Not a controlled ranking. These runs also differ in AFE, ARYL (AFS runs use Aryl reclaim), "
        "INFER_SCHEDULER/REPAIR_TRAIN (Pollux), and commit. Pollux NSGA-II is unseeded."),
    "ATS-I vs RANDOM (controlled, 3 hash seeds)": (IA_A + IA_R + ["E07"],
        "Only --random_allocate differs within each seed pair. ATS-I is deterministic. RANDOM varies with Python "
        "set order (no RNG). E07 is an earlier, unseeded RANDOM run."),
    "AFE pairs": (["E01", "E08-rerun", "E02", "E03", "E06"],
        "Best DeepBoot pair: E01 (AFE 0) vs E08-rerun (AFE 1), both with verified commands. E02 is provisional "
        "(no command record) and differs from its rerun. AFS pair E03/E06 uses ARYL=1. Each setting was run once."),
    "AISS ablation": (["AISS-0", "AISS-1"], "Only --AISS differs (run_ablation.sh). AISS-1 is identical to E01."),
    "Workload scaling small → middle": (["E01", "E04"],
        "Same flags (AFE off). The middle trace has 5× more inference rows and different arrivals, so this is "
        "descriptive, not causal."),
    "Custom": ([], ""),
}
preset = st.selectbox("Comparison", list(PRESETS))
default, caveat = PRESETS[preset]
keys = st.multiselect("Experiments", list(cat), default=[k for k in default if k in cat],
                      format_func=lambda k: cat[k].label)
if caveat:
    st.warning(caveat)
if not keys:
    st.stop()

st.subheader("Configuration")
cfg_rows = [{"experiment": k, "group": cat[k].group, **cat[k].config} for k in keys]
st.dataframe(pandas.DataFrame(cfg_rows), hide_index=True, use_container_width=True)

st.subheader("Results")
st.markdown(theme.badge("repo"), unsafe_allow_html=True)
rows = [EL.summary_metrics(k) for k in keys]
res = pandas.DataFrame(rows)
def _cell(v):
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return "unavailable"
    return f"{v:,.2f}" if isinstance(v, float) else str(v)


st.dataframe(res.set_index("experiment").T.applymap(_cell),
             use_container_width=True)
st.caption("All values were recomputed from each run's raw files. 'unavailable' means the source file was not retained; "
           "it does not mean zero.")

c1, c2 = st.columns(2)
m = res.melt(id_vars="experiment", value_vars=[c for c in ["training mean JCT (s)", "training P50 JCT (s)", "training P95 JCT (s)"] if c in res])
fig = go.Figure()
for stat, g in m.groupby("variable", sort=False):
    fig.add_trace(go.Bar(x=g["experiment"], y=g["value"], name=stat.replace(" JCT (s)", "")))
c1.plotly_chart(fig.update_layout(barmode="group", title="Training JCT (s)", height=360,
                                  legend=dict(orientation="h", y=-0.25)), use_container_width=True)
fig = go.Figure()
if "inference mean JCT (s)" in res:
    fig.add_trace(go.Bar(x=res["experiment"], y=res["inference mean JCT (s)"], name="inference mean", marker_color="#F59E0B"))
if "inference P95 JCT (s)" in res:
    fig.add_trace(go.Bar(x=res["experiment"], y=res["inference P95 JCT (s)"], name="inference P95", marker_color="#FCD34D"))
c2.plotly_chart(fig.update_layout(barmode="group", title="Inference latency / JCT (s)", height=360,
                                  legend=dict(orientation="h", y=-0.25)), use_container_width=True)

c1, c2 = st.columns(2)
gcols = [c for c in ["allocated GPU %", "real GPU %"] if c in res]
fig = go.Figure()
for col in gcols:
    fig.add_trace(go.Bar(x=res["experiment"], y=res[col], name=col))
c1.plotly_chart(fig.update_layout(barmode="group", title="Mean GPU utilisation (simulated counters, % of 64)",
                                  yaxis_range=[0, 100], height=360, legend=dict(orientation="h", y=-0.25)),
                use_container_width=True)
groups = {}
for k in keys:
    df = EL.job_jcts(k)
    if df is not None:
        groups[k] = df.loc[df["class"] == "training", "jct_s"].values
c2.plotly_chart(cdf_figure(groups, "Training JCT (s), log scale", log_x=True).update_layout(title="Training JCT CDF"),
                use_container_width=True)

with st.expander("GPU utilisation over time (runs with retained gpu.log)"):
    for k in keys:
        g = EL.gpu_series(k)
        if g is None:
            st.caption(f"{k}: gpu.log not retained")
        else:
            st.plotly_chart(gpu_util_figure(g, 64, k), use_container_width=True, key=f"gu-{k}")

if preset.startswith("ATS-I vs RANDOM") and IA_A and IA_R:
    a = [EL.summary_metrics(k)["training mean JCT (s)"] for k in IA_A]
    r = [EL.summary_metrics(k)["training mean JCT (s)"] for k in IA_R]
    st.markdown(f"**Matched pairs:** RANDOM − ATS-I training mean = "
                + ", ".join(f"{y - x:+.1f} s" for x, y in zip(a, r))
                + f" (mean {np.mean(r) - np.mean(a):+.1f} s, {100 * (np.mean(r) / np.mean(a) - 1):+.1f}%). "
                "Three pairs cannot establish statistical significance.")

st.divider()
st.subheader("Paper vs repository vs prototype")
st.caption("These three sources are NOT interchangeable. Paper values were read from figures (approximate). "
           "Repository values are the team's runs. Prototype values come from this app's current run.")
proto = None
if ctl.is_complete():
    jt = ctl.job_table()
    v = jt[(jt["class"] == "training")]["jct_s"].dropna()
    if len(v):
        proto = {"label": f"Prototype: {state_label}" if (state_label := ctl.label) else "Prototype run",
                 "train_h": v.mean() / 3600, "makespan_h": ctl.cluster.clock / 3600,
                 "full_small": len(ctl.initial_workload) == 3360 and not ctl.injected_rows}

tab9, tab14, tab11 = st.tabs(["Fig. 9 avg training JCT", "Fig. 14 inference policy", "Fig. 11(b) makespan"])
with tab9:
    scale = st.radio("Workload scale", ["small", "middle", "large"], horizontal=True)
    names = list(PR.FIG9_AVG_TRAINING_JCT_H)
    pv = [PR.FIG9_AVG_TRAINING_JCT_H[n].get(scale) for n in names]
    fig = go.Figure(go.Bar(x=names, y=pv, name=PR.PROVENANCE, marker_color=COLORS["paper"], opacity=0.75))
    xs, ys, txt = [], [], []
    for mp in PR.REPO_TO_PAPER:
        fig_, sched, sc = mp["paper"]
        if sc == scale and mp["repo"] in cat:
            xs.append(sched)
            ys.append(EL.summary_metrics(mp["repo"])["training mean JCT (s)"] / 3600)
            txt.append(f"{mp['repo']}: {mp['match']}")
    fig.add_trace(go.Scatter(x=xs, y=ys, mode="markers", name="Repository experiment", text=txt, hoverinfo="text+y",
                             marker=dict(size=14, color=COLORS["repo"], symbol="diamond", line=dict(width=1, color="#0F172A"))))
    if proto and scale == "small":
        fig.add_trace(go.Scatter(x=["DeepBoot" if ctl.cfg.policy == "dp" else {"pollux": "Pollux", "afs": "AFS"}[ctl.cfg.policy]],
                                 y=[proto["train_h"]], mode="markers", name="Prototype run",
                                 marker=dict(size=14, color=COLORS["prototype"], symbol="star")))
    fig.update_layout(yaxis_title="Average training JCT (h)", height=420, legend=dict(orientation="h", y=-0.2))
    st.plotly_chart(fig, use_container_width=True)
    st.dataframe(pandas.DataFrame(PR.REPO_TO_PAPER).assign(paper=lambda d: d["paper"].map(lambda p: " / ".join(p))),
                 hide_index=True, use_container_width=True)
    if proto and not proto["full_small"]:
        st.info("The prototype point comes from a reduced or modified scenario, so it is not comparable with the paper's "
                "full-workload bars. It is shown for orientation only.")
with tab14:
    fig = go.Figure()
    for pol, vals in PR.FIG14_INFER_POLICY_H.items():
        fig.add_trace(go.Bar(x=list(vals), y=list(vals.values()), name=f"Paper ≈ {pol}"))
    if IA_A and IA_R:
        fig.add_trace(go.Scatter(x=["small", "small"], y=[np.mean([EL.summary_metrics(k)["training mean JCT (s)"] for k in K]) / 3600 for K in (IA_R, IA_A)],
                                 mode="markers+text", text=["repo RANDOM", "repo ATS-I"], textposition="middle right",
                                 marker=dict(size=13, color=[COLORS["inference_running"], COLORS["repo"]], symbol="diamond"),
                                 name="Repository (AFE off, 3 seeds)"))
    fig.update_layout(barmode="group", yaxis_title="Average training JCT (h)", height=400)
    st.plotly_chart(fig, use_container_width=True)
    st.caption("The repository study uses AFE=0, and its RANDOM path is not random (hash-ordered first-fit). The "
               "direction matches the paper (≈+8% at small vs +5.1% here); the absolute values differ.")
with tab11:
    fig = go.Figure()
    for pol, vals in PR.FIG11B_MAKESPAN_H.items():
        fig.add_trace(go.Bar(x=list(vals), y=list(vals.values()), name=f"Paper ≈ {pol}"))
    reps = [("E08-rerun", "DeepBoot"), ("E06", "AFS"), ("E05", "Pollux")]
    fig.add_trace(go.Scatter(x=["small"] * 3, y=[EL.summary_metrics(k)["makespan (simulated h)"] for k, _ in reps],
                             text=[f"{k} ({p})" for k, p in reps], mode="markers+text", textposition="middle right",
                             marker=dict(size=12, color=COLORS["repo"], symbol="diamond"), name="Repository"))
    fig.update_layout(barmode="group", yaxis_title="Makespan (h)", height=400)
    st.plotly_chart(fig, use_container_width=True)
    st.warning("Pollux's repository makespan (≈19.6 h) cannot show the paper's penalty (≈26 h): the simulator logs "
               "scheduler wall time but never adds it to simulated time.")

with st.expander("Known caveats (from docs/DEEPBOOT_PAPER_AND_EXPERIMENT_COMPARISON.md)"):
    for c in PR.KNOWN_CAVEATS:
        st.markdown(f"- {c}")

st.subheader("Plots generated by the research code")
imgs = [(k, p) for k in keys for p in cat[k].plots]
team_plots = os.path.join(EL.TEAM, "plots")
imgs += [("team plots", os.path.join(team_plots, f)) for f in sorted(os.listdir(team_plots)) if f.endswith(".png")]
if imgs:
    cols = st.columns(3)
    for i, (k, p) in enumerate(imgs):
        cols[i % 3].image(p, caption=f"{k} · {os.path.basename(p)}", use_column_width=True)
