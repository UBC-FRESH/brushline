"""Low-vegetation state space and discretization.

The state space is the shared vocabulary for the P4 growth, treatment, calibration, hazard, and
model card work. It defines the functional groups, continuous state variables, state classes,
class probabilities, uncertainty, and the deterministic projection from one observation to a valid
``brushline.state.v1`` state. It does not run growth or a treatment transition.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from brushline.model.state import (
    FUNCTIONAL_GROUPS,
    STATE_CLASSES,
    FunctionalGroup,
    StateClass,
    StateContract,
    Uncertainty,
    VegetationState,
    validate_state_contract,
)
from brushline.model.validation import ContractValidation

STATE_SPACE_SCHEMA_VERSION: Literal["brushline.state-space.v1"] = "brushline.state-space.v1"
STATE_VARIABLES: tuple[str, ...] = (
    "height_m",
    "cover_pct",
    "density_per_ha",
    "biomass_kg_per_ha",
    "age_years",
)
COVERAGE_STATES: tuple[str, ...] = ("observed", "partial", "missing", "out_of_domain")
STATE_SPACE_GROUPS: tuple[str, ...] = FUNCTIONAL_GROUPS
STATE_SPACE_CLASSES: tuple[str, ...] = STATE_CLASSES


class StateVariable(BaseModel):
    """One continuous state variable.

    Parameters
    ----------
    name : str
        Variable name.
    unit : str
        Unit label.
    minimum : float
        Lower bound.
    maximum : float or None
        Upper bound, when finite.
    unknown_rule : str
        Rule applied when the value is unavailable.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str
    unit: str
    minimum: float
    maximum: float | None
    unknown_rule: str


STATE_VARIABLE_SPECS: tuple[StateVariable, ...] = (
    StateVariable(
        name="height_m",
        unit="m",
        minimum=0,
        maximum=100,
        unknown_rule="unavailable height becomes an unknown or partial state",
    ),
    StateVariable(
        name="cover_pct",
        unit="%",
        minimum=0,
        maximum=100,
        unknown_rule="unavailable cover becomes an unknown or partial state",
    ),
    StateVariable(
        name="density_per_ha",
        unit="stems/ha",
        minimum=0,
        maximum=None,
        unknown_rule="unavailable density stays null",
    ),
    StateVariable(
        name="biomass_kg_per_ha",
        unit="kg/ha",
        minimum=0,
        maximum=None,
        unknown_rule="unavailable biomass stays null",
    ),
    StateVariable(
        name="age_years",
        unit="years",
        minimum=0,
        maximum=300,
        unknown_rule="unavailable age stays null",
    ),
)


