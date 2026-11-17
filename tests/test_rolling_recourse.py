"""Tests for rolling policy with annual recourse."""

from __future__ import annotations

from datetime import UTC, datetime

from brushline.strategic.rolling_recourse import evaluate_rolling_recourse
from brushline.strategic.stateful import (
    StatefulConfig,
    StatefulMethod,
    StatefulPeriod,
    StatefulPlan,
    StatefulSegment,
    build_stateful_plan,
)

CREATED = datetime(2026, 11, 17, tzinfo=UTC)


def _problem() -> tuple[
    StatefulPlan, list[StatefulSegment], list[StatefulMethod], list[StatefulPeriod]
]:
    segments = [
        StatefulSegment(
            segment_id=f"s{index}",
            span_id=f"u{index}",
            length_m=500,
            area_ha=3.5,
            initial_risk=0.2 + index * 0.03,
        )
        for index in range(3)
    ]
    methods = [
        StatefulMethod(method="mowing", cost_per_ha=420, hours_per_ha=7, risk_reduction=0.3),
        StatefulMethod(method="manual", cost_per_ha=1450, hours_per_ha=32, risk_reduction=0.55),
    ]
    periods = [
        StatefulPeriod(year=2027, budget=20000, capacity_hours=100),
        StatefulPeriod(year=2028, budget=20000, capacity_hours=100),
    ]
    plan = build_stateful_plan(
        instance_id="tiny",
        segments=segments,
        methods=methods,
        periods=periods,
        config=StatefulConfig(risk_weight=1.0, max_seconds=30),
        created_utc=CREATED,
    )
    return plan, segments, methods, periods


def test_rolling_recourse_cases() -> None:
    plan, segments, methods, periods = _problem()
    result = evaluate_rolling_recourse(
        instance_id="rolling-recourse",
        plan=plan,
        segments=segments,
        methods=methods,
        periods=periods,
        config=StatefulConfig(risk_weight=1.0, max_seconds=30),
        episodes=2,
        seed=7,
        created_utc=CREATED,
    )
    assert [case.name for case in result.cases] == [
        "static-fixed",
        "fixed-future-recourse",
        "rolling-only",
        "rolling-recourse",
    ]
    assert result.years == [2027, 2028]
    assert result.cases[-1].budget_violation_probability == 0
    assert result.cases[-1].cost_band.p10 <= result.cases[-1].cost_band.p90
