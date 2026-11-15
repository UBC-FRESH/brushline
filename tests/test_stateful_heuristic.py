"""Tests for the Fresh Solutions stateful heuristic."""

from __future__ import annotations

import random
from datetime import UTC, datetime

import pytest

pytest.importorskip("fresh_solutions")

from brushline.strategic.heuristic import (
    HeuristicError,
    StatefulHeuristicAdapter,
    build_stateful_heuristic,
)
from brushline.strategic.stateful import (
    StatefulConfig,
    StatefulMethod,
    StatefulPeriod,
    StatefulSegment,
)

CREATED = datetime(2026, 11, 15, tzinfo=UTC)


def _segments() -> list[StatefulSegment]:
    return [
        StatefulSegment(segment_id="a", span_id="u1", length_m=500, area_ha=3.5, initial_risk=0.4),
        StatefulSegment(segment_id="b", span_id="u1", length_m=500, area_ha=3.5, initial_risk=0.2),
    ]


def _methods() -> list[StatefulMethod]:
    return [
        StatefulMethod(method="mowing", cost_per_ha=420, hours_per_ha=7, risk_reduction=0.3),
        StatefulMethod(method="manual", cost_per_ha=1450, hours_per_ha=32, risk_reduction=0.55),
    ]


def _periods() -> list[StatefulPeriod]:
    return [
        StatefulPeriod(year=2027, budget=20000, capacity_hours=100),
        StatefulPeriod(year=2028, budget=20000, capacity_hours=100),
    ]


def test_stateful_heuristic_is_feasible_and_replayable() -> None:
    plan = build_stateful_heuristic(
        instance_id="tiny",
        segments=_segments(),
        methods=_methods(),
        periods=_periods(),
        config=StatefulConfig(risk_weight=1.0),
        iterations=100,
        seed=3,
        created_utc=CREATED,
    )
    assert plan.status == "feasible"
    assert plan.replay_ok
    assert plan.total_cost <= 40000
    assert int(plan.search["evaluations"]) >= 1
    assert plan.search["fresh_solutions_version"] != "not-installed"
    assert plan.created_utc == CREATED


def test_stateful_adapter_contract_and_validation() -> None:
    adapter = StatefulHeuristicAdapter(
        _segments(), _methods(), _periods(), StatefulConfig(risk_weight=1.0)
    )
    assignment = adapter.initial_assignment()
    assert set(assignment) == set(range(adapter.variable_count))
    assert adapter.option_count(0) == 3
    assert adapter.option_at(0, 0) == "none"
    rng = random.Random(4)
    changed = adapter.mutate(assignment, 1.0, rng)
    assert changed != assignment
    child = adapter.crossover(assignment, changed, rng)
    assert set(child) == set(range(adapter.variable_count))
    change = adapter.propose(assignment, rng)
    assert change is not None
    updated = adapter.apply(assignment, change)
    assert adapter.undo(updated, change) == assignment
    assert adapter.evaluate(assignment).feasible
    with pytest.raises(HeuristicError):
        adapter.mutate(assignment, 2.0, rng)
    with pytest.raises(HeuristicError):
        adapter.evaluate({0: 0})
    with pytest.raises(HeuristicError):
        adapter.option_count(999)