class FunctionalGroupProfile(BaseModel):
    """The expected state envelope for one functional group.

    Parameters
    ----------
    group : str
        Functional group.
    label : str
        Human label.
    height_max_m : float
        Typical maximum height.
    cover_min_pct : float
        Minimum woody cover.
    resprouts : bool
        Whether the group commonly resprouts after cutting.
    notes : str
        Short notes or caveats.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    group: str
    label: str
    height_max_m: float = Field(gt=0)
    cover_min_pct: float = Field(ge=0, le=100)
    resprouts: bool = False
    notes: str = ""


FUNCTIONAL_GROUP_PROFILES: tuple[FunctionalGroupProfile, ...] = (
    FunctionalGroupProfile(
        group="shrub",
        label="Shrub",
        height_max_m=4.0,
        cover_min_pct=20.0,
        resprouts=True,
        notes="Low woody vegetation; cutting can increase density.",
    ),
    FunctionalGroupProfile(
        group="deciduous_sprout",
        label="Deciduous sprout",
        height_max_m=10.0,
        cover_min_pct=20.0,
        resprouts=True,
        notes="Resprouting hardwood; top-kill is not removal.",
    ),
    FunctionalGroupProfile(
        group="conifer",
        label="Conifer",
        height_max_m=20.0,
        cover_min_pct=20.0,
        resprouts=False,
        notes="Young conifer or mature edge; method-specific selectivity matters.",
    ),
    FunctionalGroupProfile(
        group="grass_herb",
        label="Grass and herb",
        height_max_m=0.5,
        cover_min_pct=10.0,
        resprouts=True,
        notes="Low herbaceous layer; not a woody cover class.",
    ),
    FunctionalGroupProfile(
        group="unknown",
        label="Unknown",
        height_max_m=100.0,
        cover_min_pct=0.0,
        resprouts=False,
        notes="No usable observation.",
    ),
)


class StateSpaceConfig(BaseModel):
    """Discretization and coverage rules.

    Parameters
    ----------
    grass_max_height_m : float, optional
        Grass/herb height maximum. Defaults to ``0.5``.
    shrub_max_height_m : float, optional
        Shrub height maximum. Defaults to ``4``.
    young_tree_max_height_m : float, optional
        Young-tree height maximum. Defaults to ``10``.
    mature_height_m : float, optional
        Mature-edge height minimum. Defaults to ``15``.
    cover_min_pct : float, optional
        Woody cover minimum. Defaults to ``20``.
    mixed_min_strata : int, optional
        Number of cover-bearing strata for a mixed class. Defaults to ``2``.
    unknown_below_coverage_pct : float, optional
        Coverage below which a state is unknown. Defaults to ``10``.
    observed_min_coverage_pct : float, optional
        Coverage needed for an observed state. Defaults to ``50``.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    grass_max_height_m: float = Field(default=0.5, gt=0)
    shrub_max_height_m: float = Field(default=4.0, gt=0)
    young_tree_max_height_m: float = Field(default=10.0, gt=0)
    mature_height_m: float = Field(default=15.0, gt=0)
    cover_min_pct: float = Field(default=20.0, ge=0, le=100)
    mixed_min_strata: int = Field(default=2, ge=2)
    unknown_below_coverage_pct: float = Field(default=10.0, ge=0, le=100)
    observed_min_coverage_pct: float = Field(default=50.0, ge=0, le=100)

    @model_validator(mode="after")
    def _ordered_thresholds(self) -> StateSpaceConfig:
        if not (
            self.grass_max_height_m
            < self.shrub_max_height_m
            < self.young_tree_max_height_m
            < self.mature_height_m
        ):
            raise ValueError("height thresholds must increase")
        if self.unknown_below_coverage_pct >= self.observed_min_coverage_pct:
            raise ValueError("unknown coverage threshold must be below observed coverage")
        return self


class StateStratum(BaseModel):
    """One vegetation stratum in an observation.

    Parameters
    ----------
    functional_group : str
        Functional group.
    height_m : float
        Stratum height.
    cover_pct : float
        Stratum cover.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    functional_group: FunctionalGroup
    height_m: float = Field(ge=0)
    cover_pct: float = Field(ge=0, le=100)


class StateObservation(BaseModel):
    """One segment observation used to project the state space.

    Parameters
    ----------
    segment_id : str
        Segment id.
    state_year : int
        Observation year.
    functional_group : str
        Dominant functional group.
    height_m : float or None
        Observed height.
    cover_pct : float or None
        Observed cover.
    density_per_ha : float or None
        Observed density.
    biomass_kg_per_ha : float or None
        Observed biomass.
    age_years : int or None
        Age since disturbance.
    coverage_pct : float
        Observation coverage.
    height_sd : float, optional
        Height standard deviation.
    cover_sd : float, optional
        Cover standard deviation.
    density_sd : float, optional
        Density standard deviation.
    strata : list of StateStratum, optional
        Vertical strata.
    in_domain : bool, optional
        Whether the observation is in the model domain. Defaults to ``True``.
    domain_reason : str, optional
        Reason when out of domain.
    observation_id : str or None, optional
        Observation id.
    source : str
        Observation source.
    source_version : str
        Source version.
    model_card_id : str or None, optional
        Optional model card.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    segment_id: str = Field(min_length=1)
    state_year: int = Field(ge=1900, le=2200)
    functional_group: FunctionalGroup
    height_m: float | None = Field(default=None, ge=0)
    cover_pct: float | None = Field(default=None, ge=0, le=100)
    density_per_ha: float | None = Field(default=None, ge=0)
    biomass_kg_per_ha: float | None = Field(default=None, ge=0)
    age_years: int | None = Field(default=None, ge=0)
    coverage_pct: float = Field(ge=0, le=100)
    height_sd: float = Field(default=0.0, ge=0)
    cover_sd: float = Field(default=0.0, ge=0)
    density_sd: float = Field(default=0.0, ge=0)
    strata: list[StateStratum] = Field(default_factory=list)
    in_domain: bool = True
    domain_reason: str = ""
    observation_id: str | None = None
    source: str = Field(min_length=1)
    source_version: str = Field(min_length=1)
    model_card_id: str | None = None

    @model_validator(mode="after")
    def _observation_consistency(self) -> StateObservation:
        if self.functional_group == "unknown" and (
            self.height_m not in (None, 0) or self.cover_pct not in (None, 0)
        ):
            raise ValueError("an unknown group needs empty height and cover")
        if not self.in_domain and not self.domain_reason.strip():
            raise ValueError("an out-of-domain observation needs a reason")
        return self


