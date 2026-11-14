"""Tests for initial vegetation state from field, CHM, and context evidence."""

from __future__ import annotations

from datetime import UTC, date, datetime

import pytest
from brushline.integrations.canopy import CanopyBand, CanopySupport, TreeSupport
from brushline.integrations.lidar import LidarProductProvenance
from brushline.model.state import validate_state_contract
from brushline.state_init import (
    PROTOTYPE_MODEL_CARD,
    FieldObservation,
    InventoryEvidence,
    SegmentEvidence,
    SiteIndexEvidence,
    StateDecision,
    StateInitializationConfig,
    StateInitializationError,
    initialize_state,
    validate_state_initialization,
)
from pydantic import ValidationError

NOW = datetime(2026, 11, 14, tzinfo=UTC)


def _provenance(product: str = "chm") -> LidarProductProvenance:
    return LidarProductProvenance(
        bundle_id="lidarbc-test",
        bundle_version="2026.1",
        femic_version="0.2.0a1",
        product_id=f"{product}-1",
        product=product,
        sha256="a" * 64,
        crs="EPSG:3005",
        resolution_m=1.0,
        vertical_datum="CGVD2013",
        licence_id="OGL-BC",
        retrieved_utc="2026-06-01T00:00:00+00:00",
        source_tile_ids=["tile-1"],
        source_layer_ids=[1],
        derived=False,
        lineage=[],
    )


def _canopy(
    *,
    height: float | None = 2.0,
    cover_2m: float | None = 30.0,
    cover_5m: float | None = 30.0,
    cover_10m: float | None = 10.0,
    cover_20m: float | None = 0.0,
    height_max: float | None = None,
    state: str = "observed",
    tree: TreeSupport | None = None,
    reason: str = "",
) -> CanopySupport:
    if height is None:
        return CanopySupport(
            segment_id="s1",
            state="missing",
            coverage_pct=0,
            candidate_pixels=25,
            valid_pixels=0,
            structure=[],
            tree=tree,
            buffer_m=10,
            reason=reason or "no cells",
        )
    maximum = height_max if height_max is not None else height
    return CanopySupport(
        segment_id="s1",
        state=state,
        coverage_pct=100,
        candidate_pixels=25,
        valid_pixels=25,
        height_mean_m=height,
        height_median_m=height,
        height_p90_m=height * 1.1,
        height_p95_m=height * 1.2,
        height_p99_m=height * 1.3,
        height_max_m=maximum,
        cover_2m_pct=cover_2m,
        cover_5m_pct=cover_5m,
        cover_10m_pct=cover_10m,
        cover_20m_pct=cover_20m,
        structure=[CanopyBand(lower_m=0, upper_m=5, cover_pct=30)],
        tree=tree,
        buffer_m=10,
        reason=reason,
    )


def _tree(species: list[str] | None = None) -> TreeSupport:
    return TreeSupport(
        segment_id="s1",
        provenance=_provenance("individual_tree"),
        tree_count=2,
        mean_height_m=12,
        mean_crown_radius_m=2,
        species=species or ["conifer"],
    )


def _evidence(
    canopy: CanopySupport | None = None,
    *,
    field_observations: list[FieldObservation] | None = None,
    inventory: InventoryEvidence | None = None,
    site_index: SiteIndexEvidence | None = None,
    hint: str | None = None,
) -> SegmentEvidence:
    return SegmentEvidence(
        segment_id="s1",
        canopy=canopy,
        canopy_source=_provenance() if canopy is not None else None,
        field_observations=field_observations or [],
        inventory=inventory,
        site_index=site_index,
        climate_zone="CWH",
        disturbance="none",
        treatment_history=["t1"],
        functional_group_hint=hint,
    )


def test_grass_herb_state() -> None:
    """Low height and low woody cover initializes grass/herb."""
    report = initialize_state(
        [_evidence(_canopy(height=0.3, cover_2m=5, cover_5m=0, cover_10m=0))],
        created_utc=NOW,
    )
    state = report.contract.states[0]
    assert state.state_class == "grass_herb"
    assert state.functional_group == "grass_herb"
    assert state.height_m == pytest.approx(0.3)
    assert state.cover_pct == 5
    assert state.model_card_id == PROTOTYPE_MODEL_CARD
    assert validate_state_contract(report.contract).is_valid
    assert validate_state_initialization(report).is_valid


def test_shrub_state() -> None:
    """Low woody height initializes shrub."""
    report = initialize_state([_evidence(_canopy())], created_utc=NOW)
    state = report.contract.states[0]
    assert state.state_class == "shrub"
    assert state.functional_group == "shrub"
    assert state.cover_pct == 30


