"""Fast segment-level low-vegetation growth.

The growth model uses saturating height and cover curves per functional group, with site,
climate, and competition modifiers. It preserves uncertainty and age, flags out-of-domain
environments instead of extrapolating, and does not apply a treatment transition. It is
deterministic and cheap enough for the P5 search loop.
"""

from __future__ import annotations

import math
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from brushline.model.state import FunctionalGroup, StateClass, Uncertainty, VegetationState
from brushline.model.validation import ContractValidation
from brushline.vegetation.state_space import (
    StateDistribution,
    StateSpaceConfig,
    classify_state,
)

GROWTH_SCHEMA_VERSION: Literal["brushline.growth.v1"] = "brushline.growth.v1"
GROWTH_STATUSES: tuple[str, ...] = ("grown", "out_of_domain", "unknown")
GROWTH_MODEL_CARD = "brushline.low-vegetation.prototype.v0"


class GrowthError(ValueError):
    """Raised when a growth request is internally inconsistent."""


class GrowthParameters(BaseModel):
    """Growth parameters for one functional group.

    Parameters
    ----------
    group : str
        Functional group.
    height_max_m : float
        Height asymptote.
    height_rate : float
        Height saturation rate per year.
    cover_max_pct : float
        Cover asymptote.
    cover_rate : float
        Cover saturation rate per year.
    density_max_per_ha : float
        Density asymptote, or zero when density is not modelled.
    density_rate : float
        Density saturation rate per year.
    height_sd_m : float
        Annual height uncertainty.
    cover_sd_pct : float
        Annual cover uncertainty.
    competition_sensitivity : float
        Competition effect from 0 to 1.
    notes : str
        Short caveat.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    group: str
    height_max_m: float = Field(gt=0)
    height_rate: float = Field(gt=0)
    cover_max_pct: float = Field(gt=0, le=100)
    cover_rate: float = Field(gt=0)
    density_max_per_ha: float = Field(default=0, ge=0)
    density_rate: float = Field(default=0, ge=0)
    height_sd_m: float = Field(default=0, ge=0)
    cover_sd_pct: float = Field(default=0, ge=0)
    competition_sensitivity: float = Field(default=0, ge=0, le=1)
    notes: str = ""


GROWTH_PARAMETERS: tuple[GrowthParameters, ...] = (
    GrowthParameters(
        group="shrub",
        height_max_m=4.0,
        height_rate=0.35,
        cover_max_pct=90,
        cover_rate=0.35,
        density_max_per_ha=5000,
        density_rate=0.3,
        height_sd_m=0.35,
        cover_sd_pct=8,
        competition_sensitivity=0.35,
        notes="Low woody vegetation; cutting can increase density.",
    ),
    GrowthParameters(
        group="deciduous_sprout",
        height_max_m=10.0,
        height_rate=0.25,
        cover_max_pct=95,
        cover_rate=0.3,
        density_max_per_ha=3000,
        density_rate=0.25,
        height_sd_m=0.5,
        cover_sd_pct=10,
        competition_sensitivity=0.45,
        notes="Resprouting hardwood.",
    ),
    GrowthParameters(
        group="conifer",
        height_max_m=20.0,
        height_rate=0.12,
        cover_max_pct=90,
        cover_rate=0.2,
        density_max_per_ha=2000,
        density_rate=0.2,
        height_sd_m=0.6,
        cover_sd_pct=10,
        competition_sensitivity=0.3,
        notes="Young conifer or mature edge.",
    ),
    GrowthParameters(
        group="grass_herb",
        height_max_m=0.6,
        height_rate=0.9,
        cover_max_pct=100,
        cover_rate=0.8,
        density_max_per_ha=0,
        density_rate=0,
        height_sd_m=0.1,
        cover_sd_pct=12,
        competition_sensitivity=0.1,
        notes="Herbaceous layer; not a woody cover class.",
    ),
    GrowthParameters(
        group="unknown",
        height_max_m=1,
        height_rate=0.01,
        cover_max_pct=1,
        cover_rate=0.01,
        density_max_per_ha=0,
        density_rate=0,
        notes="No growth for an unknown state.",
    ),
)


class GrowthConfig(BaseModel):
    """Site, climate, and uncertainty rules for growth.

    Parameters
    ----------
    site_index_reference_m : float, optional
        Reference site index. Defaults to ``20``.
    site_factor_min : float, optional
        Minimum site modifier. Defaults to ``0.5``.
    site_factor_max : float, optional
        Maximum site modifier. Defaults to ``1.5``.
    site_index_min_m : float, optional
        Lower site-index domain. Defaults to ``0``.
    site_index_max_m : float, optional
        Upper site-index domain. Defaults to ``40``.
    climate_factor_min : float, optional
        Lower climate modifier domain. Defaults to ``0.5``.
    climate_factor_max : float, optional
        Upper climate modifier domain. Defaults to ``1.5``.
    max_years : int, optional
        Maximum step length. Defaults to ``20``.
    model_card_id : str, optional
        Model card id.
    state_space : StateSpaceConfig, optional
        Discretization rules.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    site_index_reference_m: float = Field(default=20.0, gt=0)
    site_factor_min: float = Field(default=0.5, gt=0)
    site_factor_max: float = Field(default=1.5, gt=0)
    site_index_min_m: float = Field(default=0.0, ge=0)
    site_index_max_m: float = Field(default=40.0, gt=0)
    climate_factor_min: float = Field(default=0.5, gt=0)
    climate_factor_max: float = Field(default=1.5, gt=0)
    max_years: int = Field(default=20, ge=1)
    model_card_id: str = GROWTH_MODEL_CARD
    state_space: StateSpaceConfig = Field(default_factory=StateSpaceConfig)

    @model_validator(mode="after")
    def _ordered_ranges(self) -> GrowthConfig:
        if self.site_factor_min >= self.site_factor_max:
            raise ValueError("site factor range must increase")
        if self.site_index_min_m >= self.site_index_max_m:
            raise ValueError("site-index domain must increase")
        if self.climate_factor_min >= self.climate_factor_max:
            raise ValueError("climate factor range must increase")
        return self


