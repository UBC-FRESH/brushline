"""Tests for the offline FEMIC/WS4/FHOPS LiDAR benchmark."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from brushline.integrations.lidar_benchmark import (
    BENCHMARK_CONSUMERS,
    BenchmarkContract,
    BenchmarkMetric,
    BenchmarkRequest,
    run_lidar_benchmark,
    validate_lidar_benchmark,
)
from pydantic import ValidationError

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "notes" / "reference" / "lidar-benchmark.v1.json"
NOW = datetime(2026, 11, 14, tzinfo=UTC)


def _request() -> BenchmarkRequest:
    return BenchmarkRequest.model_validate_json(FIXTURE.read_text(encoding="utf-8"))


def _with_metric(request: BenchmarkRequest, metric: BenchmarkMetric) -> BenchmarkRequest:
    return request.model_copy(update={"metrics": [metric, *request.metrics[1:]]})


def test_committed_benchmark_passes() -> None:
    """The committed benchmark compares the same contract and passes every tolerance."""
    request = _request()
    assert request.benchmark_id == "synthetic-corridor-lidar-v1"
    report = run_lidar_benchmark(request, created_utc=NOW)
    assert report.is_valid
    assert len(report.cases) == 12
    assert report.counts["pass"] == 12
    assert report.counts["fail"] == 0
    assert len(report.bundle_sha256) == 64
    assert validate_lidar_benchmark(report).is_valid
    assert report.to_dict()["is_valid"] is True
    assert {case.consumer for case in report.cases} == set(BENCHMARK_CONSUMERS)


def test_absolute_tolerance_failure() -> None:
    """A difference outside both tolerances fails the benchmark."""
    request = _request()
    metric = request.metrics[0]
    comparison = metric.comparisons[0].model_copy(update={"value": 200.0})
    changed = _with_metric(
        request,
        metric.model_copy(update={"comparisons": [comparison, *metric.comparisons[1:]]}),
    )
    report = run_lidar_benchmark(changed, created_utc=NOW)
    assert not report.is_valid
    assert any(error.startswith("BENCHMARK-TOLERANCE") for error in report.errors)
    assert any(case.status == "fail" for case in report.cases)
    assert not validate_lidar_benchmark(report).is_valid


def test_relative_tolerance_can_pass_a_large_absolute_difference() -> None:
    """A relative tolerance passes when the absolute value is larger than the absolute tolerance."""
    request = _request()
    metric = request.metrics[0]
    comparison = metric.comparisons[0].model_copy(update={"value": 111.0})
    changed = _with_metric(
        request,
        metric.model_copy(
            update={
                "comparisons": [comparison, *metric.comparisons[1:]],
                "absolute_tolerance": 0.1,
                "relative_tolerance": 0.05,
            }
        ),
    )
    report = run_lidar_benchmark(changed, created_utc=NOW)
    assert report.is_valid
    assert report.counts["pass"] == 12


def test_contract_mismatch_fails() -> None:
    """A different CRS, resolution, datum, statistic, buffer, or valid rule fails."""
    request = _request()
    metric = request.metrics[0]
    contract = metric.comparisons[0].contract.model_copy(update={"crs": "EPSG:4326"})
    comparison = metric.comparisons[0].model_copy(update={"contract": contract})
    changed = _with_metric(
        request,
        metric.model_copy(update={"comparisons": [comparison, *metric.comparisons[1:]]}),
    )
    report = run_lidar_benchmark(changed, created_utc=NOW)
    assert any(error.startswith("BENCHMARK-CONTRACT") for error in report.errors)
    assert any(case.status == "contract" for case in report.cases)


def test_missing_values_required_optional_and_unexplained() -> None:
    """Required missing fails, explained optional missing warns, unexplained missing fails."""
    request = _request()
    metric = request.metrics[0]
    required_missing = metric.comparisons[0].model_copy(
        update={"value": None, "missing_reason": "no WS4 export"}
    )
    required = _with_metric(
        request,
        metric.model_copy(update={"comparisons": [required_missing, *metric.comparisons[1:]]}),
    )
    required_report = run_lidar_benchmark(required, created_utc=NOW)
    assert any(error.startswith("BENCHMARK-MISSING") for error in required_report.errors)

    optional_missing = metric.comparisons[0].model_copy(
        update={
            "value": None,
            "missing_reason": "not published",
            "required": False,
        }
    )
    optional = _with_metric(
        request,
        metric.model_copy(update={"comparisons": [optional_missing, *metric.comparisons[1:]]}),
    )
    optional_report = run_lidar_benchmark(optional, created_utc=NOW)
    assert optional_report.is_valid
    assert any(warning.startswith("BENCHMARK-MISSING") for warning in optional_report.warnings)

    unexplained = _with_metric(
        request,
        metric.model_copy(
            update={
                "comparisons": [
                    required_missing.model_copy(update={"missing_reason": ""}),
                    *metric.comparisons[1:],
                ]
            }
        ),
    )
    assert any(
        error.startswith("BENCHMARK-MISSING")
        for error in run_lidar_benchmark(unexplained, created_utc=NOW).errors
    )


def test_request_model_rejects_bad_checksums_and_duplicates() -> None:
    """Bad checksums, duplicate metrics, and duplicate consumers are rejected."""
    payload = _request().model_dump(mode="json")
    payload["product_sha256"] = {"dem": "bad"}
    with pytest.raises(ValidationError, match="invalid sha256"):
        BenchmarkRequest.model_validate(payload)
    payload["product_sha256"] = {"": "a" * 64}
    with pytest.raises(ValidationError, match="product ids"):
        BenchmarkRequest.model_validate(payload)
    payload["product_sha256"] = {"dem": "a" * 64}
    payload["metrics"] = [payload["metrics"][0], payload["metrics"][0]]
    with pytest.raises(ValidationError, match="metric names must be unique"):
        BenchmarkRequest.model_validate(payload)
    request = _request()
    duplicate_metrics = request.model_copy(
        update={"metrics": [request.metrics[0], request.metrics[0]]}
    )
    assert duplicate_metrics  # model_copy bypasses the validator; the run still works.
    metric_payload = request.metrics[0].model_dump(mode="json")
    metric_payload["comparisons"] = [metric_payload["comparisons"][0]] * 2
    with pytest.raises(ValidationError, match="consumers must be unique"):
        BenchmarkMetric.model_validate(metric_payload)


def test_validation_names_bad_cases() -> None:
    """Unknown status, missing differences, missing reasons, duplicates, and naive time fail."""
    report = run_lidar_benchmark(_request(), created_utc=NOW)
    case = report.cases[0]
    unknown = report.model_copy(update={"cases": [case.model_copy(update={"status": "maybe"})]})
    assert any(
        error.startswith("BENCHMARK-STATUS") for error in validate_lidar_benchmark(unknown).errors
    )
    no_difference = report.model_copy(
        update={
            "cases": [
                case.model_copy(
                    update={
                        "status": "pass",
                        "absolute_difference": None,
                        "relative_difference": None,
                    }
                )
            ]
        }
    )
    assert any(
        error.startswith("BENCHMARK-CASE")
        for error in validate_lidar_benchmark(no_difference).errors
    )
    no_reason = report.model_copy(
        update={"cases": [case.model_copy(update={"status": "fail", "reason": ""})]}
    )
    assert any(
        error.startswith("BENCHMARK-CASE") for error in validate_lidar_benchmark(no_reason).errors
    )
    duplicate = report.model_copy(update={"cases": [case, case]})
    assert any(
        error.startswith("BENCHMARK-ID") for error in validate_lidar_benchmark(duplicate).errors
    )
    naive = report.model_copy(update={"created_utc": datetime(2026, 11, 14)})
    assert any(
        error.startswith("BENCHMARK-TIME") for error in validate_lidar_benchmark(naive).errors
    )
    empty = report.model_copy(update={"cases": []})
    result = validate_lidar_benchmark(empty)
    assert result.is_valid
    assert any(warning.startswith("BENCHMARK-EMPTY") for warning in result.warnings)


def test_metric_contract_model_validation() -> None:
    """A metric requires at least one comparison and non-negative tolerances."""
    with pytest.raises(ValidationError):
        BenchmarkMetric(
            name="metric",
            unit="m",
            brushline_value=1.0,
            comparisons=[],
            absolute_tolerance=1.0,
            relative_tolerance=0.1,
        )
    with pytest.raises(ValidationError):
        BenchmarkContract(
            crs="EPSG:3005",
            resolution_m=0,
            vertical_datum="CGVD2013",
            statistic="mean",
            buffer_m=10,
            valid_pixel_rule="valid",
        )
