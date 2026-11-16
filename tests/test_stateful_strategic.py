"""Tests for stateful MILP strategic planning."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from brushline.strategic.stateful import (
    StatefulConfig,
    StatefulError,
    StatefulMethod,
    StatefulPeriod,
    StatefulSegment,
    build_stateful_plan,
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


def _periods(budget: float = 20000) -> list[StatefulPeriod]:
    return [
        StatefulPeriod(year=2027, budget=budget, capacity_hours=6000),
        StatefulPeriod(year=2028, budget=budget, capacity_hours=6000),
    ]


def test_stateful_milp_optimal_replay_and_budget() -> None:
    plan = build_stateful_plan(
        instance_id="tiny",
        segments=_segments(),
        methods=_methods(),
        periods=_periods(),
        config=StatefulConfig(risk_weight=1.0, cost_weight=0.0),
        created_utc=CREATED,
    )
    assert plan.status == "optimal"
    assert plan.replay_ok
    assert plan.actions
    assert plan.total_cost <= 40000
    assert plan.actions[0].risk_after <= plan.actions[0].risk_before
    assert plan.created_utc == CREATED


def test_stateful_robust_factors_solve() -> None:
    plan = build_stateful_plan(
        instance_id="tiny",
        segments=_segments(),
        methods=_methods(),
        periods=_periods(),
        config=StatefulConfig(risk_weight=1.0),
        robust_factors=[
            [(2027, 1.2, 1.0, 1.0), (2028, 1.2, 1.0, 1.0)],
            [(2027, 1.5, 1.0, 0.8), (2028, 1.5, 1.0, 0.8)],
        ],
        created_utc=CREATED,
    )
    assert plan.status == "optimal"
    assert plan.replay_ok


def test_stateful_zero_budget_leaves_growth() -> None:
    plan = build_stateful_plan(
        instance_id="tiny",
        segments=_segments(),
        methods=_methods(),
        periods=_periods(budget=0),
        config=StatefulConfig(risk_weight=1.0),
        created_utc=CREATED,
    )
    assert plan.status == "optimal"
    assert not plan.actions
    assert plan.total_cost == 0
    assert plan.mean_risk > 0


def test_stateful_risk_target_and_duplicate_validation() -> None:
    plan = build_stateful_plan(
        instance_id="tiny",
        segments=_segments(),
        methods=_methods(),
        periods=_periods(),
        config=StatefulConfig(risk_weight=1.0, max_mean_risk=0.2),
        created_utc=CREATED,
    )
    assert plan.mean_risk <= 0.2 + 1e-9
    with pytest.raises(StatefulError, match="unique"):
        build_stateful_plan(
            instance_id="tiny",
            segments=[_segments()[0], _segments()[0]],
            methods=_methods(),
            periods=_periods(),
        )
    with pytest.raises(StatefulError, match="non-empty"):
        build_stateful_plan(
            instance_id="tiny",
            segments=[],
            methods=_methods(),
            periods=_periods(),
        )
