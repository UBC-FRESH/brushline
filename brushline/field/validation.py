"""Validation and normalization for field observations."""

from __future__ import annotations

import csv
import json
import math
from collections.abc import Mapping
from datetime import date
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

FIELD_SCHEMA_VERSION: Literal["brushline.field-observation.v1"] = "brushline.field-observation.v1"
FIELD_VALIDATION_SCHEMA_VERSION: Literal["brushline.field-validation.v1"] = (
    "brushline.field-validation.v1"
)

FIELD_COLUMNS: tuple[str, ...] = (
    "plot_id",
    "visit_date",
    "observer",
    "unit_id",
    "position",
    "latitude",
    "longitude",
    "gps_accuracy_m",
    "shrub_species",
    "shrub_height_cm",
    "shrub_cover_pct",
    "shrub_stems",
    "recent_cut",
    "cut_height_cm",
    "row_width_m",
    "tree_species",
    "tree_height_m",
    "tree_distance_m",
    "conductor_clearance_m",
    "photo_ids",
    "notes",
)

_REQUIRED_COLUMNS = frozenset({"plot_id", "visit_date", "observer", "unit_id", "position"})
_TRUE_VALUES = frozenset({"1", "true", "t", "yes", "y"})
_FALSE_VALUES = frozenset({"0", "false", "f", "no", "n"})


class FieldObservation(BaseModel):
    """One normalized field-plot observation.

    Attributes
    ----------
    schema_version : {"brushline.field-observation.v1"}
        Observation schema.
    plot_id : str
        Planned plot identifier.
    visit_date : datetime.date
        Field visit date.
    observer : str
        Observer or crew lead.
    unit_id : str
        Planned corridor treatment unit.
    position : {"center", "edge"}
        Plot position within the corridor.
    latitude, longitude : float
        WGS84 coordinates.
    gps_accuracy_m : float, optional
        Receiver accuracy.
    shrub_height_cm, shrub_cover_pct, shrub_stems : float or int, optional
        Dominant shrub-layer measurements.
    recent_cut : bool, optional
        Whether recent cutting was visible.
    cut_height_cm : float, optional
        Stubble height where recent cutting was visible.
    row_width_m : float, optional
        Measured maintained right-of-way width.
    tree_species : str, optional
        Dominant tree at the plot.
    tree_height_m, tree_distance_m, conductor_clearance_m : float, optional
        Tree and clearance measurements.
    photo_ids : list of str
        Photo file identifiers.
    notes : str
        Free text.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["brushline.field-observation.v1"] = FIELD_SCHEMA_VERSION
    plot_id: str = Field(min_length=1)
    visit_date: date
    observer: str = Field(min_length=1)
    unit_id: str = Field(min_length=1)
    position: Literal["center", "edge"]
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    gps_accuracy_m: float | None = Field(default=None, ge=0)
    shrub_species: str | None = None
    shrub_height_cm: float | None = Field(default=None, ge=0, le=500)
    shrub_cover_pct: float | None = Field(default=None, ge=0, le=100)
    shrub_stems: int | None = Field(default=None, ge=0, le=100000)
    recent_cut: bool | None = None
    cut_height_cm: float | None = Field(default=None, ge=0, le=200)
    row_width_m: float | None = Field(default=None, ge=0, le=300)
    tree_species: str | None = None
    tree_height_m: float | None = Field(default=None, ge=0, le=150)
    tree_distance_m: float | None = Field(default=None, ge=0, le=200)
    conductor_clearance_m: float | None = Field(default=None, ge=-20, le=200)
    photo_ids: list[str] = Field(default_factory=list)
    notes: str = ""


class FieldPlotReference(BaseModel):
    """Planned plot location used to cross-check a field observation."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    plot_id: str = Field(min_length=1)
    unit_id: str = Field(min_length=1)
    position: Literal["center", "edge"]
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)


