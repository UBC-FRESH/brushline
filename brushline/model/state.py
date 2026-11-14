"""Vegetation state, treatment, transition, and observation contract.

The state is a distribution over interpretable classes with continuous summaries, not a point
estimate. A treatment is a transition with method-specific efficacy and regrowth, not a reset to
zero. An observation is evidence with coverage, error, and provenance. The validator checks the
state keys, the ranges, the year windows, the references, and the treatment transitions.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

STATE_SCHEMA_VERSION: Literal["brushline.state.v1"] = "brushline.state.v1"
FUNCTIONAL_GROUPS: tuple[str, ...] = (
    "unknown",
    "shrub",
    "deciduous_sprout",
    "conifer",
    "grass_herb",
)
STATE_CLASSES: tuple[str, ...] = (
    "unknown",
    "partial",
    "grass_herb",
    "shrub",
    "young_tree",
    "mixed",
    "mature_edge",
)
TREATMENT_METHODS: tuple[str, ...] = (
    "manual",
    "mechanical",
    "chemical",
    "mowing",
    "grazing",
    "prescribed_fire",
    "other",
)
SEASONS: tuple[str, ...] = ("spring", "summer", "fall", "winter", "any")
SENSORS: tuple[str, ...] = (
    "lidar",
    "uav_lidar",
    "imagery",
    "field",
    "inspection",
    "other",
)
TREATMENT_STATUSES: tuple[str, ...] = ("planned", "applied", "cancelled")
MIN_YEAR: int = 1900
MAX_YEAR: int = 2200

FunctionalGroup = Literal[
    "unknown",
    "shrub",
    "deciduous_sprout",
    "conifer",
    "grass_herb",
]
StateClass = Literal[
    "unknown",
    "partial",
    "grass_herb",
    "shrub",
    "young_tree",
    "mixed",
    "mature_edge",
]
TreatmentMethod = Literal[
    "manual",
    "mechanical",
    "chemical",
    "mowing",
    "grazing",
    "prescribed_fire",
    "other",
]
Season = Literal["spring", "summer", "fall", "winter", "any"]
Sensor = Literal["lidar", "uav_lidar", "imagery", "field", "inspection", "other"]
TreatmentStatus = Literal["planned", "applied", "cancelled"]


@dataclass(frozen=True)
class StateValidation:
    """The outcome of validating a state contract.

    Parameters
    ----------
    errors : tuple of str
        Named errors. An empty tuple means the contract is valid.
    warnings : tuple of str
        Non-fatal findings.
    counts : dict of str to int
        Object counts.
    """

    errors: tuple[str, ...]
    warnings: tuple[str, ...]
    counts: dict[str, int]

    @property
    def is_valid(self) -> bool:
        """Return whether the contract passed every check.

        Returns
        -------
        bool
            ``True`` when there are no errors.
        """
        return not self.errors

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-ready report.

        Returns
        -------
        dict of str to object
            Validity, errors, warnings, and counts.
        """
        return {
            "is_valid": self.is_valid,
            "errors": list(self.errors),
            "warnings": list(self.warnings),
            "counts": dict(sorted(self.counts.items())),
        }


