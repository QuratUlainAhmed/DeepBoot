"""Integration-layer tests: bridge flags, injection fidelity, reset, instrumentation, loaders."""
import pandas
import pytest

from dashboard.engine import sim_bridge
from dashboard.engine.sim_bridge import SimConfig, sim
from dashboard.engine.simulation_controller import SimulationController
from dashboard.engine.workload_manager import InjectionError, make_row
from .conftest import run_controller


def test_globals_follow_cli_defaults_not_import_defaults():
    sim.ARYL = True  # import-time value in simulator.py
    sim_bridge.apply_globals(SimConfig())
    assert sim.ARYL == 0 and sim.AISS == 1 and sim.AFE == 0 and sim.INFER_SCHEDULER == 1
    assert sim.args.interval == 60


@pytest.mark.parametrize("kind", ["training", "inference"])
def test_injected_job_equals_csv_row(kind, tiny_workload):
    """A job injected through the dashboard must behave exactly like the same row
    appended to the workload CSV."""
    t_last = int(tiny_workload["time"].max()) + 30
    if kind == "training":
        row = make_row("training", "cifar10-ui1", "cifar10", t_last)
    else:
        row = make_row("inference", "inference-bert-ui1", "infer-bert-1", t_last, duration=5.0)
    with_row = pandas.concat([tiny_workload, pandas.DataFrame([row])], ignore_index=True)
    ref = run_controller(with_row, SimConfig(policy="dp"))

    ctl = SimulationController(tiny_workload, SimConfig(policy="dp"))
    ctl.run_until(target_clock=10, wall_budget_s=30)
    ctl.inject(row)
    while not ctl.is_complete():
        ctl.run_until(None, wall_budget_s=30)
    assert ctl.cluster.get_jcts() == ref.cluster.get_jcts()
    assert ctl.cluster.gpu_util_dict == ref.cluster.gpu_util_dict


def test_injection_validation(tiny_workload):
    ctl = SimulationController(tiny_workload, SimConfig(policy="dp"))
    ctl.run_until(target_clock=100, wall_budget_s=30)
    with pytest.raises(InjectionError):
        ctl.inject(make_row("training", "late", "cifar10", 50))  # in the past
    with pytest.raises(InjectionError):
        ctl.inject(make_row("training", tiny_workload["name"].iloc[0], "cifar10", 500))  # duplicate
    with pytest.raises(InjectionError):
        ctl.inject(make_row("inference", "inference-x-1", "cifar10", 500, duration=3))  # wrong app type


def test_reset_restores_initial_state_and_replays_identically(tiny_workload):
    ctl = SimulationController(tiny_workload, SimConfig(policy="dp"))
    ctl.run_until(target_clock=600, wall_budget_s=30)
    first = ctl.cluster.get_jcts()
    ctl.inject(make_row("training", "ncf-ui9", "ncf", ctl.cluster.clock + 10))
    ctl.reset()
    assert ctl.cluster.clock == 0 and len(ctl.snapshots) == 1 and ctl.events == [] and ctl.injected_rows == []
    assert "ncf-ui9" not in ctl.cluster.job_dict
    ctl.run_until(target_clock=600, wall_budget_s=30)
    assert ctl.cluster.get_jcts() == first


def test_instrumentation_matches_actual_allocations(tiny_workload):
    ctl = SimulationController(tiny_workload, SimConfig(policy="dp"))
    ctl.run_until(target_clock=1200, wall_budget_s=60)
    atst = [d for d in ctl.decisions if d["kind"] == "ATS-T" and d.get("knapsack")]
    assert atst, "expected ATS-T decisions"
    for d in atst:
        chosen = dict(zip([j["job"] for j in d["jobs"]], d["knapsack"]["chosen_replicas"]))
        for job, w in chosen.items():
            assert len(d["new_alloc"].get(job, [])) == w  # replicas2allocation realises the knapsack choice
        assert sum(chosen.values()) <= d["capacity"]
    for d in ctl.decisions:
        if d["kind"] == "ATS-I":
            for r in d["reclaims"]:
                assert r["training_job"] in ctl.cluster.job_dict


def test_snapshots_never_overcommit(tiny_workload):
    ctl = SimulationController(tiny_workload, SimConfig(policy="dp", AFE=1))
    ctl.run_until(target_clock=1500, wall_budget_s=60)
    for s in ctl.snapshots:
        per_node = {}
        for alloc in s["allocations"].values():
            for n in alloc:
                per_node[n] = per_node.get(n, 0) + 1
        assert all(v <= 4 for v in per_node.values())
        assert sum(s["breakdown"].values()) == sum(per_node.values())


def test_experiment_loader_reproduces_reported_values():
    from dashboard.data import experiment_loader as EL
    cat = EL.catalog()
    assert {"E01", "E02", "E03", "E04", "E05", "E06", "E07", "E08-rerun", "AISS-0", "AISS-1"} <= set(cat)
    e01 = EL.summary_metrics("E01")
    assert round(e01["training mean JCT (s)"], 2) == 2442.58
    assert round(e01["allocated GPU %"], 2) == 94.42
    assert round(EL.summary_metrics("E08-rerun")["training mean JCT (s)"], 2) == 2348.03
    assert round(EL.summary_metrics("AISS-0")["inference mean JCT (s)"], 2) == 10.78
    e05 = EL.summary_metrics("E05")
    assert EL.gpu_series("E05") is None and "analysis-summary" in e05["GPU source"]
