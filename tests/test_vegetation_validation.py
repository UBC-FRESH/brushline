"""Tests for P4.6 held-out vegetation validation and candidate benchmarking."""

from __future__ import annotations

import json
import math
from datetime import UTC, date, datetime
from pathlib import Path
from typing import cast

import pytest
from brushline.vegetation.validation import (
    CandidatePrediction,
    CandidateSummary,
    LagSummary,
    MetricSummary,
    ValidationConfig,
    ValidationDataset,
    ValidationRecord,
    VegetationValidationError,
    VegetationValidationReport,
    validate_vegetation,
    validate_vegetation_validation,
)
from pydantic import ValidationError

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "notes" / "reference" / "vegetation-validation.v1.json"
NOW = datetime(2026, 11, 14, tzinfo=UTC)


def _payload() -> dict[str, object]:
    return cast(
        "dict[str, object]",
        json.loads(FIXTURE.read_text(encoding="utf-8")),
    )


def _dataset() -> ValidationDataset:
    payload = _payload()
    return ValidationDataset.model_validate(
        {
            "schema_version": payload["schema_version"],
            "records": payload["records"],
        }
    )


def _config() -> ValidationConfig:
    return ValidationConfig.model_validate(_payload()["config"])


def _report(
    dataset: ValidationDataset | None = None,
    config: ValidationConfig | None = None,
) -> VegetationValidationReport:
    return validate_vegetation(
        dataset or _dataset(),
        config or _config(),
        created_utc=NOW,
    )


def test_committed_validation_passes() -> None:
    """The committed fixture produces group metrics, lags, and candidates."""
    report = _report()
    result = validate_vegetation_validation(report)
    assert result.is_valid
    assert report.counts["records"] == 9
    assert report.counts["holdout_records"] == 6
    assert report.counts["eligible_records"] == 3
    assert report.excluded == {"coverage": 1, "out_of_domain": 1, "time_lag": 1}
    assert {metric.group for metric in report.metrics} == {
        "conifer",
        "grass_herb",
        "shrub",
    }
    assert all(metric.interval_coverage == 1.0 for metric in report.metrics)
    assert {lag.lag_years for lag in report.lags} == {0, 1, 2}
    assert {candidate.name for candidate in report.candidates} == {
        "medfate",
        "fvs_ffe",
    }
    assert report.open_questions


def test_validation_dataset_round_trip() -> None:
    """The validation dataset and record lag are deterministic."""
    dataset = _dataset()
    record = dataset.records[0]
    assert record.lag_years == 0
    assert ValidationDataset.model_validate_json(dataset.model_dump_json()) == dataset
    out = next(item for item in dataset.records if item.observation_id == "v08")
    assert out.lag_years == 8


def test_missing_holdout_records_and_unknown_blocks() -> None:
    """Unknown blocks and a holdout with no records are errors."""
    dataset = _dataset()
    unknown = validate_vegetation(
        dataset,
        _config().model_copy(update={"holdout_blocks": ["missing"]}),
        created_utc=NOW,
    )
    assert any(error.startswith("VALIDATION-BLOCK") for error in unknown.errors)
    assert any(error.startswith("VALIDATION-HOLDOUT") for error in unknown.errors)
    subset = dataset.model_copy(
        update={"records": [record for record in dataset.records if record.spatial_block == "a"]}
    )
    no_holdout = validate_vegetation(
        subset,
        _config(),
        created_utc=NOW,
    )
    assert any(error.startswith("VALIDATION-HOLDOUT") for error in no_holdout.errors)


def test_all_records_excluded() -> None:
    """A holdout with no eligible record is a named error."""
    dataset = _dataset()
    low_coverage = dataset.model_copy(
        update={"records": [record for record in dataset.records if record.observation_id == "v06"]}
    )
    report = validate_vegetation(low_coverage, _config(), created_utc=NOW)
    assert any(error.startswith("VALIDATION-EMPTY") for error in report.errors)
    assert report.excluded["coverage"] == 1


