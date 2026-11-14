"""Offline benchmark against the FEMIC, WS4, and FHOPS LiDAR consumers.

The benchmark compares the same bundle pin, segment, CRS, resolution, datum, statistic, buffer,
and valid-pixel rule. It records absolute and relative differences for every metric and consumer,
fails on an unexplained missing value or a difference outside the tolerance, and never calls a
sibling runtime.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from brushline.model.validation import ContractValidation, check_duplicates

LIDAR_BENCHMARK_REQUEST_SCHEMA_VERSION: Literal["brushline.lidar-benchmark-request.v1"] = (
    "brushline.lidar-benchmark-request.v1"
)
LIDAR_BENCHMARK_SCHEMA_VERSION: Literal["brushline.lidar-benchmark.v1"] = (
    "brushline.lidar-benchmark.v1"
)
BENCHMARK_CONSUMERS: tuple[str, ...] = ("femic", "ws4", "fhops")
BENCHMARK_STATUSES: tuple[str, ...] = ("pass", "fail", "missing", "contract")
SHA256_PATTERN = r"^[0-9a-f]{64}$"


class BenchmarkContract(BaseModel):
    """The shared measurement contract for one benchmark.

    Parameters
    ----------
    crs : str
        Coordinate reference system.
    resolution_m : float
        Native resolution in metres.
    vertical_datum : str
        Vertical datum.
    statistic : str
        Aggregation statistic.
    buffer_m : float
        Segment buffer.
    valid_pixel_rule : str
        Valid-pixel rule.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    crs: str = Field(min_length=1)
    resolution_m: float = Field(gt=0)
    vertical_datum: str = Field(min_length=1)
    statistic: str = Field(min_length=1)
    buffer_m: float = Field(ge=0)
    valid_pixel_rule: str = Field(min_length=1)


class BenchmarkValue(BaseModel):
    """One consumer's value for one metric.

    Parameters
    ----------
    consumer : str
        Consumer name, such as ``femic``, ``ws4``, or ``fhops``.
    value : float or None
        Metric value, or ``None`` when unavailable.
    provenance : str
        Evidence reference.
    contract : BenchmarkContract
        Measurement contract declared by the consumer.
    missing_reason : str, optional
        Why the value is missing.
    required : bool, optional
        Whether a missing value fails the benchmark. Defaults to ``True``.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    consumer: str = Field(min_length=1)
    value: float | None = None
    provenance: str = Field(min_length=1)
    contract: BenchmarkContract
    missing_reason: str = ""
    required: bool = True


class BenchmarkMetric(BaseModel):
    """One metric and its Brushline and sibling-consumer values.

    Parameters
    ----------
    name : str
        Metric name.
    unit : str
        Metric unit.
    brushline_value : float
        Brushline value.
    comparisons : list of BenchmarkValue
        Sibling-consumer values.
    absolute_tolerance : float
        Absolute tolerance in the metric unit.
    relative_tolerance : float
        Relative tolerance as a fraction.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str = Field(min_length=1)
    unit: str = Field(min_length=1)
    brushline_value: float
    comparisons: list[BenchmarkValue] = Field(min_length=1)
    absolute_tolerance: float = Field(ge=0)
    relative_tolerance: float = Field(ge=0, le=1)

    @model_validator(mode="after")
    def _unique_consumers(self) -> BenchmarkMetric:
        names = [item.consumer for item in self.comparisons]
        if len(set(names)) != len(names):
            raise ValueError("comparison consumers must be unique per metric")
        return self


