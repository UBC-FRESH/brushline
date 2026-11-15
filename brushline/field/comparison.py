"""Compare validated field observations with planned LiDAR targets."""

from __future__ import annotations

import json
import math
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from brushline.field.validation import FieldObservation, FieldValidationReport

FIELD_COMPARISON_SCHEMA_VERSION: Literal["brushline.field-comparison.v1"] = (
    "brushline.field-comparison.v1"
)

ComparisonStatus = Literal["insufficient", "provisional", "adequate"]


class FieldPlotTarget(BaseModel):
    """Planned plot target metrics from the field-kit GeoJSON."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    plot_id: str
    unit_id: str
    position: Literal["center", "edge"]
    planned_year: int | None = None
    target_shrub_patches: int | None = None
    target_mean_cover_pct: float | None = None
    target_max_shrub_height_m: float | None = None
    target_tree_clumps: int | None = None
    target_canopy_height_m: float | None = None


class FieldComparisonRow(BaseModel):
    """One plot's observed-to-target comparison."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    plot_id: str
    unit_id: str
    position: Literal["center", "edge"]
    planned_year: int | None
    observed_shrub_cover_pct: float | None
    target_mean_cover_pct: float | None
    cover_delta_pct: float | None
    cover_ratio: float | None
    observed_shrub_height_cm: float | None
    target_max_shrub_height_m: float | None
    height_delta_cm: float | None
    height_ratio: float | None
    recent_cut: bool | None
    status: Literal["complete", "partial"]


class FieldUnitComparison(BaseModel):
    """Unit-level residual summary."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    unit_id: str
    n_plots: int
    n_cover: int
    n_height: int
    cover_bias_pct: float | None
    cover_mae_pct: float | None
    cover_rmse_pct: float | None
    height_bias_cm: float | None
    height_mae_cm: float | None
    height_rmse_cm: float | None


class FieldCalibrationSuggestion(BaseModel):
    """Non-applied review factors and treatment-evidence status."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    status: ComparisonStatus
    sample_size_cover: int
    sample_size_height: int
    cover_multiplier: float | None
    height_multiplier: float | None
    treatment_response_status: Literal["not_tested"] = "not_tested"


