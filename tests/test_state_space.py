"""Tests for the P4 low-vegetation state space and discretization."""

from __future__ import annotations

import pytest
from brushline.model.state import StateContract, VegetationState, validate_state_contract
from brushline.vegetation.state_space import (
    FUNCTIONAL_GROUP_PROFILES,
    STATE_SPACE_CLASSES,
    STATE_SPACE_GROUPS,
    STATE_VARIABLES,
    StateDistribution,
    StateObservation,
    StateProjection,
    StateSpaceConfig,
    StateStratum,
    StateVariable,
    project_state,
    validate_state_projection,
)
from pydantic import ValidationError


def _observation(**updates: object) -> StateObservation:
    values: dict[str, object] = {
        "segment_id": "s1",
        "state_year": 2026,
        "functional_group": "shrub",
        "height_m": 2.0,
        "cover_pct": 30.0,
        "density_per_ha": 1000.0,
        "age_years": 3,
        "coverage_pct": 100.0,
        "height_sd": 0.2,
        "cover_sd": 5.0,
        "source": "field",
        "source_version": "2026",
        "observation_id": "f1",
    }
    values.update(updates)
    return StateObservation.model_validate(values)


def test_state_space_variables_and_profiles_are_complete() -> None:
    """Every variable and functional group has a documented envelope."""
    assert STATE_VARIABLES == (
        "height_m",
        "cover_pct",
        "density_per_ha",
        "biomass_kg_per_ha",
        "age_years",
    )
    assert {profile.group for profile in FUNCTIONAL_GROUP_PROFILES} == set(STATE_SPACE_GROUPS)
    for spec in (
        StateVariable(
            name="height_m",
            unit="m",
            minimum=0,
            maximum=100,
            unknown_rule="unknown",
        ),
    ):
        assert spec.unit == "m"
    assert STATE_SPACE_CLASSES == (
        "unknown",
        "partial",
        "grass_herb",
        "shrub",
        "young_tree",
        "mixed",
        "mature_edge",
    )


@pytest.mark.parametrize(
    ("height", "cover", "expected"),
    [
        (0.3, 5.0, "grass_herb"),
        (2.0, 30.0, "shrub"),
        (6.0, 30.0, "young_tree"),
        (16.0, 30.0, "mature_edge"),
        (12.0, 0.0, "unknown"),
    ],
)
def test_observed_classes(height: float, cover: float, expected: str) -> None:
    """Height and cover thresholds select a deterministic class."""
    projection = project_state(
        _observation(height_m=height, cover_pct=cover),
    )
    assert projection.coverage_state == "observed"
    if expected == "unknown":
        assert projection.state_class == "unknown"
        assert projection.functional_group == "unknown"
        assert projection.coverage_state == "observed"
    else:
        assert projection.state_class == expected
        assert projection.functional_group == "shrub"


def test_mixed_uses_strata() -> None:
    """Multiple cover-bearing strata produce a mixed class."""
    observation = _observation(
        height_m=6,
        cover_pct=30,
        strata=[
            StateStratum(functional_group="shrub", height_m=2, cover_pct=30),
            StateStratum(functional_group="conifer", height_m=6, cover_pct=30),
        ],
    )
    projection = project_state(observation)
    assert projection.state_class == "mixed"
    assert projection.coverage_state == "observed"


def test_partial_and_unknown_coverage() -> None:
    """Low coverage becomes partial or unknown, not an observed state."""
    partial = project_state(_observation(coverage_pct=25))
    assert partial.state_class == "partial"
    assert partial.coverage_state == "partial"
    assert partial.functional_group == "shrub"
    assert partial.reason
    assert partial.to_vegetation_state().state_class == "partial"
    unknown = project_state(_observation(coverage_pct=5))
    assert unknown.state_class == "unknown"
    assert unknown.coverage_state == "missing"
    assert unknown.functional_group == "unknown"
    assert unknown.to_vegetation_state().state_class == "unknown"


def test_out_of_domain_is_partial_and_flagged() -> None:
    """An out-of-domain observation becomes a flagged partial state."""
    projection = project_state(
        _observation(
            in_domain=False,
            domain_reason="outside the calibrated climate range",
        )
    )
    assert projection.state_class == "partial"
    assert projection.coverage_state == "out_of_domain"
    assert projection.reason == "outside the calibrated climate range"


def test_missing_height_and_group_are_unknown() -> None:
    """Missing height or an unknown group produces an unknown state."""
    no_height = project_state(_observation(height_m=None))
    assert no_height.state_class == "unknown"
    assert no_height.distribution.height_m == 0
    no_group = project_state(_observation(functional_group="unknown", height_m=0, cover_pct=0))
    assert no_group.state_class == "unknown"


