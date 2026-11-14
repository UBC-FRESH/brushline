"""Contract tests for vegetation state, treatments, transitions, and observations."""

from __future__ import annotations

from datetime import date

import pytest
from brushline.model.state import (
    FunctionalGroup,
    Observation,
    StateClass,
    StateContract,
    TreatmentAction,
    TreatmentTransition,
    Uncertainty,
    VegetationState,
    validate_state_contract,
)
from pydantic import ValidationError


def _state(
    segment_id: str = "s1",
    *,
    functional_group: FunctionalGroup = "shrub",
    state_class: StateClass = "shrub",
    height_m: float = 2.0,
    cover_pct: float = 50.0,
    confidence: float = 0.9,
) -> VegetationState:
    return VegetationState(
        segment_id=segment_id,
        state_year=2026,
        functional_group=functional_group,
        state_class=state_class,
        height_m=height_m,
        cover_pct=cover_pct,
        density_per_ha=1200.0 if state_class != "unknown" else None,
        age_years=3,
        uncertainty=Uncertainty(confidence=confidence),
        source="synthetic",
        source_version="1.0",
    )


def _contract() -> StateContract:
    return StateContract(
        states=[
            _state("s1"),
            _state("s2", functional_group="grass_herb", state_class="grass_herb"),
        ],
        treatments=[
            TreatmentAction(
                action_id="a1",
                segment_id="s1",
                year=2026,
                season="summer",
                method="mowing",
                intensity=0.8,
                efficacy=0.7,
                cost_per_ha=1200.0,
                status="applied",
            )
        ],
        transitions=[
            TreatmentTransition(
                transition_id="t1",
                segment_id="s1",
                year=2026,
                method="mowing",
                before_height_m=2.0,
                after_height_m=0.5,
                before_cover_pct=50.0,
                after_cover_pct=10.0,
                efficacy=0.75,
                regrowth_delay_years=2,
                source="synthetic",
            )
        ],
        observations=[
            Observation(
                observation_id="o1",
                segment_id="s1",
                observed_date=date(2026, 7, 1),
                sensor="lidar",
                product="CHM",
                coverage_pct=100.0,
                height_m=2.0,
                cover_pct=50.0,
                height_error_m=0.2,
                cover_error_pct=5.0,
                source="synthetic",
                source_version="1.0",
            )
        ],
    )


def test_valid_contract_passes() -> None:
    """A well-formed state contract passes with the required segments."""
    report = validate_state_contract(_contract(), required_segment_ids={"s1", "s2"})
    assert report.is_valid
    assert report.errors == ()
    assert report.counts["states"] == 2
    assert report.counts["treatments"] == 1
    assert report.counts["segments_with_state"] == 2


def test_report_is_json_ready() -> None:
    """The report serializes its validity, errors, warnings, and counts."""
    payload = validate_state_contract(_contract()).to_dict()
    assert payload["is_valid"] is True
    assert payload["errors"] == []
    assert payload["counts"] == {
        "observations": 1,
        "segments_with_state": 2,
        "states": 2,
        "treatments": 1,
        "transitions": 1,
    }


def test_duplicate_state_key_is_named() -> None:
    """Two states with the same segment/year/group fail with STATE-ID."""
    contract = _contract()
    duplicate = contract.model_copy(update={"states": [contract.states[0], contract.states[0]]})
    report = validate_state_contract(duplicate)
    assert any(message.startswith("STATE-ID") for message in report.errors)


def test_duplicate_action_transition_and_observation_ids_are_named() -> None:
    """Duplicate ids in each collection fail with STATE-ID."""
    contract = _contract()
    variants = [
        contract.model_copy(
            update={"treatments": [contract.treatments[0], contract.treatments[0]]}
        ),
        contract.model_copy(
            update={"transitions": [contract.transitions[0], contract.transitions[0]]}
        ),
        contract.model_copy(
            update={"observations": [contract.observations[0], contract.observations[0]]}
        ),
    ]
    for variant in variants:
        report = validate_state_contract(variant)
        assert any(message.startswith("STATE-ID") for message in report.errors)


def test_missing_required_segment_is_named() -> None:
    """A required segment without a state fails with STATE-MISSING."""
    report = validate_state_contract(_contract(), required_segment_ids={"s1", "s2", "s3"})
    assert any(message.startswith("STATE-MISSING") for message in report.errors)


def test_treatment_transition_and_observation_references_are_named() -> None:
    """A reference to a segment with no state fails with STATE-REF."""
    contract = _contract()
    bad_treatment = contract.treatments[0].model_copy(update={"segment_id": "s9"})
    bad_transition = contract.transitions[0].model_copy(update={"segment_id": "s9"})
    bad_observation = contract.observations[0].model_copy(update={"segment_id": "s9"})
    variants = [
        contract.model_copy(update={"treatments": [bad_treatment]}),
        contract.model_copy(update={"transitions": [bad_transition]}),
        contract.model_copy(update={"observations": [bad_observation]}),
    ]
    for variant in variants:
        report = validate_state_contract(variant)
        assert any(message.startswith("STATE-REF") for message in report.errors)


