"""Held-out validation and candidate benchmark for the low-vegetation model.

The validator compares observed and predicted height, cover, and density on a spatial holdout.
It reports error by functional group, interval coverage, time-lag sensitivity, out-of-domain and
coverage exclusions, and a candidate benchmark with recorded disagreement. It does not run a live
sibling model.
"""

from __future__ import annotations

import math
from datetime import UTC, date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from brushline.model.state import FunctionalGroup
from brushline.model.validation import ContractValidation, check_duplicates

VEGETATION_VALIDATION_SCHEMA_VERSION: Literal["brushline.vegetation-validation.v1"] = (
    "brushline.vegetation-validation.v1"
)
VALIDATION_VARIABLES: tuple[str, ...] = ("height_m", "cover_pct", "density_per_ha")


class VegetationValidationError(ValueError):
    """Raised when a validation dataset is internally inconsistent."""


class CandidatePrediction(BaseModel):
    """One candidate model's prediction for an observation.

    Parameters
    ----------
    name : str
        Candidate name.
    height_m : float
        Predicted height.
    cover_pct : float
        Predicted cover.
    density_per_ha : float or None
        Predicted density.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str = Field(min_length=1)
    height_m: float = Field(ge=0)
    cover_pct: float = Field(ge=0, le=100)
    density_per_ha: float | None = Field(default=None, ge=0)


class ValidationRecord(BaseModel):
    """One observed/predicted validation record.

    Parameters
    ----------
    observation_id : str
        Stable record id.
    segment_id : str
        Segment id.
    spatial_block : str
        Spatial holdout block.
    observed_date : datetime.date
        Observation date.
    prediction_year : int
        Year of the prediction.
    functional_group : str
        Functional group.
    observed_height_m : float
        Observed height.
    predicted_height_m : float
        Predicted height.
    predicted_height_sd : float
        Predicted height standard deviation.
    observed_cover_pct : float
        Observed cover.
    predicted_cover_pct : float
        Predicted cover.
    predicted_cover_sd : float
        Predicted cover standard deviation.
    observed_density_per_ha : float or None
        Observed density.
    predicted_density_per_ha : float or None
        Predicted density.
    predicted_density_sd : float, optional
        Predicted density standard deviation.
    coverage_pct : float
        Observation coverage.
    in_domain : bool, optional
        Whether the observation is in domain. Defaults to ``True``.
    domain_reason : str, optional
        Reason when out of domain.
    treatment_history : list of str, optional
        Treatment history.
    source : str
        Source.
    source_version : str
        Source version.
    candidates : list of CandidatePrediction, optional
        Candidate predictions.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    observation_id: str = Field(min_length=1)
    segment_id: str = Field(min_length=1)
    spatial_block: str = Field(min_length=1)
    observed_date: date
    prediction_year: int = Field(ge=1900, le=2200)
    functional_group: FunctionalGroup
    observed_height_m: float = Field(ge=0)
    predicted_height_m: float = Field(ge=0)
    predicted_height_sd: float = Field(ge=0)
    observed_cover_pct: float = Field(ge=0, le=100)
    predicted_cover_pct: float = Field(ge=0, le=100)
    predicted_cover_sd: float = Field(ge=0)
    observed_density_per_ha: float | None = Field(default=None, ge=0)
    predicted_density_per_ha: float | None = Field(default=None, ge=0)
    predicted_density_sd: float = Field(default=0.0, ge=0)
    coverage_pct: float = Field(ge=0, le=100)
    in_domain: bool = True
    domain_reason: str = ""
    treatment_history: list[str] = Field(default_factory=list)
    source: str = Field(min_length=1)
    source_version: str = Field(min_length=1)
    candidates: list[CandidatePrediction] = Field(default_factory=list)

    @model_validator(mode="after")
    def _record_consistency(self) -> ValidationRecord:
        if not self.in_domain and not self.domain_reason.strip():
            raise ValueError("an out-of-domain record needs a reason")
        if (self.observed_density_per_ha is None) != (self.predicted_density_per_ha is None):
            raise ValueError("density needs both observed and predicted values")
        names = [candidate.name for candidate in self.candidates]
        if len(set(names)) != len(names):
            raise ValueError("candidate names must be unique per record")
        return self

    @property
    def lag_years(self) -> int:
        """Return the prediction-to-observation lag.

        Returns
        -------
        int
            Observation year minus prediction year.
        """
        return self.observed_date.year - self.prediction_year


