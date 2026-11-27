"""Headless render of every Streamlit page (streamlit.testing AppTest)."""
import os

import pytest
from streamlit.testing.v1 import AppTest

DASH = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
PAGES = ["app.py"] + [os.path.join("pages", p) for p in sorted(os.listdir(os.path.join(DASH, "pages"))) if p.endswith(".py")]


@pytest.mark.parametrize("page", PAGES)
def test_page_renders_without_exception(page):
    at = AppTest.from_file(os.path.join(DASH, page), default_timeout=120)
    at.run()
    assert not at.exception, [e.value for e in at.exception]


def test_next_step_button_advances_real_simulation():
    at = AppTest.from_file(os.path.join(DASH, "pages", "3_Interactive_Simulation.py"), default_timeout=120)
    at.run()
    from dashboard.engine import state_manager
    ctl = state_manager.controller()
    before = ctl.steps_executed
    next_btn = [b for b in at.button if "Next Event" in b.label][0]
    next_btn.click().run()
    assert not at.exception
    assert ctl.steps_executed == before + 1
    assert ctl.cluster.clock > 0


def test_training_submission_reaches_simulator():
    at = AppTest.from_file(os.path.join(DASH, "pages", "2_Job_Management.py"), default_timeout=120)
    at.run()
    from dashboard.engine import state_manager
    ctl = state_manager.controller()
    n = len(ctl.cluster.jobs)
    at.button[0].click().run()  # first form submit = training job
    assert not at.exception
    assert len(ctl.cluster.jobs) == n + 1
    assert ctl.injected_rows and ctl.injected_rows[-1]["name"] in ctl.cluster.job_dict