class BenchmarkRequest(BaseModel):
    """A deterministic benchmark request.

    Parameters
    ----------
    schema_version : {"brushline.lidar-benchmark-request.v1"}
        Request schema version.
    benchmark_id : str
        Benchmark id.
    bundle_id : str
        Pinned LiDAR bundle id.
    bundle_version : str
        Pinned bundle version.
    segment_id : str
        Segment id.
    product_sha256 : dict of str to str
        Product ids and their SHA-256 checksums.
    contract : BenchmarkContract
        Shared measurement contract.
    metrics : list of BenchmarkMetric
        Metric comparisons.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["brushline.lidar-benchmark-request.v1"] = (
        LIDAR_BENCHMARK_REQUEST_SCHEMA_VERSION
    )
    benchmark_id: str = Field(min_length=1)
    bundle_id: str = Field(min_length=1)
    bundle_version: str = Field(min_length=1)
    segment_id: str = Field(min_length=1)
    product_sha256: dict[str, str] = Field(min_length=1)
    contract: BenchmarkContract
    metrics: list[BenchmarkMetric] = Field(min_length=1)

    @field_validator("product_sha256")
    @classmethod
    def _checksum_shape(cls, value: dict[str, str]) -> dict[str, str]:
        for product_id, digest in value.items():
            if not product_id:
                raise ValueError("product ids must not be empty")
            if len(digest) != 64 or any(char not in "0123456789abcdef" for char in digest):
                raise ValueError(f"product {product_id} has an invalid sha256")
        return value

    @model_validator(mode="after")
    def _metric_names(self) -> BenchmarkRequest:
        names = [metric.name for metric in self.metrics]
        if len(set(names)) != len(names):
            raise ValueError("metric names must be unique")
        return self


class BenchmarkCase(BaseModel):
    """One comparison result.

    Parameters
    ----------
    metric : str
        Metric name.
    consumer : str
        Consumer name.
    brushline_value : float
        Brushline value.
    comparison_value : float or None
        Sibling value.
    absolute_difference : float or None
        Absolute difference.
    relative_difference : float or None
        Relative difference.
    absolute_tolerance : float
        Absolute tolerance.
    relative_tolerance : float
        Relative tolerance.
    status : str
        ``pass``, ``fail``, ``missing``, or ``contract``.
    reason : str
        Result reason.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    metric: str = Field(min_length=1)
    consumer: str = Field(min_length=1)
    brushline_value: float
    comparison_value: float | None = None
    absolute_difference: float | None = None
    relative_difference: float | None = None
    absolute_tolerance: float
    relative_tolerance: float
    status: str
    reason: str = ""


