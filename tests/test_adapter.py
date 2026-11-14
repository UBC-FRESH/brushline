"""Tests for the P5.4 Fresh Solutions adapter and exact replay."""

from __future__ import annotations

import random
from pathlib import Path

import pytest
from pydantic import ValidationError

pytest.importorskip("fresh_solutions")

from brushline.model.corridor import ServiceStandard
from brushline.optimization.adapter import (
    ADAPTER_NAME,
    INFEASIBLE_PENALTY,
    SCALARIZATIONS,
    AdapterError,
    BrushlineAdapter,
    Scalarization,
    SearchRun,
    SearchSpec,
    fresh_solutions_version,
    replay_checkpoint,
    run_search,
)
from brushline.optimization.evaluator import ScheduleEvaluator, SegmentContext
from brushline.optimization.formulation import Formulation
from brushline.optimization.operators import OperatorConfig
from brushline.vegetation.state_space import StateDistribution
from fresh_solutions.contracts import Change, Evaluation

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "notes" / "reference" / "p5-formulation.v1.json"
STANDARD = ServiceStandard(service_standard_id="std1", max_height_m=4.0, min_clearance_m=1.0)


def _evaluator() -> ScheduleEvaluator:
    formulation = Formulation.model_validate_json(FIXTURE.read_text(encoding="utf-8"))
    return ScheduleEvaluator(
        formulation,
        [
            SegmentContext(
                segment_id="s1",
                functional_group="shrub",
                initial=StateDistribution(
                    class_probabilities={"shrub": 0.8, "unknown": 0.2},
                    height_m=1.5,
                    height_sd=0.2,
                    cover_pct=40,
                    cover_sd=4,
                    density_per_ha=1000,
                    density_sd=50,
                    age_years=1,
                    confidence=0.6,
                ),
                service_standard=STANDARD,
                length_m=100,
                asset_height_m=8,
            ),
            SegmentContext(
                segment_id="s2",
                functional_group="grass_herb",
                initial=StateDistribution(
                    class_probabilities={"grass_herb": 0.8, "unknown": 0.2},
                    height_m=0.4,
                    height_sd=0.1,
                    cover_pct=70,
                    cover_sd=4,
                    density_per_ha=0,
                    density_sd=0,
                    age_years=1,
                    confidence=0.8,
                ),
                service_standard=STANDARD,
                length_m=150,
                asset_height_m=8,
            ),
        ],
    )


def _adapter(
    scalarization: Scalarization | None = None,
    config: OperatorConfig | None = None,
) -> BrushlineAdapter:
    return BrushlineAdapter(_evaluator(), scalarization, config)


def _selected(adapter: BrushlineAdapter) -> dict[int, int]:
    assignment = adapter.initial_assignment()
    variable = next(
        item.index
        for item in adapter.evaluator.formulation.variables
        if item.kind == "treatment" and item.target_id == "s1" and item.period_id == "p2026"
    )
    assignment[variable] = adapter.evaluator.formulation.variables[variable].option_ids.index(
        "mow-l1"
    )
    return assignment


def test_adapter_contract_and_scalarization() -> None:
    """The adapter exposes the Fresh Solutions contract and a four-objective scalar."""
    adapter = _adapter()
    assert adapter.name == ADAPTER_NAME
    assert adapter.variable_count == 6
    assert adapter.option_count(0) == 3
    assert adapter.option_at(0, 0) == "none"
    initial = adapter.initial_assignment()
    assert set(initial) == set(range(6))
    result = adapter.evaluate(initial)
    assert isinstance(result, Evaluation)
    assert result.feasible
    expected = adapter.evaluator.evaluate(initial).scalar_objective(adapter.scalarization.weights)
    assert result.objective == pytest.approx(expected)
    assert set(result.details) >= {
        "present_cost",
        "service_risk",
        "service_attainment",
        "uncertainty",
        "total_cost",
        "violations",
    }
    batch = adapter.evaluate_batch([initial, _selected(adapter)])
    assert len(batch) == 2
    assert batch[0] == result
    invalid = adapter.evaluate({0: 0})
    assert not invalid.feasible
    assert invalid.objective >= INFEASIBLE_PENALTY


def test_scalarizations_and_spec_validation() -> None:
    """Scalarizations and search settings validate their inputs."""
    assert {item.name for item in SCALARIZATIONS} == {
        "cost_first",
        "risk_first",
        "service_first",
        "uncertainty_first",
        "balanced",
    }
    with pytest.raises(ValidationError):
        Scalarization(name="bad", weights={"present_cost": 1})
    names = ("present_cost", "service_risk", "service_attainment", "uncertainty")
    with pytest.raises(ValidationError):
        Scalarization(name="bad", weights=dict.fromkeys(names, -1))
    with pytest.raises(ValidationError):
        Scalarization(name="bad", weights=dict.fromkeys(names, 0))
    assert SearchSpec(mode="local", instance_id="i").requested_budget == 101
    assert SearchSpec(mode="population", instance_id="i").requested_budget == 96
    assert SearchSpec(mode="hybrid", instance_id="i").requested_budget == 197
    assert SearchSpec(mode="convergence", instance_id="i").requested_budget == 1000
    with pytest.raises(ValidationError):
        SearchSpec.model_validate({"mode": "unknown", "instance_id": "i"})
    with pytest.raises(ValidationError):
        SearchSpec(mode="local", instance_id="i", iterations=-1)
    assert fresh_solutions_version() != "not-installed"


