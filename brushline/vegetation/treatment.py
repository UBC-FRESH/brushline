"""Method-specific low-vegetation treatment transitions.

A treatment is a transition, not a reset to zero. The model records the immediate top-kill and
cover reduction, a density change from resprouting, a regrowth delay, and a post-delay trajectory
through the P4.2 growth model. The efficacy parameters are priors; P4.4 calibrates them.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from brushline.model.state import (
    SEASONS,
    FunctionalGroup,
    Season,
    StateClass,
    TreatmentMethod,
    Uncertainty,
    VegetationState,
)
from brushline.model.validation import ContractValidation
from brushline.vegetation.growth import (
    GrowthConfig,
    GrowthEnvironment,
    GrowthRequest,
    grow,
)
from brushline.vegetation.state_space import (
    StateDistribution,
    StateSpaceConfig,
    classify_state,
)

TREATMENT_SCHEMA_VERSION: Literal["brushline.treatment.v1"] = "brushline.treatment.v1"
TREATMENT_STATUSES: tuple[str, ...] = ("applied", "out_of_domain", "unknown")
TREATMENT_MODEL_CARD = "brushline.low-vegetation.prototype.v0"
DEFAULT_SEASON_FACTORS: dict[str, float] = {
    "spring": 1.0,
    "summer": 0.9,
    "fall": 0.8,
    "winter": 0.6,
    "any": 1.0,
}


class TreatmentError(ValueError):
    """Raised when a treatment request is internally inconsistent."""


class TreatmentParameters(BaseModel):
    """Base parameters for one treatment method.

    Parameters
    ----------
    method : str
        Treatment method.
    efficacy : float
        Base efficacy.
    selectivity : float
        Preserved non-target fraction from 0 to 1.
    top_kill : float
        Height-reduction share from 0 to 1.
    resprout_factor : float
        Density increase from resprouting from 0 to 1.
    regrowth_delay_years : int
        Delay before regrowth.
    cost_per_ha : float
        Variable cost per hectare.
    fixed_cost : float
        Fixed cost per action.
    currency : str
        Currency.
    notes : str
        Caveat.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    method: TreatmentMethod
    efficacy: float = Field(ge=0, le=1)
    selectivity: float = Field(ge=0, le=1)
    top_kill: float = Field(ge=0, le=1)
    resprout_factor: float = Field(ge=0, le=1)
    regrowth_delay_years: int = Field(ge=0, le=20)
    cost_per_ha: float = Field(ge=0)
    fixed_cost: float = Field(default=0, ge=0)
    currency: str = "CAD"
    notes: str = ""


TREATMENT_PARAMETERS: tuple[TreatmentParameters, ...] = (
    TreatmentParameters(
        method="manual",
        efficacy=0.55,
        selectivity=0.9,
        top_kill=0.7,
        resprout_factor=0.5,
        regrowth_delay_years=1,
        cost_per_ha=1200,
        notes="Selective cutting; residual stems and resprouting are likely.",
    ),
    TreatmentParameters(
        method="mechanical",
        efficacy=0.75,
        selectivity=0.7,
        top_kill=0.9,
        resprout_factor=0.6,
        regrowth_delay_years=1,
        cost_per_ha=900,
        notes="Mechanical cutting; soil disturbance can increase resprouting.",
    ),
    TreatmentParameters(
        method="mowing",
        efficacy=0.65,
        selectivity=0.8,
        top_kill=0.8,
        resprout_factor=0.7,
        regrowth_delay_years=1,
        cost_per_ha=500,
        notes="Mowing top-kills but does not remove woody rootstock.",
    ),
    TreatmentParameters(
        method="chemical",
        efficacy=0.8,
        selectivity=0.6,
        top_kill=0.6,
        resprout_factor=0.3,
        regrowth_delay_years=2,
        cost_per_ha=700,
        notes="Chemical efficacy depends on active ingredient, timing, and species.",
    ),
    TreatmentParameters(
        method="grazing",
        efficacy=0.35,
        selectivity=0.4,
        top_kill=0.4,
        resprout_factor=0.4,
        regrowth_delay_years=0,
        cost_per_ha=300,
        notes="Grazing is selective and does not remove woody rootstock.",
    ),
    TreatmentParameters(
        method="prescribed_fire",
        efficacy=0.7,
        selectivity=0.3,
        top_kill=0.7,
        resprout_factor=0.6,
        regrowth_delay_years=2,
        cost_per_ha=1100,
        fixed_cost=2500,
        notes="Smoke, safety, and weather constraints are not modelled here.",
    ),
    TreatmentParameters(
        method="other",
        efficacy=0.3,
        selectivity=0.5,
        top_kill=0.3,
        resprout_factor=0.5,
        regrowth_delay_years=1,
        cost_per_ha=0,
        notes="Unspecified method; require a field record before operational use.",
    ),
)