class ValidationDataset(BaseModel):
    """A deterministic validation dataset.

    Parameters
    ----------
    schema_version : {"brushline.vegetation-validation.v1"}
        Dataset schema version.
    records : list of ValidationRecord
        Validation records.
    """

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["brushline.vegetation-validation.v1"] = (
        VEGETATION_VALIDATION_SCHEMA_VERSION
    )
    records: list[ValidationRecord] = Field(min_length=1)


class ValidationConfig(BaseModel):
    """Holdout, lag, coverage, and comparison rules.

    Parameters
    ----------
    holdout_blocks : list of str
        Spatial blocks held out.
    min_coverage_pct : float, optional
        Minimum observation coverage. Defaults to ``50``.
    max_lag_years : int, optional
        Maximum absolute prediction lag. Defaults to ``5``.
    interval_z : float, optional
        Interval multiplier. Defaults to ``1.96``.
    include_out_of_domain : bool, optional
        Include out-of-domain records in metrics. Defaults to ``False``.
    candidate_disagreement_tolerance : float, optional
        RMSE difference that raises a question. Defaults to ``0.25``.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    holdout_blocks: list[str] = Field(min_length=1)
    min_coverage_pct: float = Field(default=50.0, ge=0, le=100)
    max_lag_years: int = Field(default=5, ge=0)
    interval_z: float = Field(default=1.96, gt=0)
    include_out_of_domain: bool = False
    candidate_disagreement_tolerance: float = Field(default=0.25, ge=0)


class MetricSummary(BaseModel):
    """Error summary for one group and variable.

    Parameters
    ----------
    group : str
        Functional group.
    variable : str
        Variable name.
    n : int
        Record count.
    observed_mean : float
        Observed mean.
    predicted_mean : float
        Predicted mean.
    rmse : float
        Root mean squared error.
    mae : float
        Mean absolute error.
    bias : float
        Mean predicted minus observed.
    interval_coverage : float or None
        Share inside the predicted interval.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    group: str
    variable: str
    n: int = Field(ge=0)
    observed_mean: float
    predicted_mean: float
    rmse: float = Field(ge=0)
    mae: float = Field(ge=0)
    bias: float
    interval_coverage: float | None = Field(default=None, ge=0, le=1)


class LagSummary(BaseModel):
    """Error summary at one prediction lag.

    Parameters
    ----------
    lag_years : int
        Absolute prediction lag.
    n : int
        Record count.
    height_rmse : float
        Height RMSE.
    cover_rmse : float
        Cover RMSE.
    height_bias : float
        Height bias.
    cover_bias : float
        Cover bias.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    lag_years: int = Field(ge=0)
    n: int = Field(ge=0)
    height_rmse: float = Field(ge=0)
    cover_rmse: float = Field(ge=0)
    height_bias: float
    cover_bias: float


class CandidateSummary(BaseModel):
    """Error summary for one candidate model.

    Parameters
    ----------
    name : str
        Candidate name.
    n : int
        Record count.
    height_rmse : float
        Height RMSE.
    cover_rmse : float
        Cover RMSE.
    height_bias : float
        Height bias.
    cover_bias : float
        Cover bias.
    height_rmse_difference : float
        Candidate height RMSE minus Brushline height RMSE.
    cover_rmse_difference : float
        Candidate cover RMSE minus Brushline cover RMSE.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str
    n: int = Field(ge=0)
    height_rmse: float = Field(ge=0)
    cover_rmse: float = Field(ge=0)
    height_bias: float
    cover_bias: float
    height_rmse_difference: float
    cover_rmse_difference: float