class GrowthEnvironment(BaseModel):
    """Site, climate, competition, and domain context.

    Parameters
    ----------
    site_index_m : float or None
        Site index, when known.
    climate_factor : float, optional
        Climate modifier. Defaults to ``1``.
    competition : float, optional
        Competition from 0 to 1. Defaults to ``0``.
    in_domain : bool, optional
        Whether the environment is inside the model domain. Defaults to ``True``.
    domain_reason : str, optional
        Why the environment is outside the domain.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    site_index_m: float | None = Field(default=None, ge=0)
    climate_factor: float = Field(default=1.0, gt=0)
    competition: float = Field(default=0.0, ge=0, le=1)
    in_domain: bool = True
    domain_reason: str = ""

    @model_validator(mode="after")
    def _domain_reason(self) -> GrowthEnvironment:
        if not self.in_domain and not self.domain_reason.strip():
            raise ValueError("an out-of-domain environment needs a reason")
        return self


class GrowthRequest(BaseModel):
    """A growth step for one segment.

    Parameters
    ----------
    segment_id : str
        Segment id.
    functional_group : str
        Functional group.
    current : StateDistribution
        Current distribution.
    years : int
        Growth step in years.
    environment : GrowthEnvironment
        Site, climate, and competition context.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    segment_id: str = Field(min_length=1)
    functional_group: FunctionalGroup
    current: StateDistribution
    years: int = Field(ge=1, le=50)
    environment: GrowthEnvironment = Field(default_factory=GrowthEnvironment)


