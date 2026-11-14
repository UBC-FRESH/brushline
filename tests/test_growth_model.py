"""Tests for the P4.2 fast low-vegetation growth model."""

from __future__ import annotations

from typing import cast

import pytest
from brushline.model.state import (
    FunctionalGroup,
    StateContract,
    VegetationState,
    validate_state_contract,
)
from brushline.vegetation.growth import (
    GROWTH_PARAMETERS,
    GrowthConfig,
    GrowthEnvironment,
    GrowthError,
    GrowthRequest,
    grow,
    validate_growth_result,
)
from brushline.vegetation.state_space import (
    StateDistribution,
    classify_state,
)
from pydantic import ValidationError


def _distribution(
    *,
    height: float = 2.0,
    cover: float = 30.0,
    density: float | None = 1000.0,
    age: int | None = 3,
    height_sd: float = 0.2,
    cover_sd: float = 5.0,
) -> StateDistribution:
    return StateDistribution(
        class_probabilities={"shrub": 0.8, "unknown": 0.2},
        height_m=height,
        height_sd=height_sd,
        cover_pct=cover,
        cover_sd=cover_sd,
        density_per_ha=density,
        density_sd=50.0,
        age_years=age,
        confidence=0.8,
    )


def _request(
    *,
    group: FunctionalGroup = "shrub",
    current: StateDistribution | None = None,
    years: int = 1,
    environment: GrowthEnvironment | None = None,
) -> GrowthRequest:
    return GrowthRequest(
        segment_id="s1",
        functional_group=group,
        current=current or _distribution(),
        years=years,
        environment=environment or GrowthEnvironment(),
    )


def test_growth_is_monotone_and_bounded() -> None:
    """A single growth step increases height/cover but stays below the asymptote."""
    result = grow(_request(), GrowthConfig())
    assert result.status == "grown"
    assert result.next is not None
    assert result.next.height_m > result.previous.height_m
    assert result.next.cover_pct > result.previous.cover_pct
    assert result.next.height_m <= 4.0
    assert result.next.cover_pct <= 90
    assert result.height_change_m is not None
    assert result.height_change_m > 0
    assert result.next.age_years == 4
    assert result.next.confidence < result.previous.confidence
    assert validate_growth_result(result).is_valid


def test_repeated_growth_never_exceeds_asymptote() -> None:
    """Repeated steps approach, but never exceed, the parameters' asymptotes."""
    current = _distribution()
    for _ in range(30):
        result = grow(_request(current=current), GrowthConfig())
        assert result.next is not None
        current = result.next
    assert current.height_m <= 4.0 + 1e-9
    assert current.cover_pct <= 90 + 1e-9


@pytest.mark.parametrize("group", ["shrub", "deciduous_sprout", "conifer", "grass_herb"])
def test_each_functional_group_has_parameters(group: FunctionalGroup) -> None:
    """Every modelled group has a distinct curve and uncertainty."""
    result = grow(
        _request(
            group=group,
            current=_distribution(height=0.1, cover=5, density=None),
        )
    )
    assert result.status == "grown"
    assert result.next is not None
    assert result.next.height_m > 0.1
    assert result.next.cover_pct > 5
    assert validate_growth_result(result).is_valid


def test_site_climate_and_competition_modify_growth() -> None:
    """Higher site/climate increases growth; competition reduces it."""
    base = grow(_request(years=3), GrowthConfig())
    high_site = grow(
        _request(
            years=3,
            environment=GrowthEnvironment(site_index_m=30, climate_factor=1.3),
        )
    )
    competition = grow(
        _request(
            years=3,
            environment=GrowthEnvironment(competition=1.0),
        )
    )
    assert base.next is not None
    assert high_site.next is not None
    assert competition.next is not None
    assert high_site.next.height_m > base.next.height_m
    assert competition.next.height_m < base.next.height_m
    assert competition.next.cover_pct < base.next.cover_pct


def test_site_index_none_and_climate_clamping() -> None:
    """An unknown site index is neutral and an extreme climate is bounded by config."""
    result = grow(
        _request(
            years=1,
            environment=GrowthEnvironment(site_index_m=None, climate_factor=10),
        ),
        GrowthConfig(climate_factor_max=20),
    )
    assert result.status == "grown"
    assert result.next is not None


def test_out_of_domain_environment_is_blocked() -> None:
    """An explicit or computed out-of-domain environment has no next state."""
    explicit = grow(
        _request(
            environment=GrowthEnvironment(
                in_domain=False,
                domain_reason="outside the calibration region",
            )
        )
    )
    assert explicit.status == "out_of_domain"
    assert explicit.next is None
    assert explicit.reason == "outside the calibration region"
    assert validate_growth_result(explicit).is_valid
    site = grow(
        _request(environment=GrowthEnvironment(site_index_m=50)),
        GrowthConfig(site_index_max_m=40),
    )
    assert site.status == "out_of_domain"
    assert "site index" in site.reason
    climate = grow(
        _request(environment=GrowthEnvironment(climate_factor=3)),
        GrowthConfig(climate_factor_max=1.5),
    )
    assert climate.status == "out_of_domain"
    assert "climate" in climate.reason


def test_unknown_group_is_blocked() -> None:
    """An unknown group does not grow."""
    result = grow(_request(group="unknown"), GrowthConfig())
    assert result.status == "unknown"
    assert result.next is None
    assert result.reason
    assert validate_growth_result(result).is_valid


