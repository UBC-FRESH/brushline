"""Tests for method-specific low-vegetation treatment transitions."""

from __future__ import annotations

import pytest
from brushline.model.state import StateContract, VegetationState, validate_state_contract
from brushline.vegetation.growth import GrowthEnvironment
from brushline.vegetation.state_space import StateDistribution
from brushline.vegetation.treatment import (
    TREATMENT_PARAMETERS,
    TreatmentConfig,
    TreatmentError,
    TreatmentRequest,
    apply_treatment,
    validate_treatment_result,
)
from pydantic import ValidationError


def _distribution(
    *,
    height: float = 2.0,
    cover: float = 30.0,
    density: float | None = 1000.0,
    age: int | None = 3,
) -> StateDistribution:
    return StateDistribution(
        class_probabilities={"shrub": 0.8, "unknown": 0.2},
        height_m=height,
        height_sd=0.2,
        cover_pct=cover,
        cover_sd=5.0,
        density_per_ha=density,
        density_sd=50.0,
        age_years=age,
        confidence=0.8,
    )


def _request(**updates: object) -> TreatmentRequest:
    values: dict[str, object] = {
        "segment_id": "s1",
        "functional_group": "shrub",
        "current": _distribution(),
        "method": "mowing",
        "season": "spring",
        "intensity": 1.0,
        "quantity_ha": 2.0,
        "regrowth_years": 0,
        "environment": GrowthEnvironment(),
    }
    values.update(updates)
    return TreatmentRequest.model_validate(values)


def test_immediate_transition_reduces_and_keeps_residual() -> None:
    """A mowing transition reduces height/cover, increases density, and keeps a residual."""
    result = apply_treatment(_request())
    assert result.status == "applied"
    assert result.immediate is not None
    assert result.immediate.height_m < result.previous.height_m
    assert result.immediate.cover_pct < result.previous.cover_pct
    assert result.immediate.height_m > 0
    assert result.immediate.cover_pct > 0
    assert result.density_change_per_ha is not None
    assert result.density_change_per_ha > 0
    assert result.immediate.age_years == 0
    assert result.cost == 1000.0
    assert result.currency == "CAD"
    assert result.height_reduction_m is not None
    assert result.height_reduction_m > 0
    assert result.cover_reduction_pct is not None
    assert result.cover_reduction_pct > 0
    assert validate_treatment_result(result).is_valid


def test_delayed_trajectory_uses_growth() -> None:
    """A trajectory beyond the delay grows above the immediate state."""
    result = apply_treatment(
        _request(regrowth_years=6),
        TreatmentConfig(),
    )
    assert result.immediate is not None
    assert result.next is not None
    assert result.next.height_m > result.immediate.height_m
    assert result.next.cover_pct > result.immediate.cover_pct
    assert result.regrowth_delay_years == 1
    assert result.next_state_class is not None
    assert validate_treatment_result(result).is_valid


def test_horizon_inside_delay_holds_immediate_state() -> None:
    """A horizon shorter than the delay does not grow."""
    result = apply_treatment(_request(regrowth_years=1, method="chemical"))
    assert result.immediate is not None
    assert result.next is not None
    assert result.next.height_m == result.immediate.height_m
    assert result.next.cover_pct == result.immediate.cover_pct


def test_method_and_season_change_efficacy() -> None:
    """Method and season factors change the effective transition."""
    spring = apply_treatment(_request(method="mowing", season="spring"))
    winter = apply_treatment(_request(method="mowing", season="winter"))
    chemical = apply_treatment(_request(method="chemical", season="spring"))
    assert spring.efficiency > winter.efficiency
    assert spring.immediate is not None
    assert winter.immediate is not None
    assert chemical.immediate is not None
    assert spring.immediate.height_m < winter.immediate.height_m
    assert spring.efficiency != chemical.efficiency


def test_unknown_group_is_blocked() -> None:
    """An unknown group has no treatment transition."""
    result = apply_treatment(_request(functional_group="unknown"))
    assert result.status == "unknown"
    assert result.immediate is None
    assert result.reason
    assert validate_treatment_result(result).is_valid


def test_out_of_domain_is_blocked() -> None:
    """An out-of-domain environment has no transition."""
    result = apply_treatment(
        _request(
            environment=GrowthEnvironment(
                in_domain=False,
                domain_reason="outside the treatment domain",
            )
        )
    )
    assert result.status == "out_of_domain"
    assert result.immediate is None
    assert result.reason == "outside the treatment domain"


def test_trajectory_out_of_domain_keeps_immediate() -> None:
    """A treatment can apply while the post-delay trajectory is blocked."""
    result = apply_treatment(
        _request(regrowth_years=4, environment=GrowthEnvironment(site_index_m=50)),
        TreatmentConfig(),
    )
    assert result.status == "applied"
    assert result.immediate is not None
    assert result.next is None
    assert "trajectory blocked" in result.reason
    assert validate_treatment_result(result).is_valid


def test_to_state_contract_and_blocked_conversion() -> None:
    """The trajectory converts to a valid state; a blocked result does not."""
    result = apply_treatment(_request(regrowth_years=3))
    state = result.to_vegetation_state(2027)
    assert state.state_year == 2027
    assert validate_state_contract(_contract_for(state)).is_valid
    blocked = apply_treatment(_request(functional_group="unknown"))
    with pytest.raises(TreatmentError, match="no post-treatment"):
        blocked.to_vegetation_state(2027)