def test_young_tree_requires_species_evidence() -> None:
    """A young-tree candidate with species evidence is young_tree; without it is partial."""
    with_tree = initialize_state(
        [_evidence(_canopy(height=6, cover_2m=10, cover_5m=20, cover_10m=30, tree=_tree()))],
        created_utc=NOW,
    )
    assert with_tree.contract.states[0].state_class == "young_tree"
    assert with_tree.contract.states[0].functional_group == "conifer"
    without_tree = initialize_state(
        [_evidence(_canopy(height=6, cover_2m=10, cover_5m=20, cover_10m=30))],
        created_utc=NOW,
    )
    assert without_tree.contract.states[0].state_class == "partial"
    assert without_tree.contract.states[0].functional_group == "shrub"
    assert without_tree.open_questions


def test_mixed_and_mature_edge_states() -> None:
    """Multiple strata initialize mixed; a tall tree edge initializes mature_edge."""
    mixed = initialize_state(
        [_evidence(_canopy(height=6, cover_2m=30, cover_5m=40, cover_10m=30))],
        created_utc=NOW,
    )
    assert mixed.contract.states[0].state_class == "mixed"
    mature = initialize_state(
        [
            _evidence(
                _canopy(
                    height=12,
                    height_max=20,
                    cover_2m=20,
                    cover_5m=30,
                    cover_10m=30,
                    tree=_tree(),
                )
            )
        ],
        created_utc=NOW,
    )
    assert mature.contract.states[0].state_class == "mature_edge"
    assert mature.contract.states[0].functional_group == "conifer"


def test_functional_group_hint_overrides_tree_species() -> None:
    """A species hint is used before the tree default."""
    report = initialize_state(
        [
            _evidence(
                _canopy(height=6, cover_2m=10, cover_5m=20, cover_10m=30, tree=_tree(["conifer"])),
                hint="deciduous_sprout",
            )
        ],
        created_utc=NOW,
    )
    assert report.contract.states[0].functional_group == "deciduous_sprout"


def test_missing_canopy_is_unknown() -> None:
    """Missing canopy evidence initializes an explicit unknown state."""
    report = initialize_state([_evidence(_canopy(height=None))], created_utc=NOW)
    state = report.contract.states[0]
    assert state.state_class == "unknown"
    assert state.functional_group == "unknown"
    assert state.height_m == 0
    assert state.cover_pct == 0
    assert state.uncertainty.confidence == 0
    assert report.decisions[0].coverage_state == "missing"
    assert report.open_questions


def test_partial_and_out_of_domain_canopy_are_partial_states() -> None:
    """Partial and out-of-domain canopy evidence never becomes observed."""
    for canopy_state in ("partial", "out_of_domain"):
        canopy = _canopy(state=canopy_state, reason=f"{canopy_state} reason")
        report = initialize_state([_evidence(canopy)], created_utc=NOW)
        state = report.contract.states[0]
        assert state.state_class == "partial"
        assert state.uncertainty.confidence == pytest.approx(0.35)
        assert canopy_state in report.decisions[0].reason


def test_field_observation_overrides_chm_and_is_attached() -> None:
    """A high-quality field observation is used and attached to the contract."""
    field = FieldObservation(
        observation_id="f1",
        segment_id="s1",
        observed_date=date(2026, 6, 1),
        state_class="young_tree",
        functional_group="conifer",
        height_m=5.0,
        cover_pct=55.0,
        density_per_ha=800,
        age_years=3,
        coverage_pct=100,
        height_error_m=0.4,
        cover_error_pct=5,
        confidence=0.9,
        source="plot",
        source_version="2026",
        model_card_id="field-card",
    )
    report = initialize_state(
        [
            _evidence(
                _canopy(height=2, cover_5m=30),
                field_observations=[field],
                inventory=InventoryEvidence(
                    segment_id="s1",
                    height_m=6,
                    cover_pct=50,
                    vintage="2024",
                    source="VRI",
                    source_version="2024",
                ),
                site_index=SiteIndexEvidence(
                    segment_id="s1",
                    site_index_m=18,
                    species="Fd",
                    source="SIBEC",
                    source_version="2024",
                ),
            )
        ],
        created_utc=NOW,
    )
    state = report.contract.states[0]
    assert state.state_class == "young_tree"
    assert state.functional_group == "conifer"
    assert state.source == "plot"
    assert state.observation_id == "f1"
    assert report.contract.observations[0].observation_id == "f1"
    decision = report.decisions[0]
    assert decision.source == "field"
    assert decision.inventory_vintage == "2024"
    assert decision.site_index_m == 18
    assert decision.climate_zone == "CWH"


