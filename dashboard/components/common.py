"""Per-page setup: page config, theme, sidebar status."""
from __future__ import annotations

import streamlit as st

from dashboard.components import theme
from dashboard.engine import state_manager


def page(title: str, icon: str = "🧭", live_sidebar: bool = True):
    st.set_page_config(page_title=f"{title} · DeepBoot", page_icon=icon, layout="wide")
    theme.apply()
    ctl = state_manager.ensure_default()
    with st.sidebar:
        st.markdown("### DeepBoot simulator")
        sc = state_manager.store().get("scenario") or {}
        st.caption(sc.get("label", ""))
        st.markdown(
            f'<div class="db-mono">policy={ctl.cfg.policy} AFE={ctl.cfg.AFE} AISS={ctl.cfg.AISS} '
            f'ARYL={ctl.cfg.ARYL} random={ctl.cfg.random_allocate} protect×{ctl.cfg.protect_times}</div>',
            unsafe_allow_html=True)
        if live_sidebar:
            c1, c2 = st.columns(2)
            c1.metric("Sim. clock", f"{ctl.cluster.clock:,} s")
            c2.metric("Steps", f"{ctl.steps_executed:,}")
        else:
            st.caption("Live clock and step count are shown in the main panel.")
        st.caption("Done ✓" if ctl.is_complete() else ("Stopped: research-code error" if ctl.error else "In progress"))
        st.caption("One shared simulation per server. Change it on the Home page.")
    if ctl.error:
        st.error(f"The research simulator raised **{ctl.error['type']}** at simulated t = {ctl.error['clock']} s: "
                 f"{ctl.error['message'] or '(no message)'}. The traceback shows where in the research code it was raised. "
                 "The dashboard does not catch or alter it inside the simulator. The simulation state may be partially "
                 "updated, so stepping is disabled. Reset or choose another scenario.")
        with st.expander("Traceback"):
            st.code(ctl.error["traceback"])
    return ctl
