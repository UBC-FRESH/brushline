"""Tests for the P7.2 resource plan."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from brushline.tactical.resources import (
    ContractorProfile,
    ResourceError,
    ResourceRequest,
    build_resource_plan,
)
from pydantic import ValidationError

NOW = datetime(2026, 11, 14, tzinfo=UTC)


def _profiles() -> list[ContractorProfile]:
    return [
        ContractorProfile(
            contractor_id="c1",
            methods=["mowing", "manual"],
            rate_per_unit=100,
            travel_cost_per_km=2,
            supervision_rate=0.1,
            overhead_fraction=0.05,
            risk_fraction=0.02,
            annual_capacity_units=2,
        )
    ]


def _requests() -> list[ResourceRequest]:
    return [
        ResourceRequest(
            request_id="r1",
            contractor_id="c1",
            method="mowing",
            year=2026,
            capacity_units=1,
            travel_km=10,
        ),
        ResourceRequest(
            request_id="r2",
            contractor_id="c1",
            method="mowing",
            year=2026,
            capacity_units=2,
            travel_km=5,
        ),
    ]


def test_cost_build_up_and_capacity_violation() -> None:
    """Every cost line is explicit and excess capacity is named."""
    plan = build_resource_plan(
        plan_id="r", instance_id="tiny", requests=_requests(), profiles=_profiles()
    )
    assert not plan.feasible
    assert any(v.code == "RESOURCE-CAPACITY" for v in plan.violations)
    assert {line.label for line in plan.lines} == {
        "base",
        "travel",
        "supervision",
        "overhead",
        "risk",
    }
    assert plan.by_contractor["c1"] == pytest.approx(plan.total_cost)
    assert plan.by_year == {2026: pytest.approx(plan.total_cost)}
    assert plan.created_utc.tzinfo is not None


def test_missing_profile_method_and_models() -> None:
    """Missing profiles and methods are explicit; local models validate."""
    missing = _requests()[0].model_copy(update={"contractor_id": "missing"})
    plan = build_resource_plan(
        plan_id="r", instance_id="tiny", requests=[missing], profiles=_profiles()
    )
    assert not plan.feasible
    assert plan.violations[0].code == "RESOURCE-PROFILE"
    bad_method = _requests()[0].model_copy(update={"method": "chemical"})
    plan = build_resource_plan(
        plan_id="r", instance_id="tiny", requests=[bad_method], profiles=_profiles()
    )
    assert any(v.code == "RESOURCE-METHOD" for v in plan.violations)
    with pytest.raises(ResourceError):
        build_resource_plan(
            plan_id="r",
            instance_id="tiny",
            requests=[],
            profiles=[_profiles()[0], _profiles()[0]],
        )
    with pytest.raises(ValidationError):
        ContractorProfile(
            contractor_id="x",
            methods=[],
            rate_per_unit=1,
            annual_capacity_units=1,
        )
    with pytest.raises(ValidationError):
        ResourceRequest(
            request_id="x",
            contractor_id="c",
            method="mowing",
            year=2026,
            capacity_units=0,
        )