def test_low_quality_field_falls_back_to_chm() -> None:
    """A field observation below the rules does not override the CHM."""
    field = FieldObservation(
        observation_id="f1",
        segment_id="s1",
        observed_date=date(2026, 6, 1),
        state_class="shrub",
        functional_group="shrub",
        height_m=2.0,
        cover_pct=30,
        coverage_pct=10,
        confidence=0.2,
        source="plot",
        source_version="2026",
    )
    report = initialize_state(
        [_evidence(_canopy(), field_observations=[field])],
        created_utc=NOW,
    )
    assert report.decisions[0].source == "lidar-chm"
    assert any("below the coverage" in question for question in report.open_questions)


def test_canopy_observation_and_chm_provenance_are_attached() -> None:
    """A canopy state carries its product provenance and a CHM observation."""
    report = initialize_state([_evidence(_canopy())], created_utc=NOW)
    state = report.contract.states[0]
    assert state.observation_id == "chm:s1:chm-1"
    observation = report.contract.observations[0]
    assert observation.observation_id == "chm:s1:chm-1"
    assert observation.sensor == "lidar"
    assert observation.model_card_id == PROTOTYPE_MODEL_CARD
    assert observation.source_version


def test_invalid_canopy_date_omits_observation() -> None:
    """An invalid provenance timestamp leaves the state valid without an observation row."""
    canopy = _canopy()
    source = _provenance().model_copy(update={"retrieved_utc": "bad"})
    evidence = SegmentEvidence(
        segment_id="s1",
        canopy=canopy,
        canopy_source=source,
    )
    report = initialize_state([evidence], created_utc=NOW)
    assert report.contract.observations == []
    assert validate_state_initialization(report).is_valid
    assert any("No observation rows" in question for question in report.open_questions)


def test_empty_and_duplicate_segments_fail() -> None:
    """An empty or duplicate segment list cannot initialize a contract."""
    with pytest.raises(StateInitializationError, match="at least one"):
        initialize_state([])
    evidence = _evidence(_canopy())
    with pytest.raises(StateInitializationError, match="duplicate segment"):
        initialize_state([evidence, evidence])


def test_field_and_evidence_models_reject_invalid_inputs() -> None:
    """Field, segment, and decision models reject inconsistent evidence."""
    invalid_field: dict[str, object] = {
        "observation_id": "f1",
        "segment_id": "s1",
        "observed_date": date(2026, 6, 1),
        "state_class": "maybe",
        "functional_group": "shrub",
        "height_m": 1,
        "cover_pct": 1,
        "coverage_pct": 100,
        "source": "plot",
        "source_version": "1",
    }
    with pytest.raises(ValidationError, match="state_class"):
        FieldObservation.model_validate(invalid_field)
    with pytest.raises(ValidationError, match="source provenance"):
        SegmentEvidence(segment_id="s1", canopy=_canopy())
    with pytest.raises(ValidationError, match="segment_id"):
        SegmentEvidence(
            segment_id="s1",
            canopy=_canopy().model_copy(update={"segment_id": "s2"}),
            canopy_source=_provenance(),
        )
    with pytest.raises(ValidationError, match="sum to 1"):
        StateDecision(
            segment_id="s1",
            state_class="shrub",
            functional_group="shrub",
            confidence=0.5,
            source="test",
            coverage_state="observed",
            height_m=1,
            cover_pct=1,
            class_probabilities={"shrub": 0.2},
        )


def test_state_initialization_validator_names_bad_decisions() -> None:
    """The report validator catches mismatched decisions and missing observations."""
    report = initialize_state([_evidence(_canopy())], created_utc=NOW)
    bad_class = report.model_copy(
        update={"decisions": [report.decisions[0].model_copy(update={"state_class": "mixed"})]}
    )
    assert any(
        error.startswith("STATE-DECISION")
        for error in validate_state_initialization(bad_class).errors
    )
    bad_confidence = report.model_copy(
        update={"decisions": [report.decisions[0].model_copy(update={"confidence": 0.1})]}
    )
    assert any(
        error.startswith("STATE-DECISION")
        for error in validate_state_initialization(bad_confidence).errors
    )
    duplicate = report.model_copy(update={"decisions": [report.decisions[0], report.decisions[0]]})
    assert any(
        error.startswith("STATE-ID") for error in validate_state_initialization(duplicate).errors
    )
    no_reason = report.model_copy(
        update={"decisions": [report.decisions[0].model_copy(update={"reason": ""})]}
    )
    assert any(
        warning.startswith("STATE-REASON")
        for warning in validate_state_initialization(no_reason).warnings
    )
    naive = report.model_copy(update={"created_utc": datetime(2026, 11, 14)})
    assert any(
        error.startswith("STATE-TIME") for error in validate_state_initialization(naive).errors
    )


