"""Tests for the P4.7 low-vegetation model card and domain contract."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from brushline.vegetation.model_card import (
    ApplicabilityDomain,
    LowVegetationModelCard,
    ModelCardDomainError,
    ModelCardEvidence,
    ModelCardRequest,
    PredictorSpec,
    check_domain,
    require_in_domain,
    validate_model_card,
)
from pydantic import ValidationError

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "notes" / "reference" / "low-vegetation-model-card.v1.json"
NOW = datetime(2026, 11, 14, tzinfo=UTC)


def _card() -> LowVegetationModelCard:
    return LowVegetationModelCard.model_validate_json(FIXTURE.read_text(encoding="utf-8"))


def _request(**updates: object) -> ModelCardRequest:
    values: dict[str, object] = {
        "functional_group": "shrub",
        "treatment_method": "mowing",
        "site_index_m": 20,
        "climate_factor": 1.0,
        "lag_years": 1,
        "coverage_pct": 100,
    }
    values.update(updates)
    return ModelCardRequest.model_validate(values)


def test_committed_model_card_is_valid() -> None:
    """The committed card names predictors, evidence, metrics, candidates, and caveats."""
    card = _card()
    result = validate_model_card(card)
    assert result.is_valid
    assert result.counts["predictors"] == 7
    assert result.counts["groups"] == 4
    assert result.counts["metrics"] == 8
    assert result.counts["candidates"] == 2
    assert card.licence == "Apache-2.0"
    assert card.citation
    assert card.decision_boundary
    assert card.uncertainty.interval_level == 0.95
    assert card.training.n_records == 13
    assert card.validation.n_records == 3


def test_card_json_round_trip() -> None:
    """The model card round-trips through JSON."""
    card = _card()
    loaded = LowVegetationModelCard.model_validate_json(card.model_dump_json())
    assert loaded == card


def test_in_domain_request_passes() -> None:
    """A request inside every domain check passes."""
    card = _card()
    check = check_domain(card, _request())
    assert check.in_domain is True
    assert check.reasons == []
    assert check.model_id == card.model_id
    assert require_in_domain(card, _request()).in_domain is True


def test_out_of_domain_requests_are_named() -> None:
    """Each domain boundary has a named reason and require_in_domain raises."""
    card = _card()
    cases: list[tuple[ModelCardRequest, str]] = [
        (_request(functional_group="unknown"), "functional group"),
        (_request(site_index_m=50), "site index"),
        (_request(climate_factor=2), "climate factor"),
        (_request(lag_years=6), "lag"),
        (_request(coverage_pct=20), "coverage"),
    ]
    for request, reason in cases:
        check = check_domain(card, request)
        assert check.in_domain is False
        assert any(reason in item for item in check.reasons)
        with pytest.raises(ModelCardDomainError):
            require_in_domain(card, request)


def test_treatment_method_domain() -> None:
    """A treatment method outside the card domain is rejected."""
    card = _card()
    domain = card.domain.model_copy(update={"treatment_methods": ["mowing"]})
    restricted = card.model_copy(update={"domain": domain})
    check = check_domain(restricted, _request(treatment_method="manual"))
    assert check.in_domain is False
    assert any("treatment method" in reason for reason in check.reasons)


def test_predictor_and_domain_model_validation() -> None:
    """Predictor and domain ranges must be ordered."""
    with pytest.raises(ValidationError, match="predictor minimum"):
        PredictorSpec(name="x", unit="m", minimum=2, maximum=1)
    with pytest.raises(ValidationError, match="site-index"):
        ApplicabilityDomain(
            functional_groups=["shrub"],
            treatment_methods=["mowing"],
            site_index_min_m=40,
            site_index_max_m=20,
            climate_factor_min=0.5,
            climate_factor_max=1.5,
            max_lag_years=5,
            min_coverage_pct=50,
        )
    with pytest.raises(ValidationError, match="climate-factor"):
        ApplicabilityDomain(
            functional_groups=["shrub"],
            treatment_methods=["mowing"],
            site_index_min_m=0,
            site_index_max_m=40,
            climate_factor_min=1.5,
            climate_factor_max=1.0,
            max_lag_years=5,
            min_coverage_pct=50,
        )


def test_request_and_evidence_validation() -> None:
    """Request and evidence ranges are enforced."""
    with pytest.raises(ValidationError):
        _request(site_index_m=-1)
    with pytest.raises(ValidationError):
        _request(coverage_pct=101)
    with pytest.raises(ValidationError):
        _request(functional_group="other")
    with pytest.raises(ValidationError):
        ModelCardEvidence(
            dataset_id="d",
            source="s",
            source_version="1",
            licence="x",
            n_records=0,
            spatial_blocks=["a"],
            period="2026",
            provenance="p",
        )


def test_validator_names_bad_card_fields() -> None:
    """The validator catches status, evidence, metric, candidate, and uncertainty errors."""
    card = _card()
    cases: list[tuple[dict[str, object], str]] = [
        ({"status": "maybe"}, "MODEL-CARD-STATUS"),
        (
            {"predictors": [card.predictors[0].model_copy(update={"minimum": 101})]},
            "MODEL-CARD-PREDICTOR",
        ),
        ({"functional_groups": ["alien"]}, "MODEL-CARD-GROUP"),
        (
            {"metrics": [card.metrics[0].model_copy(update={"group": "alien"})]},
            "MODEL-CARD-METRIC",
        ),
        ({"licence": ""}, "MODEL-CARD-LICENCE"),
        ({"decision_boundary": ""}, "MODEL-CARD-BOUNDARY"),
        (
            {"domain": card.domain.model_copy(update={"functional_groups": ["alien"]})},
            "MODEL-CARD-DOMAIN",
        ),
        (
            {"domain": card.domain.model_copy(update={"treatment_methods": ["unknown"]})},
            "MODEL-CARD-DOMAIN",
        ),
        (
            {"training": card.training.model_copy(update={"n_records": 0})},
            "MODEL-CARD-EVIDENCE",
        ),
        (
            {"metrics": [card.metrics[0].model_copy(update={"variable": "unknown"})]},
            "MODEL-CARD-METRIC",
        ),
        (
            {"metrics": [card.metrics[0].model_copy(update={"n": 0})]},
            "MODEL-CARD-METRIC",
        ),
        (
            {"candidates": [card.candidates[0].model_copy(update={"n": 0})]},
            "MODEL-CARD-CANDIDATE",
        ),
        (
            {"uncertainty": card.uncertainty.model_copy(update={"propagation": ""})},
            "MODEL-CARD-UNCERTAINTY",
        ),
    ]
    for updates, prefix in cases:
        bad = card.model_copy(update=updates)
        assert any(error.startswith(prefix) for error in validate_model_card(bad).errors), prefix
    naive = card.model_copy(update={"created_utc": datetime(2026, 11, 14)})
    assert any(error.startswith("MODEL-CARD-TIME") for error in validate_model_card(naive).errors)
    no_caveats = card.model_copy(update={"caveats": []})
    assert any(
        error.startswith("MODEL-CARD-CAVEAT") for error in validate_model_card(no_caveats).errors
    )
    no_candidates = card.model_copy(update={"candidates": []})
    assert any(
        warning.startswith("MODEL-CARD-CANDIDATE")
        for warning in validate_model_card(no_candidates).warnings
    )
    no_interval = card.model_copy(
        update={"metrics": [card.metrics[0].model_copy(update={"interval_coverage": None})]}
    )
    assert any(
        warning.startswith("MODEL-CARD-INTERVAL")
        for warning in validate_model_card(no_interval).warnings
    )


def test_duplicate_card_keys_are_rejected() -> None:
    """Duplicate predictors, groups, metrics, and candidates are named."""
    card = _card()
    duplicate_predictor = card.model_copy(
        update={"predictors": [card.predictors[0], card.predictors[0]]}
    )
    assert any(
        error.startswith("MODEL-CARD-ID")
        for error in validate_model_card(duplicate_predictor).errors
    )
    duplicate_group = card.model_copy(
        update={"functional_groups": [*card.functional_groups, card.functional_groups[0]]}
    )
    assert any(
        error.startswith("MODEL-CARD-ID") for error in validate_model_card(duplicate_group).errors
    )
    duplicate_metric = card.model_copy(update={"metrics": [card.metrics[0], card.metrics[0]]})
    assert any(
        error.startswith("MODEL-CARD-ID") for error in validate_model_card(duplicate_metric).errors
    )
    duplicate_candidate = card.model_copy(
        update={"candidates": [card.candidates[0], card.candidates[0]]}
    )
    assert any(
        error.startswith("MODEL-CARD-ID")
        for error in validate_model_card(duplicate_candidate).errors
    )


def test_uncertainty_contract_requires_valid_interval() -> None:
    """The interval level must be between 0.5 and 1."""
    card = _card()
    with pytest.raises(ValidationError):
        card.uncertainty.__class__(
            interval_level=0.4,
            height_interval="h",
            cover_interval="c",
            density_interval="d",
            propagation="p",
            caveat="x",
        )
