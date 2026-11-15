"""Tests for scenario-optimized planning comparisons."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from brushline.strategic.scenario_optimization import (
    ScenarioOptimizationError,
    optimize_scenarios,
)
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


def test_scenario_optimization_bands_and_determinism() -> None:
    segments, methods, periods = _problem()
    first = optimize_scenarios(
        instance_id="scenario",
        segments=segments,
        methods=methods,
        periods=periods,
        fixed=_fixed_plan(),
        config=StatefulConfig(risk_weight=1.0, max_seconds=30),
        scenarios=5,
        seed=7,
        created_utc=CREATED,
    )
    second = optimize_scenarios(
        instance_id="scenario",
        segments=segments,
        methods=methods,
        periods=periods,
        fixed=_fixed_plan(),
        config=StatefulConfig(risk_weight=1.0, max_seconds=30),
        scenarios=5,
        seed=7,
        created_utc=CREATED,
    )
    assert first.fixed_cost_band.p10 <= first.fixed_cost_band.p50 <= first.fixed_cost_band.p90
    assert (
        first.adaptive_cost_band.p10 <= first.adaptive_cost_band.p50 <= first.adaptive_cost_band.p90
    )
    assert len(first.outcomes) == 5
    assert first.outcomes == second.outcomes
    assert first.mean_regret == second.mean_regret
    assert all(outcome.adaptive_status == "optimal" for outcome in first.outcomes)
    assert first.fixed_capacity_violation_probability >= 0
    assert first.fixed_budget_violation_probability >= 0


def test_scenario_optimization_validation() -> None:
    segments, methods, periods = _problem()
    with pytest.raises(ScenarioOptimizationError, match="non-empty"):
        optimize_scenarios(
            instance_id="scenario",
            segments=[],
            methods=methods,
            periods=periods,
            fixed=_fixed_plan(),
            scenarios=1,
        )
    with pytest.raises(ScenarioOptimizationError, match="positive"):
        optimize_scenarios(
            instance_id="scenario",
            segments=segments,
            methods=methods,
            periods=periods,
            fixed=_fixed_plan(),
            scenarios=0,
        )