def test_partial_confidence_coverage_and_delay_warnings() -> None:
    """A partial state, low confidence, partial coverage, and long delay are warnings."""
    contract = _contract()
    partial = contract.states[0].model_copy(
        update={"state_class": "partial", "uncertainty": Uncertainty(confidence=0.2)}
    )
    observation = contract.observations[0].model_copy(update={"coverage_pct": 40.0})
    transition = contract.transitions[0].model_copy(update={"regrowth_delay_years": 25})
    variant = contract.model_copy(
        update={
            "states": [partial, contract.states[1]],
            "observations": [observation],
            "transitions": [transition],
        }
    )
    report = validate_state_contract(variant)
    assert report.is_valid
    assert any(message.startswith("STATE-PARTIAL") for message in report.warnings)
    assert any(message.startswith("STATE-UNCERTAIN") for message in report.warnings)
    assert any(message.startswith("STATE-COVERAGE") for message in report.warnings)
    assert any(message.startswith("STATE-DELAY") for message in report.warnings)


def test_unknown_state_must_be_empty() -> None:
    """An unknown state must have the unknown group and zero height and cover."""
    valid = _state(
        "s1",
        functional_group="unknown",
        state_class="unknown",
        height_m=0.0,
        cover_pct=0.0,
    )
    assert valid.state_class == "unknown"
    with pytest.raises(ValidationError):
        _state(
            "s1",
            functional_group="unknown",
            state_class="unknown",
            height_m=1.0,
            cover_pct=0.0,
        )
    with pytest.raises(ValidationError):
        _state("s1", functional_group="shrub", state_class="unknown", height_m=0.0, cover_pct=0.0)
    with pytest.raises(ValidationError):
        _state("s1", functional_group="unknown", state_class="shrub")


def test_unknown_state_must_have_no_density_or_biomass() -> None:
    """An unknown state must not carry density or biomass."""
    with pytest.raises(ValidationError):
        VegetationState(
            segment_id="s1",
            state_year=2026,
            functional_group="unknown",
            state_class="unknown",
            height_m=0.0,
            cover_pct=0.0,
            density_per_ha=1.0,
            source="synthetic",
            source_version="1.0",
        )


def test_state_ranges_are_enforced() -> None:
    """Cover, density, and year ranges fail at the model boundary."""
    with pytest.raises(ValidationError):
        _state("s1", cover_pct=101.0)
    with pytest.raises(ValidationError):
        VegetationState(
            segment_id="s1",
            state_year=2026,
            functional_group="shrub",
            state_class="shrub",
            height_m=1.0,
            cover_pct=10.0,
            density_per_ha=-1.0,
            source="synthetic",
            source_version="1.0",
        )
    with pytest.raises(ValidationError):
        VegetationState(
            segment_id="s1",
            state_year=1800,
            functional_group="shrub",
            state_class="shrub",
            height_m=1.0,
            cover_pct=10.0,
            source="synthetic",
            source_version="1.0",
        )


def test_treatment_ranges_are_enforced() -> None:
    """Treatment intensity and efficacy are bounded to 0 to 1."""
    with pytest.raises(ValidationError):
        TreatmentAction(
            action_id="a1",
            segment_id="s1",
            year=2026,
            season="summer",
            method="mowing",
            intensity=1.5,
            efficacy=0.5,
        )
    with pytest.raises(ValidationError):
        TreatmentAction(
            action_id="a1",
            segment_id="s1",
            year=2026,
            season="summer",
            method="mowing",
            intensity=0.5,
            efficacy=1.5,
        )


def test_transition_cannot_increase_height_or_cover() -> None:
    """A treatment transition must not increase height or cover."""
    with pytest.raises(ValidationError):
        TreatmentTransition(
            transition_id="t1",
            segment_id="s1",
            year=2026,
            method="mowing",
            before_height_m=1.0,
            after_height_m=2.0,
            before_cover_pct=10.0,
            after_cover_pct=10.0,
            efficacy=0.5,
            regrowth_delay_years=1,
            source="synthetic",
        )
    with pytest.raises(ValidationError):
        TreatmentTransition(
            transition_id="t1",
            segment_id="s1",
            year=2026,
            method="mowing",
            before_height_m=1.0,
            after_height_m=1.0,
            before_cover_pct=10.0,
            after_cover_pct=20.0,
            efficacy=0.5,
            regrowth_delay_years=1,
            source="synthetic",
        )


def test_observation_ranges_are_enforced() -> None:
    """Observation coverage and error must be bounded and non-negative."""
    with pytest.raises(ValidationError):
        Observation(
            observation_id="o1",
            segment_id="s1",
            observed_date=date(2026, 7, 1),
            sensor="lidar",
            product="CHM",
            coverage_pct=101.0,
            source="synthetic",
            source_version="1.0",
        )
    with pytest.raises(ValidationError):
        Observation(
            observation_id="o1",
            segment_id="s1",
            observed_date=date(2026, 7, 1),
            sensor="lidar",
            product="CHM",
            coverage_pct=50.0,
            height_error_m=-0.1,
            source="synthetic",
            source_version="1.0",
        )
    with pytest.raises(ValidationError):
        Observation(
            observation_id="o1",
            segment_id="s1",
            observed_date=date(1800, 7, 1),
            sensor="lidar",
            product="CHM",
            coverage_pct=50.0,
            source="synthetic",
            source_version="1.0",
        )


def test_contract_round_trips_through_json() -> None:
    """The state contract round-trips through JSON without a semantic change."""
    contract = _contract()
    loaded = StateContract.model_validate_json(contract.model_dump_json())
    assert loaded == contract
