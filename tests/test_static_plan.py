"""Tests for static-plan stress evaluation."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from brushline.strategic.stateful import (
    StatefulConfig,
    StatefulMethod,
    StatefulPeriod,
    StatefulPlan,
    StatefulSegment,
    build_stateful_plan,
)
from brushline.strategic.static_plan import (
    StaticPlanCase,
    StaticPlanError,
    evaluate_static_plans,
)

CREATED = datetime(2026, 11, 16, tzinfo=UTC)


def _plan(
    segments: list[StatefulSegment],
    methods: list[StatefulMethod],
    periods: list[StatefulPeriod],
    budget: float,
) -> StatefulPlan:
    return build_stateful_plan(
        instance_id="static",
        segments=segments,
        methods=methods,
        periods=[period.model_copy(update={"budget": budget}) for period in periods],
        config=StatefulConfig(risk_weight=1.0, max_seconds=30),
        created_utc=CREATED,
    )


def test_static_plan_evaluation_and_determinism() -> None:
    segments = [
        StatefulSegment(
            segment_id=f"s{index}",
            span_id=f"u{index}",
            length_m=500,
            area_ha=3.5,
            initial_risk=0.2 + index * 0.02,
        )
        for index in range(4)
    ]
    methods = [
        StatefulMethod(
            method="mowing",
            cost_per_ha=420,
            hours_per_ha=7,
            risk_reduction=0.3,
        ),
        StatefulMethod(
            method="manual",
            cost_per_ha=1450,
            hours_per_ha=32,
            risk_reduction=0.55,
        ),
    ]
    actual_periods = [
        StatefulPeriod(year=2027, budget=20000, capacity_hours=100),
        StatefulPeriod(year=2028, budget=20000, capacity_hours=100),
    ]
    low_plan = _plan(segments, methods, actual_periods, 10000)
    high_plan = _plan(segments, methods, actual_periods, 20000)
    cases = [
        StaticPlanCase(name="low", nominal_budget=10000, plan=low_plan),
        StaticPlanCase(name="high", nominal_budget=20000, plan=high_plan),
    ]
    first = evaluate_static_plans(
        instance_id="static",
        plans=cases,
        periods=actual_periods,
        episodes=10,
        seed=2,
        created_utc=CREATED,
    )
    second = evaluate_static_plans(
        instance_id="static",
        plans=cases,
        periods=actual_periods,
        episodes=10,
        seed=2,
        created_utc=CREATED,
    )
    assert first.plans == second.plans
    assert first.actual_budget == 40000
    assert len(first.plans) == 2
    assert all(plan.cost_band.p10 <= plan.cost_band.p90 for plan in first.plans)
    assert first.recommended in {"low", "high", None}


def test_static_plan_validation() -> None:
    segments = [
        StatefulSegment(
            segment_id="s",
            span_id="u",
            length_m=500,
            area_ha=3.5,
            initial_risk=0.2,
        )
    ]
    methods = [StatefulMethod(method="mowing", cost_per_ha=420, hours_per_ha=7, risk_reduction=0.3)]
    periods = [StatefulPeriod(year=2027, budget=20000, capacity_hours=100)]
    case = StaticPlanCase(
        name="one",
        nominal_budget=20000,
        plan=_plan(segments, methods, periods, 20000),
    )
    with pytest.raises(StaticPlanError, match="non-empty"):
        evaluate_static_plans(instance_id="static", plans=[], periods=periods)
    with pytest.raises(StaticPlanError, match="positive"):
        evaluate_static_plans(instance_id="static", plans=[case], periods=periods, episodes=0)
    with pytest.raises(StaticPlanError, match="unique"):
        evaluate_static_plans(
            instance_id="static",
            plans=[case],
            periods=[periods[0], periods[0]],
        )
