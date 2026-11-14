"""Tests for the P6.3 strategic monitoring policy."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from brushline.strategic.monitoring import (
    MonitoringConfig,
    MonitoringError,
    MonitoringOption,
    MonitoringPolicy,
    MonitoringSpan,
    build_monitoring_policy,
    validate_monitoring_inputs,
)
from pydantic import ValidationError

NOW = datetime(2026, 11, 14, tzinfo=UTC)


def _spans() -> list[MonitoringSpan]:
    return [
        MonitoringSpan(
            span_id="sp1",
            segment_ids=["s1", "s2"],
            baseline_uncertainty=0.6,
            service_risk=0.5,
            route_m=1000,
        ),
        MonitoringSpan(
            span_id="sp2",
            segment_ids=["s3"],
            baseline_uncertainty=0.3,
            service_risk=0.2,
            route_m=500,
        ),
    ]


def _options() -> list[MonitoringOption]:
    return [
        MonitoringOption(
            option_id="sp1-lidar",
            span_id="sp1",
            sensor="lidar",
            route="full",
            interval_years=1,
            sampling_intensity=0.8,
            cost_per_event=50,
            uncertainty_reduction=0.5,
            risk_reduction=0.4,
        ),
        MonitoringOption(
            option_id="sp1-field",
            span_id="sp1",
            sensor="field",
            route="sample",
            interval_years=2,
            sampling_intensity=0.4,
            cost_per_event=20,
            uncertainty_reduction=0.3,
            risk_reduction=0.2,
        ),
        MonitoringOption(
            option_id="sp2-field",
            span_id="sp2",
            sensor="field",
            route="sample",
            interval_years=2,
            sampling_intensity=0.5,
            cost_per_event=50,
            uncertainty_reduction=0.5,
            risk_reduction=0.4,
        ),
    ]


def _policy(
    config: MonitoringConfig | None = None,
    options: list[MonitoringOption] | None = None,
) -> MonitoringPolicy:
    return build_monitoring_policy(
        policy_id="p6-monitoring",
        instance_id="tiny",
        spans=_spans(),
        options=_options() if options is None else options,
        config=config,
        created_utc=NOW,
    )


def test_monitoring_is_selected_by_value_not_a_fixed_calendar() -> None:
    """The policy chooses intervals, sensors, routes, and event years by net value."""
    policy = _policy(MonitoringConfig(horizon_years=5, budget=400, value_per_unit=1000))
    assert policy.feasible
    assert policy.total_cost == 400
    assert len(policy.decisions) == 2
    by_span = {item.span_id: item for item in policy.decisions}
    assert by_span["sp1"].sensor == "lidar"
    assert by_span["sp1"].interval_years == 1
    assert by_span["sp1"].event_years == [2026, 2027, 2028, 2029, 2030]
    assert by_span["sp2"].interval_years == 2
    assert by_span["sp2"].event_years == [2026, 2028, 2030]
    assert policy.expected_uncertainty_reduction == pytest.approx(0.225)
    assert policy.expected_risk_reduction == pytest.approx(0.14)
    assert policy.total_net_value > 0
    assert policy.created_utc == NOW
    assert len(policy.caveats) == 3


def test_budget_and_minimum_value_can_leave_spans_unmonitored() -> None:
    """A budget or value floor can select nothing without hiding the decision."""
    low_budget = _policy(MonitoringConfig(horizon_years=5, budget=50, value_per_unit=1000))
    assert low_budget.feasible
    assert low_budget.decisions == []
    assert low_budget.total_cost == 0
    high_floor = _policy(
        MonitoringConfig(
            horizon_years=5,
            budget=1000,
            value_per_unit=1000,
            min_net_value=10000,
        )
    )
    assert high_floor.decisions == []
    assert high_floor.total_net_value == 0


def test_no_options_and_invalid_references() -> None:
    """Empty and invalid inputs are explicit."""
    empty = _policy(options=[])
    assert empty.decisions == []
    assert empty.feasible
    assert validate_monitoring_inputs(_spans(), []).warnings != ()
    bad = _options()[0].model_copy(update={"span_id": "missing"})
    with pytest.raises(MonitoringError):
        _policy(options=[bad])
    with pytest.raises(MonitoringError):
        _policy(options=[_options()[0], _options()[0]])
    assert not validate_monitoring_inputs(_spans(), [bad]).is_valid


def test_models_validate_local_rules() -> None:
    """Span and option rules reject impossible values."""
    with pytest.raises(ValidationError):
        MonitoringSpan(
            span_id="bad",
            segment_ids=[],
            baseline_uncertainty=0,
            service_risk=0,
            route_m=1,
        )
    with pytest.raises(ValidationError):
        MonitoringOption(
            option_id="bad",
            span_id="sp1",
            sensor="lidar",
            route="",
            interval_years=1,
            sampling_intensity=0,
            cost_per_event=1,
            uncertainty_reduction=0,
            risk_reduction=0,
        )
    with pytest.raises(ValidationError):
        MonitoringOption(
            option_id="bad",
            span_id="sp1",
            sensor="lidar",
            route="x",
            interval_years=0,
            sampling_intensity=0,
            cost_per_event=1,
            uncertainty_reduction=0,
            risk_reduction=0,
        )
    with pytest.raises(ValidationError):
        MonitoringConfig(horizon_years=0)