def test_step_length_is_bounded() -> None:
    """A step longer than the config maximum fails."""
    with pytest.raises(GrowthError, match="maximum"):
        grow(_request(years=30), GrowthConfig(max_years=20))


def test_to_state_contract_and_blocked_conversion() -> None:
    """A grown distribution converts to a valid state; a blocked one does not."""
    result = grow(_request())
    state = result.to_vegetation_state(2027)
    assert state.state_year == 2027
    assert state.functional_group == "shrub"
    assert validate_state_contract(_contract_for(state)).is_valid
    blocked = grow(_request(group="unknown"))
    with pytest.raises(GrowthError, match="no grown"):
        blocked.to_vegetation_state(2027)


def _contract_for(state: VegetationState) -> StateContract:
    return StateContract(states=[state])


def test_config_validation() -> None:
    """Site, climate, and domain ranges must be ordered."""
    with pytest.raises(ValidationError, match="site factor"):
        GrowthConfig(site_factor_min=2, site_factor_max=1)
    with pytest.raises(ValidationError, match="site-index"):
        GrowthConfig(site_index_min_m=40, site_index_max_m=20)
    with pytest.raises(ValidationError, match="climate factor"):
        GrowthConfig(climate_factor_min=2, climate_factor_max=1)
    with pytest.raises(ValidationError, match="out-of-domain"):
        GrowthEnvironment(in_domain=False)


def test_request_and_parameter_validation() -> None:
    """Invalid years and group values are rejected."""
    with pytest.raises(ValidationError):
        _request(years=0)
    with pytest.raises(ValidationError):
        _request(group=cast("FunctionalGroup", "other"))
    assert {item.group for item in GROWTH_PARAMETERS} == {
        "shrub",
        "deciduous_sprout",
        "conifer",
        "grass_herb",
        "unknown",
    }


def test_growth_validator_names_bad_results() -> None:
    """The growth validator catches status, bounds, probabilities, and age errors."""
    result = grow(_request())
    bad_status = result.model_copy(update={"status": "maybe"})
    assert any(
        error.startswith("GROWTH-STATUS") for error in validate_growth_result(bad_status).errors
    )
    no_next = result.model_copy(update={"next": None})
    assert any(error.startswith("GROWTH-NEXT") for error in validate_growth_result(no_next).errors)
    assert result.next is not None
    no_height = result.model_copy(
        update={"next": result.next.model_copy(update={"height_m": result.previous.height_m - 1})}
    )
    assert any(
        error.startswith("GROWTH-MONOTONE") for error in validate_growth_result(no_height).errors
    )
    over_bound = result.model_copy(
        update={"next": result.next.model_copy(update={"height_m": 99, "cover_pct": 99})}
    )
    assert any(
        error.startswith("GROWTH-BOUND") for error in validate_growth_result(over_bound).errors
    )
    probability = result.model_copy(
        update={"next": result.next.model_copy(update={"class_probabilities": {"unknown": 1.0}})}
    )
    assert any(
        error.startswith("GROWTH-PROBABILITY")
        for error in validate_growth_result(probability).errors
    )
    age = result.model_copy(
        update={"next": result.next.model_copy(update={"age_years": result.previous.age_years})}
    )
    assert any(error.startswith("GROWTH-AGE") for error in validate_growth_result(age).errors)
    blocked = grow(_request(group="unknown"))
    blocked_next = blocked.model_copy(
        update={
            "next": result.next,
            "next_state_class": result.next_state_class,
        }
    )
    assert any(
        error.startswith("GROWTH-NEXT") for error in validate_growth_result(blocked_next).errors
    )


def test_growth_to_partial_and_asymptote_edges() -> None:
    """Unknown next classes become partial and an at-asymptote state does not shrink."""
    partial = grow(_request(current=_distribution(height=12, cover=5)))
    assert partial.next is not None
    assert partial.next_state_class == "partial"
    at_asymptote = grow(_request(current=_distribution(height=4, cover=90)))
    assert at_asymptote.status == "grown"
    assert at_asymptote.next is not None
    assert at_asymptote.next.height_m == 4
    assert at_asymptote.next.cover_pct == 90


def test_growth_validator_reason_and_cover_errors() -> None:
    """A blocked result needs a reason and grown cover cannot decrease."""
    blocked = grow(_request(group="unknown"))
    no_reason = blocked.model_copy(update={"reason": ""})
    assert any(
        error.startswith("GROWTH-REASON") for error in validate_growth_result(no_reason).errors
    )
    grown = grow(_request())
    assert grown.next is not None
    cover_down = grown.model_copy(
        update={"next": grown.next.model_copy(update={"cover_pct": grown.previous.cover_pct - 1})}
    )
    assert any(
        error.startswith("GROWTH-MONOTONE") for error in validate_growth_result(cover_down).errors
    )


def test_parameters_lookup_rejects_unknown_group() -> None:
    """The private parameter lookup rejects an unregistered group."""
    from brushline.vegetation.growth import _parameters

    with pytest.raises(GrowthError, match="no growth parameters"):
        _parameters("other")  # type: ignore[arg-type]  # Intentional invalid group.


def test_classify_state_public_helper() -> None:
    """The shared class helper covers incomplete and unknown inputs."""
    assert classify_state(None, 20, "shrub") == "unknown"
    assert classify_state(2, None, "shrub") == "unknown"
    assert classify_state(2, 30, "unknown") == "unknown"
    assert classify_state(2, 30, "shrub") == "shrub"
