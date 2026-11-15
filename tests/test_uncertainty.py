"""Tests for execution uncertainty sampling."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from brushline.strategic.stateful import StatefulPeriod
from brushline.strategic.uncertainty import (
    UncertaintyConfig,
    UncertaintyError,
    evaluate_uncertainty,
)
from brushline.tactical.program import TacticalAction
from brushline.tactical.resources import ContractorProfile

CREATED = datetime(2026, 11, 15, tzinfo=UTC)


def _actions() -> list[TacticalAction]:
    return [
        TacticalAction(
            action_id="a1",
            unit_id="u1",
            year=2027,
            season="fall",
            method="mowing",
            contractor_id="c1",
            cost=1000,
            capacity_units=100,
        ),
        TacticalAction(
            action_id="a2",
            unit_id="u2",
            year=2028,
            season="fall",
            method="mowing",
            contractor_id="c1",
            cost=1000,
            capacity_units=100,
        ),
    ]


def _profiles() -> list[ContractorProfile]:
    return [
        ContractorProfile(
            contractor_id="c1",
            methods=["mowing"],
            annual_capacity_units=150,
            rate_per_unit=10,
        )
    ]


def _periods() -> list[StatefulPeriod]:
    return [
        StatefulPeriod(year=2027, budget=900, capacity_hours=120),
        StatefulPeriod(year=2028, budget=900, capacity_hours=120),
    ]


def test_uncertainty_bands_and_determinism() -> None:
    first = evaluate_uncertainty(
        instance_id="i",
        actions=_actions(),
        periods=_periods(),
        profiles=_profiles(),
        config=UncertaintyConfig(samples=100, seed=3),
        created_utc=CREATED,
    )
    second = evaluate_uncertainty(
        instance_id="i",
        actions=_actions(),
        periods=_periods(),
        profiles=_profiles(),
        config=UncertaintyConfig(samples=100, seed=3),
        created_utc=CREATED,
    )
    assert first.cost_band.p10 <= first.cost_band.p50 <= first.cost_band.p90
    assert first.hours_band.p10 <= first.hours_band.p50 <= first.hours_band.p90
    assert first.cost_band == second.cost_band
    assert first.samples_detail == second.samples_detail
    assert first.probability_budget_exceeded > 0
    assert len(first.sensitivity) == 5
    assert first.sensitivity[0].name == "baseline"


def test_uncertainty_capacity_stress_and_validation() -> None:
    result = evaluate_uncertainty(
        instance_id="i",
        actions=_actions(),
        periods=_periods(),
        profiles=_profiles(),
        config=UncertaintyConfig(samples=20, seed=3, hours_sigma=0.0, capacity_sigma=0.0),
        created_utc=CREATED,
    )
    assert result.probability_contractor_shortfall == 0
    with pytest.raises(UncertaintyError, match="non-empty"):
        evaluate_uncertainty(
            instance_id="i",
            actions=[],
            periods=_periods(),
            profiles=_profiles(),
        )