class TreatmentConfig(BaseModel):
    """Residual, season, growth, and cost rules.

    Parameters
    ----------
    min_residual_height_m : float, optional
        Minimum height after treatment. Defaults to ``0.05``.
    min_residual_cover_pct : float, optional
        Minimum cover after treatment. Defaults to ``1``.
    season_factors : dict of str to float, optional
        Season multipliers.
    growth_config : GrowthConfig, optional
        Post-treatment growth rules.
    state_space : StateSpaceConfig, optional
        Discretization rules.
    max_regrowth_years : int, optional
        Maximum post-treatment trajectory. Defaults to ``20``.
    model_card_id : str, optional
        Model card id.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    min_residual_height_m: float = Field(default=0.05, gt=0)
    min_residual_cover_pct: float = Field(default=1.0, ge=0, le=100)
    season_factors: dict[str, float] = Field(default_factory=lambda: dict(DEFAULT_SEASON_FACTORS))
    growth_config: GrowthConfig = Field(default_factory=GrowthConfig)
    state_space: StateSpaceConfig = Field(default_factory=StateSpaceConfig)
    max_regrowth_years: int = Field(default=20, ge=0)
    model_card_id: str = TREATMENT_MODEL_CARD

    @model_validator(mode="after")
    def _valid_seasons(self) -> TreatmentConfig:
        if any(season not in SEASONS for season in self.season_factors):
            raise ValueError("season_factors contains an unknown season")
        if any(factor < 0 or factor > 2 for factor in self.season_factors.values()):
            raise ValueError("season factors must be between 0 and 2")
        return self


class TreatmentRequest(BaseModel):
    """One treatment transition request.

    Parameters
    ----------
    segment_id : str
        Segment id.
    functional_group : str
        Functional group.
    current : StateDistribution
        Current distribution.
    method : str
        Treatment method.
    season : str
        Treatment season.
    intensity : float
        Operational intensity from 0 to 1.
    quantity_ha : float, optional
        Treated area for cost. Defaults to ``1``.
    regrowth_years : int, optional
        Post-treatment trajectory length. Defaults to ``0``.
    environment : GrowthEnvironment, optional
        Growth environment after the delay.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    segment_id: str = Field(min_length=1)
    functional_group: FunctionalGroup
    current: StateDistribution
    method: TreatmentMethod
    season: Season
    intensity: float = Field(ge=0, le=1)
    quantity_ha: float = Field(default=1.0, ge=0)
    regrowth_years: int = Field(default=0, ge=0, le=20)
    environment: GrowthEnvironment = Field(default_factory=GrowthEnvironment)