class LidarBenchmarkReport(BaseModel):
    """The deterministic benchmark report.

    Parameters
    ----------
    schema_version : {"brushline.lidar-benchmark.v1"}
        Report schema version.
    created_utc : datetime
        Timezone-aware creation time.
    request : BenchmarkRequest
        Benchmark request.
    cases : list of BenchmarkCase
        Comparison cases.
    errors : list of str
        Named failures.
    warnings : list of str
        Non-fatal findings.
    counts : dict of str to int or float
        Case counts.
    bundle_sha256 : str
        Hash of the pinned product checksums.
    """

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["brushline.lidar-benchmark.v1"] = LIDAR_BENCHMARK_SCHEMA_VERSION
    created_utc: datetime
    request: BenchmarkRequest
    cases: list[BenchmarkCase] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    counts: dict[str, int | float] = Field(default_factory=dict)
    bundle_sha256: str = Field(pattern=SHA256_PATTERN)

    @property
    def is_valid(self) -> bool:
        """Return whether the benchmark passed.

        Returns
        -------
        bool
            ``True`` when there are no errors.
        """
        return not self.errors

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-ready report.

        Returns
        -------
        dict of str to object
            Validity, cases, errors, warnings, and counts.
        """
        return {
            "is_valid": self.is_valid,
            "cases": [case.model_dump(mode="json") for case in self.cases],
            "errors": list(self.errors),
            "warnings": list(self.warnings),
            "counts": dict(sorted(self.counts.items())),
        }


def run_lidar_benchmark(
    request: BenchmarkRequest,
    *,
    created_utc: datetime | None = None,
) -> LidarBenchmarkReport:
    """Run the offline sibling-consumer benchmark.

    Parameters
    ----------
    request : BenchmarkRequest
        Benchmark request.
    created_utc : datetime, optional
        Report time. Defaults to the current UTC time.

    Returns
    -------
    LidarBenchmarkReport
        Cases, errors, warnings, and counts.
    """
    errors: list[str] = []
    warnings: list[str] = []
    cases: list[BenchmarkCase] = []
    for metric in request.metrics:
        for comparison in metric.comparisons:
            if comparison.value is None:
                if comparison.missing_reason.strip():
                    if comparison.required:
                        errors.append(
                            f"BENCHMARK-MISSING: {metric.name}/{comparison.consumer} is required "
                            f"but missing: {comparison.missing_reason}"
                        )
                    else:
                        warnings.append(
                            f"BENCHMARK-MISSING: {metric.name}/{comparison.consumer} is optional "
                            f"and missing: {comparison.missing_reason}"
                        )
                else:
                    errors.append(
                        f"BENCHMARK-MISSING: {metric.name}/{comparison.consumer} is missing "
                        "without a reason"
                    )
                cases.append(
                    BenchmarkCase(
                        metric=metric.name,
                        consumer=comparison.consumer,
                        brushline_value=metric.brushline_value,
                        absolute_tolerance=metric.absolute_tolerance,
                        relative_tolerance=metric.relative_tolerance,
                        status="missing",
                        reason=comparison.missing_reason or "no reason recorded",
                    )
                )
                continue
            if comparison.contract != request.contract:
                errors.append(
                    f"BENCHMARK-CONTRACT: {metric.name}/{comparison.consumer} does not use "
                    "the same measurement contract"
                )
                cases.append(
                    BenchmarkCase(
                        metric=metric.name,
                        consumer=comparison.consumer,
                        brushline_value=metric.brushline_value,
                        comparison_value=comparison.value,
                        absolute_tolerance=metric.absolute_tolerance,
                        relative_tolerance=metric.relative_tolerance,
                        status="contract",
                        reason="measurement contract differs",
                    )
                )
                continue
            absolute = abs(metric.brushline_value - comparison.value)
            relative = absolute / max(
                abs(metric.brushline_value),
                abs(comparison.value),
                1e-12,
            )
            passed = (
                absolute <= metric.absolute_tolerance + 1e-12
                or relative <= metric.relative_tolerance + 1e-12
            )
            if passed:
                status = "pass"
                reason = "within the absolute or relative tolerance"
            else:
                status = "fail"
                reason = "outside both tolerances"
                errors.append(
                    f"BENCHMARK-TOLERANCE: {metric.name}/{comparison.consumer} differs by "
                    f"{absolute:.6g} ({relative:.4%})"
                )
            cases.append(
                BenchmarkCase(
                    metric=metric.name,
                    consumer=comparison.consumer,
                    brushline_value=metric.brushline_value,
                    comparison_value=comparison.value,
                    absolute_difference=absolute,
                    relative_difference=relative,
                    absolute_tolerance=metric.absolute_tolerance,
                    relative_tolerance=metric.relative_tolerance,
                    status=status,
                    reason=reason,
                )
            )
    counts: dict[str, int | float] = {
        "metrics": len(request.metrics),
        "comparisons": len(cases),
        "pass": sum(1 for case in cases if case.status == "pass"),
        "fail": sum(1 for case in cases if case.status == "fail"),
        "missing": sum(1 for case in cases if case.status == "missing"),
        "contract": sum(1 for case in cases if case.status == "contract"),
    }
    bundle_sha256 = hashlib.sha256(
        "|".join(f"{key}:{value}" for key, value in sorted(request.product_sha256.items())).encode(
            "utf-8"
        )
    ).hexdigest()
    return LidarBenchmarkReport(
        created_utc=created_utc or datetime.now(UTC),
        request=request,
        cases=cases,
        errors=errors,
        warnings=warnings,
        counts=counts,
        bundle_sha256=bundle_sha256,
    )


def validate_lidar_benchmark(report: LidarBenchmarkReport) -> ContractValidation:
    """Validate the benchmark report and its case/status consistency.

    Parameters
    ----------
    report : LidarBenchmarkReport
        Report to validate.

    Returns
    -------
    ContractValidation
        Errors, warnings, and counts.
    """
    errors: list[str] = []
    warnings: list[str] = []
    check_duplicates(
        "BENCHMARK",
        "case",
        [f"{case.metric}:{case.consumer}" for case in report.cases],
        errors,
    )
    if report.created_utc.tzinfo is None:
        errors.append("BENCHMARK-TIME: created_utc is not timezone-aware")
    if not report.cases:
        warnings.append("BENCHMARK-EMPTY: the report has no cases")
    for case in report.cases:
        if case.status not in BENCHMARK_STATUSES:
            errors.append(
                f"BENCHMARK-STATUS: {case.metric}/{case.consumer} has unknown status "
                f"{case.status!r}"
            )
        if case.status == "pass" and (
            case.absolute_difference is None or case.relative_difference is None
        ):
            errors.append(f"BENCHMARK-CASE: {case.metric}/{case.consumer} pass has no difference")
        if case.status == "fail" and not case.reason.strip():
            errors.append(f"BENCHMARK-CASE: {case.metric}/{case.consumer} fail has no reason")
    errors.extend(report.errors)
    warnings.extend(report.warnings)
    counts = dict(report.counts)
    return ContractValidation(tuple(errors), tuple(warnings), counts)


__all__ = [
    "BENCHMARK_CONSUMERS",
    "BENCHMARK_STATUSES",
    "LIDAR_BENCHMARK_REQUEST_SCHEMA_VERSION",
    "LIDAR_BENCHMARK_SCHEMA_VERSION",
    "BenchmarkCase",
    "BenchmarkContract",
    "BenchmarkMetric",
    "BenchmarkRequest",
    "BenchmarkValue",
    "LidarBenchmarkReport",
    "run_lidar_benchmark",
    "validate_lidar_benchmark",
]
