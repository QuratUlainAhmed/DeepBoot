"""Interactive Simulation: play / step the unmodified research simulator and see each decision.

Everything shown is read from SimulationController (simulation_controller.py):
snapshots (Cluster.allocations + pod table), step records (events derived
from allocation diffs) and instrumentation decisions (ATS-T / ATS-I wrappers).
"""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

import time  # noqa: E402

import pandas  # noqa: E402
import streamlit as st  # noqa: E402

from dashboard.components import common, theme  # noqa: E402
from dashboard.components.charts import allocation_area, event_timeline  # noqa: E402
from dashboard.components.gpu_cluster import cluster_html, node_counts  # noqa: E402
from dashboard.components.job_cards import (event_line, fmt_alloc, narrate_decision, step_story,  # noqa: E402
                                            story_card_html)
from dashboard.engine import state_manager  # noqa: E402

ctl = common.page("Interactive Simulation", "⏯️", live_sidebar=False)
N, G = ctl.cfg.min_nodes, ctl.cfg.num_gpus
TOTAL = N * G
SPEEDS = [1, 2, 5, 10, 25, 100]


def status() -> str:
    if ctl.error:
        return "error"
    if ctl.is_complete():
        return "completed"
    if ctl.playing:
        return "running"
    return "ready" if ctl.steps_executed == 0 else "paused"


def active_counts():
    c = ctl.cluster
    tr = inf = 0
    for j in c.jobs:
        if j.submission_time <= c.clock and not (j.completion_time is not None and j.completion_time <= c.clock):
            if j.inference:
                inf += 1
            else:
                tr += 1
    return tr, inf


