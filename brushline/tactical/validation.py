"""Synthetic tactical/operational validation."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from brushline.tactical.access import AccessPlan, AccessWindow, RoadLink, build_access_plan
from brushline.tactical.fhops import FhopsConfig, FhopsResult, dry_run, request_from_action
from brushline.tactical.operations import OperationsConfig, OperationsPlan, build_operations_plan
from brushline.tactical.program import (
    TacticalAction,
    TacticalConfig,
    TacticalProgram,
    TreatmentUnit,
    build_tactical_program,
)
from brushline.tactical.resources import (
    ContractorProfile,
    ResourcePlan,
    ResourceRequest,
    build_resource_plan,
)
from brushline.tactical.timeline import (
    OperationsTimeline,
    TimelineConfig,
    build_operations_timeline,
)

VALIDATION_SCHEMA_VERSION: Literal["brushline.tactical-validation.v1"] = (
    "brushline.tactical-validation.v1"
)


class ValidationCheck(BaseModel):
    """One named validation check.

    Parameters
    ----------
    code : str
        Code.
    passed : bool
        Result.
    detail : str
        Explanation.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    code: str = Field(min_length=1)
    passed: bool
    detail: str = ""


class TacticalValidationResult(BaseModel):
    """Tactical/operational validation result.

    Parameters
    ----------
    schema_version : {"brushline.tactical-validation.v1"}
        Schema version.
    instance_id : str
        Instance id.
    program_id : str
        Program id.
    operations_id : str
        Operations plan id.
    timeline_id : str
        Timeline id.
    checks : list of ValidationCheck
        Checks.
    passed : bool
        All checks pass.
    created_utc : datetime
        Timezone-aware time.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["brushline.tactical-validation.v1"] = VALIDATION_SCHEMA_VERSION
    instance_id: str
    program_id: str
    operations_id: str
    timeline_id: str
    checks: list[ValidationCheck] = Field(min_length=1)
    passed: bool
    created_utc: datetime

    @model_validator(mode="after")
    def _time(self) -> TacticalValidationResult:
        if self.created_utc.tzinfo is None:
            raise ValueError("created_utc must be timezone-aware")
        return self


class SyntheticCase(BaseModel):
    """A complete synthetic tactical/operational case.

    Parameters
    ----------
    program : TacticalProgram
        Tactical program.
    access : AccessPlan
        Access plan.
    resources : ResourcePlan
        Resource plan.
    operations : OperationsPlan
        Operations plan.
    fhops : FhopsResult
        Dry-run FHOPS result.
    timeline : OperationsTimeline
        Timeline.
    validation : TacticalValidationResult
        Validation result.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    program: TacticalProgram
    access: AccessPlan
    resources: ResourcePlan
    operations: OperationsPlan
    fhops: FhopsResult
    timeline: OperationsTimeline
    validation: TacticalValidationResult


