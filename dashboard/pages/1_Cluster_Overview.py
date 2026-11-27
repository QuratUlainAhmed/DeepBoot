import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from collections import Counter  # noqa: E402

import pandas  # noqa: E402
import streamlit as st  # noqa: E402

from dashboard.components import common, theme  # noqa: E402
from dashboard.components.gpu_cluster import cluster_figure, node_counts  # noqa: E402

ctl = common.page("Cluster Overview", "🟦")
N, G = ctl.cfg.min_nodes, ctl.cfg.num_gpus

st.title("Cluster Overview")
st.markdown(theme.badge("proto"), unsafe_allow_html=True)
st.caption(f"Configuration verified from the simulator call: {N} workers × {G} GPUs = {N * G} modelled GPUs "
           "(simulator.py --min-nodes/--num-gpus; paper Sec. VII-A). The training/inference halves are the paper's "
           "nominal split. In this code only the Aryl path and some bookkeeping use `n // 2`; ATS-I may place "
           "inference on any worker.")

snaps = ctl.snapshots
follow = st.toggle("Follow live state", value=True)
if follow or len(snaps) == 1:
    idx = len(snaps) - 1
else:
    idx = st.slider("Replay position (scheduling step)", 0, len(snaps) - 1, len(snaps) - 1,
                    help="Each position is a state the simulator actually reached. 0 = before any job arrived.")
snap = snaps[idx]
live = idx == len(snaps) - 1
st.markdown(f"**{'Live state' if live else 'Replay'}** at simulated t = **{snap['clock']:,} s** "
            f"({snap['clock'] / 60:.1f} min)")

bd = snap["breakdown"]
used = sum(bd.values())
m = st.columns(6)
m[0].metric("Idle GPUs", N * G - used)
m[1].metric("Training", bd["training"])
m[2].metric("Training (rescaling)", bd["training_rescaling"])
m[3].metric("Inference running", bd["inference_running"])
m[4].metric("PROTECT", bd["inference_protect"])
m[5].metric("SLEEP", bd["inference_sleep"])

jobs_here = sorted(snap["allocations"])
hl = st.selectbox("Highlight a job", [""] + jobs_here, format_func=lambda j: j or "(none)")
left, right = st.columns([3, 2])
with left:
    st.markdown(theme.legend_html(), unsafe_allow_html=True)
    ev = st.plotly_chart(cluster_figure(snap, N, G, hl), use_container_width=True,
                         on_select="rerun", selection_mode="points", key=f"grid-{idx}")
    st.caption("Per-worker GPU counts are the simulator's. The simulator does not identify individual GPUs, "
               "so slot order within a worker is illustrative.")
    pts = (ev or {}).get("selection", {}).get("points", []) if isinstance(ev, dict) or hasattr(ev, "get") else []
    if pts:
        st.session_state["selected_worker"] = int(pts[0]["customdata"][0])

with right:
    w = st.session_state.get("selected_worker")
    w = st.selectbox("Worker details", list(range(N)), index=w if w is not None else 0,
                     format_func=lambda n: f"Worker {n}")
    counts = node_counts(snap, N, G)[w]
    st.markdown(f'<div class="db-card"><b>Worker {w}</b><br>'
                + "<br>".join(f"{theme.LABELS[k]}: <b>{v}</b>" for k, v in counts.items() if v) + "</div>",
                unsafe_allow_html=True)
    rows = []
    for job, alloc in snap["allocations"].items():
        c = Counter(alloc).get(w, 0)
        if c:
            p = snap["pods"].get(job, {})
            rows.append({"job/pod": job, "GPUs on worker": c, "total GPUs": len(alloc),
                         "state": p.get("status", "training"), "serving": p.get("curr_job")})
    st.dataframe(pandas.DataFrame(rows), hide_index=True, use_container_width=True)

st.subheader("GPU allocation per job")
rows = []
for job, alloc in sorted(snap["allocations"].items()):
    p = snap["pods"].get(job)
    rows.append({
        "job / pod": job,
        "class": "inference" if job.startswith("inference") else "training",
        "state": p["status"] if p else ("rescale delay" if job in snap.get("rescaling", []) else "running"),
        "GPUs": len(alloc),
        "workers": ", ".join(f"w{k}×{v}" for k, v in sorted(Counter(alloc).items())),
    })
df = pandas.DataFrame(rows)
if len(df):
    t1, t2 = st.tabs(["Training", "Inference pods"])
    t1.dataframe(df[df["class"] == "training"], hide_index=True, use_container_width=True)
    t2.dataframe(df[df["class"] == "inference"], hide_index=True, use_container_width=True)
else:
    st.info("No GPUs are allocated yet. Advance the simulation on **Interactive Simulation**.")

if not live and snap["events"]:
    with st.expander(f"Events at this step ({len(snap['events'])})", expanded=True):
        st.dataframe(pandas.DataFrame(snap["events"])[["type", "job", "detail"]], hide_index=True,
                     use_container_width=True)
