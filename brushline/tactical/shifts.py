"""Deterministic FHOPS-style crew and equipment shift scheduling.

This is a small operational prototype, not a FHOPS engine replacement. It turns tactical work
items into crew-day and machine-day assignments, respecting method skills, daily shift hours,
travel time, and contractor identity.
"""

from __future__ import annotations

import math
from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

SHIFT_SCHEMA_VERSION: Literal["brushline.tactical-shifts.v1"] = "brushline.tactical-shifts.v1"


class ShiftError(ValueError):
    """Raised when shift inputs are inconsistent."""


class ShiftWorkItem(BaseModel):
    """One tactical action to schedule."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    work_order_id: str = Field(min_length=1)
    unit_id: str = Field(min_length=1)
    method: str = Field(min_length=1)
    year: int = Field(ge=1900, le=2200)
    hours: float = Field(gt=0)
    travel_hours: float = Field(default=0, ge=0)
    contractor_id: str | None = None
    priority: int = 0


class ShiftCrew(BaseModel):
    """One crew resource."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    crew_id: str = Field(min_length=1)
    methods: list[str] = Field(min_length=1)
    shift_hours: float = Field(default=8.0, gt=0, le=24)
    contractor_id: str | None = None


class ShiftMachine(BaseModel):
    """One machine resource."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    machine_id: str = Field(min_length=1)
    methods: list[str] = Field(min_length=1)
    shift_hours: float = Field(default=8.0, gt=0, le=24)
    contractor_id: str | None = None


class ShiftConfig(BaseModel):
    """Scheduler limits."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    max_days_per_year: int = Field(default=260, ge=1, le=366)
    include_travel: bool = True


class ShiftAssignment(BaseModel):
    """One work item chunk assigned to a crew and optional machine."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    work_order_id: str
    unit_id: str
    year: int
    day: int = Field(ge=1)
    crew_id: str
    machine_id: str | None
    method: str
    start_hour: float = Field(ge=0, le=24)
    end_hour: float = Field(ge=0, le=24)
    productive_hours: float = Field(gt=0)
    travel_hours: float = Field(ge=0)


class ShiftViolation(BaseModel):
    """One named scheduling violation."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    code: str
    message: str
    work_order_id: str | None = None


