"""Operational work plan: work orders, sequence, crew assignment, and day windows."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from brushline.tactical.access import AccessPlan
from brushline.tactical.program import TacticalProgram

OPERATIONS_SCHEMA_VERSION: Literal["brushline.tactical-operations.v1"] = (
    "brushline.tactical-operations.v1"
)


class OperationsConfig(BaseModel):
    """Operational scheduling settings.

    Parameters
    ----------
    start_year : int
        First year.
    start_day : int
        First day number.
    max_orders_per_day : int
        Daily work-order cap.
    crew_ids : list of str
        Available crews.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    start_year: int = Field(default=2026, ge=1900, le=2200)
    start_day: int = Field(default=1, ge=1)
    max_orders_per_day: int = Field(default=2, ge=1)
    crew_ids: list[str] = Field(default_factory=lambda: ["crew-1"])


class WorkOrder(BaseModel):
    """One work-ready order.

    Parameters
    ----------
    work_order_id : str
        Work order id.
    action_id : str
        Source tactical action.
    unit_id : str
        Unit id.
    contractor_id : str
        Contractor id.
    crew_id : str
        Crew id.
    machine_id : str or None
        Machine id.
    year : int
        Year.
    day : int
        Day number.
    season : str
        Season.
    method : str
        Method.
    cost : float
        Cost.
    status : str
        Status.
    segment_ids : list of str, optional
        Source segment ids.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    work_order_id: str
    action_id: str
    unit_id: str
    contractor_id: str
    crew_id: str
    machine_id: str | None = None
    year: int
    day: int = Field(ge=1)
    season: str
    method: str
    cost: float = Field(ge=0)
    status: str = "ready"
    segment_ids: list[str] = Field(default_factory=list)


class OperationsViolation(BaseModel):
    """One operational violation.

    Parameters
    ----------
    code : str
        Code.
    message : str
        Explanation.
    action_id : str or None
        Action.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    code: str
    message: str
    action_id: str | None = None


class OperationsPlan(BaseModel):
    """A work-ready operational plan.

    Parameters
    ----------
    schema_version : {"brushline.tactical-operations.v1"}
        Schema version.
    plan_id : str
        Plan id.
    instance_id : str
        Instance id.
    program_id : str
        Source tactical program.
    work_orders : list of WorkOrder
        Work orders.
    feasible : bool
        All actions scheduled.
    violations : list of OperationsViolation
        Violations.
    total_cost : float
        Total cost.
    created_utc : datetime
        Timezone-aware time.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["brushline.tactical-operations.v1"] = OPERATIONS_SCHEMA_VERSION
    plan_id: str
    instance_id: str
    program_id: str
    work_orders: list[WorkOrder]
    feasible: bool
    violations: list[OperationsViolation] = Field(default_factory=list)
    total_cost: float = Field(ge=0)
    created_utc: datetime


def build_operations_plan(
    *,
    plan_id: str,
    instance_id: str,
    program: TacticalProgram,
    access: AccessPlan,
    config: OperationsConfig | None = None,
    created_utc: datetime | None = None,
) -> OperationsPlan:
    """Assign tactical actions to crews and days.

    Parameters
    ----------
    plan_id : str
        Plan id.
    instance_id : str
        Instance id.
    program : TacticalProgram
        Tactical program.
    access : AccessPlan
        Access decisions.
    config : OperationsConfig, optional
        Scheduling settings.
    created_utc : datetime, optional
        Creation time.

    Returns
    -------
    OperationsPlan
        Work orders and violations.
    """
    rules = config or OperationsConfig()
    access_by_window = {result.window_id: result for result in access.results}
    violations: list[OperationsViolation] = []
    orders: list[WorkOrder] = []
    ordered = sorted(program.actions, key=lambda item: (item.year, item.action_id))
    for index, action in enumerate(ordered):
        if action.access_window_id is None:
            violations.append(
                OperationsViolation(
                    code="OPERATIONS-ACCESS-MISSING",
                    message=f"action {action.action_id} has no access window",
                    action_id=action.action_id,
                )
            )
            continue
        result = access_by_window.get(action.access_window_id)
        if result is None:
            violations.append(
                OperationsViolation(
                    code="OPERATIONS-ACCESS-MISSING",
                    message=f"access window {action.access_window_id} is missing",
                    action_id=action.action_id,
                )
            )
            continue
        if not result.allowed:
            violations.append(
                OperationsViolation(
                    code="OPERATIONS-ACCESS-BLOCKED",
                    message=f"access is {result.status}",
                    action_id=action.action_id,
                )
            )
            continue
        crew = rules.crew_ids[index % len(rules.crew_ids)]
        day = rules.start_day + index // rules.max_orders_per_day
        unit = next((item for item in program.units if item.unit_id == action.unit_id), None)
        orders.append(
            WorkOrder(
                work_order_id=f"wo-{action.action_id}",
                action_id=action.action_id,
                unit_id=action.unit_id,
                contractor_id=action.contractor_id,
                crew_id=crew,
                machine_id=None,
                year=action.year,
                day=day,
                season=action.season,
                method=action.method,
                cost=action.cost,
                segment_ids=list(unit.segment_ids) if unit else [],
            )
        )
    return OperationsPlan(
        plan_id=plan_id,
        instance_id=instance_id,
        program_id=program.program_id,
        work_orders=orders,
        feasible=not violations,
        violations=violations,
        total_cost=sum(order.cost for order in orders),
        created_utc=created_utc or datetime.now(UTC),
    )


__all__ = [
    "OPERATIONS_SCHEMA_VERSION",
    "OperationsConfig",
    "OperationsPlan",
    "OperationsViolation",
    "WorkOrder",
    "build_operations_plan",
]
