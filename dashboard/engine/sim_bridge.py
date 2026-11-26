"""Bridge between the dashboard and the unmodified DeepBoot research simulator.

The research simulator (``simulator.py``) is written as a command-line program.
Its feature flags (AISS, AFE, ARYL, ...) are *module-level globals* that are only
assigned inside ``if __name__ == "__main__"``. Its ``event_update`` method also
reads a module-level ``args`` namespace. Merely importing the module therefore
leaves the flags at import-time defaults, and these DIFFER from the CLI defaults
(e.g. ``simulator.ARYL`` is True on import, but ``--ARYL`` defaults to 0).

This module:
  * puts the repository root on ``sys.path`` so the research code is imported
    unchanged from its original location;
  * sets every global exactly as the ``__main__`` block of simulator.py does;
  * builds the policy and ``Cluster`` exactly as ``simulate()`` does
    (simulator.py lines 1065-1091).

No research file is modified. Nothing here re-implements scheduling logic.
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
from dataclasses import dataclass, asdict, field
from typing import Optional

sys.dont_write_bytecode = True  # the repo commits __pycache__/*.pyc; never rewrite them

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

import pandas  # noqa: E402

import simulator as sim  # noqa: E402  (the unmodified research simulator)
from simulator import Cluster  # noqa: E402

# The research simulator logs several lines at INFO level for every simulated
# event (hundreds of MB for a full run). Silence INFO output in the dashboard
# process only. Logging calls have no side effects on simulation state.
logging.disable(logging.INFO)  # all research loggers (simulator, infer_scheduler, dp, ...)

POLICIES = ("dp", "pollux", "afs")  # policies exercised by the team's experiments
POLICY_LABELS = {
    "dp": "DeepBoot (ATS-T knapsack, dp.py)",
    "pollux": "Pollux (NSGA-II, pollux.py)",
    "afs": "AFS (afs.py)",
}


@dataclass
class SimConfig:
    """Mirror of simulator.py's argparse options (same names, same defaults).

    Defaults are the CLI defaults (simulator.py lines 1170-1221), NOT the
    module import-time defaults.
    """

    policy: str = "dp"
    min_nodes: int = 16
    max_nodes: Optional[int] = None
    num_gpus: int = 4
    interval: int = 60
    infer_priority: int = 1
    protect_time: int = 30
    interference: float = 0.0
    ARYL: int = 0
    AISS: int = 1
    AFE: int = 0
    INFER_SCHEDULER: int = 1
    REPAIR_TRAIN: int = 1
    protect_times: float = 1.0
    random_allocate: int = 0
    low_util: Optional[float] = None
    high_util: Optional[float] = None
    workload: str = "<dashboard>"

    def to_namespace(self) -> argparse.Namespace:
        return argparse.Namespace(**asdict(self))

    def cli_flags(self) -> str:
        """The equivalent simulator.py command line (for provenance display)."""
        return (
            f"python simulator.py --workload {self.workload} --policy {self.policy} "
            f"--AFE {self.AFE} --AISS {self.AISS} --ARYL {self.ARYL} "
            f"--INFER_SCHEDULER {self.INFER_SCHEDULER} --REPAIR_TRAIN {self.REPAIR_TRAIN} "
            f"--random_allocate {self.random_allocate} --protect_times {self.protect_times} "
            f"--interval {self.interval} --min-nodes {self.min_nodes} --num-gpus {self.num_gpus}"
        )


def apply_globals(cfg: SimConfig) -> None:
    """Assign module globals exactly as simulator.py's __main__ block does.

    Must be called before constructing a Cluster (Cluster.__init__ reads ARYL and
    RANDOM_ALLOCATE) and before every step (other methods read the rest).
    """
    sim.args = cfg.to_namespace()  # used by Cluster.event_update (args.interval)
    sim.AISS = cfg.AISS
    sim.AFE = cfg.AFE
    sim.INFER_SCHEDULER = cfg.INFER_SCHEDULER
    sim.REPAIR_TRAIN = cfg.REPAIR_TRAIN
    sim.RANDOM_ALLOCATE = cfg.random_allocate
    sim.ARYL = cfg.ARYL
    sim.PROTECT_TIMES = cfg.protect_times
    sim.NUM_NODE = cfg.min_nodes


def build_policy(cfg: SimConfig, cluster_ref: dict):
    """Policy construction copied from simulate() (simulator.py 1066-1085)."""
    if cfg.policy == "tiresias":
        policy = sim.TiresiasPolicy(lambda: cluster_ref["cluster"].current_time)
    elif cfg.policy == "optimus":
        policy = sim.Optimus()
    elif cfg.policy == "afs":
        policy = sim.AFS()
    elif cfg.policy == "aryl":
        policy = sim.Aryl()
    elif cfg.policy == "dp":
        policy = sim.DeepBoot()
    else:
        policy = sim.PolluxPolicy()
        policy.sched_train = sim.INFER_SCHEDULER
        policy.repair_train = sim.REPAIR_TRAIN
    policy.interval = cfg.interval
    policy.infer_priority = cfg.infer_priority
    return policy


def build_cluster(workload: pandas.DataFrame, cfg: SimConfig) -> Cluster:
    """Construct the research Cluster exactly as simulate() does."""
    apply_globals(cfg)
    ref: dict = {}
    policy = build_policy(cfg, ref)
    cluster = Cluster(
        workload,
        policy,
        cfg.min_nodes,
        num_gpus=cfg.num_gpus,
        max_nodes=cfg.max_nodes,
        interference=cfg.interference,
        low_util=cfg.low_util,
        high_util=cfg.high_util,
    )
    cluster.protect_time = cfg.protect_time
    ref["cluster"] = cluster
    return cluster


def training_applications() -> list:
    return [k for k in sim.APPLICATIONS if not k.startswith("infer")]


def inference_models() -> list:
    return [k for k in sim.APPLICATIONS if k.startswith("infer")]