class StateDistribution(BaseModel):
    """The class and continuous distribution for one projected state.

    Parameters
    ----------
    class_probabilities : dict of str to float
        State-class probabilities.
    height_m : float
        Mean height.
    height_sd : float
        Height standard deviation.
    cover_pct : float
        Mean cover.
    cover_sd : float
        Cover standard deviation.
    density_per_ha : float or None
        Mean density.
    density_sd : float
        Density standard deviation.
    age_years : int or None
        Mean age.
    confidence : float
        Overall confidence.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    class_probabilities: dict[str, float]
    height_m: float = Field(ge=0)
    height_sd: float = Field(ge=0)
    cover_pct: float = Field(ge=0, le=100)
    cover_sd: float = Field(ge=0)
    density_per_ha: float | None = Field(default=None, ge=0)
    density_sd: float = Field(default=0.0, ge=0)
    age_years: int | None = Field(default=None, ge=0)
    confidence: float = Field(ge=0, le=1)

    @model_validator(mode="after")
    def _probability_shape(self) -> StateDistribution:
        if not self.class_probabilities:
            raise ValueError("class probabilities must not be empty")
        if any(name not in STATE_SPACE_CLASSES for name in self.class_probabilities):
            raise ValueError("class probabilities contain an unknown state class")
        if any(value < 0 or value > 1 for value in self.class_probabilities.values()):
            raise ValueError("class probabilities must be between 0 and 1")
        if abs(sum(self.class_probabilities.values()) - 1.0) > 1e-6:
            raise ValueError("class probabilities must sum to 1")
        return self


class StateProjection(BaseModel):
    """One segment's projection into the shared state space.

    Parameters
    ----------
    schema_version : {"brushline.state-space.v1"}
        Projection schema version.
    segment_id : str
        Segment id.
    state_year : int
        State year.
    state_class : str
        Selected state class.
    functional_group : str
        Selected functional group.
    coverage_state : str
        Observed, partial, missing, or out of domain.
    distribution : StateDistribution
        Class and continuous distribution.
    observation : StateObservation
        Observation that produced the projection.
    reason : str
        Projection reason.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["brushline.state-space.v1"] = STATE_SPACE_SCHEMA_VERSION
    segment_id: str
    state_year: int
    state_class: StateClass
    functional_group: FunctionalGroup
    coverage_state: str
    distribution: StateDistribution
    observation: StateObservation
    reason: str

    @model_validator(mode="after")
    def _state_consistency(self) -> StateProjection:
        if self.coverage_state not in COVERAGE_STATES:
            raise ValueError(f"unknown coverage state {self.coverage_state!r}")
        if self.state_class == "unknown" and self.functional_group != "unknown":
            raise ValueError("an unknown class needs an unknown group")
        return self

    def to_vegetation_state(self) -> VegetationState:
        """Project the distribution to the shared state contract.

        Returns
        -------
        VegetationState
            A valid state for the segment and year.
        """
        return VegetationState(
            segment_id=self.segment_id,
            state_year=self.state_year,
            functional_group=self.functional_group,
            state_class=self.state_class,
            height_m=self.distribution.height_m,
            cover_pct=self.distribution.cover_pct,
            density_per_ha=self.distribution.density_per_ha,
            biomass_kg_per_ha=None,
            age_years=self.distribution.age_years,
            uncertainty=Uncertainty(
                height_m_sd=self.distribution.height_sd,
                cover_pct_sd=self.distribution.cover_sd,
                density_sd=self.distribution.density_sd,
                confidence=self.distribution.confidence,
            ),
            source=self.observation.source,
            source_version=self.observation.source_version,
            model_card_id=self.observation.model_card_id,
            observation_id=self.observation.observation_id,
        )