class FieldValidationReport(BaseModel):
    """Normalized field observations plus validation findings."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["brushline.field-validation.v1"] = FIELD_VALIDATION_SCHEMA_VERSION
    source_csv: str
    source_plots: str
    valid: bool
    plots_expected: int
    observations: list[FieldObservation]
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


def _value(row: Mapping[str, str], key: str) -> str:
    value = row.get(key)
    return "" if value is None else value.strip()


def _optional(row: Mapping[str, str], key: str) -> str | None:
    value = _value(row, key)
    return value or None


def _photo_ids(row: Mapping[str, str]) -> list[str]:
    raw = _value(row, "photo_ids").replace(";", ",")
    return [item.strip() for item in raw.split(",") if item.strip()]


def _optional_bool(row: Mapping[str, str], key: str, errors: list[str]) -> bool | None:
    value = _value(row, key).lower()
    if not value:
        return None
    if value in _TRUE_VALUES:
        return True
    if value in _FALSE_VALUES:
        return False
    errors.append(f"{key}: expected yes/no/true/false, got {value!r}")
    return None


def _payload(row: Mapping[str, str], errors: list[str]) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "plot_id": _value(row, "plot_id"),
        "visit_date": _value(row, "visit_date"),
        "observer": _value(row, "observer"),
        "unit_id": _value(row, "unit_id"),
        "position": _value(row, "position").lower(),
        "latitude": _value(row, "latitude"),
        "longitude": _value(row, "longitude"),
        "shrub_species": _optional(row, "shrub_species"),
        "tree_species": _optional(row, "tree_species"),
        "photo_ids": _photo_ids(row),
        "notes": _value(row, "notes"),
        "recent_cut": _optional_bool(row, "recent_cut", errors),
    }
    for key in (
        "gps_accuracy_m",
        "shrub_height_cm",
        "shrub_cover_pct",
        "shrub_stems",
        "cut_height_cm",
        "row_width_m",
        "tree_height_m",
        "tree_distance_m",
        "conductor_clearance_m",
    ):
        payload[key] = _optional(row, key)
    return payload


def _read_csv(path: Path) -> tuple[list[dict[str, str]], list[str], list[str]]:
    errors: list[str] = []
    if not path.exists():
        return [], [f"FIELD-FILE: observations file does not exist: {path}"], []
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        headers = tuple(reader.fieldnames or ())
        missing = sorted(_REQUIRED_COLUMNS.difference(headers))
        if missing:
            errors.append(f"FIELD-CSV: missing required columns: {', '.join(missing)}")
        rows = list(reader)
    if not rows:
        errors.append("FIELD-CSV: observations CSV has no data rows")
    return rows, errors, list(headers)


def _load_plots(path: Path) -> dict[str, FieldPlotReference]:
    if not path.exists():
        raise ValueError(f"FIELD-PLOTS: plots file does not exist: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    features = data.get("features")
    if not isinstance(features, list):
        raise ValueError("FIELD-PLOTS: plots file must be a GeoJSON FeatureCollection")
    plots: dict[str, FieldPlotReference] = {}
    for feature in features:
        if not isinstance(feature, dict):
            continue
        geometry = feature.get("geometry")
        properties = feature.get("properties")
        if not isinstance(geometry, dict) or not isinstance(properties, dict):
            continue
        if geometry.get("type") != "Point" or not properties.get("plot_id"):
            continue
        coordinates = geometry.get("coordinates")
        if not isinstance(coordinates, list) or len(coordinates) < 2:
            continue
        try:
            plot = FieldPlotReference.model_validate(
                {
                    "plot_id": properties.get("plot_id"),
                    "unit_id": properties.get("unit_id"),
                    "position": properties.get("position"),
                    "longitude": coordinates[0],
                    "latitude": coordinates[1],
                }
            )
        except ValidationError as exc:
            raise ValueError(f"FIELD-PLOTS: invalid plot reference: {exc}") from exc
        plots[plot.plot_id] = plot
    if not plots:
        raise ValueError("FIELD-PLOTS: plots file has no point features")
    return plots


def _distance_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius = 6371008.8
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * radius * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _validation_error(error: ValidationError) -> str:
    details = []
    for item in error.errors():
        location = ".".join(str(part) for part in item.get("loc", ()))
        message = item.get("msg", "invalid value")
        details.append(f"{location}: {message}" if location else str(message))
    return "; ".join(details)


def validate_field_csv(csv_path: str | Path, plots_path: str | Path) -> FieldValidationReport:
    """Validate a field-observation CSV against planned plot references.

    Parameters
    ----------
    csv_path : str or Path
        CSV exported from the field kit.
    plots_path : str or Path
        GeoJSON FeatureCollection of planned plot points.

    Returns
    -------
    FieldValidationReport
        Normalized observations, errors, and warnings.

    Raises
    ------
    ValueError
        If the plots file cannot be read or has no point features.
    """
    observations_path = Path(csv_path)
    references_path = Path(plots_path)
    plots = _load_plots(references_path)
    rows, errors, _headers = _read_csv(observations_path)
    observations: list[FieldObservation] = []
    warnings: list[str] = []
    seen: set[tuple[str, date]] = set()
    for row_number, row in enumerate(rows, start=2):
        row_errors: list[str] = []
        payload = _payload(row, row_errors)
        if row_errors:
            errors.extend(f"row {row_number}: FIELD-VALUE: {message}" for message in row_errors)
            continue
        try:
            observation = FieldObservation.model_validate(payload)
        except ValidationError as exc:
            errors.append(f"row {row_number}: FIELD-VALUE: {_validation_error(exc)}")
            continue
        observations.append(observation)
        key = (observation.plot_id, observation.visit_date)
        if key in seen:
            errors.append(
                f"row {row_number}: FIELD-DUPLICATE: duplicate observation for "
                f"{observation.plot_id} on {observation.visit_date}"
            )
        seen.add(key)
        reference = plots.get(observation.plot_id)
        if reference is None:
            errors.append(f"row {row_number}: FIELD-PLOT: unknown plot_id {observation.plot_id!r}")
            continue
        if observation.unit_id != reference.unit_id:
            errors.append(
                f"row {row_number}: FIELD-UNIT: unit_id {observation.unit_id!r} does not match "
                f"planned {reference.unit_id!r}"
            )
        if observation.position != reference.position:
            errors.append(
                f"row {row_number}: FIELD-POSITION: position {observation.position!r} does not "
                f"match planned {reference.position!r}"
            )
        distance = _distance_m(
            observation.latitude,
            observation.longitude,
            reference.latitude,
            reference.longitude,
        )
        if distance > 50:
            errors.append(
                f"row {row_number}: FIELD-GPS: coordinates are {distance:.1f} m from the "
                "planned plot"
            )
        elif distance > 25:
            warnings.append(
                f"row {row_number}: FIELD-GPS: coordinates are {distance:.1f} m from the "
                "planned plot"
            )
        if not observation.photo_ids:
            warnings.append(f"row {row_number}: no photo_ids recorded")
        if observation.shrub_height_cm is None or observation.shrub_cover_pct is None:
            warnings.append(f"row {row_number}: shrub height/cover is incomplete")
    if not observations and not errors:
        errors.append("FIELD-CSV: no valid observations were parsed")
    return FieldValidationReport(
        source_csv=str(observations_path),
        source_plots=str(references_path),
        valid=not errors,
        plots_expected=len(plots),
        observations=observations,
        errors=errors,
        warnings=warnings,
    )


def write_field_validation(report: FieldValidationReport, path: str | Path) -> Path:
    """Write a normalized field-validation report as JSON."""
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(report.model_dump_json(indent=2) + "\n", encoding="utf-8")
    return destination


__all__ = [
    "FIELD_COLUMNS",
    "FIELD_SCHEMA_VERSION",
    "FIELD_VALIDATION_SCHEMA_VERSION",
    "FieldObservation",
    "FieldPlotReference",
    "FieldValidationReport",
    "validate_field_csv",
    "write_field_validation",
]
