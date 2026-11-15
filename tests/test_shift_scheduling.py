"""Tests for deterministic shift scheduling."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from brushline.tactical.shifts import (
    ShiftConfig,
    ShiftCrew,
    ShiftError,
    ShiftMachine,
    ShiftWorkItem,
    build_shift_plan,
)

CREATED = datetime(2026, 11, 15, tzinfo=UTC)


def _crews() -> list[ShiftCrew]:
    return [
        ShiftCrew(crew_id="crew-a", methods=["manual", "mowing"], shift_hours=8),
        ShiftCrew(crew_id="crew-b", methods=["mowing"], shift_hours=8),
    ]


def _machines() -> list[ShiftMachine]:
    return [ShiftMachine(machine_id="mower", methods=["mowing"], shift_hours=8)]


def _item(
    work_order_id: str = "wo-1",
    hours: float = 12,
    method: str = "mowing",
    contractor_id: str | None = None,
) -> ShiftWorkItem:
    return ShiftWorkItem(
        work_order_id=work_order_id,
        unit_id="U1",
        method=method,
        year=2027,
        hours=hours,
        travel_hours=1,
        contractor_id=contractor_id,
    )


def test_shift_plan_splits_work_across_days() -> None:
    plan = build_shift_plan(
        plan_id="s1",
        instance_id="i1",
        work_items=[_item()],
        crews=_crews(),
        machines=_machines(),
        config=ShiftConfig(max_days_per_year=10),
        created_utc=CREATED,
    )
    assert plan.feasible
    assert len(plan.assignments) == 2
    assert sum(item.productive_hours for item in plan.assignments) == pytest.approx(12)
    assert sum(item.travel_hours for item in plan.assignments) == pytest.approx(1)
    assert plan.total_productive_hours == pytest.approx(12)
    assert plan.crew_utilization["crew-a"] == pytest.approx(13)


def test_shift_plan_rejects_unknown_skill() -> None:
    plan = build_shift_plan(
        plan_id="s1",
        instance_id="i1",
        work_items=[_item(method="mechanical")],
        crews=_crews(),
        machines=_machines(),
        config=ShiftConfig(max_days_per_year=3),
        created_utc=CREATED,
    )
    assert not plan.feasible
    assert plan.violations
    assert plan.assignments == []


def test_shift_plan_honours_contractor_and_duplicate_checks() -> None:
    plan = build_shift_plan(
        plan_id="s1",
        instance_id="i1",
        work_items=[_item(contractor_id="target")],
        crews=[ShiftCrew(crew_id="c", methods=["mowing"], contractor_id="other")],
        machines=_machines(),
        config=ShiftConfig(max_days_per_year=2),
    )
    assert not plan.feasible
    with pytest.raises(ShiftError, match="unique"):
        build_shift_plan(
            plan_id="s1",
            instance_id="i1",
            work_items=[_item("same"), _item("same")],
            crews=_crews(),
            machines=_machines(),
        )
