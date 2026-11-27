"""The dashboard controller (with instrumentation installed) must reproduce the
unmodified CLI simulator bit-for-bit on the same workload and flags."""
import os

import pytest

from dashboard.engine.sim_bridge import SimConfig
from .conftest import run_cli, run_controller

CASES = [
    ("dp ATS-I AFE0", dict(policy="dp"), ["--policy", "dp", "--AFE", "0", "--AISS", "1"]),
    ("dp ATS-I AFE1", dict(policy="dp", AFE=1), ["--policy", "dp", "--AFE", "1", "--AISS", "1"]),
    ("dp AISS0", dict(policy="dp", AISS=0), ["--policy", "dp", "--AFE", "0", "--AISS", "0"]),
    ("dp RANDOM", dict(policy="dp", random_allocate=1), ["--policy", "dp", "--random_allocate", "1"]),
    ("dp ARYL", dict(policy="dp", ARYL=1), ["--policy", "dp", "--ARYL", "1"]),
    ("afs ARYL AFE1", dict(policy="afs", ARYL=1, AFE=1), ["--policy", "afs", "--ARYL", "1", "--AFE", "1"]),
    ("dp protect x2", dict(policy="dp", protect_times=2.0), ["--policy", "dp", "--protect_times", "2"]),
]


@pytest.mark.parametrize("name,cfg,flags", CASES, ids=[c[0] for c in CASES])
def test_controller_matches_cli(name, cfg, flags, tiny_workload, tmp_path, monkeypatch):
    # RANDOM depends on Python set order -> pin the hash seed identically in both runs.
    if cfg.get("random_allocate") and os.environ.get("PYTHONHASHSEED") != "11":
        pytest.skip("run the suite with PYTHONHASHSEED=11 to compare the hash-order-dependent RANDOM path")
    cli_jcts, cli_gpu = run_cli(tiny_workload, tmp_path, flags)
    ctl = run_controller(tiny_workload, SimConfig(**cfg))
    if cli_jcts is None:
        # The unmodified research simulator itself fails on this scenario; the
        # dashboard must fail identically (same exception type) and surface it.
        assert ctl.error is not None, "CLI failed but controller did not"
        assert ctl.error["type"] == cli_gpu["error"], (ctl.error, cli_gpu["error"])
        assert ctl.cluster.clock == ctl.error["clock"]
        pytest.xfail(f"research simulator raises {cli_gpu['error']} on this scenario (reproduced faithfully)")
    assert ctl.error is None
    assert ctl.cluster.get_jcts() == cli_jcts
    assert ctl.cluster.gpu_util_dict == cli_gpu
    assert len(ctl.events) > 0 and len(ctl.decisions) > 0
