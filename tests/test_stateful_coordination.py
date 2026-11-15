"""Tests for the Lagrangian stateful coordination bound."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from brushline.strategic.coordination import CoordinationError, coordinate_stateful
from brushline.strategic.stateful import (
    StatefulConfig,
    StatefulMethod,
    StatefulPeriod,
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
        StatefulMethod(method="mowing", cost_per_ha=420, hours_per_ha=7, risk_reduction=0.30),
        StatefulMethod(method="manual", cost_per_ha=1450, hours_per_ha=32, risk_reduction=0.55),
    ]
    periods = [
        StatefulPeriod(year=2027, budget=20000, capacity_hours=100),
        StatefulPeriod(year=2028, budget=20000, capacity_hours=100),
    ]
    return segments, methods, periods


def test_coordination_returns_valid_lower_bound() -> None:
    segments, methods, periods = _problem()
    baseline = build_stateful_plan(
        instance_id="tiny",
        segments=segments,
        methods=methods,
        periods=periods,
        config=StatefulConfig(risk_weight=1.0),
        created_utc=CREATED,
    )
    result = coordinate_stateful(
        instance_id="tiny",
        segments=segments,
        methods=methods,
        periods=periods,
        baseline=baseline,
        max_segments_per_cluster=2,
        iterations=5,
        max_seconds_per_cluster=30,
        created_utc=CREATED,
    )
    assert result.dual_bound <= baseline.objective + 1e-9
    assert result.absolute_gap >= -1e-9
    assert len(result.iterations) == 5
    assert result.best_iteration >= 0
    assert result.cluster_count == 2


def test_coordination_validation() -> None:
    segments, methods, periods = _problem()
    baseline = build_stateful_plan(
        instance_id="tiny",
        segments=segments,
        methods=methods,
        periods=periods,
        config=StatefulConfig(risk_weight=1.0),
        created_utc=CREATED,
    )
    with pytest.raises(CoordinationError, match="positive"):
        coordinate_stateful(
            instance_id="tiny",
            segments=segments,
            methods=methods,
            periods=periods,
            baseline=baseline,
            max_segments_per_cluster=0,
        )
    with pytest.raises(CoordinationError, match="non-empty"):
        coordinate_stateful(
            instance_id="tiny",
            segments=[],
            methods=methods,
            periods=periods,
            baseline=baseline,
        )
