"""Tests for the P7.5 optional FHOPS boundary."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from brushline.tactical.fhops import (
    FHOPS_PINNED_VERSION,
    FhopsBoundary,
    FhopsConfig,
    FhopsRequest,
    dry_run,
    fhops_version,
    request_from_action,
)
from brushline.tactical.program import TacticalAction
from pydantic import ValidationError

NOW = datetime(2026, 11, 14, tzinfo=UTC)


def _action() -> TacticalAction:
    return TacticalAction(
        action_id="a1",
        unit_id="u1",
        year=2026,
        season="spring",
        method="mowing",
        contractor_id="c1",
        cost=100,
        capacity_units=1,
    )


def test_mapping_and_dry_run_are_deterministic() -> None:
    """The adapter maps a tactical action and returns dry-run evidence."""
    request = request_from_action(_action(), area_ha=1, machines=2, shift_hours=8, days=2)
    assert request.unit_id == "u1"
    assert request.machines == 2
    result = dry_run(
        request,
        FhopsConfig(units_per_machine_hour=0.25, cost_per_machine_hour=100, move_cost=50),
        created_utc=NOW,
    )
    assert result.status == "dry_run"
    assert result.machine_hours == 32
    assert result.productivity_units_per_day == 4
    assert result.total_cost == 3250
    assert len(result.notes) == 2
    assert FHOPS_PINNED_VERSION in result.notes[1]
    assert result.created_utc == NOW
    assert fhops_version() != "not-installed"


def test_boundary_and_model_guards() -> None:
    """Boundary options and local request rules are explicit."""
    boundary = FhopsBoundary()
    assert boundary.package == "fhops"
    assert boundary.optional
    assert "productivity-dry-run" in boundary.capabilities
    with pytest.raises(ValidationError):
        FhopsRequest(
            unit_id="u",
            action_id="a",
            area_ha=0,
            method="mowing",
            machines=1,
            shift_hours=8,
            days=1,
        )
    with pytest.raises(ValidationError):
        FhopsConfig(units_per_machine_hour=0)
    with pytest.raises(ValidationError):
        FhopsRequest(
            unit_id="u",
            action_id="a",
            area_ha=1,
            method="mowing",
            machines=1,
            shift_hours=25,
            days=1,
        )