class FieldComparisonReport(BaseModel):
    """Validated field evidence compared with LiDAR targets."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["brushline.field-comparison.v1"] = FIELD_COMPARISON_SCHEMA_VERSION
    source_observations: str
    source_plots: str
    created_utc: datetime
    status: ComparisonStatus
    observations_compared: int
    plots_compared: int
    rows: list[FieldComparisonRow]
    units: list[FieldUnitComparison]
    calibration: FieldCalibrationSuggestion
    recommendations: list[str]
    warnings: list[str]
    caveats: list[str] = Field(default_factory=list)


def _round(value: float | None, places: int = 1) -> float | None:
    return round(value, places) if value is not None else None


def _mean(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None


def _mae(values: list[float]) -> float | None:
    return sum(abs(value) for value in values) / len(values) if values else None


def _rmse(values: list[float]) -> float | None:
    return math.sqrt(sum(value * value for value in values) / len(values)) if values else None


def _ratio(observed: list[float], target: list[float]) -> float | None:
    target_total = sum(target)
    return round(sum(observed) / target_total, 3) if target_total > 0 else None


def _load_targets(path: Path) -> dict[str, FieldPlotTarget]:
    if not path.exists():
        raise ValueError(f"FIELD-COMPARE-PLOTS: plots file does not exist: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    features = data.get("features")
    if not isinstance(features, list):
        raise ValueError("FIELD-COMPARE-PLOTS: plots file must be a GeoJSON FeatureCollection")
    targets: dict[str, FieldPlotTarget] = {}
    for feature in features:
        if not isinstance(feature, dict):
            continue
        properties = feature.get("properties")
        geometry = feature.get("geometry")
        if not isinstance(properties, dict) or not isinstance(geometry, dict):
            continue
        if geometry.get("type") != "Point" or not properties.get("plot_id"):
            continue
        try:
            target = FieldPlotTarget.model_validate(properties)
        except Exception as exc:  # pragma: no cover - defensive GeoJSON boundary
            raise ValueError(f"FIELD-COMPARE-PLOTS: invalid plot target: {exc}") from exc
        targets[target.plot_id] = target
    if not targets:
        raise ValueError("FIELD-COMPARE-PLOTS: plots file has no plot targets")
    return targets


def _load_observations(path: Path) -> FieldValidationReport:
    if not path.exists():
        raise ValueError(f"FIELD-COMPARE-OBSERVATIONS: file does not exist: {path}")
    try:
        return FieldValidationReport.model_validate_json(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise ValueError(
            f"FIELD-COMPARE-OBSERVATIONS: expected a validated field report: {exc}"
        ) from exc


def _comparison_row(observation: FieldObservation, target: FieldPlotTarget) -> FieldComparisonRow:
    observed_cover = observation.shrub_cover_pct
    target_cover = target.target_mean_cover_pct
    cover_delta = (
        observed_cover - target_cover
        if observed_cover is not None and target_cover is not None
        else None
    )
    cover_ratio = (
        observed_cover / target_cover
        if observed_cover is not None and target_cover not in (None, 0)
        else None
    )
    observed_height = observation.shrub_height_cm
    target_height_cm = (
        target.target_max_shrub_height_m * 100.0
        if target.target_max_shrub_height_m is not None
        else None
    )
    height_delta = (
        observed_height - target_height_cm
        if observed_height is not None and target_height_cm is not None
        else None
    )
    height_ratio = (
        observed_height / target_height_cm
        if observed_height is not None and target_height_cm not in (None, 0)
        else None
    )
    status: Literal["complete", "partial"] = (
        "complete" if cover_delta is not None and height_delta is not None else "partial"
    )
    return FieldComparisonRow(
        plot_id=observation.plot_id,
        unit_id=observation.unit_id,
        position=observation.position,
        planned_year=target.planned_year,
        observed_shrub_cover_pct=observed_cover,
        target_mean_cover_pct=target_cover,
        cover_delta_pct=_round(cover_delta) if cover_delta is not None else None,
        cover_ratio=_round(cover_ratio, 3) if cover_ratio is not None else None,
        observed_shrub_height_cm=observed_height,
        target_max_shrub_height_m=target.target_max_shrub_height_m,
        height_delta_cm=_round(height_delta) if height_delta is not None else None,
        height_ratio=_round(height_ratio, 3) if height_ratio is not None else None,
        recent_cut=observation.recent_cut,
        status=status,
    )


def _unit_summary(unit_id: str, rows: list[FieldComparisonRow]) -> FieldUnitComparison:
    cover_deltas = [row.cover_delta_pct for row in rows if row.cover_delta_pct is not None]
    height_deltas = [row.height_delta_cm for row in rows if row.height_delta_cm is not None]
    return FieldUnitComparison(
        unit_id=unit_id,
        n_plots=len(rows),
        n_cover=len(cover_deltas),
        n_height=len(height_deltas),
        cover_bias_pct=_round(_mean(cover_deltas)),
        cover_mae_pct=_round(_mae(cover_deltas)),
        cover_rmse_pct=_round(_rmse(cover_deltas)),
        height_bias_cm=_round(_mean(height_deltas)),
        height_mae_cm=_round(_mae(height_deltas)),
        height_rmse_cm=_round(_rmse(height_deltas)),
    )


def _status(n_cover: int, n_height: int) -> ComparisonStatus:
    if n_cover >= 8 and n_height >= 8:
        return "adequate"
    if n_cover >= 3 and n_height >= 3:
        return "provisional"
    return "insufficient"


def _recommendations(
    rows: list[FieldComparisonRow],
    status: ComparisonStatus,
    cover_bias: float | None,
    height_bias: float | None,
    sample_cover: int,
    sample_height: int,
) -> list[str]:
    recommendations: list[str] = []
    if status == "insufficient":
        recommendations.append(
            "Collect more complete shrub cover and height pairs before changing model parameters."
        )
    if cover_bias is not None and abs(cover_bias) >= 10.0:
        direction = "underestimates" if cover_bias > 0 else "overestimates"
        recommendations.append(
            f"LiDAR {direction} shrub cover by {abs(cover_bias):.1f} percentage points on average; "
            "review the understory return threshold and cover estimator."
        )
    if height_bias is not None and abs(height_bias) >= 50.0:
        direction = "underestimates" if height_bias > 0 else "overestimates"
        recommendations.append(
            f"LiDAR {direction} shrub height by {abs(height_bias):.1f} cm on average; "
            "check the field top-height definition against the CHM maximum."
        )
    if sample_cover < 8 or sample_height < 8:
        recommendations.append(
            "The sample is below the eight-pair review gate; target at least eight complete "
            "cover and height pairs before a calibration review."
        )
    if any(row.recent_cut for row in rows):
        recommendations.append(
            "Record observed cutting or mowing as treatment history before attributing residuals "
            "to LiDAR or growth."
        )
    recommendations.append(
        "Treatment height reduction and annual regrowth remain untested until before/after "
        "measurements exist."
    )
    return recommendations


def compare_field_data(
    validation: FieldValidationReport,
    plots_path: str | Path,
    created_utc: datetime | None = None,
) -> FieldComparisonReport:
    """Compare validated observations with planned plot targets.

    Parameters
    ----------
    validation : FieldValidationReport
        Normalized field observations.
    plots_path : str or Path
        GeoJSON with planned plot target metrics.
    created_utc : datetime, optional
        Creation time; defaults to the current UTC time.

    Returns
    -------
    FieldComparisonReport
        Residuals, unit summaries, sample status, and non-applied recommendations.

    Raises
    ------
    ValueError
        If the plots file is missing or has no plot targets.
    """
    plots = _load_targets(Path(plots_path))
    rows: list[FieldComparisonRow] = []
    warnings: list[str] = []
    if validation.errors:
        warnings.append(
            f"Source validation report has {len(validation.errors)} errors; "
            "only parsed observations were compared."
        )
    for observation in validation.observations:
        target = plots.get(observation.plot_id)
        if target is None:
            warnings.append(f"plot {observation.plot_id} has no target record")
            continue
        if observation.unit_id != target.unit_id:
            warnings.append(
                f"plot {observation.plot_id} unit {observation.unit_id} differs from "
                f"target unit {target.unit_id}"
            )
        if observation.position != target.position:
            warnings.append(
                f"plot {observation.plot_id} position {observation.position} differs from "
                f"target position {target.position}"
            )
        rows.append(_comparison_row(observation, target))
    if not rows:
        raise ValueError("FIELD-COMPARE-EMPTY: no observations matched plot targets")
    cover_pairs = [
        (row.observed_shrub_cover_pct, row.target_mean_cover_pct)
        for row in rows
        if row.observed_shrub_cover_pct is not None and row.target_mean_cover_pct is not None
    ]
    height_pairs = [
        (row.observed_shrub_height_cm, row.target_max_shrub_height_m)
        for row in rows
        if row.observed_shrub_height_cm is not None and row.target_max_shrub_height_m is not None
    ]
    cover_deltas = [observed - target for observed, target in cover_pairs]
    height_deltas = [observed - target * 100.0 for observed, target in height_pairs]
    cover_observed = [observed for observed, _target in cover_pairs]
    cover_targets = [target for _observed, target in cover_pairs]
    height_observed = [observed for observed, _target in height_pairs]
    height_targets = [target * 100.0 for _observed, target in height_pairs]
    status = _status(len(cover_pairs), len(height_pairs))
    cover_bias = _mean(cover_deltas)
    height_bias = _mean(height_deltas)
    units = [
        _unit_summary(unit_id, [row for row in rows if row.unit_id == unit_id])
        for unit_id in sorted({row.unit_id for row in rows})
    ]
    return FieldComparisonReport(
        source_observations=validation.source_csv,
        source_plots=str(plots_path),
        created_utc=created_utc or datetime.now(UTC),
        status=status,
        observations_compared=len(rows),
        plots_compared=len({row.plot_id for row in rows}),
        rows=rows,
        units=units,
        calibration=FieldCalibrationSuggestion(
            status=status,
            sample_size_cover=len(cover_pairs),
            sample_size_height=len(height_pairs),
            cover_multiplier=_ratio(cover_observed, cover_targets),
            height_multiplier=_ratio(height_observed, height_targets),
        ),
        recommendations=_recommendations(
            rows, status, cover_bias, height_bias, len(cover_pairs), len(height_pairs)
        ),
        warnings=warnings,
        caveats=[
            "Residuals compare different definitions: field plot cover/height versus LiDAR "
            "target surfaces.",
            "Suggested multipliers are review aids, not automatically applied corrections.",
            "No before/after field evidence exists for treatment efficacy or regrowth.",
            "Field evidence is not a survey-grade or safety certification.",
        ],
    )


def compare_field_files(
    observations_path: str | Path,
    plots_path: str | Path,
    created_utc: datetime | None = None,
) -> FieldComparisonReport:
    """Load a validated observation report and compare it with plot targets."""
    return compare_field_data(
        _load_observations(Path(observations_path)),
        plots_path,
        created_utc=created_utc,
    )


def write_field_comparison(report: FieldComparisonReport, path: str | Path) -> Path:
    """Write a field comparison report as JSON."""
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(report.model_dump_json(indent=2) + "\n", encoding="utf-8")
    return destination


__all__ = [
    "FIELD_COMPARISON_SCHEMA_VERSION",
    "ComparisonStatus",
    "FieldCalibrationSuggestion",
    "FieldComparisonReport",
    "FieldComparisonRow",
    "FieldPlotTarget",
    "FieldUnitComparison",
    "compare_field_data",
    "compare_field_files",
    "write_field_comparison",
]
