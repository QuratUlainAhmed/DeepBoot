import json
import os
import subprocess
import sys

import pytest

sys.dont_write_bytecode = True  # keep the committed research __pycache__/*.pyc untouched
os.environ["PYTHONDONTWRITEBYTECODE"] = "1"

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

# The ORIGINAL research environment, used to run the unmodified CLI as ground truth.
RESEARCH_PY = os.environ.get("DEEPBOOT_RESEARCH_PYTHON",
                             os.path.expanduser("~/miniforge3/envs/pollux/bin/python"))


@pytest.fixture(scope="session")
def tiny_workload():
    from dashboard.engine.workload_manager import load_workload, reduced_scenario
    return reduced_scenario(load_workload("small"), n_training=4, inference_window_s=900)


def run_cli(workload_df, tmp_path, flags):
    """Run the unmodified simulator.py exactly as the experiments did; return (jcts, gpu_dict)."""
    csv = tmp_path / "w.csv"
    workload_df.to_csv(csv, index=False)
    out = tmp_path / "cli_out"
    py = RESEARCH_PY if os.path.exists(RESEARCH_PY) else sys.executable
    cmd = [py, "simulator.py", "--workload", str(csv), "--log_file", "0", "--output", str(out),
           "--min-nodes", "16", "--num-gpus", "4"] + flags
    r = subprocess.run(cmd, cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
                       env={**os.environ, "PYTHONHASHSEED": "11", "PYTHONDONTWRITEBYTECODE": "1"})
    if r.returncode != 0:
        tail = r.stderr.decode()[-3000:]
        exc = tail.strip().splitlines()[-1].split(":")[0]
        return None, {"error": exc, "stderr": tail}
    return json.load(open(out / "summary.json"))["jcts"], json.load(open(out / "gpu.log"))


def run_controller(workload_df, cfg):
    from dashboard.engine.simulation_controller import SimulationController
    ctl = SimulationController(workload_df, cfg)
    while not ctl.is_complete() and ctl.error is None:
        ctl.run_until(None, wall_budget_s=30)
    return ctl