class VegetationValidationReport(BaseModel):
    """The held-out validation and candidate benchmark report.

    Parameters
    ----------
    schema_version : {"brushline.vegetation-validation.v1"}
        Report schema version.
    created_utc : datetime
        Timezone-aware creation time.
    config : ValidationConfig
        Validation rules.
    metrics : list of MetricSummary
        Brushline error by group and variable.
    lags : list of LagSummary
        Time-lag sensitivity.
    candidates : list of CandidateSummary
        Candidate benchmark.
    excluded : dict of str to int
        Excluded record counts.
    errors : list of str
        Named validation failures.
    warnings : list of str
        Non-fatal findings.
    open_questions : list of str
        Reviewer questions.
    counts : dict of str to int or float
        Summary counts.
    """

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["brushline.vegetation-validation.v1"] = (
        VEGETATION_VALIDATION_SCHEMA_VERSION
    )
    created_utc: datetime
    config: ValidationConfig
    metrics: list[MetricSummary] = Field(default_factory=list)
    lags: list[LagSummary] = Field(default_factory=list)
    candidates: list[CandidateSummary] = Field(default_factory=list)
    excluded: dict[str, int] = Field(default_factory=dict)
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    open_questions: list[str] = Field(default_factory=list)
    counts: dict[str, int | float] = Field(default_factory=dict)

    @property
    def is_valid(self) -> bool:
        """Return whether the validation passed.

        Returns
        -------
        bool
            ``True`` when there are no errors.
        """
        return not self.errors

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-ready report summary.

        Returns
        -------
        dict of str to object
            Validity, metrics, lags, candidates, errors, warnings, and counts.
        """
        return {
            "is_valid": self.is_valid,
            "metrics": [metric.model_dump(mode="json") for metric in self.metrics],
            "lags": [lag.model_dump(mode="json") for lag in self.lags],
            "candidates": [candidate.model_dump(mode="json") for candidate in self.candidates],
            "errors": list(self.errors),
            "warnings": list(self.warnings),
            "counts": dict(sorted(self.counts.items())),
        }


def validate_vegetation(
    dataset: ValidationDataset,
    config: ValidationConfig,
    *,
    created_utc: datetime | None = None,
) -> VegetationValidationReport:
    """Validate held-out observations and benchmark candidate predictions.

    Parameters
    ----------
    dataset : ValidationDataset
        Observed and predicted records.
    config : ValidationConfig
        Holdout, lag, coverage, and candidate rules.
    created_utc : datetime, optional
        Report time.

    Returns
    -------
    VegetationValidationReport
        Errors, lags, candidates, and reviewer questions.

    Raises
    ------
    VegetationValidationError
        When observation ids or spatial blocks are duplicated.
    """
    identifiers = [record.observation_id for record in dataset.records]
    if len(set(identifiers)) != len(identifiers):
        raise VegetationValidationError("observation ids must be unique")
    blocks = {record.spatial_block for record in dataset.records}
    errors: list[str] = []
    warnings: list[str] = []
    unknown_blocks = sorted(set(config.holdout_blocks) - blocks)
    for block in unknown_blocks:
        errors.append(f"VALIDATION-BLOCK: holdout block {block!r} is not in the dataset")
    holdout = [
        record for record in dataset.records if record.spatial_block in config.holdout_blocks
    ]
    if not holdout:
        errors.append("VALIDATION-HOLDOUT: no records in the holdout blocks")
    excluded: dict[str, int] = {
        "coverage": 0,
        "out_of_domain": 0,
        "time_lag": 0,
    }
    eligible: list[ValidationRecord] = []
    for record in holdout:
        if record.coverage_pct < config.min_coverage_pct:
            excluded["coverage"] += 1
            continue
        if not record.in_domain and not config.include_out_of_domain:
            excluded["out_of_domain"] += 1
            continue
        if abs(record.lag_years) > config.max_lag_years:
            excluded["time_lag"] += 1
            continue
        eligible.append(record)
    if not eligible:
        errors.append("VALIDATION-EMPTY: no eligible holdout records")
    metrics = _metrics(eligible, config)
    lags = _lags(eligible)
    candidates = _candidates(eligible, config)
    if not candidates:
        warnings.append("VALIDATION-CANDIDATE: no candidate predictions were supplied")
    open_questions: list[str] = []
    if excluded["coverage"]:
        open_questions.append(
            f"{excluded['coverage']} holdout records were excluded for low coverage."
        )
    if excluded["out_of_domain"]:
        open_questions.append(f"{excluded['out_of_domain']} holdout records were out of domain.")
    if excluded["time_lag"]:
        open_questions.append(
            f"{excluded['time_lag']} holdout records exceeded the time-lag window."
        )
    for candidate in candidates:
        if (
            abs(candidate.height_rmse_difference) > config.candidate_disagreement_tolerance
            or abs(candidate.cover_rmse_difference) > config.candidate_disagreement_tolerance
        ):
            open_questions.append(
                f"Candidate {candidate.name} differs from Brushline beyond the "
                "disagreement tolerance."
            )
    counts: dict[str, int | float] = {
        "records": len(dataset.records),
        "holdout_records": len(holdout),
        "eligible_records": len(eligible),
        "groups": len({record.functional_group for record in eligible}),
        "candidates": len(candidates),
        "excluded": sum(excluded.values()),
    }
    return VegetationValidationReport(
        created_utc=created_utc or datetime.now(UTC),
        config=config,
        metrics=metrics,
        lags=lags,
        candidates=candidates,
        excluded=excluded,
        errors=errors,
        warnings=warnings,
        open_questions=open_questions,
        counts=counts,
    )


def validate_vegetation_validation(
    report: VegetationValidationReport,
) -> ContractValidation:
    """Validate a vegetation validation report.

    Parameters
    ----------
    report : VegetationValidationReport
        Report to validate.

    Returns
    -------
    ContractValidation
        Errors, warnings, and counts.
    """
    errors: list[str] = []
    warnings: list[str] = []
    check_duplicates(
        "VALIDATION",
        "metric",
        [f"{metric.group}:{metric.variable}" for metric in report.metrics],
        errors,
    )
    check_duplicates(
        "VALIDATION",
        "candidate",
        [candidate.name for candidate in report.candidates],
        errors,
    )
    if report.created_utc.tzinfo is None:
        errors.append("VALIDATION-TIME: created_utc is not timezone-aware")
    if report.errors:
        errors.extend(report.errors)
    for metric in report.metrics:
        if metric.variable not in VALIDATION_VARIABLES:
            errors.append(
                f"VALIDATION-METRIC: {metric.group} has unknown variable {metric.variable!r}"
            )
        if metric.n == 0:
            warnings.append(f"VALIDATION-EMPTY: {metric.group}/{metric.variable} has no records")
        if metric.interval_coverage is not None and not (0 <= metric.interval_coverage <= 1):
            errors.append(
                f"VALIDATION-INTERVAL: {metric.group}/{metric.variable} coverage is outside 0 to 1"
            )
    for lag in report.lags:
        if lag.lag_years < 0:
            errors.append("VALIDATION-LAG: negative time lag")
    for candidate in report.candidates:
        if candidate.n == 0:
            warnings.append(f"VALIDATION-EMPTY: candidate {candidate.name} has no records")
    if not report.candidates:
        warnings.append("VALIDATION-CANDIDATE: the report has no candidate benchmark")
    counts = dict(report.counts)
    return ContractValidation(tuple(errors), tuple(warnings), counts)


def _metrics(
    records: list[ValidationRecord],
    config: ValidationConfig,
) -> list[MetricSummary]:
    groups = sorted({record.functional_group for record in records})
    metrics: list[MetricSummary] = []
    for group in groups:
        group_records = [record for record in records if record.functional_group == group]
        height = _metric(
            group,
            "height_m",
            [
                (record.observed_height_m, record.predicted_height_m, record.predicted_height_sd)
                for record in group_records
            ],
            config.interval_z,
        )
        cover = _metric(
            group,
            "cover_pct",
            [
                (record.observed_cover_pct, record.predicted_cover_pct, record.predicted_cover_sd)
                for record in group_records
            ],
            config.interval_z,
        )
        metrics.extend([height, cover])
        density_rows = [
            (
                record.observed_density_per_ha,
                record.predicted_density_per_ha,
                record.predicted_density_sd,
            )
            for record in group_records
            if record.observed_density_per_ha is not None
            and record.predicted_density_per_ha is not None
        ]
        if density_rows:
            metrics.append(
                _metric(
                    group,
                    "density_per_ha",
                    [
                        (observed, predicted, sd)
                        for observed, predicted, sd in density_rows
                        if observed is not None and predicted is not None
                    ],
                    config.interval_z,
                )
            )
    return metrics


def _metric(
    group: str,
    variable: str,
    rows: list[tuple[float, float, float]],
    interval_z: float,
) -> MetricSummary:
    n = len(rows)
    observed = [row[0] for row in rows]
    predicted = [row[1] for row in rows]
    errors = [pred - obs for obs, pred, _ in rows]
    rmse = math.sqrt(sum(error * error for error in errors) / n)
    mae = sum(abs(error) for error in errors) / n
    bias = sum(errors) / n
    covered = sum(1 for obs, pred, sd in rows if abs(pred - obs) <= interval_z * sd)
    return MetricSummary(
        group=group,
        variable=variable,
        n=n,
        observed_mean=sum(observed) / n,
        predicted_mean=sum(predicted) / n,
        rmse=rmse,
        mae=mae,
        bias=bias,
        interval_coverage=covered / n,
    )


def _lags(records: list[ValidationRecord]) -> list[LagSummary]:
    groups: dict[int, list[ValidationRecord]] = {}
    for record in records:
        groups.setdefault(abs(record.lag_years), []).append(record)
    summaries: list[LagSummary] = []
    for lag in sorted(groups):
        group = groups[lag]
        height_errors = [record.predicted_height_m - record.observed_height_m for record in group]
        cover_errors = [record.predicted_cover_pct - record.observed_cover_pct for record in group]
        summaries.append(
            LagSummary(
                lag_years=lag,
                n=len(group),
                height_rmse=math.sqrt(sum(error * error for error in height_errors) / len(group)),
                cover_rmse=math.sqrt(sum(error * error for error in cover_errors) / len(group)),
                height_bias=sum(height_errors) / len(group),
                cover_bias=sum(cover_errors) / len(group),
            )
        )
    return summaries


def _candidates(
    records: list[ValidationRecord],
    config: ValidationConfig,
) -> list[CandidateSummary]:
    names = sorted({candidate.name for record in records for candidate in record.candidates})
    brushline_height = _overall_rmse(records, "height")
    brushline_cover = _overall_rmse(records, "cover")
    summaries: list[CandidateSummary] = []
    for name in names:
        rows = [
            (record, candidate)
            for record in records
            for candidate in record.candidates
            if candidate.name == name
        ]
        height_errors = [
            candidate.height_m - record.observed_height_m for record, candidate in rows
        ]
        cover_errors = [
            candidate.cover_pct - record.observed_cover_pct for record, candidate in rows
        ]
        height_rmse = math.sqrt(sum(error * error for error in height_errors) / len(rows))
        cover_rmse = math.sqrt(sum(error * error for error in cover_errors) / len(rows))
        summaries.append(
            CandidateSummary(
                name=name,
                n=len(rows),
                height_rmse=height_rmse,
                cover_rmse=cover_rmse,
                height_bias=sum(height_errors) / len(rows),
                cover_bias=sum(cover_errors) / len(rows),
                height_rmse_difference=height_rmse - brushline_height,
                cover_rmse_difference=cover_rmse - brushline_cover,
            )
        )
    return summaries


def _overall_rmse(records: list[ValidationRecord], variable: str) -> float:
    if not records:
        return 0.0
    if variable == "height":
        errors = [record.predicted_height_m - record.observed_height_m for record in records]
    else:
        errors = [record.predicted_cover_pct - record.observed_cover_pct for record in records]
    return math.sqrt(sum(error * error for error in errors) / len(records))


__all__ = [
    "VALIDATION_VARIABLES",
    "VEGETATION_VALIDATION_SCHEMA_VERSION",
    "CandidatePrediction",
    "CandidateSummary",
    "LagSummary",
    "MetricSummary",
    "ValidationConfig",
    "ValidationDataset",
    "ValidationRecord",
    "VegetationValidationError",
    "VegetationValidationReport",
    "validate_vegetation",
    "validate_vegetation_validation",
]
