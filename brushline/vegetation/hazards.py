"""Hazard and service indicators from the vegetation state and corridor context.

The indicators are decision aids, not engineering certifications. Each component records its
formula, units, inputs, and caveat. A missing input is unknown, never zero. The reliability proxy
is a declared weighted combination of the available components.
"""

from __future__ import annotations

import math
from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from brushline.model.corridor import ServiceStandard
from brushline.model.validation import ContractValidation

HAZARD_SCHEMA_VERSION: Literal["brushline.hazards.v1"] = "brushline.hazards.v1"
CLEARANCE_STATUSES: tuple[str, ...] = ("clear", "at_risk", "exceeded", "unknown")
FALL_IN_STATUSES: tuple[str, ...] = ("low", "moderate", "high", "unknown")
FUEL_STATUSES: tuple[str, ...] = ("low", "moderate", "high", "unknown")
ACCESS_CLASSES: tuple[str, ...] = ("high", "moderate", "low", "unknown")
RELIABILITY_CLASSES: tuple[str, ...] = ("high", "moderate", "low", "unknown")
RELIABILITY_COMPONENTS: tuple[str, ...] = ("clearance", "fall_in", "fuel", "access")
DEFAULT_WEIGHTS: dict[str, float] = {
    "clearance": 0.4,
    "fall_in": 0.25,
    "fuel": 0.15,
    "access": 0.2,
}


class HazardConfig(BaseModel):
    """Thresholds, weights, and formula assumptions.

    Parameters
    ----------
    clearance_warning_m : float, optional
        Margin at or below which clearance is at risk. Defaults to ``1``.
    wind_factor : float, optional
        Fall-in reach multiplier. Defaults to ``1.5``.
    fuel_distance_scale_m : float, optional
        Neighbour decay distance. Defaults to ``50``.
    access_slope_zero_deg : float, optional
        Slope at which the access slope factor reaches zero. Defaults to ``30``.
    weights : dict of str to float, optional
        Reliability weights.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    clearance_warning_m: float = Field(default=1.0, ge=0)
    wind_factor: float = Field(default=1.5, gt=0)
    fuel_distance_scale_m: float = Field(default=50.0, gt=0)
    access_slope_zero_deg: float = Field(default=30.0, gt=0)
    weights: dict[str, float] = Field(default_factory=lambda: dict(DEFAULT_WEIGHTS))

    @model_validator(mode="after")
    def _weights(self) -> HazardConfig:
        if set(self.weights) != set(RELIABILITY_COMPONENTS):
            raise ValueError("weights must name every reliability component")
        if any(value < 0 for value in self.weights.values()):
            raise ValueError("weights must be non-negative")
        if abs(sum(self.weights.values()) - 1.0) > 1e-9:
            raise ValueError("weights must sum to 1")
        return self


class FuelNeighbor(BaseModel):
    """One adjacent segment's fuel evidence.

    Parameters
    ----------
    segment_id : str
        Neighbour segment id.
    cover_pct : float
        Neighbour cover.
    distance_m : float
        Distance from the segment.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    segment_id: str = Field(min_length=1)
    cover_pct: float = Field(ge=0, le=100)
    distance_m: float = Field(ge=0)


