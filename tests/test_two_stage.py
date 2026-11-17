"""Tests for first-year two-stage operational recourse."""

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
from brushline.strategic.two_stage import (
    TwoStageError,
    evaluate_two_stage,
    evaluate_two_stage_multi,
)

CREATED = datetime(2026, 11, 17, tzinfo=UTC)


def _plan() -> tuple[StatefulPlan, list[StatefulSegment]]:
    segments = [
        StatefulSegment(
            segment_id=f"s{index}",
            span_id=f"u{index}",
            length_m=500,
            area_ha=3.5,
            initial_risk=0.2 + index * 0.03,
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
    periods = [
        StatefulPeriod(year=2027, budget=20000, capacity_hours=100),
        StatefulPeriod(year=2028, budget=20000, capacity_hours=100),
    ]
    return build_stateful_plan(
        instance_id="tiny",
        segments=segments,
        methods=methods,
        periods=periods,
        config=StatefulConfig(risk_weight=1.0, max_seconds=30),
        created_utc=CREATED,
    ), segments


def test_two_stage_recourse_bands_and_determinism() -> None:
    plan, segments = _plan()
    first = evaluate_two_stage(
        instance_id="two-stage",
        plan=plan,
        segments=segments,
        budget=20000,
        capacity_hours=100,
        episodes=10,
        seed=7,
        created_utc=CREATED,
    )
    second = evaluate_two_stage(
        instance_id="two-stage",
        plan=plan,
        segments=segments,
        budget=20000,
        capacity_hours=100,
        episodes=10,
        seed=7,
        created_utc=CREATED,
    )
    assert first.outcomes == second.outcomes
    assert first.static_cost_band.p10 <= first.static_cost_band.p90
    assert first.recourse_cost_band.p10 <= first.recourse_cost_band.p90
    assert first.recourse_budget_violation_probability == 0
    assert first.recourse_capacity_violation_probability == 0
    assert first.mean_deferred_actions >= 0
    assert first.mean_risk_loss >= 0


def test_two_stage_multi_year_recourse() -> None:
    plan, segments = _plan()
    result = evaluate_two_stage_multi(
        instance_id="two-stage-multi",
        plan=plan,
        segments=segments,
        periods=[
            StatefulPeriod(year=2027, budget=20000, capacity_hours=100),
            StatefulPeriod(year=2028, budget=20000, capacity_hours=100),
        ],
        episodes=5,
        seed=7,
        created_utc=CREATED,
    )
    assert result.episodes == 5
    assert result.years == [2027, 2028]
    assert result.recourse_budget_violation_probability == 0
    assert result.recourse_capacity_violation_probability == 0
    assert result.recourse_cost_band.p10 <= result.recourse_cost_band.p90


def test_two_stage_validation() -> None:
    plan, segments = _plan()
    with pytest.raises(TwoStageError, match="non-empty"):
        evaluate_two_stage(
            instance_id="two-stage",
            plan=plan,
            segments=[],
            budget=20000,
            capacity_hours=100,
        )
    with pytest.raises(TwoStageError, match="positive"):
        evaluate_two_stage(
            instance_id="two-stage",
            plan=plan,
            segments=segments,
            budget=20000,
            capacity_hours=100,
            episodes=0,
        )