def _contract_for(state: VegetationState) -> StateContract:
    return StateContract(states=[state])


def test_regrowth_horizon_limit() -> None:
    """A horizon above the configured maximum fails."""
    with pytest.raises(TreatmentError, match="maximum"):
        apply_treatment(
            _request(regrowth_years=20),
            TreatmentConfig(max_regrowth_years=5),
        )


def test_config_and_request_validation() -> None:
    """Season, factor, intensity, and residual rules are validated."""
    with pytest.raises(ValidationError, match="unknown season"):
        TreatmentConfig(season_factors={"monsoon": 1.0})
    with pytest.raises(ValidationError, match="season factors"):
        TreatmentConfig(season_factors={"spring": 3.0})
    with pytest.raises(ValidationError):
        _request(intensity=2.0)
    with pytest.raises(ValidationError):
        _request(method="unknown")
    with pytest.raises(ValidationError):
        _request(regrowth_years=21)
    with pytest.raises(ValidationError, match="less than or equal"):
        TreatmentRequest.model_validate(
            {
                **_request().model_dump(),
                "intensity": 2.0,
            }
        )


def test_immediate_unknown_class_becomes_partial() -> None:
    """A residual that does not match a class becomes a partial state."""
    result = apply_treatment(_request(current=_distribution(height=12, cover=5)))
    assert result.immediate is not None
    assert result.immediate_state_class == "partial"


def test_parameters_and_private_lookup() -> None:
    """Every method has parameters; an unregistered method is rejected."""
    assert {item.method for item in TREATMENT_PARAMETERS} == {
        "manual",
        "mechanical",
        "mowing",
        "chemical",
        "grazing",
        "prescribed_fire",
        "other",
    }
    from brushline.vegetation.treatment import _parameters

    with pytest.raises(TreatmentError, match="no treatment parameters"):
        _parameters("unknown")  # type: ignore[arg-type]  # Intentional invalid method.


def test_treatment_validator_names_bad_results() -> None:
    """The validator catches status, next, height/cover, cost, and efficiency errors."""
    result = apply_treatment(_request())
    bad_status = result.model_copy(update={"status": "maybe"})
    assert any(
        error.startswith("TREATMENT-STATUS")
        for error in validate_treatment_result(bad_status).errors
    )
    blocked_with_next = result.model_copy(update={"status": "unknown"})
    assert any(
        error.startswith("TREATMENT-NEXT")
        for error in validate_treatment_result(blocked_with_next).errors
    )
    assert result.immediate is not None
    height_up = result.model_copy(
        update={
            "immediate": result.immediate.model_copy(
                update={"height_m": result.previous.height_m + 1}
            )
        }
    )
    assert any(
        error.startswith("TREATMENT-HEIGHT")
        for error in validate_treatment_result(height_up).errors
    )
    cover_up = result.model_copy(
        update={
            "immediate": result.immediate.model_copy(
                update={"cover_pct": result.previous.cover_pct + 1}
            )
        }
    )
    assert any(
        error.startswith("TREATMENT-COVER") for error in validate_treatment_result(cover_up).errors
    )
    zero = result.model_copy(
        update={"immediate": result.immediate.model_copy(update={"height_m": 0})}
    )
    assert any(
        error.startswith("TREATMENT-RESIDUAL") for error in validate_treatment_result(zero).errors
    )
    no_class = result.model_copy(update={"next_state_class": None})
    assert any(
        error.startswith("TREATMENT-NEXT") for error in validate_treatment_result(no_class).errors
    )
    no_immediate = result.model_copy(update={"immediate": None})
    assert any(
        error.startswith("TREATMENT-NEXT")
        for error in validate_treatment_result(no_immediate).errors
    )
    negative_cost = result.model_copy(update={"cost": -1})
    assert any(
        error.startswith("TREATMENT-COST")
        for error in validate_treatment_result(negative_cost).errors
    )
    negative_cover = result.model_copy(
        update={"immediate": result.immediate.model_copy(update={"cover_pct": -1})}
    )
    assert any(
        error.startswith("TREATMENT-RESIDUAL")
        for error in validate_treatment_result(negative_cover).errors
    )
    negative_height_change = result.model_copy(update={"height_reduction_m": -1})
    assert any(
        error.startswith("TREATMENT-HEIGHT")
        for error in validate_treatment_result(negative_height_change).errors
    )
    negative_cover_change = result.model_copy(update={"cover_reduction_pct": -1})
    assert any(
        error.startswith("TREATMENT-COVER")
        for error in validate_treatment_result(negative_cover_change).errors
    )
    bad_efficiency = result.model_copy(update={"efficiency": 2})
    assert any(
        error.startswith("TREATMENT-EFFICIENCY")
        for error in validate_treatment_result(bad_efficiency).errors
    )
    blocked = apply_treatment(_request(functional_group="unknown"))
    no_reason = blocked.model_copy(update={"reason": ""})
    assert any(
        error.startswith("TREATMENT-REASON")
        for error in validate_treatment_result(no_reason).errors
    )


def test_immediate_class_can_remain_shrub() -> None:
    """A light treatment can leave a non-unknown immediate class."""
    result = apply_treatment(_request(method="manual", intensity=0.4))
    assert result.immediate is not None
    assert result.immediate_state_class == "shrub"