def test_projection_to_state_contract_is_valid() -> None:
    """Observed, partial, and unknown projections all validate as state contracts."""
    for observation in (
        _observation(),
        _observation(coverage_pct=25),
        _observation(coverage_pct=5),
    ):
        projection = project_state(observation)
        result = validate_state_projection(projection)
        assert result.is_valid, result.errors
        state = projection.to_vegetation_state()
        assert state.segment_id == "s1"
        assert state.state_year == 2026
        assert validate_state_contract(_contract_for(state)).is_valid


def _contract_for(state: VegetationState) -> StateContract:
    return StateContract(states=[state])


def test_missing_cover_and_unmatched_partial() -> None:
    """Missing cover is unknown; an unmatched partial candidate becomes partial."""
    no_cover = project_state(_observation(cover_pct=None))
    assert no_cover.state_class == "unknown"
    assert no_cover.reason == "cover is unknown"
    unmatched = project_state(_observation(height_m=12, cover_pct=0, coverage_pct=25))
    assert unmatched.state_class == "partial"
    assert unmatched.coverage_state == "partial"
    assert unmatched.distribution.class_probabilities == {
        "partial": 0.7,
        "unknown": 0.3,
    }


def test_distribution_probabilities_and_ranges() -> None:
    """Distribution probabilities must name classes, be in range, and sum to one."""
    valid = StateDistribution(
        class_probabilities={"shrub": 0.8, "unknown": 0.2},
        height_m=2,
        height_sd=0.2,
        cover_pct=30,
        cover_sd=5,
        density_per_ha=1000,
        age_years=3,
        confidence=0.8,
    )
    assert valid.class_probabilities["shrub"] == 0.8
    cases = [
        ({}, "must not be empty"),
        ({"alien": 1.0}, "unknown state class"),
        ({"shrub": -0.1, "unknown": 1.1}, "between 0 and 1"),
        ({"shrub": 0.5}, "sum to 1"),
    ]
    for probabilities, message in cases:
        payload: dict[str, object] = valid.model_dump()
        payload["class_probabilities"] = probabilities
        with pytest.raises(ValidationError, match=message):
            StateDistribution.model_validate(payload)


def test_configuration_validation() -> None:
    """Height and coverage thresholds must be ordered."""
    with pytest.raises(ValidationError, match="height thresholds"):
        StateSpaceConfig(grass_max_height_m=10, shrub_max_height_m=4)
    with pytest.raises(ValidationError, match="unknown coverage"):
        StateSpaceConfig(
            unknown_below_coverage_pct=60,
            observed_min_coverage_pct=50,
        )


def test_observation_validation_errors() -> None:
    """Unknown groups, bad strata, and out-of-domain observations are rejected."""
    with pytest.raises(ValidationError, match="functional_group"):
        _observation(functional_group="other")
    with pytest.raises(ValidationError, match="empty height"):
        _observation(functional_group="unknown", height_m=1)
    with pytest.raises(ValidationError, match="functional_group"):
        StateStratum.model_validate({"functional_group": "other", "height_m": 1, "cover_pct": 1})
    with pytest.raises(ValidationError, match="needs a reason"):
        _observation(in_domain=False)
    with pytest.raises(ValidationError):
        StateStratum(functional_group="shrub", height_m=-1, cover_pct=10)


def test_projection_validator_catches_bad_records() -> None:
    """The projection validator catches class/group/value/probability errors."""
    projection = project_state(_observation())
    unknown_group = projection.model_copy(
        update={
            "state_class": "unknown",
            "functional_group": "shrub",
            "distribution": projection.distribution.model_copy(update={"height_m": 1}),
        }
    )
    assert any(
        error.startswith("STATE-SPACE-GROUP")
        for error in validate_state_projection(unknown_group).errors
    )
    known_missing_group = projection.model_copy(update={"functional_group": "unknown"})
    assert any(
        error.startswith("STATE-SPACE-GROUP")
        for error in validate_state_projection(known_missing_group).errors
    )
    no_probability = projection.model_copy(
        update={
            "distribution": projection.distribution.model_copy(
                update={"class_probabilities": {"unknown": 1.0}}
            )
        }
    )
    assert any(
        error.startswith("STATE-SPACE-PROBABILITY")
        for error in validate_state_projection(no_probability).errors
    )
    partial = project_state(_observation(coverage_pct=25))
    no_reason = partial.model_copy(update={"reason": ""})
    assert any(
        error.startswith("STATE-SPACE-REASON")
        for error in validate_state_projection(no_reason).errors
    )


def test_projection_model_rejects_invalid_coverage_and_group() -> None:
    """A projection with a bad coverage state or unknown class/group pair is rejected."""
    projection = project_state(_observation())
    payload: dict[str, object] = projection.model_dump()
    payload["coverage_state"] = "maybe"
    with pytest.raises(ValidationError, match="coverage state"):
        StateProjection.model_validate(payload)
    payload = projection.model_dump()
    payload["state_class"] = "unknown"
    payload["functional_group"] = "shrub"
    with pytest.raises(ValidationError, match="unknown group"):
        StateProjection.model_validate(payload)