class Uncertainty(BaseModel):
    """The uncertainty around a vegetation state.

    Parameters
    ----------
    height_m_sd : float, optional
        Standard deviation of height in metres. Defaults to ``0``.
    cover_pct_sd : float, optional
        Standard deviation of cover in percentage points. Defaults to ``0``.
    density_sd : float, optional
        Standard deviation of density in stems per hectare. Defaults to ``0``.
    confidence : float, optional
        Confidence in the state, from 0 to 1. Defaults to ``1``.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    height_m_sd: float = Field(default=0.0, ge=0)
    cover_pct_sd: float = Field(default=0.0, ge=0)
    density_sd: float = Field(default=0.0, ge=0)
    confidence: float = Field(default=1.0, ge=0, le=1)


class VegetationState(BaseModel):
    """One functional group's state on one segment in one year.

    Parameters
    ----------
    segment_id : str
        Segment identifier.
    state_year : int
        Year the state describes.
    functional_group : {"unknown", "shrub", "deciduous_sprout", "conifer", "grass_herb"}
        Functional group. ``unknown`` is only valid for an unknown state.
    state_class : {"unknown", "partial", "grass_herb", "shrub", "young_tree", "mixed",
        "mature_edge"}
        Interpretable summary class.
    height_m : float
        Height in metres. Must be non-negative.
    cover_pct : float
        Cover in percent, from 0 to 100.
    density_per_ha : float or None, optional
        Density in stems per hectare.
    biomass_kg_per_ha : float or None, optional
        Biomass in kilograms per hectare.
    age_years : int or None, optional
        Age since disturbance in years.
    uncertainty : Uncertainty, optional
        Uncertainty around the state.
    treatment_history : list of str, optional
        Treatment action ids applied to the segment.
    source : str
        Source of the state.
    source_version : str
        Source version or vintage.
    model_card_id : str or None, optional
        Model card used to derive the state.
    observation_id : str or None, optional
        Observation that produced or updated the state.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    segment_id: str = Field(min_length=1)
    state_year: int = Field(ge=MIN_YEAR, le=MAX_YEAR)
    functional_group: FunctionalGroup
    state_class: StateClass
    height_m: float = Field(ge=0)
    cover_pct: float = Field(ge=0, le=100)
    density_per_ha: float | None = Field(default=None, ge=0)
    biomass_kg_per_ha: float | None = Field(default=None, ge=0)
    age_years: int | None = Field(default=None, ge=0)
    uncertainty: Uncertainty = Field(default_factory=Uncertainty)
    treatment_history: list[str] = Field(default_factory=list)
    source: str = Field(min_length=1)
    source_version: str = Field(min_length=1)
    model_card_id: str | None = None
    observation_id: str | None = None

    @model_validator(mode="after")
    def _unknown_state_is_empty(self) -> VegetationState:
        if self.state_class == "unknown":
            if self.functional_group != "unknown":
                raise ValueError("an unknown state must use the unknown functional group")
            if self.height_m != 0 or self.cover_pct != 0:
                raise ValueError("an unknown state must have zero height and cover")
            if self.density_per_ha not in (None, 0):
                raise ValueError("an unknown state must have no density")
            if self.biomass_kg_per_ha not in (None, 0):
                raise ValueError("an unknown state must have no biomass")
        elif self.functional_group == "unknown":
            raise ValueError("a known state must name a functional group")
        return self


class TreatmentAction(BaseModel):
    """A planned, applied, or cancelled treatment on one segment.

    Parameters
    ----------
    action_id : str
        Stable action identifier.
    segment_id : str
        Segment identifier.
    year : int
        Treatment year.
    season : {"spring", "summer", "fall", "winter", "any"}
        Treatment season.
    method : {"manual", "mechanical", "chemical", "mowing", "grazing", "prescribed_fire", "other"}
        Treatment method.
    intensity : float
        Intensity from 0 to 1.
    efficacy : float
        Expected efficacy from 0 to 1.
    efficacy_sd : float, optional
        Standard deviation of efficacy. Defaults to ``0``.
    cost_per_ha : float, optional
        Variable cost per hectare. Defaults to ``0``.
    fixed_cost : float, optional
        Fixed cost per action. Defaults to ``0``.
    currency : str, optional
        Currency code. Defaults to ``CAD``.
    status : {"planned", "applied", "cancelled"}, optional
        Action status. Defaults to ``planned``.
    treatment_unit_id : str or None, optional
        Owning treatment unit.
    notes : str, optional
        Free notes.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    action_id: str = Field(min_length=1)
    segment_id: str = Field(min_length=1)
    year: int = Field(ge=MIN_YEAR, le=MAX_YEAR)
    season: Season
    method: TreatmentMethod
    intensity: float = Field(ge=0, le=1)
    efficacy: float = Field(ge=0, le=1)
    efficacy_sd: float = Field(default=0.0, ge=0)
    cost_per_ha: float = Field(default=0.0, ge=0)
    fixed_cost: float = Field(default=0.0, ge=0)
    currency: str = Field(default="CAD", min_length=1)
    status: TreatmentStatus = "planned"
    treatment_unit_id: str | None = None
    notes: str = ""


class TreatmentTransition(BaseModel):
    """The before-and-after state of one treatment transition.

    Parameters
    ----------
    transition_id : str
        Stable transition identifier.
    segment_id : str
        Segment identifier.
    year : int
        Transition year.
    method : {"manual", "mechanical", "chemical", "mowing", "grazing", "prescribed_fire", "other"}
        Treatment method.
    before_height_m : float
        Height before the treatment.
    after_height_m : float
        Height after the treatment.
    before_cover_pct : float
        Cover before the treatment.
    after_cover_pct : float
        Cover after the treatment.
    efficacy : float
        Observed or modelled efficacy from 0 to 1.
    regrowth_delay_years : int
        Delay before regrowth resumes.
    source : str
        Source of the transition evidence.
    observation_id : str or None, optional
        Observation that recorded the transition.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    transition_id: str = Field(min_length=1)
    segment_id: str = Field(min_length=1)
    year: int = Field(ge=MIN_YEAR, le=MAX_YEAR)
    method: TreatmentMethod
    before_height_m: float = Field(ge=0)
    after_height_m: float = Field(ge=0)
    before_cover_pct: float = Field(ge=0, le=100)
    after_cover_pct: float = Field(ge=0, le=100)
    efficacy: float = Field(ge=0, le=1)
    regrowth_delay_years: int = Field(ge=0)
    source: str = Field(min_length=1)
    observation_id: str | None = None

    @model_validator(mode="after")
    def _treatment_does_not_increase(self) -> TreatmentTransition:
        if self.after_height_m > self.before_height_m + 1e-9:
            raise ValueError("after_height_m must not exceed before_height_m")
        if self.after_cover_pct > self.before_cover_pct + 1e-9:
            raise ValueError("after_cover_pct must not exceed before_cover_pct")
        return self