def project_state(
    observation: StateObservation,
    config: StateSpaceConfig | None = None,
) -> StateProjection:
    """Project one observation into the shared state space.

    The projection is deterministic. Coverage below the unknown threshold becomes an unknown state;
    coverage below the observed threshold becomes partial. An out-of-domain observation becomes
    partial and is flagged. Otherwise the class follows the height/cover/strata rules.

    Parameters
    ----------
    observation : StateObservation
        Observation to project.
    config : StateSpaceConfig, optional
        Discretization rules.

    Returns
    -------
    StateProjection
        The selected class, group, coverage state, distribution, and reason.
    """
    rules = config or StateSpaceConfig()
    if observation.coverage_pct < rules.unknown_below_coverage_pct:
        return _unknown_projection(observation, "coverage is below the unknown threshold")
    if observation.functional_group == "unknown" or observation.height_m is None:
        return _unknown_projection(observation, "height or functional group is unknown")
    if observation.cover_pct is None:
        return _unknown_projection(observation, "cover is unknown")
    if not observation.in_domain:
        return _partial_projection(
            observation,
            rules,
            observation.domain_reason,
            coverage_state="out_of_domain",
        )
    if observation.coverage_pct < rules.observed_min_coverage_pct:
        return _partial_projection(
            observation,
            rules,
            "coverage is below the observed threshold",
            coverage_state="partial",
        )
    state_class = _classify(observation, rules)
    group = observation.functional_group
    if state_class == "unknown":
        return _unknown_projection(
            observation,
            "the observation does not match a state rule",
            coverage_state="observed",
        )
    distribution = _distribution(observation, state_class, group, confidence=0.8)
    return StateProjection(
        segment_id=observation.segment_id,
        state_year=observation.state_year,
        state_class=state_class,
        functional_group=group,
        coverage_state="observed",
        distribution=distribution,
        observation=observation,
        reason="observation meets coverage and class rules",
    )


def validate_state_projection(projection: StateProjection) -> ContractValidation:
    """Validate a projection and its state-contract conversion.

    Parameters
    ----------
    projection : StateProjection
        Projection to validate.

    Returns
    -------
    ContractValidation
        Errors, warnings, and counts.
    """
    errors: list[str] = []
    warnings: list[str] = []
    if projection.state_class == "unknown":
        if projection.functional_group != "unknown":
            errors.append("STATE-SPACE-GROUP: unknown class needs unknown group")
        if projection.distribution.height_m != 0 or projection.distribution.cover_pct != 0:
            errors.append("STATE-SPACE-VALUE: unknown class needs zero height and cover")
    elif projection.functional_group == "unknown":
        errors.append("STATE-SPACE-GROUP: known class needs a functional group")
    if projection.distribution.class_probabilities.get(projection.state_class, 0) <= 0:
        errors.append("STATE-SPACE-PROBABILITY: selected class has no probability")
    try:
        state = projection.to_vegetation_state()
    except ValueError as exc:
        errors.append(f"STATE-SPACE-STATE: {exc}")
    else:
        state_validation = validate_state_contract(
            _single_state_contract(state),
        )
        errors.extend(state_validation.errors)
        warnings.extend(state_validation.warnings)
    if projection.coverage_state in ("partial", "out_of_domain") and not projection.reason:
        errors.append("STATE-SPACE-REASON: partial or out-of-domain projection has no reason")
    counts: dict[str, int | float] = {
        "segments": 1,
        "projected": 1,
        "probability_classes": len(projection.distribution.class_probabilities),
        "confidence": projection.distribution.confidence,
    }
    return ContractValidation(tuple(errors), tuple(warnings), counts)


