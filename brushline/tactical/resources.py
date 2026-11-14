"""Contractor capacity, productivity, and cost build-up."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from brushline.model.state import TreatmentMethod

RESOURCE_SCHEMA_VERSION: Literal["brushline.tactical-resources.v1"] = (
    "brushline.tactical-resources.v1"
)


class ResourceError(ValueError):
    """Raised when resource inputs are inconsistent."""


class ContractorProfile(BaseModel):
    """One contractor/crew/machine profile.

    Parameters
    ----------
    contractor_id : str
        Contractor id.
    methods : list of str
        Methods offered.
    crews : int
        Crew count.
    machines : int
        Machine count.
    rate_per_unit : float
        Base rate per capacity unit.
    travel_cost_per_km : float
        Travel cost per kilometre.
    supervision_rate : float
        Supervision fraction of base cost.
    overhead_fraction : float
        Overhead fraction.
    risk_fraction : float
        Risk fraction of base cost.
    annual_capacity_units : float
        Annual capacity units.
    currency : str
        Currency.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    contractor_id: str = Field(min_length=1)
    methods: list[TreatmentMethod] = Field(min_length=1)
    crews: int = Field(default=1, ge=1)
    machines: int = Field(default=0, ge=0)
    rate_per_unit: float = Field(ge=0)
    travel_cost_per_km: float = Field(default=0.0, ge=0)
    supervision_rate: float = Field(default=0.0, ge=0, le=1)
    overhead_fraction: float = Field(default=0.0, ge=0, le=1)
    risk_fraction: float = Field(default=0.0, ge=0, le=1)
    annual_capacity_units: float = Field(gt=0)
    currency: str = "CAD"


class ResourceRequest(BaseModel):
    """One contractor request.

    Parameters
    ----------
    request_id : str
        Request id.
    contractor_id : str
        Contractor id.
    method : str
        Method.
    year : int
        Year.
    capacity_units : float
        Capacity units.
    travel_km : float
        Travel distance.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    request_id: str = Field(min_length=1)
    contractor_id: str = Field(min_length=1)
    method: TreatmentMethod
    year: int = Field(ge=1900, le=2200)
    capacity_units: float = Field(gt=0)
    travel_km: float = Field(default=0.0, ge=0)


class CostLine(BaseModel):
    """One cost build-up line.

    Parameters
    ----------
    label : str
        Label.
    amount : float
        Amount.
    source : str
        Source.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    label: str
    amount: float = Field(ge=0)
    source: str


class ResourceViolation(BaseModel):
    """One resource violation.

    Parameters
    ----------
    code : str
        Code.
    message : str
        Explanation.
    request_id : str or None
        Request.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    code: str
    message: str
    request_id: str | None = None


class ResourcePlan(BaseModel):
    """A contractor/resource cost plan.

    Parameters
    ----------
    schema_version : {"brushline.tactical-resources.v1"}
        Schema version.
    plan_id : str
        Plan id.
    instance_id : str
        Instance id.
    requests : list of ResourceRequest
        Requests.
    lines : list of CostLine
        Cost lines.
    total_cost : float
        Total cost.
    by_contractor : dict of str to float
        Cost by contractor.
    by_year : dict of int to float
        Cost by year.
    feasible : bool
        Capacity/method satisfied.
    violations : list of ResourceViolation
        Violations.
    created_utc : datetime
        Timezone-aware time.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["brushline.tactical-resources.v1"] = RESOURCE_SCHEMA_VERSION
    plan_id: str
    instance_id: str
    requests: list[ResourceRequest]
    lines: list[CostLine]
    total_cost: float = Field(ge=0)
    by_contractor: dict[str, float]
    by_year: dict[int, float]
    feasible: bool
    violations: list[ResourceViolation] = Field(default_factory=list)
    created_utc: datetime


def build_resource_plan(
    *,
    plan_id: str,
    instance_id: str,
    requests: list[ResourceRequest],
    profiles: list[ContractorProfile],
    created_utc: datetime | None = None,
) -> ResourcePlan:
    """Build capacity and cost evidence for contractor requests.

    Parameters
    ----------
    plan_id : str
        Plan id.
    instance_id : str
        Instance id.
    requests : list of ResourceRequest
        Requests.
    profiles : list of ContractorProfile
        Profiles.
    created_utc : datetime, optional
        Creation time.

    Returns
    -------
    ResourcePlan
        Cost lines and feasibility.
    """
    profile_map = {profile.contractor_id: profile for profile in profiles}
    if len(profile_map) != len(profiles):
        raise ResourceError("contractor profiles must be unique")
    lines: list[CostLine] = []
    by_contractor: dict[str, float] = {}
    by_year: dict[int, float] = {}
    capacity: dict[tuple[str, int], float] = {}
    violations: list[ResourceViolation] = []
    for request in sorted(requests, key=lambda item: item.request_id):
        profile = profile_map.get(request.contractor_id)
        if profile is None:
            violations.append(
                ResourceViolation(
                    code="RESOURCE-PROFILE",
                    message=f"no profile for contractor {request.contractor_id}",
                    request_id=request.request_id,
                )
            )
            continue
        if request.method not in profile.methods:
            violations.append(
                ResourceViolation(
                    code="RESOURCE-METHOD",
                    message=f"{request.contractor_id} does not offer {request.method}",
                    request_id=request.request_id,
                )
            )
        key = (request.contractor_id, request.year)
        capacity[key] = capacity.get(key, 0.0) + request.capacity_units
        if capacity[key] > profile.annual_capacity_units + 1e-9:
            violations.append(
                ResourceViolation(
                    code="RESOURCE-CAPACITY",
                    message=f"{request.contractor_id} exceeds annual capacity",
                    request_id=request.request_id,
                )
            )
        base = request.capacity_units * profile.rate_per_unit
        travel = request.travel_km * profile.travel_cost_per_km
        supervision = base * profile.supervision_rate
        overhead = (base + travel + supervision) * profile.overhead_fraction
        risk = base * profile.risk_fraction
        total = base + travel + supervision + overhead + risk
        lines.extend(
            [
                CostLine(label="base", amount=base, source=request.request_id),
                CostLine(label="travel", amount=travel, source=request.request_id),
                CostLine(label="supervision", amount=supervision, source=request.request_id),
                CostLine(label="overhead", amount=overhead, source=request.request_id),
                CostLine(label="risk", amount=risk, source=request.request_id),
            ]
        )
        by_contractor[request.contractor_id] = by_contractor.get(request.contractor_id, 0.0) + total
        by_year[request.year] = by_year.get(request.year, 0.0) + total
    return ResourcePlan(
        plan_id=plan_id,
        instance_id=instance_id,
        requests=requests,
        lines=lines,
        total_cost=sum(item.amount for item in lines),
        by_contractor=by_contractor,
        by_year=by_year,
        feasible=not violations,
        violations=violations,
        created_utc=created_utc or datetime.now(UTC),
    )


__all__ = [
    "RESOURCE_SCHEMA_VERSION",
    "ContractorProfile",
    "CostLine",
    "ResourceError",
    "ResourcePlan",
    "ResourceRequest",
    "ResourceViolation",
    "build_resource_plan",
]
