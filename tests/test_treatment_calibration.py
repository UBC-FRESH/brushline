"""Tests for P4.4 treatment efficacy and resprouting calibration."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from brushline.vegetation.calibration import (
    CalibratedTreatmentParameters,
    CalibrationCheck,
    TreatmentCalibrationConfig,
    TreatmentCalibrationError,
    TreatmentCalibrationReport,
    TreatmentObservation,
    calibrate_treatment,
    validate_treatment_calibration,
)
from brushline.vegetation.treatment import TREATMENT_PARAMETERS
from pydantic import ValidationError

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "notes" / "reference" / "treatment-calibration.v1.json"
NOW = datetime(2026, 11, 14, tzinfo=UTC)


def _observations() -> list[TreatmentObservation]:
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    return [TreatmentObservation.model_validate(item) for item in payload["observations"]]


def _report(
    config: TreatmentCalibrationConfig | None = None,
) -> TreatmentCalibrationReport:
    return calibrate_treatment(
        _observations(),
        config,
        created_utc=NOW,
    )


def _base(method: str) -> object:
    return next(item for item in TREATMENT_PARAMETERS if item.method == method)


def test_committed_calibration_passes() -> None:
    """The committed evidence produces valid calibrated cells and holdout checks."""
    report = _report()
    result = validate_treatment_calibration(report)
    assert result.is_valid
    assert result.counts["cells"] == 12
    assert result.counts["exact"] >= 1
    assert result.counts["pooled"] >= 1
    assert result.counts["holdout"] == 2
    assert result.counts["holdout_failed"] == 0
    assert report.open_questions


def test_exact_and_pooled_evidence_levels() -> None:
    """Exact, method-group, method, and prior evidence levels are distinguished."""
    report = _report()
    by_key = {(item.method, item.season, item.functional_group): item for item in report.parameters}
    assert by_key[("mowing", "spring", "shrub")].evidence_level == "exact"
    assert by_key[("mowing", "spring", "shrub")].pooled is False
    assert by_key[("mowing", "summer", "shrub")].evidence_level == "method_group"
    assert by_key[("manual", "spring", "conifer")].evidence_level == "method"
    assert by_key[("grazing", "summer", "grass_herb")].evidence_level == "prior"
    assert by_key[("grazing", "summer", "grass_herb")].pooled is True


def test_calibration_shrinks_toward_prior_and_has_intervals() -> None:
    """The posterior is bounded by the data and prior and records intervals."""
    report = _report()
    exact = next(
        item
        for item in report.parameters
        if item.method == "mowing" and item.season == "spring" and item.functional_group == "shrub"
    )
    assert 0.6 < exact.efficacy < 0.7
    assert exact.cover_efficacy == pytest.approx(0.634, abs=0.01)
    assert 0.7 < exact.top_kill <= 1.0
    assert exact.efficacy_interval[0] <= exact.efficacy <= exact.efficacy_interval[1]
    assert exact.resprout_interval[0] <= exact.resprout_factor <= exact.resprout_interval[1]
    assert exact.effective_sample_size == 7


def test_season_and_method_differences_are_visible() -> None:
    """Calibrated season and method cells are not collapsed into one value."""
    report = _report()
    spring = next(
        item for item in report.parameters if item.method == "mowing" and item.season == "spring"
    )
    fall = next(
        item for item in report.parameters if item.method == "mowing" and item.season == "fall"
    )
    chemical = next(
        item for item in report.parameters if item.method == "chemical" and item.season == "spring"
    )
    assert spring.efficacy != fall.efficacy
    assert chemical.efficacy > spring.efficacy


def test_holdout_tolerance_failure_invalidates_report() -> None:
    """A zero holdout tolerance records failures and invalidates the report."""
    report = _report(TreatmentCalibrationConfig(holdout_tolerance=0.0))
    assert report.holdout_checks
    assert all(not check.passed for check in report.holdout_checks)
    result = validate_treatment_calibration(report)
    assert not result.is_valid
    assert any(error.startswith("CALIBRATION-HOLDOUT") for error in result.errors)


def test_calibration_applies_to_treatment_parameters() -> None:
    """Calibrated values replace the treatment parameters without changing cost."""
    report = _report()
    calibrated = next(
        item for item in report.parameters if item.method == "mowing" and item.season == "spring"
    )
    base = _base("mowing")
    assert base is not None
    parameters = calibrated.to_treatment_parameters(base)  # type: ignore[arg-type]
    assert parameters.efficacy == calibrated.efficacy
    assert parameters.top_kill == calibrated.top_kill
    assert parameters.resprout_factor == calibrated.resprout_factor
    assert parameters.regrowth_delay_years == calibrated.regrowth_delay_years
    assert parameters.cost_per_ha == base.cost_per_ha  # type: ignore[attr-defined]


def test_observation_derived_values_and_validation() -> None:
    """Before/after observations compute efficacy and reject impossible transitions."""
    observation = _observations()[0]
    assert observation.height_efficacy > 0
    assert observation.cover_efficacy > 0
    assert observation.resprout_factor is not None
    with pytest.raises(ValidationError, match="after_height_m"):
        TreatmentObservation.model_validate(
            {
                **observation.model_dump(),
                "after_height_m": 3,
            }
        )
    with pytest.raises(ValidationError, match="after_cover_pct"):
        TreatmentObservation.model_validate(
            {
                **observation.model_dump(),
                "after_cover_pct": 99,
            }
        )
    with pytest.raises(ValidationError, match="density needs"):
        TreatmentObservation.model_validate(
            {
                **observation.model_dump(),
                "after_density_per_ha": None,
            }
        )
    no_density = observation.model_copy(
        update={"before_density_per_ha": None, "after_density_per_ha": None}
    )
    assert no_density.resprout_factor is None


def test_empty_and_duplicate_evidence_fail() -> None:
    """Empty evidence and duplicate observation ids fail."""
    with pytest.raises(TreatmentCalibrationError, match="at least one"):
        calibrate_treatment([])
    observation = _observations()[0]
    with pytest.raises(TreatmentCalibrationError, match="unique"):
        calibrate_treatment([observation, observation])


def test_configuration_validation() -> None:
    """Prior strength, sample count, and holdout interval are validated."""
    with pytest.raises(ValidationError):
        TreatmentCalibrationConfig(prior_strength=0)
    with pytest.raises(ValidationError):
        TreatmentCalibrationConfig(min_observations=0)
    with pytest.raises(ValidationError):
        TreatmentCalibrationConfig(holdout_every=1)
    with pytest.raises(ValidationError):
        TreatmentCalibrationConfig(holdout_tolerance=2)


def test_calibration_validator_names_bad_cells() -> None:
    """The validator catches duplicate cells, bad evidence, sources, samples, and time."""
    report = _report()
    cell = report.parameters[0]
    duplicate = report.model_copy(update={"parameters": [cell, cell]})
    assert any(
        error.startswith("CALIBRATION-ID")
        for error in validate_treatment_calibration(duplicate).errors
    )
    bad_level = report.model_copy(
        update={"parameters": [cell.model_copy(update={"evidence_level": "other"})]}
    )
    assert any(
        error.startswith("CALIBRATION-EVIDENCE")
        for error in validate_treatment_calibration(bad_level).errors
    )
    no_source = report.model_copy(
        update={"parameters": [cell.model_copy(update={"source_ids": []})]}
    )
    assert any(
        error.startswith("CALIBRATION-SOURCE")
        for error in validate_treatment_calibration(no_source).errors
    )
    no_samples = report.model_copy(
        update={"parameters": [cell.model_copy(update={"sample_size": 0})]}
    )
    assert any(
        error.startswith("CALIBRATION-EVIDENCE")
        for error in validate_treatment_calibration(no_samples).errors
    )
    no_weight = report.model_copy(
        update={
            "parameters": [cell.model_copy(update={"sample_size": 0, "effective_sample_size": 1})]
        }
    )
    assert any(
        error.startswith("CALIBRATION-SAMPLE")
        for error in validate_treatment_calibration(no_weight).errors
    )
    naive = report.model_copy(update={"created_utc": datetime(2026, 11, 14)})
    assert any(
        error.startswith("CALIBRATION-TIME")
        for error in validate_treatment_calibration(naive).errors
    )
    no_checks = report.model_copy(update={"holdout_checks": []})
    assert any(
        warning.startswith("CALIBRATION-EMPTY")
        for warning in validate_treatment_calibration(no_checks).warnings
    )


def test_calibration_models_reject_bad_intervals() -> None:
    """A calibrated cell enforces ordered intervals and delay ranges."""
    report = _report()
    cell = report.parameters[0].model_dump()
    cell["efficacy_interval"] = (0.8, 0.2)
    with pytest.raises(ValidationError, match="efficacy interval"):
        CalibratedTreatmentParameters.model_validate(cell)
    cell = report.parameters[0].model_dump()
    cell["delay_min_years"] = 3
    cell["delay_max_years"] = 1
    with pytest.raises(ValidationError, match="delay range"):
        CalibratedTreatmentParameters.model_validate(cell)


def test_calibration_check_model() -> None:
    """A held-out check requires non-negative error and a bounded tolerance."""
    check = CalibrationCheck(
        observation_id="o1",
        method="mowing",
        season="spring",
        functional_group="shrub",
        observed_efficacy=0.5,
        predicted_efficacy=0.4,
        absolute_error=0.1,
        tolerance=0.2,
        passed=True,
    )
    assert check.passed
    with pytest.raises(ValidationError):
        CalibrationCheck(
            observation_id="o1",
            method="mowing",
            season="spring",
            functional_group="shrub",
            observed_efficacy=0.5,
            predicted_efficacy=0.4,
            absolute_error=-0.1,
            tolerance=0.2,
            passed=True,
        )


def test_report_requires_a_cell() -> None:
    """A calibration report cannot have an empty parameter list."""
    report = _report()
    with pytest.raises(ValidationError):
        TreatmentCalibrationReport(
            created_utc=NOW,
            config=report.config,
            parameters=[],
        )


def test_single_observation_and_no_holdout() -> None:
    """A single observation calibrates with a warning when no held-out check exists."""
    report = calibrate_treatment(
        [_observations()[0].model_copy(update={"sample_size": 1})],
        TreatmentCalibrationConfig(min_observations=1),
        created_utc=NOW,
    )
    assert report.holdout_checks == []
    assert any("No leave-one-out" in question for question in report.open_questions)
    result = validate_treatment_calibration(report)
    assert result.is_valid
    assert any(warning.startswith("CALIBRATION-EMPTY") for warning in result.warnings)


def test_cell_and_calibration_model_validation() -> None:
    """Bad evidence levels, intervals, and prior flags are rejected."""
    report = _report()
    cell = report.parameters[0].model_dump()
    cell["evidence_level"] = "other"
    with pytest.raises(ValidationError, match="evidence level"):
        CalibratedTreatmentParameters.model_validate(cell)
    cell = report.parameters[0].model_dump()
    cell["resprout_interval"] = (0.8, 0.2)
    with pytest.raises(ValidationError, match="resprout interval"):
        CalibratedTreatmentParameters.model_validate(cell)
    bad_prior = report.parameters[0].model_copy(update={"evidence_level": "prior", "pooled": False})
    bad_report = report.model_copy(update={"parameters": [bad_prior]})
    assert any(
        error.startswith("CALIBRATION-EVIDENCE")
        for error in validate_treatment_calibration(bad_report).errors
    )


def test_base_parameters_reject_unknown_method() -> None:
    """The private parameter lookup rejects an unregistered method."""
    from brushline.vegetation.calibration import _base_parameters

    with pytest.raises(TreatmentCalibrationError, match="no treatment parameters"):
        _base_parameters("unknown")  # type: ignore[arg-type]  # Intentional invalid method.