def test_validate_state_initialization_warns_without_observations() -> None:
    """A report with no observation rows is valid but warned."""
    report = initialize_state([_evidence(_canopy())], created_utc=NOW)
    empty = report.model_copy(
        update={"contract": report.contract.model_copy(update={"observations": []})}
    )
    result = validate_state_initialization(empty)
    assert result.is_valid
    assert any(warning.startswith("STATE-OBSERVATION") for warning in result.warnings)


def test_field_unknown_and_group_consistency_errors() -> None:
    """The field model rejects unknown states with values or known states without a group."""
    base: dict[str, object] = {
        "observation_id": "f1",
        "segment_id": "s1",
        "observed_date": date(2026, 6, 1),
        "state_class": "unknown",
        "functional_group": "unknown",
        "height_m": 0,
        "cover_pct": 0,
        "coverage_pct": 100,
        "source": "plot",
        "source_version": "1",
    }
    with pytest.raises(ValidationError, match="unknown group"):
        FieldObservation.model_validate({**base, "functional_group": "shrub"})
    with pytest.raises(ValidationError, match="zero height"):
        FieldObservation.model_validate({**base, "height_m": 1})
    with pytest.raises(ValidationError, match="needs a functional group"):
        FieldObservation.model_validate(
            {**base, "state_class": "shrub", "functional_group": "unknown"}
        )


def test_segment_evidence_rejects_mismatched_context() -> None:
    """Canopy provenance, inventory, site index, and hints must agree with the segment."""
    with pytest.raises(ValidationError, match="must be a CHM"):
        SegmentEvidence(
            segment_id="s1",
            canopy=_canopy(),
            canopy_source=_provenance("dem"),
        )
    with pytest.raises(ValidationError, match="inventory segment_id"):
        SegmentEvidence(
            segment_id="s1",
            inventory=InventoryEvidence(
                segment_id="s2",
                height_m=4,
                cover_pct=20,
                vintage="2024",
                source="VRI",
                source_version="2024",
            ),
        )
    with pytest.raises(ValidationError, match="site-index segment_id"):
        SegmentEvidence(
            segment_id="s1",
            site_index=SiteIndexEvidence(
                segment_id="s2",
                site_index_m=18,
                species="Fd",
                source="SIBEC",
                source_version="2024",
            ),
        )
    with pytest.raises(ValidationError, match="functional group hint"):
        SegmentEvidence(segment_id="s1", functional_group_hint="other")


def test_observed_canopy_without_cover_is_unknown() -> None:
    """An observed support without cover fields cannot produce a known state."""
    canopy = _canopy().model_copy(update={"cover_2m_pct": None})
    report = initialize_state([_evidence(canopy)], created_utc=NOW)
    assert report.contract.states[0].state_class == "unknown"
    assert report.contract.observations == []


def test_tree_species_deciduous_and_unknown() -> None:
    """Deciduous species initialize deciduous_sprout; unknown species stays partial."""
    deciduous = initialize_state(
        [
            _evidence(
                _canopy(
                    height=6,
                    cover_2m=10,
                    cover_5m=20,
                    cover_10m=30,
                    tree=_tree(["aspen"]),
                )
            )
        ],
        created_utc=NOW,
    )
    assert deciduous.contract.states[0].functional_group == "deciduous_sprout"
    unknown = initialize_state(
        [
            _evidence(
                _canopy(
                    height=6,
                    cover_2m=10,
                    cover_5m=20,
                    cover_10m=30,
                    tree=_tree(["unknown species"]),
                )
            )
        ],
        created_utc=NOW,
    )
    assert unknown.contract.states[0].state_class == "partial"


def test_partial_fallback_and_height_sd_without_p90() -> None:
    """An unmatched canopy is partial; a missing p90 uses the fallback height SD."""
    canopy = _canopy(height=5, cover_2m=0, cover_5m=0, cover_10m=0).model_copy(
        update={"height_p90_m": None}
    )
    report = initialize_state([_evidence(canopy)], created_utc=NOW)
    state = report.contract.states[0]
    assert state.state_class == "partial"
    assert state.functional_group == "shrub"
    assert state.uncertainty.height_m_sd == 0.5


