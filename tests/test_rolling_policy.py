"""Tests for the rolling-horizon policy simulation."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from brushline.strategic.rolling_policy import RollingPolicyError, simulate_rolling_policy
from brushline.strategic.stateful import (
    StatefulConfig,
    StatefulMethod,
    StatefulPeriod,
    StatefulPlan,
    StatefulSegment,
    build_stateful_plan,
)

CREATED = datetime(2026, 11, 15, tzinfo=UTC)


def _problem() -> tuple[list[StatefulSegment], list[StatefulMethod], list[StatefulPeriod]]:
    segments = [
        StatefulSegment(
            segment_id=f"s{index}",
            span_id=f"u{index // 2}",
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
    return segments, methods, periods


def _fixed_plan() -> StatefulPlan:
    segments, methods, periods = _problem()
    return build_stateful_plan(
        instance_id="fixed",
        segments=segments,
        methods=methods,
        periods=periods,
        config=StatefulConfig(risk_weight=1.0, max_seconds=30),
        created_utc=CREATED,
    )


def test_rolling_policy_bands_and_determinism() -> None:
    segments, methods, periods = _problem()
    first = simulate_rolling_policy(
        instance_id="rolling",
        segments=segments,
        methods=methods,
        periods=periods,
        fixed=_fixed_plan(),
        config=StatefulConfig(risk_weight=1.0, max_seconds=30),
        episodes=3,
        seed=4,
        created_utc=CREATED,
    )
    second = simulate_rolling_policy(
        instance_id="rolling",
        segments=segments,
        methods=methods,
        periods=periods,
        fixed=_fixed_plan(),
        config=StatefulConfig(risk_weight=1.0, max_seconds=30),
        episodes=3,
        seed=4,
        created_utc=CREATED,
    )
    assert first.episodes == 3
    assert first.episodes_detail == second.episodes_detail
    assert first.fixed_cost_band.p10 <= first.fixed_cost_band.p50 <= first.fixed_cost_band.p90
    assert first.rolling_cost_band.p10 <= first.rolling_cost_band.p50 <= first.rolling_cost_band.p90
    assert all(item.status == "optimal" for item in first.episodes_detail[0].years)
    assert all(item.action_details for item in first.episodes_detail[0].years)
    assert first.episodes_detail[0].years[0].action_details[0].unit_id
    assert first.rolling_budget_violation_probability == 0
    assert first.fixed_budget_violation_probability >= 0
    assert first.mean_rolling_objective <= first.mean_fixed_objective
    heuristic = simulate_rolling_policy(
        instance_id="rolling-heuristic",
        segments=segments,
        methods=methods,
        periods=periods,
        fixed=_fixed_plan(),
        config=StatefulConfig(risk_weight=1.0, max_seconds=30),
        episodes=1,
        solver="heuristic",
        heuristic_iterations=20,
        seed=4,
        created_utc=CREATED,
    )
    assert heuristic.solver == "heuristic"
    assert heuristic.episodes_detail[0].years[0].status == "feasible"


def test_rolling_policy_validation() -> None:
    segments, methods, periods = _problem()
    with pytest.raises(RollingPolicyError, match="non-empty"):
        simulate_rolling_policy(
            instance_id="rolling",
            segments=[],
            methods=methods,
            periods=periods,
            fixed=_fixed_plan(),
            episodes=1,
        )
    with pytest.raises(RollingPolicyError, match="positive"):
        simulate_rolling_policy(
            instance_id="rolling",
            segments=segments,
            methods=methods,
            periods=periods,
            fixed=_fixed_plan(),
            episodes=0,
        )
    with pytest.raises(RollingPolicyError, match="unique"):
        simulate_rolling_policy(
            instance_id="rolling",
            segments=segments,
            methods=methods,
            periods=[periods[0], periods[0]],
            fixed=_fixed_plan(),
            episodes=1,
        )
    with pytest.raises(ValueError, match="timezone-aware"):
        simulate_rolling_policy(
            instance_id="rolling",
            segments=segments,
            methods=methods,
            periods=periods,
            fixed=_fixed_plan(),
            episodes=1,
            created_utc=datetime(2026, 11, 15),
        )