class ShiftPlan(BaseModel):
    """A deterministic crew/equipment shift plan."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["brushline.tactical-shifts.v1"] = SHIFT_SCHEMA_VERSION
    plan_id: str
    instance_id: str
    assignments: list[ShiftAssignment]
    total_productive_hours: float = Field(ge=0)
    total_travel_hours: float = Field(ge=0)
    crew_utilization: dict[str, float]
    machine_utilization: dict[str, float]
    feasible: bool
    violations: list[ShiftViolation] = Field(default_factory=list)
    created_utc: datetime


def _requires_machine(method: str) -> bool:
    return method in {"mowing", "mechanical"}


def build_shift_plan(
    *,
    plan_id: str,
    instance_id: str,
    work_items: list[ShiftWorkItem],
    crews: list[ShiftCrew],
    machines: list[ShiftMachine],
    config: ShiftConfig | None = None,
    created_utc: datetime | None = None,
) -> ShiftPlan:
    """Assign work items to crews, machines, days, and shift-hour windows.

    Parameters
    ----------
    plan_id : str
        Plan id.
    instance_id : str
        Instance id.
    work_items : list of ShiftWorkItem
        Tactical work items.
    crews : list of ShiftCrew
        Crews and their method skills.
    machines : list of ShiftMachine
        Machines and their method skills.
    config : ShiftConfig, optional
        Day and travel settings.
    created_utc : datetime, optional
        Creation time.

    Returns
    -------
    ShiftPlan
        Assignments, utilization, and named violations.

    Raises
    ------
    ShiftError
        If ids are duplicated or a work item has no positive hours.
    """
    rules = config or ShiftConfig()
    if len({item.work_order_id for item in work_items}) != len(work_items):
        raise ShiftError("work order ids must be unique")
    if len({item.crew_id for item in crews}) != len(crews):
        raise ShiftError("crew ids must be unique")
    if len({item.machine_id for item in machines}) != len(machines):
        raise ShiftError("machine ids must be unique")
    crew_hours: dict[tuple[str, int, int], float] = {}
    machine_hours: dict[tuple[str, int, int], float] = {}
    assignments: list[ShiftAssignment] = []
    violations: list[ShiftViolation] = []
    ordered = sorted(work_items, key=lambda item: (item.year, -item.priority, item.work_order_id))
    for item in ordered:
        remaining = item.hours
        travel_remaining = item.travel_hours if rules.include_travel else 0.0
        delivered = False
        for day in range(1, rules.max_days_per_year + 1):
            available_crews = [
                (
                    candidate,
                    candidate.shift_hours
                    - crew_hours.get((candidate.crew_id, item.year, day), 0.0),
                )
                for candidate in crews
                if item.method in candidate.methods
                and (
                    item.contractor_id is None
                    or candidate.contractor_id in (None, item.contractor_id)
                )
                and candidate.shift_hours - crew_hours.get((candidate.crew_id, item.year, day), 0.0)
                > 1e-9
            ]
            available_machines = [
                (
                    candidate,
                    candidate.shift_hours
                    - machine_hours.get((candidate.machine_id, item.year, day), 0.0),
                )
                for candidate in machines
                if item.method in candidate.methods
                and (
                    item.contractor_id is None
                    or candidate.contractor_id in (None, item.contractor_id)
                )
                and candidate.shift_hours
                - machine_hours.get((candidate.machine_id, item.year, day), 0.0)
                > 1e-9
            ]
            crew = max(available_crews, key=lambda pair: pair[1])[0] if available_crews else None
            machine = (
                max(available_machines, key=lambda pair: pair[1])[0] if available_machines else None
            )
            if crew is None:
                continue
            if _requires_machine(item.method) and machine is None:
                continue
            crew_available = crew.shift_hours - crew_hours.get((crew.crew_id, item.year, day), 0.0)
            machine_available = (
                machine.shift_hours - machine_hours.get((machine.machine_id, item.year, day), 0.0)
                if machine is not None
                else math.inf
            )
            capacity = min(crew_available, machine_available)
            if capacity <= 1e-9:
                continue
            travel = min(travel_remaining, capacity)
            productive_capacity = capacity - travel
            if productive_capacity <= 1e-9:
                continue
            productive = min(remaining, productive_capacity)
            if productive <= 1e-9:
                break
            start = crew.shift_hours - crew_available
            end = start + travel + productive
            assignments.append(
                ShiftAssignment(
                    work_order_id=item.work_order_id,
                    unit_id=item.unit_id,
                    year=item.year,
                    day=day,
                    crew_id=crew.crew_id,
                    machine_id=machine.machine_id if machine else None,
                    method=item.method,
                    start_hour=round(start, 2),
                    end_hour=round(end, 2),
                    productive_hours=round(productive, 2),
                    travel_hours=round(travel, 2),
                )
            )
            crew_hours[(crew.crew_id, item.year, day)] = (
                crew_hours.get((crew.crew_id, item.year, day), 0.0) + travel + productive
            )
            if machine is not None:
                machine_hours[(machine.machine_id, item.year, day)] = (
                    machine_hours.get((machine.machine_id, item.year, day), 0.0)
                    + travel
                    + productive
                )
            remaining -= productive
            travel_remaining -= travel
            if remaining <= 1e-9:
                delivered = True
                break
        if not delivered:
            violations.append(
                ShiftViolation(
                    code="SHIFT-UNSCHEDULED",
                    message=f"could not schedule {item.work_order_id}",
                    work_order_id=item.work_order_id,
                )
            )
    crew_utilization = {
        crew.crew_id: round(
            sum(
                value
                for (crew_id, _year, _day), value in crew_hours.items()
                if crew_id == crew.crew_id
            ),
            2,
        )
        for crew in crews
    }
    machine_utilization = {
        machine.machine_id: round(
            sum(
                value
                for (machine_id, _year, _day), value in machine_hours.items()
                if machine_id == machine.machine_id
            ),
            2,
        )
        for machine in machines
    }
    return ShiftPlan(
        plan_id=plan_id,
        instance_id=instance_id,
        assignments=assignments,
        total_productive_hours=round(sum(item.productive_hours for item in assignments), 2),
        total_travel_hours=round(sum(item.travel_hours for item in assignments), 2),
        crew_utilization=crew_utilization,
        machine_utilization=machine_utilization,
        feasible=not violations,
        violations=violations,
        created_utc=created_utc or datetime.now(UTC),
    )


__all__ = [
    "SHIFT_SCHEMA_VERSION",
    "ShiftAssignment",
    "ShiftConfig",
    "ShiftCrew",
    "ShiftError",
    "ShiftMachine",
    "ShiftPlan",
    "ShiftViolation",
    "ShiftWorkItem",
    "build_shift_plan",
]
