"""Optional FHOPS boundary and deterministic dry-run adapter."""

from __future__ import annotations

import importlib.metadata
from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from brushline.tactical.program import TacticalAction

FHOPS_SCHEMA_VERSION: Literal["brushline.tactical-fhops.v1"] = "brushline.tactical-fhops.v1"
FHOPS_PACKAGE = "fhops"
FHOPS_PINNED_VERSION = "1.1.0b1"


class FhopsError(ValueError):
    """Raised when the FHOPS boundary is inconsistent."""


class FhopsBoundary(BaseModel):
    """The optional FHOPS boundary manifest.

    Parameters
    ----------
    package : str
        Package name.
    pinned_version : str
        Supported version.
    optional : bool
        Whether the dependency is optional.
    capabilities : list of str
        Supported mapping capabilities.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    package: str = FHOPS_PACKAGE
    pinned_version: str = FHOPS_PINNED_VERSION
    optional: bool = True
    capabilities: list[str] = Field(
        default_factory=lambda: [
            "treatment-unit-to-scenario",
            "productivity-dry-run",
            "cost-dry-run",
            "timeline-dry-run",
        ]
    )


class FhopsRequest(BaseModel):
    """A FHOPS scenario request for one treatment unit.

    Parameters
    ----------
    unit_id : str
        Treatment unit.
    action_id : str
        Source action.
    area_ha : float
        Area.
    method : str
        Method.
    machines : int
        Machine count.
    shift_hours : float
        Shift hours.
    days : int
        Planned days.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    unit_id: str = Field(min_length=1)
    action_id: str = Field(min_length=1)
    area_ha: float = Field(gt=0)
    method: str
    machines: int = Field(ge=1)
    shift_hours: float = Field(gt=0, le=24)
    days: int = Field(ge=1)


class FhopsConfig(BaseModel):
    """Dry-run productivity and cost settings.

    Parameters
    ----------
    units_per_machine_hour : float
        Productivity per machine hour.
    cost_per_machine_hour : float
        Cost per machine hour.
    move_cost : float
        Fixed move cost.
    currency : str
        Currency.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    units_per_machine_hour: float = Field(default=0.25, gt=0)
    cost_per_machine_hour: float = Field(default=180.0, ge=0)
    move_cost: float = Field(default=100.0, ge=0)
    currency: str = "CAD"


class FhopsResult(BaseModel):
    """A normalized FHOPS or dry-run result.

    Parameters
    ----------
    schema_version : {"brushline.tactical-fhops.v1"}
        Schema version.
    action_id : str
        Source action.
    unit_id : str
        Unit.
    status : {"dry_run", "live", "unavailable"}
        Result status.
    machine_hours : float
        Machine hours.
    productivity_units_per_day : float
        Units per day.
    total_cost : float
        Cost.
    notes : list of str
        Notes/caveats.
    created_utc : datetime
        Timezone-aware time.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["brushline.tactical-fhops.v1"] = FHOPS_SCHEMA_VERSION
    action_id: str
    unit_id: str
    status: str
    machine_hours: float = Field(ge=0)
    productivity_units_per_day: float = Field(ge=0)
    total_cost: float = Field(ge=0)
    notes: list[str] = Field(default_factory=list)
    created_utc: datetime


def fhops_version() -> str:
    """Return the installed FHOPS version or ``not-installed``.

    Returns
    -------
    str
        Version.
    """
    try:
        return importlib.metadata.version(FHOPS_PACKAGE)
    except importlib.metadata.PackageNotFoundError:
        return "not-installed"


def request_from_action(
    action: TacticalAction,
    *,
    area_ha: float,
    machines: int = 1,
    shift_hours: float = 8.0,
    days: int = 1,
) -> FhopsRequest:
    """Map a tactical action to a FHOPS request.

    Parameters
    ----------
    action : TacticalAction
        Tactical action.
    area_ha : float
        Area.
    machines : int, optional
        Machine count.
    shift_hours : float, optional
        Shift hours.
    days : int, optional
        Days.

    Returns
    -------
    FhopsRequest
        Request.
    """
    return FhopsRequest(
        unit_id=action.unit_id,
        action_id=action.action_id,
        area_ha=area_ha,
        method=action.method,
        machines=machines,
        shift_hours=shift_hours,
        days=days,
    )


def dry_run(
    request: FhopsRequest,
    config: FhopsConfig | None = None,
    *,
    created_utc: datetime | None = None,
) -> FhopsResult:
    """Run the deterministic dry-run productivity/cost model.

    Parameters
    ----------
    request : FhopsRequest
        Request.
    config : FhopsConfig, optional
        Settings.
    created_utc : datetime, optional
        Creation time.

    Returns
    -------
    FhopsResult
        Dry-run result.
    """
    rules = config or FhopsConfig()
    machine_hours = request.machines * request.shift_hours * request.days
    productivity = request.machines * request.shift_hours * rules.units_per_machine_hour
    total_cost = machine_hours * rules.cost_per_machine_hour + rules.move_cost
    return FhopsResult(
        action_id=request.action_id,
        unit_id=request.unit_id,
        status="dry_run",
        machine_hours=machine_hours,
        productivity_units_per_day=productivity,
        total_cost=total_cost,
        notes=[
            "Dry-run only; no FHOPS engine was executed.",
            f"Boundary pins FHOPS {FHOPS_PINNED_VERSION}; installed version: {fhops_version()}.",
        ],
        created_utc=created_utc or datetime.now(UTC),
    )


__all__ = [
    "FHOPS_PACKAGE",
    "FHOPS_PINNED_VERSION",
    "FHOPS_SCHEMA_VERSION",
    "FhopsBoundary",
    "FhopsConfig",
    "FhopsError",
    "FhopsRequest",
    "FhopsResult",
    "dry_run",
    "fhops_version",
    "request_from_action",
]