# ------------------------------------------------------------------ page body
def view():
    header = st.container()
    metrics = st.container()

    # ---- C. controls (handled before rendering so every panel shows the post-action state)
    b = st.columns([1.15, 1.15, 1, 4.2])
    play_label = "⏸ Pause" if ctl.playing else ("▶ Play" if ctl.steps_executed == 0 else "▶ Resume")
    if b[0].button(play_label, type="primary", disabled=ctl.blocked() and not ctl.playing,
                   use_container_width=True, key="play"):
        ctl.playing = not ctl.playing
        st.rerun()  # full rerun: re-arms (or stops) the auto-refresh timer
    stepped = False
    if b[1].button("⏭ Next Event", disabled=ctl.blocked(), use_container_width=True, key="next",
                   help="Advance the simulator's 1 s clock until event_update() triggers the next scheduling step."):
        if ctl.playing:
            ctl.playing = False
            ctl.next_event()
            st.rerun()
        ctl.next_event()
        stepped = True
    if b[2].button("↺ Reset", use_container_width=True, key="reset",
                   help="Rebuild the same scenario at t = 0 (affects every open tab: one simulation per server)."):
        state_manager.reset_simulation()
        st.session_state.pop("_anim_step", None)
        st.rerun()

    with st.expander("Advanced controls"):
        a1, a2, a3, a4 = st.columns([1.4, 1.2, 1, 0.8])
        speed = a1.select_slider("Playback speed (scheduling steps per second)", SPEEDS,
                                 value=2, key="speed")
        to_end = a2.toggle("Run until all jobs complete", value=False)
        target = a3.number_input("…or until simulated time (s)", min_value=ctl.cluster.clock + 1,
                                 value=ctl.cluster.clock + 600, step=60, disabled=to_end)
        a4.write("")
        if a4.button("Run", use_container_width=True, disabled=ctl.blocked()):
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
            bar.progress(1.0, text=f"stopped at t = {ctl.cluster.clock:,} s" + (" (all jobs complete)" if ctl.is_complete() else ""))
            stepped = True
        st.caption("Fast-forward runs the same loop without animation; the cluster jumps to the final state.")

    # ---- auto-play
    if ctl.playing and not ctl.blocked() and not stepped:
        for _ in range(speed):
            if ctl.next_event() is None:
                break
    if ctl.playing and ctl.blocked():
        ctl.playing = False
        st.rerun()  # stop the timer and refresh the Play button

    c = ctl.cluster
    snap = ctl.snapshots[-1]
    prev = ctl.snapshots[-2] if len(ctl.snapshots) > 1 else None
    rec = getattr(ctl, "last_step", None) if ctl.steps_executed else None
    animate = st.session_state.get("_anim_step") != ctl.steps_executed
    st.session_state["_anim_step"] = ctl.steps_executed

    # ---- A. header
    sc = state_manager.store().get("scenario") or {}
    stt = status()
    with header:
        st.markdown("## DeepBoot Simulation")
        st.markdown(
            f'<div class="db-status"><span class="db-pill {stt}">{stt}</span>'
            f'<span>Simulated time <b>{c.clock:,} s</b> ({c.clock / 60:.1f} min)</span>'
            f'<span>Scenario <b>{sc.get("label", "")}</b></span>'
            f'<span class="db-mono">policy={ctl.cfg.policy} · AFE={ctl.cfg.AFE} · AISS={ctl.cfg.AISS} · '
            f'{"RANDOM" if ctl.cfg.random_allocate else "ATS-I"}{" · ARYL" if ctl.cfg.ARYL else ""}</span></div>',
            unsafe_allow_html=True)

    # ---- B. four metrics
    used = sum(len(v) for v in snap["allocations"].values())
    used_prev = sum(len(v) for v in prev["allocations"].values()) if prev else used
    tr, inf = active_counts()
    with metrics:
        m = st.columns(4)
        m[0].metric("Total GPUs", TOTAL, help=f"{N} workers × {G} GPUs (simulator --min-nodes {N} --num-gpus {G}).")
        m[1].metric("GPUs allocated", f"{used} / {TOTAL}", (used - used_prev) if rec and used != used_prev else None)
        m[2].metric("Active training jobs", tr, help="Arrived and not completed (running, rescaling or pending).")
        m[3].metric("Active inference requests", inf,
                    help="Arrived and not completed (running or queued). Warm pods without a request are not counted.")

    # ---- D. cluster
    st.markdown("#### GPU cluster")
    focus = {e["job"] for e in (rec or {}).get("events", [])
             if e["type"] not in ("completion", "training-released", "inference-release", "pod-removed")}
    st.markdown(theme.legend_html(), unsafe_allow_html=True)
    st.markdown(cluster_html(snap, N, G, prev=prev if rec else None, focus=focus, animate=animate and rec is not None),
                unsafe_allow_html=True)
    st.caption("Per-worker GPU counts and owners come directly from the simulator's allocation "
               "(`Cluster.allocations`: job → list of worker ids). The simulator does not identify individual GPUs, so "
               "the position of a slot inside a worker is illustrative. Hover a slot for details; outlined slots belong "
               "to jobs touched by the latest step.")
    with st.expander("Worker details"):
        w = st.selectbox("Worker", list(range(N)), format_func=lambda n: f"Worker {n}", key="sim_worker")
        cnt = node_counts(snap, N, G)[w]
        st.markdown(" · ".join(f"{theme.LABELS[k]}: **{v}**" for k, v in cnt.items() if v))
        rows = []
        for job, alloc in sorted(snap["allocations"].items()):
            k = alloc.count(w)
            if k:
                p = snap["pods"].get(job, {})
                rows.append({"job / pod": job, "GPUs on this worker": k, "GPUs total": len(alloc),
                             "all workers": fmt_alloc(alloc), "state": p.get("status", "training"),
                             "serving": p.get("curr_job")})
        if rows:
            st.dataframe(pandas.DataFrame(rows), hide_index=True, use_container_width=True)
        else:
            st.caption("No GPU on this worker is allocated.")

    # ---- What's happening inside DeepBoot?
    st.markdown("#### What's happening inside DeepBoot?")
    left, right = st.columns([1.35, 1])
    with left:
        if rec is None:
            st.markdown(story_card_html({"tag": "Ready", "acc": "#94A3B8", "title": "The cluster is empty.",
                                         "kv": [("Workload", f"{len(c.jobs)} jobs, first arrival at "
                                                 f"t = {int(ctl.initial_workload['time'].min())} s")],
                                         "note": "Press <b>Next Event</b> to advance to the first scheduling step, "
                                                 "or <b>Play</b> to watch continuously."}, main=True),
                        unsafe_allow_html=True)
        else:
            cards = step_story(rec, ctl)
            st.markdown(f'<div class="db-delta">Step at <b>t = {rec["clock"]:,} s</b> · '
                        f'{"60 s training tick" if rec["tick"] else "event-triggered"} · '
                        f'<code>{rec["path"]}</code></div>', unsafe_allow_html=True)
            if prev:
                parts = []
                b0, b1 = prev["breakdown"], snap["breakdown"]
                idle0, idle1 = TOTAL - sum(b0.values()), TOTAL - sum(b1.values())
                for lbl, x0, x1 in [("Idle", idle0, idle1)] + [(theme.LABELS[k], b0[k], b1[k]) for k in b1]:
                    if x0 != x1:
                        cls = "up" if x1 > x0 else "dn"
                        parts.append(f'<span class="it">{lbl} <b>{x0}</b> → <b class="{cls}">{x1}</b></span>')
                if parts:
                    st.markdown('<div class="db-delta">GPU states this step: ' + " · ".join(parts) + "</div>",
                                unsafe_allow_html=True)
            if cards:
                st.markdown(story_card_html(cards[0], main=True), unsafe_allow_html=True)
                for card in cards[1:3]:
                    st.markdown(story_card_html(card), unsafe_allow_html=True)
                if len(cards) > 3:
                    st.caption(f"+ {len(cards) - 3} more: " + ", ".join(x["tag"] for x in cards[3:]))
            else:
                st.markdown(story_card_html({"tag": "Step", "acc": "#94A3B8", "title": "Scheduler ran; nothing changed.",
                                             "kv": [("Path", f"<code>{rec['path']}</code>")], "note": None}, main=True),
                            unsafe_allow_html=True)
    with right:
        if ctl.alloc_series:
            fig = allocation_area(pandas.DataFrame(ctl.alloc_series), TOTAL)
            fig.update_layout(height=340, title=dict(text="GPU allocation over time", font=dict(size=13)),
                              xaxis_title="Simulated time (min)", margin=dict(l=10, r=10, t=36, b=10),
                              legend=dict(orientation="h", y=-0.28, yanchor="top", font=dict(size=10)))
            st.plotly_chart(fig, use_container_width=True, key=f"area-{ctl.steps_executed}")
        else:
            st.caption("The allocation chart appears after the first step.")

    # ---- Why did DeepBoot make this decision?
    with st.expander("Why did DeepBoot make this decision?"):
        if rec is None:
            st.caption("No decision yet.")
        else:
            decisions_tab(rec, snap, prev)

    # ---- Advanced → Event history & logs
    with st.expander("Advanced → Event History & Logs"):
        history()