class TreatmentResult(BaseModel):
    """The result of one treatment transition.

    Parameters
    ----------
    schema_version : {"brushline.treatment.v1"}
        Result schema version.
    segment_id : str
        Segment id.
    functional_group : str
        Functional group.
    method : str
        Method.
    season : str
        Season.
    status : str
        ``applied``, ``out_of_domain``, or ``unknown``.
    previous : StateDistribution
        Pre-treatment distribution.
    immediate : StateDistribution or None
        Immediate post-treatment distribution.
    next : StateDistribution or None
        Distribution at the end of the requested regrowth horizon.
    immediate_state_class : str or None
        Immediate class.
    next_state_class : str or None
        Trajectory class.
    efficiency : float
        Effective efficacy after season and intensity.
    height_reduction_m : float or None
        Immediate height reduction.
    cover_reduction_pct : float or None
        Immediate cover reduction.
    density_change_per_ha : float or None
        Immediate density change.
    cost : float
        Treatment cost.
    currency : str
        Cost currency.
    regrowth_delay_years : int
        Delay before regrowth.
    regrowth_years : int
        Requested trajectory length.
    environment : GrowthEnvironment
        Growth environment.
    reason : str
        Result reason.
    model_card_id : str
        Model card.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["brushline.treatment.v1"] = TREATMENT_SCHEMA_VERSION
    segment_id: str
    functional_group: FunctionalGroup
    method: TreatmentMethod
    season: Season
    status: str
    previous: StateDistribution
    immediate: StateDistribution | None = None
    next: StateDistribution | None = None
    immediate_state_class: StateClass | None = None
    next_state_class: StateClass | None = None
    efficiency: float = 0.0
    height_reduction_m: float | None = None
    cover_reduction_pct: float | None = None
    density_change_per_ha: float | None = None
    cost: float = Field(default=0, ge=0)
    currency: str = "CAD"
    regrowth_delay_years: int = 0
    regrowth_years: int = 0
    environment: GrowthEnvironment
    reason: str = ""
    model_card_id: str = TREATMENT_MODEL_CARD

    def to_vegetation_state(self, state_year: int) -> VegetationState:
        """Convert the trajectory distribution to a state contract.

        Parameters
        ----------
        state_year : int
            Output state year.

        Returns
        -------
        VegetationState
            The next or immediate state.

        Raises
        ------
        TreatmentError
            When no post-treatment distribution exists.
        """
        distribution = self.next or self.immediate
        state_class = self.next_state_class or self.immediate_state_class
        if distribution is None or state_class is None:
            raise TreatmentError("no post-treatment distribution is available")
        return VegetationState(
            segment_id=self.segment_id,
            state_year=state_year,
            functional_group=self.functional_group,
            state_class=state_class,
            height_m=distribution.height_m,
            cover_pct=distribution.cover_pct,
            density_per_ha=distribution.density_per_ha,
            age_years=distribution.age_years,
            uncertainty=Uncertainty(
                height_m_sd=distribution.height_sd,
                cover_pct_sd=distribution.cover_sd,
                density_sd=distribution.density_sd,
                confidence=distribution.confidence,
            ),
            source="brushline.vegetation.treatment",
            source_version="p4.3",
            model_card_id=self.model_card_id,
        )


def apply_treatment(
    request: TreatmentRequest,
    config: TreatmentConfig | None = None,
) -> TreatmentResult:
    """Apply one method-specific treatment transition.

    Parameters
    ----------
    request : TreatmentRequest
        Current distribution and treatment context.
    config : TreatmentConfig, optional
        Residual, season, growth, and cost rules.

    Returns
    -------
    TreatmentResult
        Immediate and trajectory distributions, cost, and reason.

    Raises
    ------
    TreatmentError
        When a regrowth horizon exceeds the configured maximum.
    """
    rules = config or TreatmentConfig()
    if request.regrowth_years > rules.max_regrowth_years:
        raise TreatmentError(
            f"regrowth_years {request.regrowth_years} exceeds the configured maximum "
            f"{rules.max_regrowth_years}"
        )
    parameters = _parameters(request.method)
    if request.functional_group == "unknown":
        return TreatmentResult(
            segment_id=request.segment_id,
            functional_group=request.functional_group,
            method=request.method,
            season=request.season,
            status="unknown",
            previous=request.current,
            environment=request.environment,
            reason="an unknown functional group has no treatment model",
            currency=parameters.currency,
            model_card_id=rules.model_card_id,
        )
    season_factor = rules.season_factors.get(request.season, 1.0)
    efficiency = min(1.0, parameters.efficacy * season_factor * request.intensity)
    if not request.environment.in_domain:
        return TreatmentResult(
            segment_id=request.segment_id,
            functional_group=request.functional_group,
            method=request.method,
            season=request.season,
            status="out_of_domain",
            previous=request.current,
            environment=request.environment,
            efficiency=efficiency,
            reason=request.environment.domain_reason,
            currency=parameters.currency,
            model_card_id=rules.model_card_id,
        )
    current = request.current
    height = max(
        rules.min_residual_height_m,
        current.height_m - current.height_m * efficiency * parameters.top_kill,
    )
    cover = max(
        rules.min_residual_cover_pct,
        current.cover_pct - current.cover_pct * efficiency,
    )
    density = (
        current.density_per_ha * (1.0 + parameters.resprout_factor * efficiency)
        if current.density_per_ha is not None
        else None
    )
    immediate_class = classify_state(
        height,
        cover,
        request.functional_group,
        rules.state_space,
    )
    if immediate_class == "unknown":
        immediate_class = "partial"
    immediate = StateDistribution(
        class_probabilities={immediate_class: 0.7, "unknown": 0.3},
        height_m=height,
        height_sd=current.height_sd + 0.1 * efficiency,
        cover_pct=cover,
        cover_sd=current.cover_sd + 2.0 * efficiency,
        density_per_ha=density,
        density_sd=current.density_sd,
        age_years=0,
        confidence=max(0.0, current.confidence - 0.1 * efficiency),
    )
    next_distribution: StateDistribution | None = immediate
    next_class: StateClass | None = immediate_class
    reason = "treatment applied; resprouting and delayed regrowth are explicit"
    if request.regrowth_years > 0:
        growth_years = max(0, request.regrowth_years - parameters.regrowth_delay_years)
        if growth_years == 0:
            next_distribution = immediate
            next_class = immediate_class
        else:
            grown = grow(
                GrowthRequest(
                    segment_id=request.segment_id,
                    functional_group=request.functional_group,
                    current=immediate,
                    years=growth_years,
                    environment=request.environment,
                ),
                rules.growth_config,
            )
            if grown.status == "grown" and grown.next is not None:
                next_distribution = grown.next
                next_class = (
                    grown.next_state_class
                    if grown.next_state_class is not None
                    else immediate_class
                )
            else:
                next_distribution = None
                next_class = None
                reason = f"trajectory blocked: {grown.reason}"
    cost = parameters.cost_per_ha * request.quantity_ha + parameters.fixed_cost
    return TreatmentResult(
        segment_id=request.segment_id,
        functional_group=request.functional_group,
        method=request.method,
        season=request.season,
        status="applied",
        previous=current,
        immediate=immediate,
        next=next_distribution,
        immediate_state_class=immediate_class,
        next_state_class=next_class,
        efficiency=efficiency,
        height_reduction_m=current.height_m - height,
        cover_reduction_pct=current.cover_pct - cover,
        density_change_per_ha=(
            density - current.density_per_ha
            if density is not None and current.density_per_ha is not None
            else None
        ),
        cost=cost,
        currency=parameters.currency,
        regrowth_delay_years=parameters.regrowth_delay_years,
        regrowth_years=request.regrowth_years,
        environment=request.environment,
        reason=reason,
        model_card_id=rules.model_card_id,
    )


def validate_treatment_result(result: TreatmentResult) -> ContractValidation:
    """Validate a treatment result and its transition invariants.

    Parameters
    ----------
    result : TreatmentResult
        Result to validate.

    Returns
    -------
    ContractValidation
        Errors, warnings, and counts.
    """
    errors: list[str] = []
    warnings: list[str] = []
    if result.status not in TREATMENT_STATUSES:
        errors.append(f"TREATMENT-STATUS: unknown status {result.status!r}")
    if result.status != "applied":
        if result.immediate is not None:
            errors.append("TREATMENT-NEXT: a blocked result has an immediate distribution")
        if not result.reason.strip():
            errors.append("TREATMENT-REASON: a blocked result has no reason")
    elif result.immediate is None:
        errors.append("TREATMENT-NEXT: an applied result has no immediate distribution")
    else:
        if result.immediate.height_m > result.previous.height_m + 1e-9:
            errors.append("TREATMENT-HEIGHT: cutting increased height")
        if result.immediate.cover_pct > result.previous.cover_pct + 1e-9:
            errors.append("TREATMENT-COVER: cutting increased cover")
        if result.immediate.height_m <= 0:
            errors.append("TREATMENT-RESIDUAL: height was reset to zero")
        if result.immediate.cover_pct < 0:
            errors.append("TREATMENT-RESIDUAL: cover is negative")
        if result.height_reduction_m is not None and result.height_reduction_m < 0:
            errors.append("TREATMENT-HEIGHT: negative height reduction")
        if result.cover_reduction_pct is not None and result.cover_reduction_pct < 0:
            errors.append("TREATMENT-COVER: negative cover reduction")
        if result.efficiency < 0 or result.efficiency > 1:
            errors.append("TREATMENT-EFFICIENCY: efficiency is outside 0 to 1")
        if result.next is not None and result.next_state_class is None:
            errors.append("TREATMENT-NEXT: trajectory has no state class")
    if result.cost < 0:
        errors.append("TREATMENT-COST: negative cost")
    counts: dict[str, int | float] = {
        "segments": 1,
        "applied": 1 if result.status == "applied" else 0,
        "cost": result.cost,
        "efficiency": result.efficiency,
    }
    return ContractValidation(tuple(errors), tuple(warnings), counts)


def _parameters(method: TreatmentMethod) -> TreatmentParameters:
    for parameters in TREATMENT_PARAMETERS:
        if parameters.method == method:
            return parameters
    raise TreatmentError(f"no treatment parameters for {method!r}")


__all__ = [
    "DEFAULT_SEASON_FACTORS",
    "TREATMENT_MODEL_CARD",
    "TREATMENT_PARAMETERS",
    "TREATMENT_SCHEMA_VERSION",
    "TREATMENT_STATUSES",
    "TreatmentConfig",
    "TreatmentError",
    "TreatmentParameters",
    "TreatmentRequest",
    "TreatmentResult",
    "apply_treatment",
    "validate_treatment_result",
]
