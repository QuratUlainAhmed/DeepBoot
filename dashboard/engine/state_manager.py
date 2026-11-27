"""Server-wide simulation store + per-session UI state.

Policy (approved): ONE active simulation per Streamlit server. The research
simulator keeps its flags in module globals, so two concurrent simulations in
one process could interfere. The single SimulationController lives in a
`st.cache_resource` store shared by all sessions; every mutation goes through
the controller's re-entrant lock and re-applies its flags first.

Per-session values (selected worker, replay position, play flag) live in
`st.session_state`. A `generation` counter detects that the simulation was
replaced or reset (possibly from another browser tab) so stale per-session
selections are discarded instead of pointing at a different run.
"""
from __future__ import annotations

import threading
from typing import Optional

import streamlit as st

from .sim_bridge import SimConfig
from .simulation_controller import SimulationController
from .workload_manager import load_workload, reduced_scenario


@st.cache_resource
def _store() -> dict:
    return {"controller": None, "generation": 0, "lock": threading.Lock(), "scenario": None}


def store() -> dict:
    return _store()


def controller() -> Optional[SimulationController]:
    return _store()["controller"]


def generation() -> int:
    return _store()["generation"]


def new_simulation(workload, cfg: SimConfig, scenario: dict) -> SimulationController:
    s = _store()
    with s["lock"]:
        old = s["controller"]
        if old is not None:
            old.playing = False
        ctl = SimulationController(workload, cfg, label=scenario.get("label", ""))
        s["controller"] = ctl
        s["scenario"] = scenario
        s["generation"] += 1
    return ctl


def reset_simulation() -> None:
    s = _store()
    with s["lock"]:
        if s["controller"] is not None:
            s["controller"].reset()
            s["generation"] += 1


def ensure_default() -> SimulationController:
    """Create the default demo (reduced small.csv, DeepBoot defaults) if none exists."""
    ctl = controller()
    if ctl is None:
        w = reduced_scenario(load_workload("small"))
        ctl = new_simulation(w, SimConfig(policy="dp", workload="reduced small.csv"),
                             {"label": "Reduced small.csv (8 training jobs, inference ≤ 1800 s)", "base": "small",
                              "n_training": 8, "window": 1800, "exclude_imagenet": True})
    sync_session()
    return ctl


def sync_session() -> None:
    """Drop per-session selections that belong to an older simulation."""
    g = generation()
    if st.session_state.get("_gen") != g:
        for k in ("selected_worker", "replay_idx", "selected_decision"):
            st.session_state.pop(k, None)
        st.session_state["_gen"] = g