def test_random_mutate_crossover_and_operator_rules() -> None:
    """Random, mutation, and crossover assignments are complete and repaired."""
    adapter = _adapter(config=OperatorConfig(locked_variables=[0]))
    rng = random.Random(1)
    random_assignment = adapter.random_assignment(rng)
    assert set(random_assignment) == set(range(adapter.variable_count))
    mutated = adapter.mutate(random_assignment, 1.0, rng)
    assert set(mutated) == set(range(adapter.variable_count))
    assert mutated[0] == random_assignment[0]
    child = adapter.crossover(random_assignment, mutated, rng)
    assert set(child) == set(range(adapter.variable_count))
    with pytest.raises(AdapterError):
        adapter.mutate(random_assignment, 2.0, rng)


def test_propose_apply_undo_and_compound_move() -> None:
    """Single-variable proposals satisfy the Fresh Solutions Change contract."""
    adapter = _adapter()
    assignment = _selected(adapter)
    change = adapter.propose(assignment, random.Random(2))
    assert isinstance(change, Change)
    updated = adapter.apply(assignment, change)
    assert updated != assignment
    assert adapter.undo(updated, change) == assignment
    with pytest.raises(AdapterError):
        adapter.apply(assignment, Change(variable=change.variable, before=99, after=0))
    with pytest.raises(AdapterError):
        adapter.undo(assignment, Change(variable=change.variable, before=0, after=99))
    move = adapter.propose_move(assignment, random.Random(3))
    assert move is not None
    assert move.apply(assignment) != assignment or move.changes


def test_local_population_hybrid_and_convergence_replay() -> None:
    """Every search mode reports an exactly replayable incumbent."""
    evaluator = _evaluator()
    specs = [
        SearchSpec(mode="local", instance_id="tiny", seed=3, iterations=8),
        SearchSpec(
            mode="population",
            instance_id="tiny",
            seed=3,
            population=4,
            generations=1,
        ),
        SearchSpec(
            mode="hybrid",
            instance_id="tiny",
            seed=3,
            population=4,
            generations=1,
            iterations=3,
        ),
        SearchSpec(
            mode="convergence",
            instance_id="tiny",
            seed=3,
            population=4,
            generations=0,
            local_iterations=2,
            max_rounds=1,
            max_evaluations=20,
            patience_rounds=1,
        ),
    ]
    for spec in specs:
        first = run_search(evaluator, spec)
        second = run_search(evaluator, spec)
        assert first.replay_ok
        assert first.feasible
        assert first.assignment == second.assignment
        assert first.objective == second.objective
        assert first.adapter == ADAPTER_NAME
        assert first.fresh_solutions_version
        assert first.budget == spec.requested_budget
        assert set(first.objective_vector) == {
            "present_cost",
            "service_risk",
            "service_attainment",
            "uncertainty",
        }
        replay = _adapter().evaluate(first.assignment)
        assert replay.objective == pytest.approx(first.objective)
        assert replay.feasible == first.feasible
        assert first.evidence["objective"] == pytest.approx(first.objective)


def test_checkpoint_save_load_and_replay(tmp_path: Path) -> None:
    """A checkpoint replays to the same assignment and objective."""
    path = tmp_path / "checkpoint.json"
    spec = SearchSpec(mode="local", instance_id="tiny", seed=4, iterations=5)
    run = run_search(_evaluator(), spec, checkpoint_path=path)
    assert path.exists()
    assert run.checkpoint_path == str(path)
    replay = replay_checkpoint(_evaluator(), path)
    assert replay.assignment == run.assignment
    assert replay.objective == pytest.approx(run.objective)
    assert replay.replay_ok
    assert replay.mode == "checkpoint"


def test_run_rejects_non_replayable_incumbent(monkeypatch: pytest.MonkeyPatch) -> None:
    """A scalar mismatch is an error, not a reported result."""
    import types

    monkeypatch.setattr(
        BrushlineAdapter,
        "evaluate",
        lambda self, assignment: Evaluation(objective=1.0, feasible=True),
    )
    monkeypatch.setattr(
        "fresh_solutions.engine.run_local_search",
        lambda adapter, config: types.SimpleNamespace(
            assignment=adapter.initial_assignment(),
            objective=0.0,
            feasible=True,
            evaluations=1,
            history=(0.0,),
        ),
    )
    with pytest.raises(AdapterError, match="replay"):
        run_search(
            _evaluator(),
            SearchSpec(mode="local", instance_id="tiny", iterations=1),
        )


def test_search_run_model_guards() -> None:
    """A SearchRun cannot hide a failed replay or an unexpected adapter."""
    with pytest.raises(ValidationError):
        SearchRun(
            mode="local",
            instance_id="tiny",
            adapter=ADAPTER_NAME,
            fresh_solutions_version="0.9.3",
            seed=1,
            budget=1,
            assignment={},
            objective=0.0,
            objective_vector={
                "present_cost": 0.0,
                "service_risk": 0.0,
                "service_attainment": 1.0,
                "uncertainty": 0.0,
            },
            feasible=True,
            evaluations=1,
            history=[],
            stop_reason="budget",
            evidence={},
            replay_ok=False,
        )


def test_core_import_does_not_require_fresh_solutions() -> None:
    """Importing the optimization package does not import the optional solver."""
    import subprocess
    import sys

    completed = subprocess.run(
        [
            sys.executable,
            "-c",
            "import sys; import brushline.optimization; "
            "assert 'fresh_solutions' not in sys.modules",
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr
