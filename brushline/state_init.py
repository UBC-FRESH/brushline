"""Initial vegetation state from LiDAR, field, inventory, and site evidence.

The initializer links the P3.1 to P3.3 products to the `brushline.state.v1` contract. It uses
field evidence first, a conservative CHM rule second, and an explicit unknown/partial state when
evidence is missing or out of domain. It does not run the P4 growth or treatment model, fit a
site-index model, or claim that a CHM resolves shrub from young-tree species.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Literal, cast

from pydantic import BaseModel, ConfigDict, Field, model_validator

from brushline.integrations.canopy import CanopySupport
from brushline.integrations.lidar import LidarProductProvenance
from brushline.integrations.terrain import TerrainSupport
from brushline.model.state import (
    FUNCTIONAL_GROUPS,
    STATE_CLASSES,
    FunctionalGroup,
    Observation,
    StateClass,
    StateContract,
    Uncertainty,
    VegetationState,
    validate_state_contract,
)
from brushline.model.validation import ContractValidation, check_duplicates

STATE_INITIALIZATION_SCHEMA_VERSION: Literal["brushline.state-initialization.v1"] = (
    "brushline.state-initialization.v1"
)
PROTOTYPE_MODEL_CARD = "brushline.low-vegetation.prototype.v0"
STATE_INIT_SOURCES: tuple[str, ...] = ("field", "lidar-chm", "coverage")
PROBABILITY_CLASSES: tuple[str, ...] = STATE_CLASSES


class StateInitializationError(ValueError):
    """Raised when the evidence cannot produce a valid initial state."""


class StateInitializationConfig(BaseModel):
    """Thresholds and evidence rules for the initial state.

    Parameters
    ----------
    state_year : int
        State year.
    grass_max_height_m : float, optional
        Maximum height for a grass/herb candidate. Defaults to ``0.5``.
    shrub_max_height_m : float, optional
        Maximum height for a shrub candidate. Defaults to ``4``.
    young_tree_max_height_m : float, optional
        Maximum height for a young-tree candidate. Defaults to ``10``.
    cover_min_pct : float, optional
        Minimum cover for a woody class. Defaults to ``20``.
    mature_edge_height_m : float, optional
        Maximum-height threshold for a mature edge. Defaults to ``15``.
    mature_edge_cover_pct : float, optional
        Cover threshold for a mature edge. Defaults to ``20``.
    field_min_coverage_pct : float, optional
        Minimum field coverage. Defaults to ``50``.
    field_min_confidence : float, optional
        Minimum field confidence. Defaults to ``0.5``.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    state_year: int = Field(default=2026, ge=1900, le=2200)
    grass_max_height_m: float = Field(default=0.5, gt=0)
    shrub_max_height_m: float = Field(default=4.0, gt=0)
    young_tree_max_height_m: float = Field(default=10.0, gt=0)
    cover_min_pct: float = Field(default=20.0, ge=0, le=100)
    mature_edge_height_m: float = Field(default=15.0, gt=0)
    mature_edge_cover_pct: float = Field(default=20.0, ge=0, le=100)
    field_min_coverage_pct: float = Field(default=50.0, ge=0, le=100)
    field_min_confidence: float = Field(default=0.5, ge=0, le=1)


class FieldObservation(BaseModel):
    """Field evidence for one segment.

    Parameters
    ----------
    observation_id : str
        Stable observation id.
    segment_id : str
        Segment id.
    observed_date : datetime.date
        Observation date.
    state_class : str
        Field state class.
    functional_group : str
        Field functional group.
    height_m : float
        Field height.
    cover_pct : float
        Field cover.
    density_per_ha : float or None
        Field density.
    age_years : int or None
        Age since disturbance.
    coverage_pct : float
        Field coverage of the segment.
    height_error_m : float
        Height error.
    cover_error_pct : float
        Cover error.
    confidence : float
        Field confidence.
    source : str
        Field source.
    source_version : str
        Source version.
    model_card_id : str or None
        Optional field model card.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    observation_id: str = Field(min_length=1)
    segment_id: str = Field(min_length=1)
    observed_date: date
    state_class: StateClass
    functional_group: FunctionalGroup
    height_m: float = Field(ge=0)
    cover_pct: float = Field(ge=0, le=100)
    density_per_ha: float | None = Field(default=None, ge=0)
    age_years: int | None = Field(default=None, ge=0)
    coverage_pct: float = Field(ge=0, le=100)
    height_error_m: float = Field(default=0.0, ge=0)
    cover_error_pct: float = Field(default=0.0, ge=0)
    confidence: float = Field(default=0.8, ge=0, le=1)
    source: str = Field(min_length=1)
    source_version: str = Field(min_length=1)
    model_card_id: str | None = None

    @model_validator(mode="after")
    def _class_consistency(self) -> FieldObservation:
        if self.state_class == "unknown":
            if self.functional_group != "unknown":
                raise ValueError("an unknown field state needs the unknown group")
            if self.height_m != 0 or self.cover_pct != 0:
                raise ValueError("an unknown field state needs zero height and cover")
        elif self.functional_group == "unknown":
            raise ValueError("a known field state needs a functional group")
        return self


class InventoryEvidence(BaseModel):
    """VRI or inventory context for one segment.

    Parameters
    ----------
    segment_id : str
        Segment id.
    height_m : float
        Inventory height.
    cover_pct : float
        Inventory cover.
    vintage : str
        Inventory vintage.
    source : str
        Inventory source.
    source_version : str
        Source version.
    model_card_id : str or None
        Optional model card.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    segment_id: str = Field(min_length=1)
    height_m: float = Field(ge=0)
    cover_pct: float = Field(ge=0, le=100)
    vintage: str = Field(min_length=1)
    source: str = Field(min_length=1)
    source_version: str = Field(min_length=1)
    model_card_id: str | None = None


class SiteIndexEvidence(BaseModel):
    """Site-index context for one segment.

    Parameters
    ----------
    segment_id : str
        Segment id.
    site_index_m : float
        Reconciled site index.
    species : str
        Species label.
    source : str
        Source.
    source_version : str
        Source version.
    model_card_id : str or None
        Optional model card.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    segment_id: str = Field(min_length=1)
    site_index_m: float = Field(ge=0)
    species: str = Field(min_length=1)
    source: str = Field(min_length=1)
    source_version: str = Field(min_length=1)
    model_card_id: str | None = None


class SegmentEvidence(BaseModel):
    """All evidence for one segment's initial state.

    Parameters
    ----------
    segment_id : str
        Segment id.
    canopy : CanopySupport or None
        P3.3 canopy support.
    terrain : TerrainSupport or None
        P3.2 terrain support.
    field_observations : list of FieldObservation
        Field evidence.
    inventory : InventoryEvidence or None
        Inventory context.
    site_index : SiteIndexEvidence or None
        Site-index context.
    climate_zone : str
        Climate or BEC context.
    disturbance : str
        Disturbance context.
    treatment_history : list of str
        Treatment action ids.
    functional_group_hint : str or None
        Optional species/functional-group hint.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    segment_id: str = Field(min_length=1)
    canopy: CanopySupport | None = None
    canopy_source: LidarProductProvenance | None = None
    terrain: TerrainSupport | None = None
    field_observations: list[FieldObservation] = Field(default_factory=list)
    inventory: InventoryEvidence | None = None
    site_index: SiteIndexEvidence | None = None
    climate_zone: str = ""
    disturbance: str = ""
    treatment_history: list[str] = Field(default_factory=list)
    functional_group_hint: str | None = None

    @model_validator(mode="after")
    def _evidence_consistency(self) -> SegmentEvidence:
        for observation in self.field_observations:
            if observation.segment_id != self.segment_id:
                raise ValueError("field observation segment_id must match the segment")
        if self.canopy is not None and self.canopy.segment_id != self.segment_id:
            raise ValueError("canopy segment_id must match the segment")
        if self.canopy is not None and self.canopy_source is None:
            raise ValueError("canopy evidence needs its source provenance")
        if (
            self.canopy is not None
            and self.canopy_source is not None
            and self.canopy_source.product != "chm"
        ):
            raise ValueError("canopy source provenance must be a CHM")
        if self.terrain is not None and self.terrain.segment_id != self.segment_id:
            raise ValueError("terrain segment_id must match the segment")
        if self.inventory is not None and self.inventory.segment_id != self.segment_id:
            raise ValueError("inventory segment_id must match the segment")
        if self.site_index is not None and self.site_index.segment_id != self.segment_id:
            raise ValueError("site-index segment_id must match the segment")
        if self.functional_group_hint is not None and (
            self.functional_group_hint not in FUNCTIONAL_GROUPS
        ):
            raise ValueError(f"unknown functional group hint {self.functional_group_hint!r}")
        return self


class StateDecision(BaseModel):
    """The audit record for one segment's initial state.

    Parameters
    ----------
    segment_id : str
        Segment id.
    state_class : str
        Selected state class.
    functional_group : str
        Selected functional group.
    confidence : float
        Confidence from 0 to 1.
    source : str
        Evidence source.
    coverage_state : str
        Canopy or field coverage state.
    height_m : float
        State height.
    cover_pct : float
        State cover.
    class_probabilities : dict of str to float
        Class probabilities.
    model_card_id : str or None
        Model card.
    observation_id : str or None
        Observation id.
    reason : str
        Decision reason.
    inventory_vintage : str
        Inventory vintage, when present.
    site_index_m : float or None
        Site index, when present.
    climate_zone : str
        Climate context.
    disturbance : str
        Disturbance context.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    segment_id: str = Field(min_length=1)
    state_class: StateClass
    functional_group: FunctionalGroup
    confidence: float = Field(ge=0, le=1)
    source: str
    coverage_state: str
    height_m: float = Field(ge=0)
    cover_pct: float = Field(ge=0, le=100)
    class_probabilities: dict[str, float] = Field(default_factory=dict)
    model_card_id: str | None = None
    observation_id: str | None = None
    reason: str = ""
    inventory_vintage: str = ""
    site_index_m: float | None = None
    climate_zone: str = ""
    disturbance: str = ""

    @model_validator(mode="after")
    def _probability_shape(self) -> StateDecision:
        if not self.class_probabilities:
            raise ValueError("class_probabilities must not be empty")
        if any(name not in PROBABILITY_CLASSES for name in self.class_probabilities):
            raise ValueError("class_probabilities contains an unknown state class")
        total = sum(self.class_probabilities.values())
        if any(value < 0 or value > 1 for value in self.class_probabilities.values()):
            raise ValueError("class probabilities must be between 0 and 1")
        if abs(total - 1.0) > 1e-6:
            raise ValueError("class probabilities must sum to 1")
        return self


class StateInitializationReport(BaseModel):
    """The result of an initial-state run.

    Parameters
    ----------
    schema_version : {"brushline.state-initialization.v1"}
        Report schema version.
    created_utc : datetime
        Timezone-aware creation time.
    config : StateInitializationConfig
        Thresholds and evidence rules.
    contract : StateContract
        The `brushline.state.v1` output.
    decisions : list of StateDecision
        Per-segment audit records.
    open_questions : list of str
        Issues the reviewer must see.
    """

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["brushline.state-initialization.v1"] = (
        STATE_INITIALIZATION_SCHEMA_VERSION
    )
    created_utc: datetime
    config: StateInitializationConfig
    contract: StateContract
    decisions: list[StateDecision] = Field(min_length=1)
    open_questions: list[str] = Field(default_factory=list)


def initialize_state(
    segments: list[SegmentEvidence],
    config: StateInitializationConfig | None = None,
    *,
    created_utc: datetime | None = None,
) -> StateInitializationReport:
    """Initialize one state per segment from field, CHM, and context evidence.

    Parameters
    ----------
    segments : list of SegmentEvidence
        Evidence for each segment.
    config : StateInitializationConfig, optional
        Thresholds and evidence rules.
    created_utc : datetime, optional
        Report time. Defaults to the current UTC time.

    Returns
    -------
    StateInitializationReport
        The validated state contract and audit decisions.

    Raises
    ------
    StateInitializationError
        When the segment list is empty or the evidence cannot produce a valid state.
    """
    if not segments:
        raise StateInitializationError("at least one segment is required")
    rules = config or StateInitializationConfig()
    states: list[VegetationState] = []
    observations: list[Observation] = []
    decisions: list[StateDecision] = []
    questions: list[str] = []
    seen_segments: set[str] = set()
    for evidence in segments:
        if evidence.segment_id in seen_segments:
            raise StateInitializationError(f"duplicate segment evidence {evidence.segment_id!r}")
        seen_segments.add(evidence.segment_id)
        field = _select_field(evidence, rules)
        if field is not None:
            state, observation, decision = _field_state(evidence, field, rules)
            states.append(state)
            observations.append(observation)
            decisions.append(decision)
            continue
        if evidence.field_observations:
            questions.append(
                f"Field evidence for {evidence.segment_id} was below the coverage or "
                "confidence rule; the CHM path was used."
            )
        canopy = evidence.canopy
        if canopy is None or canopy.state == "missing":
            state, decision = _unknown_state(evidence, rules, "no usable canopy evidence")
            states.append(state)
            decisions.append(decision)
            questions.append(f"Segment {evidence.segment_id} has no usable canopy state.")
            continue
        state, canopy_observation, decision = _canopy_state(evidence, canopy, rules)
        states.append(state)
        if canopy_observation is not None:
            observations.append(canopy_observation)
        decisions.append(decision)
        if state.state_class in ("partial", "unknown"):
            questions.append(
                f"Segment {evidence.segment_id} remains {state.state_class}; "
                "the CHM cannot resolve the low-vegetation state."
            )
        if (
            state.state_class in ("young_tree", "mature_edge")
            and evidence.functional_group_hint is None
        ):
            questions.append(
                f"Segment {evidence.segment_id} uses the conifer fallback for an "
                "unresolved woody functional group."
            )
    if any(decision.model_card_id == PROTOTYPE_MODEL_CARD for decision in decisions):
        questions.append(
            "The state uses the prototype low-vegetation rule card; P4 calibration is required."
        )
    if not observations:
        questions.append("No observation rows were attached to the state contract.")
    contract = StateContract(states=states, observations=observations)
    report = StateInitializationReport(
        created_utc=created_utc or datetime.now(UTC),
        config=rules,
        contract=contract,
        decisions=decisions,
        open_questions=questions,
    )
    validation = validate_state_initialization(report)
    if not validation.is_valid:
        raise StateInitializationError("; ".join(validation.errors))
    return report


def validate_state_initialization(
    report: StateInitializationReport,
) -> ContractValidation:
    """Validate the state contract and its audit records.

    Parameters
    ----------
    report : StateInitializationReport
        Report to validate.

    Returns
    -------
    ContractValidation
        Errors, warnings, and counts.
    """
    errors: list[str] = []
    warnings: list[str] = []
    check_duplicates(
        "STATE",
        "decision",
        [decision.segment_id for decision in report.decisions],
        errors,
    )
    if report.created_utc.tzinfo is None:
        errors.append("STATE-TIME: created_utc is not timezone-aware")
    required = {decision.segment_id for decision in report.decisions}
    state_validation = validate_state_contract(
        report.contract,
        required_segment_ids=required,
    )
    errors.extend(state_validation.errors)
    warnings.extend(state_validation.warnings)
    states_by_segment = {state.segment_id: state for state in report.contract.states}
    for decision in report.decisions:
        state = states_by_segment.get(decision.segment_id)
        if state is None:
            errors.append(f"STATE-DECISION: {decision.segment_id} has no state")
            continue
        if state.state_class != decision.state_class:
            errors.append(f"STATE-DECISION: {decision.segment_id} class does not match the state")
        if state.functional_group != decision.functional_group:
            errors.append(f"STATE-DECISION: {decision.segment_id} group does not match the state")
        if abs(state.uncertainty.confidence - decision.confidence) > 1e-6:
            errors.append(f"STATE-DECISION: {decision.segment_id} confidence does not match")
        if not decision.reason.strip():
            warnings.append(f"STATE-REASON: {decision.segment_id} has no decision reason")
    if not report.contract.observations:
        warnings.append("STATE-OBSERVATION: the contract has no observations")
    counts: dict[str, int | float] = {
        "segments": len(report.decisions),
        "states": len(report.contract.states),
        "observations": len(report.contract.observations),
        "unknown": sum(1 for state in report.contract.states if state.state_class == "unknown"),
        "partial": sum(1 for state in report.contract.states if state.state_class == "partial"),
    }
    return ContractValidation(tuple(errors), tuple(warnings), counts)


def _select_field(
    evidence: SegmentEvidence,
    config: StateInitializationConfig,
) -> FieldObservation | None:
    candidates = [
        observation
        for observation in evidence.field_observations
        if observation.coverage_pct >= config.field_min_coverage_pct
        and observation.confidence >= config.field_min_confidence
    ]
    return max(candidates, key=lambda item: item.observed_date, default=None)


def _field_state(
    evidence: SegmentEvidence,
    field: FieldObservation,
    config: StateInitializationConfig,
) -> tuple[VegetationState, Observation, StateDecision]:
    state = VegetationState(
        segment_id=evidence.segment_id,
        state_year=config.state_year,
        functional_group=field.functional_group,
        state_class=field.state_class,
        height_m=field.height_m,
        cover_pct=field.cover_pct,
        density_per_ha=field.density_per_ha,
        age_years=field.age_years,
        uncertainty=Uncertainty(
            height_m_sd=field.height_error_m,
            cover_pct_sd=field.cover_error_pct,
            confidence=field.confidence,
        ),
        treatment_history=list(evidence.treatment_history),
        source=field.source,
        source_version=field.source_version,
        model_card_id=field.model_card_id,
        observation_id=field.observation_id,
    )
    observation = Observation(
        observation_id=field.observation_id,
        segment_id=field.segment_id,
        observed_date=field.observed_date,
        sensor="field",
        product="field plot",
        coverage_pct=field.coverage_pct,
        height_m=field.height_m,
        cover_pct=field.cover_pct,
        density_per_ha=field.density_per_ha,
        height_error_m=field.height_error_m,
        cover_error_pct=field.cover_error_pct,
        model_card_id=field.model_card_id,
        source=field.source,
        source_version=field.source_version,
    )
    decision = StateDecision(
        segment_id=field.segment_id,
        state_class=field.state_class,
        functional_group=field.functional_group,
        confidence=field.confidence,
        source="field",
        coverage_state="observed",
        height_m=field.height_m,
        cover_pct=field.cover_pct,
        class_probabilities=_probabilities(field.state_class, field.confidence),
        model_card_id=field.model_card_id,
        observation_id=field.observation_id,
        reason="field observation meets coverage and confidence rules",
        inventory_vintage=evidence.inventory.vintage if evidence.inventory else "",
        site_index_m=evidence.site_index.site_index_m if evidence.site_index else None,
        climate_zone=evidence.climate_zone,
        disturbance=evidence.disturbance,
    )
    return state, observation, decision


def _canopy_state(
    evidence: SegmentEvidence,
    canopy: CanopySupport,
    config: StateInitializationConfig,
) -> tuple[VegetationState, Observation | None, StateDecision]:
    source = evidence.canopy_source
    if source is None:
        raise StateInitializationError("canopy evidence has no source provenance")
    state_class, group, height, cover, reason = _classify_canopy(
        canopy,
        config,
        evidence.functional_group_hint,
    )
    if canopy.state in ("partial", "out_of_domain"):
        state_class = "partial"
        group = group if group != "unknown" else _fallback_group(canopy, config)
        reason = f"{canopy.reason}; state is partial"
    confidence = _canopy_confidence(canopy, state_class)
    if state_class == "unknown":
        state, decision = _unknown_state(evidence, config, reason)
        return state, None, decision
    state = VegetationState(
        segment_id=evidence.segment_id,
        state_year=config.state_year,
        functional_group=group,
        state_class=state_class,
        height_m=height,
        cover_pct=cover,
        uncertainty=Uncertainty(
            height_m_sd=_height_sd(canopy, height),
            cover_pct_sd=10.0,
            confidence=confidence,
        ),
        treatment_history=list(evidence.treatment_history),
        source="femic-chm",
        source_version=f"{source.bundle_id}:{source.bundle_version}:{source.product_id}",
        model_card_id=PROTOTYPE_MODEL_CARD,
        observation_id=f"chm:{evidence.segment_id}:{source.product_id}",
    )
    observation = _canopy_observation(canopy, source, evidence.segment_id, height, cover)
    observation_id = (
        f"chm:{evidence.segment_id}:{source.product_id}" if observation is not None else None
    )
    if observation is None:
        state = state.model_copy(update={"observation_id": None})
    decision = StateDecision(
        segment_id=evidence.segment_id,
        state_class=state_class,
        functional_group=group,
        confidence=confidence,
        source="lidar-chm",
        coverage_state=canopy.state,
        height_m=height,
        cover_pct=cover,
        class_probabilities=_probabilities(state_class, confidence),
        model_card_id=PROTOTYPE_MODEL_CARD,
        observation_id=observation_id,
        reason=reason,
        inventory_vintage=evidence.inventory.vintage if evidence.inventory else "",
        site_index_m=evidence.site_index.site_index_m if evidence.site_index else None,
        climate_zone=evidence.climate_zone,
        disturbance=evidence.disturbance,
    )
    return state, observation, decision


def _unknown_state(
    evidence: SegmentEvidence,
    config: StateInitializationConfig,
    reason: str,
) -> tuple[VegetationState, StateDecision]:
    state = VegetationState(
        segment_id=evidence.segment_id,
        state_year=config.state_year,
        functional_group="unknown",
        state_class="unknown",
        height_m=0,
        cover_pct=0,
        uncertainty=Uncertainty(confidence=0.0),
        treatment_history=list(evidence.treatment_history),
        source="coverage",
        source_version="p3.4",
        model_card_id=None,
        observation_id=None,
    )
    decision = StateDecision(
        segment_id=evidence.segment_id,
        state_class="unknown",
        functional_group="unknown",
        confidence=0.0,
        source="coverage",
        coverage_state=evidence.canopy.state if evidence.canopy else "missing",
        height_m=0,
        cover_pct=0,
        class_probabilities={"unknown": 1.0},
        model_card_id=None,
        observation_id=None,
        reason=reason,
        inventory_vintage=evidence.inventory.vintage if evidence.inventory else "",
        site_index_m=evidence.site_index.site_index_m if evidence.site_index else None,
        climate_zone=evidence.climate_zone,
        disturbance=evidence.disturbance,
    )
    return state, decision


def _classify_canopy(
    canopy: CanopySupport,
    config: StateInitializationConfig,
    hint: str | None,
) -> tuple[StateClass, FunctionalGroup, float, float, str]:
    height = canopy.height_mean_m
    c2 = canopy.cover_2m_pct
    c5 = canopy.cover_5m_pct
    c10 = canopy.cover_10m_pct
    if height is None or c2 is None or c5 is None or c10 is None:
        return "unknown", "unknown", 0.0, 0.0, "canopy support has no height or cover"
    if (
        canopy.height_max_m is not None
        and canopy.height_max_m >= config.mature_edge_height_m
        and c10 >= config.mature_edge_cover_pct
        and canopy.tree is not None
        and canopy.tree.tree_count > 0
    ):
        group = _group_from_tree(canopy, hint) or "conifer"
        return "mature_edge", group, height, c10, "mature tree evidence at the corridor edge"
    if c2 >= config.cover_min_pct and c10 >= config.cover_min_pct:
        return (
            "mixed",
            _group_from_tree(canopy, hint) or "shrub",
            height,
            c10,
            ("multiple canopy strata exceed the cover threshold"),
        )
    if height <= config.grass_max_height_m and c2 < config.cover_min_pct:
        return "grass_herb", "grass_herb", height, c2, "low height and low woody cover"
    if height <= config.shrub_max_height_m and c5 >= config.cover_min_pct:
        return "shrub", "shrub", height, c5, "low woody height with shrub cover"
    if height <= config.young_tree_max_height_m and c10 >= config.cover_min_pct:
        tree_group = _group_from_tree(canopy, hint)
        if tree_group is None:
            return (
                "partial",
                _fallback_group(canopy, config),
                height,
                c10,
                ("young-tree candidate without species evidence"),
            )
        return (
            "young_tree",
            tree_group,
            height,
            c10,
            "young-tree height and cover with species evidence",
        )
    return (
        "partial",
        _fallback_group(canopy, config),
        height,
        c10,
        ("canopy observed but no low-vegetation rule matched"),
    )


def _group_from_tree(canopy: CanopySupport, hint: str | None) -> FunctionalGroup | None:
    if hint in ("conifer", "deciduous_sprout", "shrub", "grass_herb"):
        return cast("FunctionalGroup", hint)
    if canopy.tree is None:
        return None
    species = " ".join(canopy.tree.species).casefold()
    if any(word in species for word in ("conifer", "pine", "fir", "spruce", "hemlock", "cedar")):
        return "conifer"
    if any(word in species for word in ("deciduous", "aspen", "birch", "alder", "maple", "poplar")):
        return "deciduous_sprout"
    return None


def _fallback_group(canopy: CanopySupport, config: StateInitializationConfig) -> FunctionalGroup:
    if canopy.height_mean_m is not None and canopy.height_mean_m <= config.grass_max_height_m:
        return "grass_herb"
    return "shrub"


def _canopy_confidence(canopy: CanopySupport, state_class: str) -> float:
    if state_class == "unknown":
        return 0.0
    if state_class == "partial":
        return 0.35
    return min(0.85, 0.55 + canopy.coverage_pct / 400.0)


def _height_sd(canopy: CanopySupport, height: float) -> float:
    if canopy.height_p90_m is None:
        return 0.5
    return max(0.2, (canopy.height_p90_m - height) / 1.2816)


def _probabilities(primary: str, confidence: float) -> dict[str, float]:
    if primary == "unknown" or confidence >= 1.0:
        return {primary: 1.0}
    return {primary: round(confidence, 6), "unknown": round(1.0 - confidence, 6)}


def _canopy_observation(
    canopy: CanopySupport,
    source: LidarProductProvenance,
    segment_id: str,
    height: float,
    cover: float,
) -> Observation | None:
    try:
        observed = date.fromisoformat(source.retrieved_utc[:10])
    except ValueError:
        return None
    return Observation(
        observation_id=f"chm:{segment_id}:{source.product_id}",
        segment_id=segment_id,
        observed_date=observed,
        sensor="lidar",
        product="CHM",
        coverage_pct=canopy.coverage_pct,
        height_m=height,
        cover_pct=cover,
        height_error_m=_height_sd(canopy, height),
        cover_error_pct=10.0,
        model_card_id=PROTOTYPE_MODEL_CARD,
        source="femic-chm",
        source_version=f"{source.bundle_id}:{source.bundle_version}:{source.product_id}",
    )


__all__ = [
    "PROTOTYPE_MODEL_CARD",
    "STATE_INITIALIZATION_SCHEMA_VERSION",
    "STATE_INIT_SOURCES",
    "FieldObservation",
    "InventoryEvidence",
    "SegmentEvidence",
    "SiteIndexEvidence",
    "StateDecision",
    "StateInitializationConfig",
    "StateInitializationError",
    "StateInitializationReport",
    "initialize_state",
    "validate_state_initialization",
]