def _single_state_contract(state: VegetationState) -> StateContract:
    return StateContract(states=[state])


def _classify(observation: StateObservation, config: StateSpaceConfig) -> StateClass:
    height = observation.height_m
    cover = observation.cover_pct
    assert height is not None
    assert cover is not None
    strata = observation.strata
    if (
        strata
        and sum(1 for stratum in strata if stratum.cover_pct >= config.cover_min_pct)
        >= config.mixed_min_strata
    ):
        return "mixed"
    if height >= config.mature_height_m and cover >= config.cover_min_pct:
        return "mature_edge"
    if height <= config.grass_max_height_m and cover < config.cover_min_pct:
        return "grass_herb"
    if height <= config.shrub_max_height_m and cover >= config.cover_min_pct:
        return "shrub"
    if height <= config.young_tree_max_height_m and cover >= config.cover_min_pct:
        return "young_tree"
    return "unknown"


def _unknown_projection(
    observation: StateObservation,
    reason: str,
    *,
    coverage_state: str = "missing",
) -> StateProjection:
    distribution = StateDistribution(
        class_probabilities={"unknown": 1.0},
        height_m=0,
        height_sd=0,
        cover_pct=0,
        cover_sd=0,
        density_per_ha=None,
        density_sd=0,
        age_years=None,
        confidence=0.0,
    )
    return StateProjection(
        segment_id=observation.segment_id,
        state_year=observation.state_year,
        state_class="unknown",
        functional_group="unknown",
        coverage_state=coverage_state,
        distribution=distribution,
        observation=observation,
        reason=observation.domain_reason if not observation.in_domain else reason,
    )


def _partial_projection(
    observation: StateObservation,
    config: StateSpaceConfig,
    reason: str,
    *,
    coverage_state: str,
) -> StateProjection:
    candidate = _classify(observation, config)
    group = observation.functional_group if observation.functional_group != "unknown" else "shrub"
    if candidate == "unknown":
        probabilities = {"partial": 0.7, "unknown": 0.3}
    else:
        probabilities = {candidate: 0.6, "partial": 0.3, "unknown": 0.1}
    distribution = _distribution(
        observation,
        "partial",
        group,
        confidence=0.35,
        probabilities=probabilities,
    )
    return StateProjection(
        segment_id=observation.segment_id,
        state_year=observation.state_year,
        state_class="partial",
        functional_group=group,
        coverage_state=coverage_state,
        distribution=distribution,
        observation=observation,
        reason=reason,
    )


def _distribution(
    observation: StateObservation,
    state_class: StateClass,
    group: FunctionalGroup,
    *,
    confidence: float,
    probabilities: dict[str, float] | None = None,
) -> StateDistribution:
    if probabilities is None:
        probabilities = {state_class: confidence, "unknown": 1.0 - confidence}
    height = observation.height_m or 0.0
    cover = observation.cover_pct or 0.0
    return StateDistribution(
        class_probabilities={key: round(value, 6) for key, value in probabilities.items()},
        height_m=height,
        height_sd=observation.height_sd,
        cover_pct=cover,
        cover_sd=observation.cover_sd,
        density_per_ha=observation.density_per_ha,
        density_sd=observation.density_sd,
        age_years=observation.age_years,
        confidence=confidence,
    )