def test_confidence_one_and_decision_probability_errors() -> None:
    """A full-confidence field state uses one probability; invalid probability records fail."""
    field = FieldObservation(
        observation_id="f1",
        segment_id="s1",
        observed_date=date(2026, 6, 1),
        state_class="shrub",
        functional_group="shrub",
        height_m=2,
        cover_pct=30,
        coverage_pct=100,
        confidence=1.0,
        source="plot",
        source_version="1",
    )
    report = initialize_state(
        [_evidence(_canopy(), field_observations=[field])],
        created_utc=NOW,
    )
    assert report.decisions[0].class_probabilities == {"shrub": 1.0}
    base: dict[str, object] = {
        "segment_id": "s1",
        "state_class": "shrub",
        "functional_group": "shrub",
        "confidence": 0.5,
        "source": "test",
        "coverage_state": "observed",
        "height_m": 1,
        "cover_pct": 1,
        "class_probabilities": {},
    }
    with pytest.raises(ValidationError, match="must not be empty"):
        StateDecision.model_validate(base)
    with pytest.raises(ValidationError, match="unknown state class"):
        StateDecision.model_validate({**base, "class_probabilities": {"other": 1.0}})
    with pytest.raises(ValidationError, match="between 0 and 1"):
        StateDecision.model_validate(
            {**base, "class_probabilities": {"shrub": -0.1, "unknown": 1.1}}
        )


def test_validator_reports_missing_decision_state() -> None:
    """A decision with no matching state is a named error."""
    report = initialize_state([_evidence(_canopy())], created_utc=NOW)
    empty = report.model_copy(
        update={"contract": report.contract.model_copy(update={"states": []})}
    )
    assert any(
        error.startswith("STATE-DECISION") for error in validate_state_initialization(empty).errors
    )


def test_field_observation_segment_mismatch() -> None:
    """A field observation for another segment is rejected."""
    field = FieldObservation(
        observation_id="f1",
        segment_id="s2",
        observed_date=date(2026, 6, 1),
        state_class="shrub",
        functional_group="shrub",
        height_m=2,
        cover_pct=30,
        coverage_pct=100,
        source="plot",
        source_version="1",
    )
    with pytest.raises(ValidationError, match="field observation segment_id"):
        SegmentEvidence(segment_id="s1", field_observations=[field])


def test_terrain_segment_mismatch() -> None:
    """A terrain support for another segment is rejected."""
    from brushline.integrations.terrain import TerrainSupport

    terrain = TerrainSupport(
        segment_id="s2",
        state="observed",
        coverage_pct=100,
        candidate_pixels=4,
        valid_pixels=4,
        elevation_m=100,
        slope_deg=5,
        aspect_deg=180,
        terrain_class="gentle",
        access_proxy=0.8,
        access_class="high",
        buffer_m=10,
    )
    with pytest.raises(ValidationError, match="terrain segment_id"):
        SegmentEvidence(segment_id="s1", terrain=terrain)


def test_unknown_field_zero_state_is_valid() -> None:
    """An unknown field observation with zero values is valid evidence."""
    field = FieldObservation(
        observation_id="f0",
        segment_id="s1",
        observed_date=date(2026, 6, 1),
        state_class="unknown",
        functional_group="unknown",
        height_m=0,
        cover_pct=0,
        coverage_pct=100,
        confidence=1.0,
        source="plot",
        source_version="1",
    )
    report = initialize_state(
        [_evidence(_canopy(), field_observations=[field])],
        created_utc=NOW,
    )
    assert report.contract.states[0].state_class == "unknown"
    assert report.decisions[0].class_probabilities == {"unknown": 1.0}


def test_unmatched_low_canopy_falls_back_to_grass() -> None:
    """An unmatched low canopy uses the grass/herb fallback group."""
    report = initialize_state(
        [_evidence(_canopy(height=0.3, cover_2m=30, cover_5m=0, cover_10m=0))],
        created_utc=NOW,
    )
    state = report.contract.states[0]
    assert state.state_class == "partial"
    assert state.functional_group == "grass_herb"


def test_validator_names_group_mismatch() -> None:
    """A decision group that differs from the state is named."""
    report = initialize_state([_evidence(_canopy())], created_utc=NOW)
    bad = report.model_copy(
        update={
            "decisions": [report.decisions[0].model_copy(update={"functional_group": "conifer"})]
        }
    )
    assert any(
        error.startswith("STATE-DECISION") for error in validate_state_initialization(bad).errors
    )


def test_canopy_state_without_source_provenance_raises() -> None:
    """The private canopy path refuses evidence without source provenance."""
    from brushline.state_init import _canopy_state

    evidence = _evidence(_canopy()).model_copy(update={"canopy_source": None})
    with pytest.raises(StateInitializationError, match="source provenance"):
        _canopy_state(evidence, _canopy(), StateInitializationConfig())
