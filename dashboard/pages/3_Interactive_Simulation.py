import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

import time  # noqa: E402

import pandas  # noqa: E402
import streamlit as st  # noqa: E402

from dashboard.components import common, theme  # noqa: E402
from dashboard.components.charts import event_timeline  # noqa: E402
from dashboard.components.gpu_cluster import cluster_figure  # noqa: E402
from dashboard.components.job_cards import event_line, summarize_step  # noqa: E402
from dashboard.engine import state_manager  # noqa: E402

ctl = common.page("Interactive Simulation", "⏯️", live_sidebar=False)
N, G = ctl.cfg.min_nodes, ctl.cfg.num_gpus

st.title("Interactive Simulation")
st.markdown(theme.badge("proto"), unsafe_allow_html=True)
st.caption("One **step** = advancing the simulator's 1-second clock until `event_update()` triggers a scheduling call "
           "(a 60 s training tick, a job arrival or finish, or a waiting inference request with a reusable pod). "
           "This is exactly how `simulate()` advances. Seconds with no event are skipped, but their GPU counters "
           "are still recorded.")

b = st.columns([1, 1, 1, 1, 1.4, 1.6])
if b[0].button("▶ Start / Resume", type="primary", disabled=ctl.blocked(), use_container_width=True):
    ctl.playing = True
if b[1].button("⏸ Pause", use_container_width=True):
    ctl.playing = False
if b[2].button("⏭ Next step", disabled=ctl.blocked(), use_container_width=True):
    ctl.playing = False
    ctl.next_event()
confirm = b[4].checkbox("confirm reset")
if b[3].button("↺ Reset", disabled=not confirm, use_container_width=True):
    state_manager.reset_simulation()
    st.rerun()
speed = b[5].select_slider("Speed (steps per refresh)", [1, 2, 5, 10, 25, 100], value=2)

with st.expander("Run until… (fast-forward; use this for the full trace)"):
    r1, r2, r3 = st.columns([1.2, 1, 1])
    to_end = r1.toggle("Until all jobs complete", value=False)
    target = r2.number_input("Target simulated time (s)", min_value=ctl.cluster.clock + 1,
                             value=ctl.cluster.clock + 600, step=60, disabled=to_end)
    if r3.button("Run", use_container_width=True, disabled=ctl.blocked()):
        ctl.playing = False
        goal = None if to_end else int(target)
        bar = st.progress(0.0, text="running…")
        start_clock, t0 = ctl.cluster.clock, time.time()
        last = max(int(ctl.initial_workload["time"].max()), 1)
        while not ctl.blocked() and (goal is None or ctl.cluster.clock < goal):
            ctl.run_until(goal, wall_budget_s=1.5)
            frac = ((ctl.cluster.clock - start_clock) / (goal - start_clock)) if goal else min(ctl.cluster.clock / (last * 2.5), 0.99)
            bar.progress(min(max(frac, 0.0), 1.0),
                         text=f"t = {ctl.cluster.clock:,} s · {ctl.steps_executed:,} steps · {time.time() - t0:.0f} s wall")
        bar.progress(1.0, text=f"stopped at t = {ctl.cluster.clock:,} s"
                     + (" (all jobs complete)" if ctl.is_complete() else ""))
        st.caption("Navigating away or pressing Stop interrupts the run; state stays consistent at the last full step.")


def live_view():
    if ctl.playing and not ctl.blocked():
        for _ in range(speed):
            if ctl.next_event() is None:
                break
    if ctl.blocked():
        ctl.playing = False
    c = ctl.cluster
    k = st.columns(5)
    k[0].metric("Simulated time", f"{c.clock:,} s", f"{c.clock / 3600:.2f} h", delta_color="off")
    k[1].metric("Scheduling steps", f"{ctl.steps_executed:,}")
    done = len(c.finish_job_set)
    k[2].metric("Jobs completed", f"{done} / {len(c.jobs)}")
    used = sum(len(v) for v in c.allocations.values())
    k[3].metric("GPUs allocated", f"{used} / {N * G}")
    k[4].metric("State", "error" if ctl.error else "complete" if ctl.is_complete() else ("playing" if ctl.playing else "paused"))

    left, right = st.columns([1.1, 1])
    with left:
        st.markdown("#### Cluster")
        st.markdown(theme.legend_html(), unsafe_allow_html=True)
        st.plotly_chart(cluster_figure(ctl.snapshots[-1], N, G), use_container_width=True,
                        key=f"live-{ctl.steps_executed}")
    with right:
        st.markdown("#### What just happened")
        rec = getattr(ctl, "last_step", None)
        if rec is None:
            st.info("Nothing has happened yet. Press **Next step** to let the first job arrive.")
        else:
            st.markdown(f'<div class="db-card">Step at <b>t = {rec["clock"]:,} s</b> (Δ {rec["interval"]} s, '
                        f'{"60 s training tick" if rec["tick"] else "event-triggered"})</div>', unsafe_allow_html=True)
            for line in summarize_step(rec):
                st.markdown(line)
            evs = rec["events"]
            order = ["arrival", "pod-state", "pod-removed", "warm-reuse", "inference-placement", "training-start",
                     "training-scale-up", "training-scale-down", "training-migrate", "training-preempted",
                     "inference-release", "training-released", "completion"]
            for e in sorted(evs, key=lambda e: order.index(e["type"]) if e["type"] in order else 99)[:30]:
                st.markdown(event_line(e))
            if len(evs) > 30:
                st.caption(f"… {len(evs) - 30} more in the log below")

    st.markdown("#### Event log")
    if ctl.events:
        df = pandas.DataFrame(ctl.events)
        types = sorted(df["type"].unique())
        pick = st.multiselect("Event types", types, default=[t for t in types if t not in ("pod-state",)])
        view = df[df["type"].isin(pick)]
        st.plotly_chart(event_timeline(view), use_container_width=True, key=f"tl-{ctl.steps_executed}")
        st.dataframe(view.iloc[::-1][["clock", "type", "job", "detail"]].head(500), hide_index=True,
                     use_container_width=True, height=300)
    else:
        st.caption("No events yet.")


st.fragment(run_every=1.0 if ctl.playing and not ctl.blocked() else None)(live_view)()