def build_synthetic_case(created_utc: datetime | None = None) -> SyntheticCase:
    """Build and validate a deterministic synthetic tactical/operational case.

    Parameters
    ----------
    created_utc : datetime, optional
        Creation time.

    Returns
    -------
    SyntheticCase
        Program, access, resources, operations, dry-run, timeline, and validation.
    """
    created = created_utc or datetime(2026, 11, 14, tzinfo=UTC)
    units = [
        TreatmentUnit(
            unit_id="u1",
            span_id="sp1",
            segment_ids=["s1", "s2"],
            area_ha=2,
            allowed_methods=["mowing"],
            allowed_seasons=["spring"],
        ),
        TreatmentUnit(
            unit_id="u2",
            span_id="sp1",
            segment_ids=["s3"],
            area_ha=1,
            allowed_methods=["manual"],
            allowed_seasons=["fall"],
        ),
    ]
    actions = [
        TacticalAction(
            action_id="a1",
            unit_id="u1",
            year=2026,
            season="spring",
            method="mowing",
            contractor_id="c1",
            cost=100,
            capacity_units=1,
            access_window_id="w1",
        ),
        TacticalAction(
            action_id="a2",
            unit_id="u2",
            year=2026,
            season="fall",
            method="manual",
            contractor_id="c2",
            cost=80,
            capacity_units=1,
            access_window_id="w2",
        ),
    ]
    program = build_tactical_program(
        program_id="p7-program",
        instance_id="synthetic-tactical",
        units=units,
        actions=actions,
        config=TacticalConfig(horizon_years=1, start_year=2026, budget_by_year={2026: 300}),
        created_utc=created,
    )
    links = [
        RoadLink(
            link_id="l1",
            source="fresh-road",
            status="open",
            status_source="alsroads",
            length_m=200,
        ),
        RoadLink(
            link_id="l2",
            source="fresh-road",
            status="open",
            status_source="alsroads",
            length_m=100,
        ),
    ]
    windows = [
        AccessWindow(window_id="w1", unit_id="u1", link_id="l1", year=2026, season="spring"),
        AccessWindow(window_id="w2", unit_id="u2", link_id="l2", year=2026, season="fall"),
    ]
    access = build_access_plan(
        plan_id="p7-access",
        instance_id="synthetic-tactical",
        windows=windows,
        links=links,
        created_utc=created,
    )
    profiles = [
        ContractorProfile(
            contractor_id="c1",
            methods=["mowing"],
            rate_per_unit=100,
            travel_cost_per_km=2,
            supervision_rate=0.1,
            overhead_fraction=0.05,
            risk_fraction=0.02,
            annual_capacity_units=2,
        ),
        ContractorProfile(
            contractor_id="c2",
            methods=["manual"],
            rate_per_unit=80,
            travel_cost_per_km=2,
            supervision_rate=0.1,
            overhead_fraction=0.05,
            risk_fraction=0.02,
            annual_capacity_units=2,
        ),
    ]
    requests = [
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
            contractor_id="c2",
            method="manual",
            year=2026,
            capacity_units=1,
            travel_km=5,
        ),
    ]
    resources = build_resource_plan(
        plan_id="p7-resources",
        instance_id="synthetic-tactical",
        requests=requests,
        profiles=profiles,
        created_utc=created,
    )
    operations = build_operations_plan(
        plan_id="p7-operations",
        instance_id="synthetic-tactical",
        program=program,
        access=access,
        config=OperationsConfig(max_orders_per_day=1, crew_ids=["crew-1", "crew-2"]),
        created_utc=created,
    )
    fhops = dry_run(
        request_from_action(actions[0], area_ha=2, machines=1, shift_hours=8, days=1),
        FhopsConfig(units_per_machine_hour=0.2, cost_per_machine_hour=100, move_cost=50),
        created_utc=created,
    )
    timeline = build_operations_timeline(
        timeline_id="p7-timeline",
        instance_id="synthetic-tactical",
        plan=operations,
        config=TimelineConfig(start_time=datetime(2026, 3, 1, tzinfo=UTC)),
        created_utc=created,
    )
    checks = [
        ValidationCheck(
            code="CAPACITY",
            passed=program.feasible and resources.feasible,
            detail="program and contractor capacity are feasible",
        ),
        ValidationCheck(
            code="ACCESS",
            passed=access.feasible,
            detail=f"access windows={len(access.results)}",
        ),
        ValidationCheck(
            code="SEASONALITY",
            passed=not any(
                item.code in {"TACTICAL-SEASON", "TACTICAL-METHOD"} for item in program.violations
            ),
            detail="methods and seasons match the units",
        ),
        ValidationCheck(
            code="TRACEABILITY",
            passed={order.action_id for order in operations.work_orders}
            == {action.action_id for action in program.actions},
            detail=f"work orders={len(operations.work_orders)}",
        ),
        ValidationCheck(
            code="DRY_RUN",
            passed=fhops.status == "dry_run" and fhops.total_cost > 0,
            detail=f"status={fhops.status} cost={fhops.total_cost:.2f}",
        ),
        ValidationCheck(
            code="TIMELINE",
            passed=len(timeline.events) == len(operations.work_orders) * 2,
            detail=f"events={len(timeline.events)}",
        ),
    ]
    validation = TacticalValidationResult(
        instance_id="synthetic-tactical",
        program_id=program.program_id,
        operations_id=operations.plan_id,
        timeline_id=timeline.timeline_id,
        checks=checks,
        passed=all(check.passed for check in checks),
        created_utc=created,
    )
    return SyntheticCase(
        program=program,
        access=access,
        resources=resources,
        operations=operations,
        fhops=fhops,
        timeline=timeline,
        validation=validation,
    )


def write_validation(result: TacticalValidationResult, path: str | Path) -> Path:
    """Write a validation result.

    Parameters
    ----------
    result : TacticalValidationResult
        Result.
    path : str or Path
        Destination.

    Returns
    -------
    Path
        Written path.
    """
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(result.model_dump_json(indent=2) + "\n", encoding="utf-8")
    return destination


def load_validation(path: str | Path) -> TacticalValidationResult:
    """Load a validation result.

    Parameters
    ----------
    path : str or Path
        Source.

    Returns
    -------
    TacticalValidationResult
        Result.
    """
    return TacticalValidationResult.model_validate_json(Path(path).read_text(encoding="utf-8"))


__all__ = [
    "VALIDATION_SCHEMA_VERSION",
    "SyntheticCase",
    "TacticalValidationResult",
    "ValidationCheck",
    "build_synthetic_case",
    "load_validation",
    "write_validation",
]