def test_include_out_of_domain_and_lag_window() -> None:
    """Out-of-domain records can be included; the lag window excludes old predictions."""
    report = validate_vegetation(
        _dataset(),
        _config().model_copy(update={"include_out_of_domain": True}),
        created_utc=NOW,
    )
    assert report.excluded["out_of_domain"] == 0
    assert report.counts["eligible_records"] == 4
    lag = validate_vegetation(
        _dataset(),
        _config().model_copy(update={"max_lag_years": 1}),
        created_utc=NOW,
    )
    assert lag.excluded["time_lag"] == 2
    assert lag.counts["eligible_records"] == 2


def test_candidate_warning_and_disagreement_question() -> None:
    """A missing candidate is a warning; a tight tolerance raises disagreement questions."""
    dataset = _dataset()
    no_candidates = dataset.model_copy(
        update={
            "records": [record.model_copy(update={"candidates": []}) for record in dataset.records]
        }
    )
    report = validate_vegetation(no_candidates, _config(), created_utc=NOW)
    assert any(warning.startswith("VALIDATION-CANDIDATE") for warning in report.warnings)
    tight = validate_vegetation(
        dataset,
        _config().model_copy(update={"candidate_disagreement_tolerance": 0.0}),
        created_utc=NOW,
    )
    assert any("differs from Brushline" in question for question in tight.open_questions)
    tolerant = validate_vegetation(
        dataset,
        _config().model_copy(update={"candidate_disagreement_tolerance": 10.0}),
        created_utc=NOW,
    )
    assert not any("differs from Brushline" in question for question in tolerant.open_questions)


def test_candidate_metrics_differences() -> None:
    """Candidate summaries record RMSE differences against Brushline."""
    report = _report()
    height = _brushline_overall("height")
    cover = _brushline_overall("cover")
    for candidate in report.candidates:
        assert candidate.n == 3
        assert candidate.height_rmse_difference == pytest.approx(candidate.height_rmse - height)
        assert candidate.cover_rmse_difference == pytest.approx(candidate.cover_rmse - cover)


def _brushline_overall(variable: str) -> float:
    dataset = _dataset()
    config = _config()
    records = [
        record
        for record in dataset.records
        if record.spatial_block in config.holdout_blocks
        and record.coverage_pct >= config.min_coverage_pct
        and (record.in_domain or config.include_out_of_domain)
        and abs(record.lag_years) <= config.max_lag_years
    ]
    if variable == "height":
        errors = [r.predicted_height_m - r.observed_height_m for r in records]
    else:
        errors = [r.predicted_cover_pct - r.observed_cover_pct for r in records]
    return math.sqrt(sum(error * error for error in errors) / len(records))


def test_record_validation_errors() -> None:
    """Out-of-domain, density, candidate, and range rules are validated."""
    record = _dataset().records[0]
    with pytest.raises(ValidationError, match="out-of-domain"):
        ValidationRecord.model_validate(
            {**record.model_dump(), "in_domain": False, "domain_reason": ""}
        )
    with pytest.raises(ValidationError, match="density needs"):
        ValidationRecord.model_validate({**record.model_dump(), "predicted_density_per_ha": None})
    with pytest.raises(ValidationError, match="candidate names"):
        ValidationRecord.model_validate(
            {
                **record.model_dump(),
                "candidates": [
                    CandidatePrediction(name="same", height_m=1, cover_pct=1),
                    CandidatePrediction(name="same", height_m=2, cover_pct=2),
                ],
            }
        )
    with pytest.raises(ValidationError):
        ValidationRecord.model_validate({**record.model_dump(), "observed_height_m": -1})


def test_config_and_dataset_validation() -> None:
    """Empty holdout, bad coverage, empty records, and candidate ranges are rejected."""
    with pytest.raises(ValidationError):
        ValidationConfig(holdout_blocks=[])
    with pytest.raises(ValidationError):
        ValidationConfig(holdout_blocks=["a"], min_coverage_pct=101)
    with pytest.raises(ValidationError):
        ValidationDataset(records=[])
    with pytest.raises(ValidationError):
        CandidatePrediction(name="x", height_m=1, cover_pct=101)