class AccessEvidence(BaseModel):
    """Source-preserving road and slope evidence.

    Parameters
    ----------
    slope_deg : float
        Local slope.
    road_status : str
        Source road status, such as ``class_1``.
    road_status_source : str
        Source name for the status.
    road_score : float
        Explicit source-preserving score from 0 to 1.
    distance_m : float
        Distance to the road evidence.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    slope_deg: float = Field(ge=0, le=90)
    road_status: str = Field(min_length=1)
    road_status_source: str = Field(min_length=1)
    road_score: float = Field(ge=0, le=1)
    distance_m: float = Field(ge=0)


class HazardRequest(BaseModel):
    """One segment's hazard inputs.

    Parameters
    ----------
    segment_id : str
        Segment id.
    height_m : float
        Mean vegetation height.
    cover_pct : float
        Mean vegetation cover.
    height_sd_m : float, optional
        Height standard deviation.
    service_standard : ServiceStandard
        Service standard.
    asset_height_m : float or None, optional
        Conductor or asset height above ground.
    edge_height_m : float or None, optional
        Mature-edge tree height.
    edge_distance_m : float or None, optional
        Distance from the mature edge to the asset.
    neighbors : list of FuelNeighbor, optional
        Adjacent fuel evidence.
    access : AccessEvidence or None, optional
        Road and slope evidence.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    segment_id: str = Field(min_length=1)
    height_m: float = Field(ge=0)
    cover_pct: float = Field(ge=0, le=100)
    height_sd_m: float = Field(default=0.0, ge=0)
    service_standard: ServiceStandard
    asset_height_m: float | None = Field(default=None, gt=0)
    edge_height_m: float | None = Field(default=None, ge=0)
    edge_distance_m: float | None = Field(default=None, ge=0)
    neighbors: list[FuelNeighbor] = Field(default_factory=list)
    access: AccessEvidence | None = None

    @model_validator(mode="after")
    def _edge_pair(self) -> HazardRequest:
        if (self.edge_height_m is None) != (self.edge_distance_m is None):
            raise ValueError("edge height and distance must be supplied together")
        return self


class ClearanceIndicator(BaseModel):
    """Clearance versus the service standard and optional asset.

    Parameters
    ----------
    status : str
        ``clear``, ``at_risk``, ``exceeded``, or ``unknown``.
    height_m : float
        Vegetation height.
    max_height_m : float
        Service-standard maximum.
    min_clearance_m : float
        Service-standard clearance.
    asset_height_m : float or None
        Asset height, when supplied.
    height_margin_m : float
        Service maximum minus vegetation height.
    clearance_gap_m : float or None
        Asset height minus vegetation height and minimum clearance.
    formula : str
        Formula description.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    status: str
    height_m: float
    max_height_m: float
    min_clearance_m: float
    asset_height_m: float | None
    height_margin_m: float
    clearance_gap_m: float | None
    formula: str = (
        "height_margin = max_height - height; gap = asset_height - height - min_clearance"
    )


class FallInIndicator(BaseModel):
    """Mature-edge fall-in reach and risk.

    Parameters
    ----------
    status : str
        ``low``, ``moderate``, ``high``, or ``unknown``.
    edge_height_m : float or None
        Tree height.
    edge_distance_m : float or None
        Distance to the asset.
    wind_factor : float
        Reach multiplier.
    reach_m : float or None
        Fall-in reach.
    risk : float or None
        Risk from 0 to 1.
    formula : str
        Formula description.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    status: str
    edge_height_m: float | None
    edge_distance_m: float | None
    wind_factor: float
    reach_m: float | None
    risk: float | None = Field(default=None, ge=0, le=1)
    formula: str = "reach = edge_height * wind_factor; risk = clamp(1 - distance / reach, 0, 1)"


class FuelIndicator(BaseModel):
    """Fuel continuity from adjacent segments.

    Parameters
    ----------
    status : str
        ``low``, ``moderate``, ``high``, or ``unknown``.
    connectivity : float or None
        Connectivity from 0 to 1.
    neighbor_count : int
        Number of neighbours.
    formula : str
        Formula description.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    status: str
    connectivity: float | None = Field(default=None, ge=0, le=1)
    neighbor_count: int = Field(ge=0)
    formula: str = "distance-weighted mean neighbour cover / 100"


class AccessIndicator(BaseModel):
    """Slope and source-preserving road access proxy.

    Parameters
    ----------
    status : str
        ``high``, ``moderate``, ``low``, or ``unknown``.
    slope_deg : float or None
        Local slope.
    slope_factor : float or None
        Slope factor from 0 to 1.
    road_status : str
        Source road status.
    road_status_source : str
        Source name.
    road_score : float or None
        Source score.
    distance_m : float or None
        Distance to road evidence.
    proxy : float or None
        Access proxy from 0 to 1.
    formula : str
        Formula description.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    status: str
    slope_deg: float | None = None
    slope_factor: float | None = Field(default=None, ge=0, le=1)
    road_status: str = ""
    road_status_source: str = ""
    road_score: float | None = Field(default=None, ge=0, le=1)
    distance_m: float | None = Field(default=None, ge=0)
    proxy: float | None = Field(default=None, ge=0, le=1)
    formula: str = "proxy = clamp(1 - slope / zero_slope, 0, 1) * road_score"