class GrowthResult(BaseModel):
    """The result of one growth step.

    Parameters
    ----------
    schema_version : {"brushline.growth.v1"}
        Result schema version.
    segment_id : str
        Segment id.
    functional_group : str
        Functional group.
    status : str
        ``grown``, ``out_of_domain``, or ``unknown``.
    years : int
        Growth step.
    previous : StateDistribution
        Previous distribution.
    next : StateDistribution or None
        Next distribution, or ``None`` when the step is blocked.
    next_state_class : str or None
        Class implied by the grown distribution.
    environment : GrowthEnvironment
        Environment context.
    height_change_m : float or None
        Height change.
    cover_change_pct : float or None
        Cover change.
    reason : str
        Why the step is blocked or how it grew.
    model_card_id : str
        Model card.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["brushline.growth.v1"] = GROWTH_SCHEMA_VERSION
    segment_id: str
    functional_group: FunctionalGroup
    status: str
    years: int
    previous: StateDistribution
    next: StateDistribution | None = None
    next_state_class: StateClass | None = None
    environment: GrowthEnvironment
    height_change_m: float | None = None
    cover_change_pct: float | None = None
    reason: str = ""
    model_card_id: str = GROWTH_MODEL_CARD

    def to_vegetation_state(self, state_year: int) -> VegetationState:
        """Convert the grown distribution to a state contract.

        Parameters
        ----------
        state_year : int
            Output state year.

        Returns
        -------
        VegetationState
            The grown state.

        Raises
        ------
        GrowthError
            When the growth step did not produce a next distribution.
        """
        if self.next is None or self.next_state_class is None:
            raise GrowthError("no grown distribution is available")
        return VegetationState(
            segment_id=self.segment_id,
            state_year=state_year,
            functional_group=self.functional_group,
            state_class=self.next_state_class,
            height_m=self.next.height_m,
            cover_pct=self.next.cover_pct,
            density_per_ha=self.next.density_per_ha,
            age_years=self.next.age_years,
            uncertainty=Uncertainty(
                height_m_sd=self.next.height_sd,
                cover_pct_sd=self.next.cover_sd,
                density_sd=self.next.density_sd,
                confidence=self.next.confidence,
            ),
            source="brushline.vegetation.growth",
            source_version="p4.2",
            model_card_id=self.model_card_id,
        )


def grow(
    request: GrowthRequest,
    config: GrowthConfig | None = None,
) -> GrowthResult:
    """Grow one segment by a fixed number of years.

    Parameters
    ----------
    request : GrowthRequest
        Current distribution, group, years, and environment.
    config : GrowthConfig, optional
        Growth rules.

    Returns
    -------
    GrowthResult
        The grown distribution or an explicit blocked status.

    Raises
    ------
    GrowthError
        When the step length exceeds the configured maximum.
    """
    rules = config or GrowthConfig()
    if request.years > rules.max_years:
        raise GrowthError(f"years {request.years} exceeds the configured maximum {rules.max_years}")
    reason = _domain_reason(request.environment, rules)
    if reason:
        return GrowthResult(
            segment_id=request.segment_id,
            functional_group=request.functional_group,
            status="out_of_domain",
            years=request.years,
            previous=request.current,
            environment=request.environment,
            reason=reason,
            model_card_id=rules.model_card_id,
        )
    if request.functional_group == "unknown":
        return GrowthResult(
            segment_id=request.segment_id,
            functional_group=request.functional_group,
            status="unknown",
            years=request.years,
            previous=request.current,
            environment=request.environment,
            reason="an unknown functional group has no growth model",
            model_card_id=rules.model_card_id,
        )
    parameters = _parameters(request.functional_group)
    modifier = _modifier(request.environment, parameters, rules)
    current = request.current
    height = _saturate(
        current.height_m,
        parameters.height_max_m,
        parameters.height_rate,
        modifier,
        request.years,
    )
    cover = _saturate(
        current.cover_pct,
        parameters.cover_max_pct,
        parameters.cover_rate,
        modifier,
        request.years,
    )
    density = (
        _saturate(
            current.density_per_ha or 0,
            parameters.density_max_per_ha,
            parameters.density_rate,
            modifier,
            request.years,
        )
        if current.density_per_ha is not None and parameters.density_max_per_ha > 0
        else current.density_per_ha
    )
    age = current.age_years + request.years if current.age_years is not None else None
    state_class = classify_state(
        height,
        cover,
        request.functional_group,
        rules.state_space,
    )
    if state_class == "unknown":
        state_class = "partial"
    probabilities = {
        state_class: 0.8,
        "unknown": 0.2,
    }
    next_distribution = StateDistribution(
        class_probabilities=probabilities,
        height_m=height,
        height_sd=math.hypot(
            current.height_sd,
            parameters.height_sd_m * request.years,
        ),
        cover_pct=cover,
        cover_sd=math.hypot(
            current.cover_sd,
            parameters.cover_sd_pct * request.years,
        ),
        density_per_ha=density,
        density_sd=(
            math.hypot(
                current.density_sd,
                parameters.density_rate * request.years,
            )
            if density is not None
            else 0.0
        ),
        age_years=age,
        confidence=max(0.0, current.confidence - 0.02 * request.years),
    )
    return GrowthResult(
        segment_id=request.segment_id,
        functional_group=request.functional_group,
        status="grown",
        years=request.years,
        previous=current,
        next=next_distribution,
        next_state_class=state_class,
        environment=request.environment,
        height_change_m=height - current.height_m,
        cover_change_pct=cover - current.cover_pct,
        reason="saturating growth with site, climate, and competition modifiers",
        model_card_id=rules.model_card_id,
    )


def validate_growth_result(result: GrowthResult) -> ContractValidation:
    """Validate a growth result and its bounds.

    Parameters
    ----------
    result : GrowthResult
        Result to validate.

    Returns
    -------
    ContractValidation
        Errors, warnings, and counts.
    """
    errors: list[str] = []
    warnings: list[str] = []
    if result.status not in GROWTH_STATUSES:
        errors.append(f"GROWTH-STATUS: unknown status {result.status!r}")
    if result.status != "grown":
        if result.next is not None:
            errors.append("GROWTH-NEXT: a blocked result has a next distribution")
        if not result.reason.strip():
            errors.append("GROWTH-REASON: a blocked result has no reason")
    else:
        if result.next is None or result.next_state_class is None:
            errors.append("GROWTH-NEXT: a grown result has no next distribution")
        else:
            parameters = _parameters(result.functional_group)
            if result.next.height_m < result.previous.height_m - 1e-9:
                errors.append("GROWTH-MONOTONE: height decreased during growth")
            if result.next.cover_pct < result.previous.cover_pct - 1e-9:
                errors.append("GROWTH-MONOTONE: cover decreased during growth")
            if result.next.height_m > parameters.height_max_m + 1e-9:
                errors.append("GROWTH-BOUND: height exceeds the asymptote")
            if result.next.cover_pct > parameters.cover_max_pct + 1e-9:
                errors.append("GROWTH-BOUND: cover exceeds the asymptote")
            if result.next.class_probabilities.get(result.next_state_class, 0) <= 0:
                errors.append("GROWTH-PROBABILITY: next class has no probability")
            if (
                result.next.age_years is not None
                and result.previous.age_years is not None
                and result.next.age_years != result.previous.age_years + result.years
            ):
                errors.append("GROWTH-AGE: age did not advance by the step")
    counts: dict[str, int | float] = {
        "segments": 1,
        "years": result.years,
        "status": 1 if result.status == "grown" else 0,
    }
    return ContractValidation(tuple(errors), tuple(warnings), counts)


def _parameters(group: FunctionalGroup) -> GrowthParameters:
    for parameters in GROWTH_PARAMETERS:
        if parameters.group == group:
            return parameters
    raise GrowthError(f"no growth parameters for {group!r}")


def _domain_reason(environment: GrowthEnvironment, config: GrowthConfig) -> str:
    if not environment.in_domain:
        return environment.domain_reason
    if environment.site_index_m is not None and not (
        config.site_index_min_m <= environment.site_index_m <= config.site_index_max_m
    ):
        return "site index is outside the growth applicability domain"
    if not (config.climate_factor_min <= environment.climate_factor <= config.climate_factor_max):
        return "climate factor is outside the growth applicability domain"
    return ""


def _modifier(
    environment: GrowthEnvironment,
    parameters: GrowthParameters,
    config: GrowthConfig,
) -> float:
    site = 1.0
    if environment.site_index_m is not None:
        site = max(
            config.site_factor_min,
            min(
                config.site_factor_max,
                environment.site_index_m / config.site_index_reference_m,
            ),
        )
    climate = max(
        config.climate_factor_min,
        min(config.climate_factor_max, environment.climate_factor),
    )
    competition = max(
        0.0,
        1.0 - environment.competition * parameters.competition_sensitivity,
    )
    return site * climate * competition


def _saturate(
    current: float,
    asymptote: float,
    rate: float,
    modifier: float,
    years: int,
) -> float:
    if current >= asymptote:
        return current
    return asymptote - (asymptote - current) * math.exp(-rate * modifier * years)


__all__ = [
    "GROWTH_MODEL_CARD",
    "GROWTH_PARAMETERS",
    "GROWTH_SCHEMA_VERSION",
    "GROWTH_STATUSES",
    "GrowthConfig",
    "GrowthEnvironment",
    "GrowthError",
    "GrowthParameters",
    "GrowthRequest",
    "GrowthResult",
    "grow",
    "validate_growth_result",
]