def test_duplicate_observation_ids_fail() -> None:
    """Duplicate record ids fail before metrics are computed."""
    dataset = _dataset()
    duplicate = dataset.model_copy(update={"records": [dataset.records[0], dataset.records[0]]})
    with pytest.raises(VegetationValidationError, match="unique"):
        validate_vegetation(duplicate, _config())


def test_report_validator_names_bad_metrics_and_candidates() -> None:
    """The validator catches duplicates, unknown variables, intervals, lags, and time."""
    report = _report()
    metric = report.metrics[0]
    duplicate = report.model_copy(update={"metrics": [metric, metric]})
    assert any(
        error.startswith("VALIDATION-ID")
        for error in validate_vegetation_validation(duplicate).errors
    )
    unknown = report.model_copy(
        update={"metrics": [metric.model_copy(update={"variable": "unknown"})]}
    )
    assert any(
        error.startswith("VALIDATION-METRIC")
        for error in validate_vegetation_validation(unknown).errors
    )
    interval = report.model_copy(
        update={"metrics": [metric.model_copy(update={"interval_coverage": 2.0})]}
    )
    assert any(
        error.startswith("VALIDATION-INTERVAL")
        for error in validate_vegetation_validation(interval).errors
    )
    zero = report.model_copy(update={"metrics": [metric.model_copy(update={"n": 0})]})
    assert any(
        warning.startswith("VALIDATION-EMPTY")
        for warning in validate_vegetation_validation(zero).warnings
    )
    lag = report.model_copy(update={"lags": [report.lags[0].model_copy(update={"lag_years": -1})]})
    assert any(
        error.startswith("VALIDATION-LAG") for error in validate_vegetation_validation(lag).errors
    )
    no_candidate_records = report.model_copy(
        update={"candidates": [report.candidates[0].model_copy(update={"n": 0})]}
    )
    assert any(
        warning.startswith("VALIDATION-EMPTY")
        for warning in validate_vegetation_validation(no_candidate_records).warnings
    )
    no_candidates = report.model_copy(update={"candidates": []})
    assert any(
        warning.startswith("VALIDATION-CANDIDATE")
        for warning in validate_vegetation_validation(no_candidates).warnings
    )
    naive = report.model_copy(update={"created_utc": datetime(2026, 11, 14)})
    assert any(
        error.startswith("VALIDATION-TIME")
        for error in validate_vegetation_validation(naive).errors
    )
    duplicate_candidate = report.model_copy(
        update={"candidates": [report.candidates[0], report.candidates[0]]}
    )
    assert any(
        error.startswith("VALIDATION-ID")
        for error in validate_vegetation_validation(duplicate_candidate).errors
    )


def test_report_model_helpers() -> None:
    """The report serializes and exposes its validity."""
    report = _report()
    assert report.is_valid
    payload = report.to_dict()
    assert payload["is_valid"] is True
    assert len(cast("list[object]", payload["metrics"])) == len(report.metrics)
    assert cast("dict[str, object]", payload["counts"])["records"] == 9
    failed = report.model_copy(update={"errors": ["VALIDATION-TEST: failure"]})
    assert not failed.is_valid
    assert not validate_vegetation_validation(failed).is_valid


def test_metric_and_lag_models() -> None:
    """Metric and lag models enforce the documented ranges."""
    with pytest.raises(ValidationError):
        MetricSummary(
            group="shrub",
            variable="height_m",
            n=1,
            observed_mean=1,
            predicted_mean=1,
            rmse=-1,
            mae=0,
            bias=0,
        )
    with pytest.raises(ValidationError):
        LagSummary(
            lag_years=-1,
            n=1,
            height_rmse=0,
            cover_rmse=0,
            height_bias=0,
            cover_bias=0,
        )
    with pytest.raises(ValidationError):
        CandidateSummary(
            name="x",
            n=-1,
            height_rmse=0,
            cover_rmse=0,
            height_bias=0,
            cover_bias=0,
            height_rmse_difference=0,
            cover_rmse_difference=0,
        )
    assert date(2026, 6, 1).year == 2026