class Observation(BaseModel):
    """One remote or field observation of a segment.

    Parameters
    ----------
    observation_id : str
        Stable observation identifier.
    segment_id : str
        Segment identifier.
    observed_date : datetime.date
        Observation date.
    sensor : {"lidar", "uav_lidar", "imagery", "field", "inspection", "other"}
        Sensor or method.
    product : str
        Product name, such as CHM, cover, or field plot.
    coverage_pct : float
        Fraction of the segment covered, from 0 to 100.
    height_m : float or None, optional
        Observed height in metres.
    cover_pct : float or None, optional
        Observed cover in percent.
    density_per_ha : float or None, optional
        Observed density in stems per hectare.
    height_error_m : float, optional
        Height measurement error in metres. Defaults to ``0``.
    cover_error_pct : float, optional
        Cover measurement error in percentage points. Defaults to ``0``.
    model_card_id : str or None, optional
        Model card used to derive the observation.
    source : str
        Source name.
    source_version : str
        Source version or vintage.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    observation_id: str = Field(min_length=1)
    segment_id: str = Field(min_length=1)
    observed_date: date
    sensor: Sensor
    product: str = Field(min_length=1)
    coverage_pct: float = Field(ge=0, le=100)
    height_m: float | None = Field(default=None, ge=0)
    cover_pct: float | None = Field(default=None, ge=0, le=100)
    density_per_ha: float | None = Field(default=None, ge=0)
    height_error_m: float = Field(default=0.0, ge=0)
    cover_error_pct: float = Field(default=0.0, ge=0)
    model_card_id: str | None = None
    source: str = Field(min_length=1)
    source_version: str = Field(min_length=1)

    @field_validator("observed_date")
    @classmethod
    def _year_window(cls, value: date) -> date:
        if not MIN_YEAR <= value.year <= MAX_YEAR:
            raise ValueError(f"observed_date year must be between {MIN_YEAR} and {MAX_YEAR}")
        return value


class StateContract(BaseModel):
    """The root state, treatment, transition, and observation contract.

    Parameters
    ----------
    states : list of VegetationState
        Vegetation states.
    treatments : list of TreatmentAction
        Treatment actions.
    transitions : list of TreatmentTransition
        Treatment transitions.
    observations : list of Observation
        Observations.
    """

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["brushline.state.v1"] = STATE_SCHEMA_VERSION
    states: list[VegetationState] = Field(min_length=1)
    treatments: list[TreatmentAction] = Field(default_factory=list)
    transitions: list[TreatmentTransition] = Field(default_factory=list)
    observations: list[Observation] = Field(default_factory=list)


def validate_state_contract(
    contract: StateContract,
    *,
    required_segment_ids: set[str] | None = None,
) -> StateValidation:
    """Validate state keys, references, ranges, and required segment coverage.

    Parameters
    ----------
    contract : StateContract
        The contract to validate.
    required_segment_ids : set of str or None, optional
        Segments that must have at least one state. When ``None``, the check is skipped.

    Returns
    -------
    StateValidation
        Errors, warnings, and object counts.
    """
    errors: list[str] = []
    warnings: list[str] = []
    state_keys: set[tuple[str, int, str]] = set()
    segments_with_state: set[str] = set()
    for state in contract.states:
        key = (state.segment_id, state.state_year, state.functional_group)
        if key in state_keys:
            errors.append(
                f"STATE-ID: duplicate state key {state.segment_id}/{state.state_year}/"
                f"{state.functional_group}"
            )
        state_keys.add(key)
        segments_with_state.add(state.segment_id)
        if state.state_class == "partial":
            warnings.append(
                f"STATE-PARTIAL: segment {state.segment_id} has a partial state in "
                f"{state.state_year}"
            )
        if state.uncertainty.confidence < 0.5:
            warnings.append(
                f"STATE-UNCERTAIN: segment {state.segment_id} has confidence "
                f"{state.uncertainty.confidence}"
            )
    _check_duplicates("treatment action", [item.action_id for item in contract.treatments], errors)
    _check_duplicates(
        "treatment transition",
        [item.transition_id for item in contract.transitions],
        errors,
    )
    _check_duplicates(
        "observation", [item.observation_id for item in contract.observations], errors
    )
    for action in contract.treatments:
        if action.segment_id not in segments_with_state:
            errors.append(
                f"STATE-REF: treatment action {action.action_id} references segment "
                f"{action.segment_id} with no state"
            )
    for transition in contract.transitions:
        if transition.segment_id not in segments_with_state:
            errors.append(
                f"STATE-REF: transition {transition.transition_id} references segment "
                f"{transition.segment_id} with no state"
            )
        if transition.regrowth_delay_years > 20:
            warnings.append(
                f"STATE-DELAY: transition {transition.transition_id} has a regrowth delay of "
                f"{transition.regrowth_delay_years} years"
            )
    for observation in contract.observations:
        if observation.segment_id not in segments_with_state:
            errors.append(
                f"STATE-REF: observation {observation.observation_id} references segment "
                f"{observation.segment_id} with no state"
            )
        if observation.coverage_pct < 100:
            warnings.append(
                f"STATE-COVERAGE: observation {observation.observation_id} covers "
                f"{observation.coverage_pct} percent of the segment"
            )
    if required_segment_ids is not None:
        missing = sorted(required_segment_ids - segments_with_state)
        for segment_id in missing:
            errors.append(f"STATE-MISSING: segment {segment_id} has no state")
    counts = {
        "states": len(contract.states),
        "treatments": len(contract.treatments),
        "transitions": len(contract.transitions),
        "observations": len(contract.observations),
        "segments_with_state": len(segments_with_state),
    }
    return StateValidation(tuple(errors), tuple(warnings), counts)


def _check_duplicates(label: str, values: list[str], errors: list[str]) -> None:
    """Append one error for each duplicated value.

    Parameters
    ----------
    label : str
        Human label for the collection.
    values : list of str
        Identifiers in the collection.
    errors : list of str
        Error accumulator.
    """
    seen: set[str] = set()
    duplicates: set[str] = set()
    for value in values:
        if value in seen:
            duplicates.add(value)
        seen.add(value)
    for value in sorted(duplicates):
        errors.append(f"STATE-ID: duplicate {label} id {value}")
