import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

import streamlit as st  # noqa: E402

from dashboard.components import common, theme  # noqa: E402
from dashboard.engine.sim_bridge import inference_models, training_applications  # noqa: E402
from dashboard.engine.workload_manager import InjectionError, make_row  # noqa: E402

ctl = common.page("Job Management", "📋")
c = ctl.cluster

st.title("Job Management")
st.markdown(theme.badge("proto"), unsafe_allow_html=True)
st.caption("A submitted job is added to the running research `Cluster` exactly as `Cluster.__init__` builds a "
           "workload row (dashboard/engine/workload_manager.py::inject_job). This is equivalent to appending the "
           "row to the workload CSV. It then goes through the normal simulator workflow: arrival event → ATS-T at "
           "the next 60 s tick (training) or ATS-I at the next event (inference).")

if ctl.blocked():
    st.warning("This simulation has finished. Reset it (Interactive Simulation page) or create a new one "
               "(Home page) before submitting jobs.")

ft, fi = st.columns(2)
with ft:
    st.subheader("Submit a training job")
    with st.form("train"):
        app = st.selectbox("Application (model + dataset trace)", training_applications(),
                           help="Throughput and convergence come from traces/<app>/ via applications.py")
        n_existing = sum(1 for j in c.jobs if j.app == app)
        name = st.text_input("Job name", f"{app}-ui{len(ctl.injected_rows) + 1}")
        t = st.number_input("Arrival time (simulated s)", min_value=c.clock + 1, value=c.clock + 1, step=1)
        extra = {}
        if ctl.cfg.policy == "afs":
            extra["num_replicas"] = st.number_input("num_replicas (read by AFS)", 1, 64, 4)
            extra["batch_size"] = st.number_input("batch_size (read by AFS)", 1, 65536, 256)
        else:
            st.caption(f"Policy `{ctl.cfg.policy}` ignores num_replicas/batch_size (simulator.py:458-461). "
                       "ATS-T chooses the replica count, and training length comes from the application trace. "
                       "There is no duration field.")
        sub_t = st.form_submit_button("Submit training job", type="primary", disabled=ctl.blocked())
    if sub_t:
        try:
            ctl.inject(make_row("training", name, app, int(t), **extra))
            st.success(f"{name} queued: arrives at t={int(t)} s and is considered by ATS-T at the next 60 s tick.")
        except InjectionError as e:
            st.error(str(e))

with fi:
    st.subheader("Submit inference requests")
    with st.form("infer"):
        model = st.selectbox("Model", inference_models())
        existing = sorted({j.app for j in c.jobs if j.inference and j.app.startswith(model + "-")})
        app_id = st.selectbox("Service instance (application id)", existing + ["new instance"],
                              help="Warm-pod reuse only happens within the same application id (simulator.py:200-236).")
        if app_id == "new instance":
            k = 1 + max([int(a.rsplit("-", 1)[1]) for a in existing] + [0])
            app_id = f"{model}-{k}"
        t = st.number_input("First arrival (simulated s)", min_value=c.clock + 1, value=c.clock + 1, step=1, key="it")
        dur = st.number_input("Service duration per request (s)", 1, 60, 5,
                              help="Workload files use 1–9 s (small), 1–19 (middle), 1–29 (large).")
        n = st.number_input("Number of requests", 1, 50, 1)
        gap = st.number_input("Spacing between requests (s)", 0, 600, 0)
        sub_i = st.form_submit_button("Submit inference request(s)", type="primary", disabled=ctl.blocked())
    if sub_i:
        ok = 0
        for i in range(int(n)):
            nm = f"inference-{model.replace('infer-', '')}-ui{len(ctl.injected_rows) + 1}"
            try:
                ctl.inject(make_row("inference", nm, app_id, int(t) + i * int(gap), duration=float(dur)))
                ok += 1
            except InjectionError as e:
                st.error(str(e))
                break
        if ok:
            st.success(f"{ok} request(s) for {app_id} queued from t={int(t)} s. Each is one replica on one GPU.")

st.divider()
jt = ctl.job_table()
st.subheader("Jobs")
counts = jt["status"].value_counts()
cols = st.columns(6)
for col, s in zip(cols, ["not yet arrived", "pending", "running", "rescaling", "completed"]):
    col.metric(s.capitalize(), int(counts.get(s, 0)))
cols[5].metric("Submitted via UI", int(jt["injected"].sum()))

pend = jt[jt["status"] == "pending"].copy()
if len(pend):
    pend["waiting_s"] = c.clock - pend["submitted_s"]
    st.markdown("**Queue: arrived but holding no GPU**")
    st.dataframe(pend[["job", "class", "application", "submitted_s", "waiting_s", "restarts"]]
                 .sort_values("submitted_s"), hide_index=True, use_container_width=True)

cls = st.radio("Class", ["training", "inference", "all"], horizontal=True)
view = jt if cls == "all" else jt[jt["class"] == cls]
tabs = st.tabs(["Running / rescaling", "Pending", "Completed", "Not yet arrived", "Submitted via UI"])
sel = [view["status"].isin(["running", "rescaling"]), view["status"] == "pending", view["status"] == "completed",
       view["status"] == "not yet arrived", view["injected"]]
for tab, m in zip(tabs, sel):
    with tab:
        st.dataframe(view[m], hide_index=True, use_container_width=True)
st.caption("queue_wait_s: training = first non-empty placement time − submission (placement_update_history). "
           "Inference = start_execute_time − submission. jct_s = completion − submission. "
           "rescale_left_s = remaining modelled rescale delay.")
