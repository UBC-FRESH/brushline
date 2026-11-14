"""Tests for the P8.3 value of information."""

from __future__ import annotations

import pytest
from brushline.monitoring.value import MonitoringCandidate, fixed_calendar, select_monitoring


def test_value_selection_and_calendar() -> None:
    candidates = [
        MonitoringCandidate(
            candidate_id="a",
            span_id="s1",
            cost=10,
            coverage=0.9,
            uncertainty=0.8,
            expected_loss_reduction=50,
        ),
        MonitoringCandidate(
            candidate_id="b",
            span_id="s2",
            cost=100,
            coverage=0.9,
            uncertainty=0.8,
            expected_loss_reduction=20,
        ),
    ]
    value = select_monitoring(candidates, report_id="r", budget=20)
    assert len(value.choices) == 1
    assert value.choices[0].candidate_id == "a"
    assert value.total_cost == 10
    assert value.expected_loss_reduction == 50
    assert value.value_of_information == 40
    assert value.regret_per_dollar == 5
    calendar = fixed_calendar(candidates, report_id="r", budget=20)
    assert len(calendar.choices) == 1
    assert calendar.choices[0].candidate_id == "a"


def test_negative_value_and_budget() -> None:
    candidates = [
        MonitoringCandidate(
            candidate_id="a",
            span_id="s1",
            cost=100,
            coverage=1,
            uncertainty=1,
            expected_loss_reduction=1,
        )
    ]
    value = select_monitoring(candidates, report_id="r", budget=10)
    assert value.choices == []
    assert value.total_cost == 0
    assert value.value_of_information == 0
    with pytest.raises(ValueError, match="non-negative"):
        select_monitoring([], report_id="r", budget=-1)