class ReliabilityIndicator(BaseModel):
    """Weighted reliability proxy.

    Parameters
    ----------
    status : str
        ``high``, ``moderate``, ``low``, or ``unknown``.
    score : float or None
        Score from 0 to 1.
    weights : dict of str to float
        Weights used.
    components : dict of str to float
        Available component scores.
    formula : str
        Formula description.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    status: str
    score: float | None = Field(default=None, ge=0, le=1)
    weights: dict[str, float]
    components: dict[str, float] = Field(default_factory=dict)
    formula: str = "weighted mean of available clearance, fall-in, fuel, and access scores"


class HazardReport(BaseModel):
    """The hazard report for one segment.

    Parameters
    ----------
    schema_version : {"brushline.hazards.v1"}
        Report schema version.
    created_utc : datetime
        Timezone-aware creation time.
    segment_id : str
        Segment id.
    clearance : ClearanceIndicator
        Clearance evidence.
    fall_in : FallInIndicator
        Fall-in evidence.
    fuel : FuelIndicator
        Fuel continuity evidence.
    access : AccessIndicator
        Access evidence.
    reliability : ReliabilityIndicator
        Weighted reliability proxy.
    caveats : list of str
        Decision-support caveats.
    """

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["brushline.hazards.v1"] = HAZARD_SCHEMA_VERSION
    created_utc: datetime
    segment_id: str
    clearance: ClearanceIndicator
    fall_in: FallInIndicator
    fuel: FuelIndicator
    access: AccessIndicator
    reliability: ReliabilityIndicator
    caveats: list[str] = Field(default_factory=list)


def assess_hazards(
    request: HazardRequest,
    config: HazardConfig | None = None,
    *,
    created_utc: datetime | None = None,
) -> HazardReport:
    """Assess the hazard and service indicators for one segment.

    Parameters
    ----------
    request : HazardRequest
        Vegetation, service standard, and context.
    config : HazardConfig, optional
        Thresholds and weights.
    created_utc : datetime, optional
        Report time.

    Returns
    -------
    HazardReport
        Component indicators and the reliability proxy.
    """
    rules = config or HazardConfig()
    clearance = _clearance(request, rules)
    fall_in = _fall_in(request, rules)
    fuel = _fuel(request, rules)
    access = _access(request, rules)
    reliability = _reliability(clearance, fall_in, fuel, access, rules)
    caveats = [
        "Decision-support proxy only; not an engineering clearance or safety certification.",
        "Road status is source-preserving; a source class is not an open/closed verdict.",
        "The reliability weights are declared assumptions, not field-calibrated coefficients.",
    ]
    if clearance.status == "unknown" or fall_in.status == "unknown":
        caveats.append("One or more reliability components are unknown and were omitted.")
    return HazardReport(
        created_utc=created_utc or datetime.now(UTC),
        segment_id=request.segment_id,
        clearance=clearance,
        fall_in=fall_in,
        fuel=fuel,
        access=access,
        reliability=reliability,
        caveats=caveats,
    )


def validate_hazard_report(report: HazardReport) -> ContractValidation:
    """Validate the hazard statuses, ranges, and reliability composition.

    Parameters
    ----------
    report : HazardReport
        Report to validate.

    Returns
    -------
    ContractValidation
        Errors, warnings, and counts.
    """
    errors: list[str] = []
    warnings: list[str] = []
    if report.created_utc.tzinfo is None:
        errors.append("HAZARD-TIME: created_utc is not timezone-aware")
    if report.clearance.status not in CLEARANCE_STATUSES:
        errors.append("HAZARD-CLEARANCE: unknown clearance status")
    if report.fall_in.status not in FALL_IN_STATUSES:
        errors.append("HAZARD-FALLIN: unknown fall-in status")
    if report.fuel.status not in FUEL_STATUSES:
        errors.append("HAZARD-FUEL: unknown fuel status")
    if report.access.status not in ACCESS_CLASSES:
        errors.append("HAZARD-ACCESS: unknown access status")
    if report.reliability.status not in RELIABILITY_CLASSES:
        errors.append("HAZARD-RELIABILITY: unknown reliability status")
    if set(report.reliability.weights) != set(RELIABILITY_COMPONENTS):
        errors.append("HAZARD-RELIABILITY: weights do not name every component")
    if abs(sum(report.reliability.weights.values()) - 1.0) > 1e-9:
        errors.append("HAZARD-RELIABILITY: weights do not sum to 1")
    if report.reliability.score is None:
        warnings.append("HAZARD-RELIABILITY: no components are available")
    elif not report.reliability.components:
        errors.append("HAZARD-RELIABILITY: score has no component evidence")
    if (
        report.clearance.status == "exceeded"
        and report.clearance.height_margin_m >= 0
        and (report.clearance.clearance_gap_m is None or report.clearance.clearance_gap_m >= 0)
    ):
        errors.append("HAZARD-CLEARANCE: exceeded status has a non-negative margin")
    if report.fall_in.status != "unknown" and report.fall_in.risk is None:
        errors.append("HAZARD-FALLIN: known status has no risk")
    if report.fuel.status == "unknown" and report.fuel.neighbor_count:
        errors.append("HAZARD-FUEL: unknown status has neighbours")
    if report.access.status != "unknown" and report.access.proxy is None:
        errors.append("HAZARD-ACCESS: known status has no proxy")
    if not report.caveats:
        warnings.append("HAZARD-CAVEAT: the report has no caveats")
    counts: dict[str, int | float] = {
        "segments": 1,
        "reliability_components": len(report.reliability.components),
    }
    if report.reliability.score is not None:
        counts["reliability"] = report.reliability.score
    return ContractValidation(tuple(errors), tuple(warnings), counts)


def _clearance(request: HazardRequest, config: HazardConfig) -> ClearanceIndicator:
    standard = request.service_standard
    margin = standard.max_height_m - request.height_m
    gap = (
        request.asset_height_m - request.height_m - standard.min_clearance_m
        if request.asset_height_m is not None
        else None
    )
    if margin >= config.clearance_warning_m and (gap is None or gap >= 0):
        status = "clear"
    elif margin >= 0 and (gap is None or gap >= 0):
        status = "at_risk"
    else:
        status = "exceeded"
    return ClearanceIndicator(
        status=status,
        height_m=request.height_m,
        max_height_m=standard.max_height_m,
        min_clearance_m=standard.min_clearance_m,
        asset_height_m=request.asset_height_m,
        height_margin_m=margin,
        clearance_gap_m=gap,
    )


def _fall_in(request: HazardRequest, config: HazardConfig) -> FallInIndicator:
    if request.edge_height_m is None or request.edge_distance_m is None:
        return FallInIndicator(
            status="unknown",
            edge_height_m=None,
            edge_distance_m=None,
            wind_factor=config.wind_factor,
            reach_m=None,
            risk=None,
        )
    reach = request.edge_height_m * config.wind_factor
    risk = max(0.0, min(1.0, 1.0 - request.edge_distance_m / reach)) if reach > 0 else 0.0
    if risk < 0.25:
        status = "low"
    elif risk < 0.6:
        status = "moderate"
    else:
        status = "high"
    return FallInIndicator(
        status=status,
        edge_height_m=request.edge_height_m,
        edge_distance_m=request.edge_distance_m,
        wind_factor=config.wind_factor,
        reach_m=reach,
        risk=risk,
    )


def _fuel(request: HazardRequest, config: HazardConfig) -> FuelIndicator:
    if not request.neighbors:
        return FuelIndicator(
            status="unknown",
            connectivity=None,
            neighbor_count=0,
        )
    weights = [
        math.exp(-neighbor.distance_m / config.fuel_distance_scale_m)
        for neighbor in request.neighbors
    ]
    total = sum(weights)
    connectivity = (
        sum(
            neighbor.cover_pct * weight
            for neighbor, weight in zip(request.neighbors, weights, strict=True)
        )
        / total
        / 100.0
        if total > 0
        else 0.0
    )
    if connectivity < 0.25:
        status = "low"
    elif connectivity < 0.6:
        status = "moderate"
    else:
        status = "high"
    return FuelIndicator(
        status=status,
        connectivity=connectivity,
        neighbor_count=len(request.neighbors),
    )


def _access(request: HazardRequest, config: HazardConfig) -> AccessIndicator:
    if request.access is None:
        return AccessIndicator(status="unknown")
    slope_factor = max(
        0.0,
        min(1.0, 1.0 - request.access.slope_deg / config.access_slope_zero_deg),
    )
    proxy = slope_factor * request.access.road_score
    if proxy >= 0.7:
        status = "high"
    elif proxy >= 0.4:
        status = "moderate"
    else:
        status = "low"
    return AccessIndicator(
        status=status,
        slope_deg=request.access.slope_deg,
        slope_factor=slope_factor,
        road_status=request.access.road_status,
        road_status_source=request.access.road_status_source,
        road_score=request.access.road_score,
        distance_m=request.access.distance_m,
        proxy=proxy,
    )


def _reliability(
    clearance: ClearanceIndicator,
    fall_in: FallInIndicator,
    fuel: FuelIndicator,
    access: AccessIndicator,
    config: HazardConfig,
) -> ReliabilityIndicator:
    components: dict[str, float] = {}
    if clearance.status == "clear":
        components["clearance"] = 1.0
    elif clearance.status == "at_risk":
        components["clearance"] = 0.5
    elif clearance.status == "exceeded":
        components["clearance"] = 0.0
    if fall_in.risk is not None:
        components["fall_in"] = 1.0 - fall_in.risk
    if fuel.connectivity is not None:
        components["fuel"] = 1.0 - fuel.connectivity
    if access.proxy is not None:
        components["access"] = access.proxy
    if not components:
        return ReliabilityIndicator(
            status="unknown",
            score=None,
            weights=dict(config.weights),
            components={},
        )
    total_weight = sum(config.weights[name] for name in components)
    score = (
        sum(components[name] * config.weights[name] for name in components) / total_weight
        if total_weight > 0
        else 0.0
    )
    if score >= 0.7:
        status = "high"
    elif score >= 0.4:
        status = "moderate"
    else:
        status = "low"
    return ReliabilityIndicator(
        status=status,
        score=score,
        weights=dict(config.weights),
        components=components,
    )


__all__ = [
    "ACCESS_CLASSES",
    "CLEARANCE_STATUSES",
    "DEFAULT_WEIGHTS",
    "FALL_IN_STATUSES",
    "FUEL_STATUSES",
    "HAZARD_SCHEMA_VERSION",
    "RELIABILITY_CLASSES",
    "RELIABILITY_COMPONENTS",
    "AccessEvidence",
    "AccessIndicator",
    "ClearanceIndicator",
    "FallInIndicator",
    "FuelIndicator",
    "FuelNeighbor",
    "HazardConfig",
    "HazardReport",
    "HazardRequest",
    "ReliabilityIndicator",
    "assess_hazards",
    "validate_hazard_report",
]
