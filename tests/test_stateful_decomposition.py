"""Tests for spatial stateful decomposition."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from brushline.strategic.decomposition import (
    DecompositionError,
    decompose_stateful,
    repair_stateful_clusters,
)
from brushline.strategic.stateful import (
    StatefulConfig,
    StatefulMethod,
    StatefulPeriod,
    StatefulSegment,
    build_stateful_plan,
)

CREATED = datetime(2026, 11, 15, tzinfo=UTC)


def _segments() -> list[StatefulSegment]:
    return [
        StatefulSegment(
            segment_id=f"s{index}",
            span_id=f"u{index // 2}",
            length_m=500,
            area_ha=3.5,
            initial_risk=0.2 + index * 0.03,
        )
        for index in range(4)
    ]


def _methods() -> list[StatefulMethod]:
    return [
        StatefulMethod(method="mowing", cost_per_ha=420, hours_per_ha=7, risk_reduction=0.30),
        StatefulMethod(method="manual", cost_per_ha=1450, hours_per_ha=32, risk_reduction=0.55),
    ]


def _periods() -> list[StatefulPeriod]:
    return [
        StatefulPeriod(year=2027, budget=20000, capacity_hours=100),
        StatefulPeriod(year=2028, budget=20000, capacity_hours=100),
    ]


def test_decomposition_builds_clusters_and_replays() -> None:
    plan = decompose_stateful(
        instance_id="tiny",
        segments=_segments(),
        methods=_methods(),
        periods=_periods(),
        config=StatefulConfig(risk_weight=1.0),
        max_segments_per_cluster=2,
        created_utc=CREATED,
    )
    assert plan.cluster_count == 2
    assert plan.plan.replay_ok
    assert plan.plan.actions
    assert plan.plan.status == "feasible"
    assert int(plan.plan.search["rounds"]) >= 1
    assert plan.plan.search["baseline_gap"] == 0.0
    assert sum(cluster.budget_total for cluster in plan.clusters) <= 40000
    assert all(cluster.status == "optimal" for cluster in plan.clusters)


def test_single_cluster_matches_direct_exact_plan() -> None:
    direct = build_stateful_plan(
        instance_id="tiny",
        segments=_segments(),
        methods=_methods(),
        periods=_periods(),
        config=StatefulConfig(risk_weight=1.0),
        created_utc=CREATED,
    )
    decomposed = decompose_stateful(
        instance_id="tiny",
        segments=_segments(),
        methods=_methods(),
        periods=_periods(),
        config=StatefulConfig(risk_weight=1.0),
        max_segments_per_cluster=10,
        baseline=direct,
        created_utc=CREATED,
    )
    assert decomposed.cluster_count == 1
    assert decomposed.plan.total_cost == pytest.approx(direct.total_cost)
    assert decomposed.plan.mean_risk == pytest.approx(direct.mean_risk)
    assert decomposed.gap_to_baseline == pytest.approx(0.0, abs=1e-12)


def test_decomposition_validation() -> None:
    with pytest.raises(DecompositionError, match="positive"):
        decompose_stateful(
            instance_id="tiny",
            segments=_segments(),
            methods=_methods(),
            periods=_periods(),
            max_segments_per_cluster=0,
        )
    with pytest.raises(DecompositionError, match="non-empty"):
        decompose_stateful(
            instance_id="tiny",
            segments=[],
            methods=_methods(),
            periods=_periods(),
        )


def test_cluster_repair_preserves_or_improves_baseline() -> None:
    baseline = build_stateful_plan(
        instance_id="tiny",
        segments=_segments(),
        methods=_methods(),
        periods=_periods(),
        config=StatefulConfig(risk_weight=1.0),
        created_utc=CREATED,
    )
    repaired = repair_stateful_clusters(
        instance_id="tiny",
        segments=_segments(),
        methods=_methods(),
        periods=_periods(),
        baseline=baseline,
        config=StatefulConfig(risk_weight=1.0, max_seconds=30),
        max_segments_per_cluster=2,
        created_utc=CREATED,
    )
    assert repaired.plan.replay_ok
    assert repaired.gap_to_baseline is not None
    assert repaired.gap_to_baseline <= 1e-9
    assert all(cluster.status == "optimal" for cluster in repaired.clusters)