def decisions_tab(rec, snap, prev):
    t_atst, t_atsi, t_afe, t_aiss, t_alloc = st.tabs(["ATS-T", "ATS-I", "AFE / rescale", "AISS", "Allocation snapshot"])
    decs = rec.get("decisions", [])
    evs = rec.get("events", [])
    with t_atst:
        recs = [d for d in decs if d["kind"] == "ATS-T"]
        if not recs:
            st.caption(f"ATS-T did not run in this step (path: `{rec['path']}`). "
                       + ("ATS-T runs at every training tick." if ctl.cfg.policy == "dp" else
                          f"Policy `{ctl.cfg.policy}` is not instrumented at decision level."))
        for d in recs:
            st.markdown(narrate_decision(d))
            ks = d.get("knapsack") or {}
            chosen = ks.get("chosen_replicas", [])
            rows = []
            for i, j in enumerate(d.get("jobs", [])):
                vals = ks.get("values", [])
                rows.append({"job": j["job"], "age (s)": j["age"], "restarts": j["num_restarts"],
                             "restart penalty": j["penalty_factor_derived"], "max replicas": j["max_replicas"],
                             "GPUs before": j["prev_gpus"], "GPUs chosen": chosen[i] if i < len(chosen) else None,
                             "best option value": (max(vals[i]) if i < len(vals) and vals[i] else None),
                             "workers before": fmt_alloc(d["prev_alloc"].get(j["job"], [])),
                             "workers after": fmt_alloc(d["new_alloc"].get(j["job"], []))})
            st.dataframe(pandas.DataFrame(rows), hide_index=True, use_container_width=True)
            st.caption(f"Free GPUs per worker given to ATS-T (capacity {d['capacity']}): "
                       + ", ".join(f"w{k}:{v}" for k, v in sorted(d["free_gpus_by_node"].items()) if v))
            st.caption("Restart penalty = max(age − restarts·10, 0)/(age + 10), recomputed for display from the "
                       "inputs (mirrors dp.py). Values row = knapsack values per replica count, from max_value_dp.")
    with t_atsi:
        recs = [d for d in decs if d["kind"] in ("ATS-I", "RANDOM")]
        active = [d for d in recs if d.get("branches") or d.get("placed")]
        if not active:
            st.caption("No inference request was placed in this step." if recs else "ATS-I did not run in this step.")
        for d in active:
            st.markdown(narrate_decision(d))
            if d.get("branches"):
                st.dataframe(pandas.DataFrame(d["branches"]), hide_index=True, use_container_width=True)
            if d.get("placed"):
                st.dataframe(pandas.DataFrame([{"request": k, "workers": fmt_alloc(v)} for k, v in d["placed"].items()]),
                             hide_index=True, use_container_width=True)
            if d.get("reclaims"):
                st.markdown("**Reclaimed from training**")
                st.dataframe(pandas.DataFrame(d["reclaims"]), hide_index=True, use_container_width=True)
            if d.get("reclaim_search"):
                st.markdown("**Reclaim search** (each candidate = one feasible (training job, worker) GPU)")
                st.dataframe(pandas.DataFrame(d["reclaim_search"]), hide_index=True, use_container_width=True)
    with t_afe:
        rs = [e for e in evs if e["type"].startswith("training-") and e["type"] != "training-released"]
        if not rs:
            st.caption("No training allocation changed in this step.")
        else:
            st.markdown(f"Rescale delay model: **{'AFE (--AFE 1)' if ctl.cfg.AFE else 'stop-resume baseline (--AFE 0)'}**. "
                        "The delay is computed by `Job.calculate_rescale_time` and training progress pauses while it counts down.")
            st.dataframe(pandas.DataFrame([{"job": e["job"], "change": e["type"].replace("training-", ""),
                                            "GPUs before": e.get("gpus_before"), "GPUs after": e.get("gpus_after"),
                                            "modelled delay (s)": e.get("rescale_delay"), "detail": e["detail"]} for e in rs]),
                         hide_index=True, use_container_width=True)
            st.caption("State preservation and synchronisation (paper Sec. V) are abstracted into this delay; "
                       "the simulator records no separate save/load or sync events.")
    with t_aiss:
        pe = [e for e in evs if e["type"] in ("pod-state", "pod-removed", "warm-reuse")]
        if pe:
            st.dataframe(pandas.DataFrame(pe)[["type", "job", "detail"]], hide_index=True, use_container_width=True)
        else:
            st.caption("No pod lifecycle transition was recorded in this step.")
        if snap["pods"]:
            st.markdown("**All inference pods now**")
            st.dataframe(pandas.DataFrame([{"pod": k, **v} for k, v in snap["pods"].items()]),
                         hide_index=True, use_container_width=True)
    with t_alloc:
        a, b = st.columns(2)
        for col, s, lbl in ((a, prev, "Before this step"), (b, snap, "After this step")):
            col.markdown(f"**{lbl}** (t = {s['clock']:,} s)" if s else f"**{lbl}**")
            if s and s["allocations"]:
                col.dataframe(pandas.DataFrame([{"job / pod": k, "GPUs": len(v), "workers": fmt_alloc(v)}
                                                for k, v in sorted(s["allocations"].items())]),
                              hide_index=True, use_container_width=True)
            else:
                col.caption("No allocations.")
    st.caption("Full decision history with knapsack values and reclaim search: page **ATS & AFE Visualization**.")


def history():
    if not ctl.events:
        st.caption("No events yet.")
        return
    df = pandas.DataFrame(ctl.events)
    types = sorted(df["type"].unique())
    pick = st.multiselect("Event types", types, default=[t for t in types if t not in ("pod-state",)], key="ev_types")
    view_df = df[df["type"].isin(pick)]
    st.plotly_chart(event_timeline(view_df), use_container_width=True, key=f"tl-{ctl.steps_executed}")
    st.dataframe(view_df.iloc[::-1][["clock", "type", "job", "detail"]].head(500), hide_index=True,
                 use_container_width=True, height=300)
    st.caption(f"{len(df):,} events recorded over {ctl.steps_executed:,} scheduling steps (newest first, 500 shown).")
    rec = getattr(ctl, "last_step", None)
    if rec is not None and ctl.steps_executed:
        st.markdown("**Latest step, raw**")
        for e in rec["events"][:30]:
            st.markdown(event_line(e))


st.fragment(run_every=1.0 if ctl.playing and not ctl.blocked() else None)(view)()
