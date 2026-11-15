"""Tests for field-versus-LiDAR comparison."""

from __future__ import annotations

import json
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Literal

import pytest
from brushline.cli import app
from brushline.field.comparison import compare_field_data, compare_field_files
from brushline.field.validation import (
    FieldObservation,
    FieldValidationReport,
)
from typer.testing import CliRunner

RUNNER = CliRunner()
CREATED = datetime(2026, 11, 20, tzinfo=UTC)


def _observation(
    plot_id: str,
    unit_id: str,
    position: Literal["center", "edge"],
    cover: float | None,
    height_cm: float | None,
    recent_cut: bool | None = None,
) -> FieldObservation:
    return FieldObservation(
        plot_id=plot_id,
        visit_date=date(2026, 11, 20),
        observer="field crew",
        unit_id=unit_id,
        position=position,
        latitude=49.27,
        longitude=-122.60,
        shrub_cover_pct=cover,
        shrub_height_cm=height_cm,
        recent_cut=recent_cut,
    )


def _validation(observations: list[FieldObservation]) -> FieldValidationReport:
    return FieldValidationReport(
        source_csv="field.csv",
        source_plots="plots.geojson",
        valid=True,
        plots_expected=len(observations),
        observations=observations,
    )


def _plots(path: Path) -> Path:
    features = []
    for plot_id, unit_id, position, cover, height, year in (
        ("P1", "U1", "center", 20, 1.0, 2027),
        ("P2", "U1", "edge", 30, 2.0, 2027),
        ("P3", "U2", "center", 40, 3.0, 2028),
    ):
        features.append(
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [-122.60, 49.27]},
                "properties": {
                    "plot_id": plot_id,
                    "unit_id": unit_id,
                    "position": position,
                    "planned_year": year,
                    "target_mean_cover_pct": cover,
                    "target_max_shrub_height_m": height,
                },
            }
        )
    path.write_text(
        json.dumps({"type": "FeatureCollection", "features": features}),
        encoding="utf-8",
    )
    return path


def test_compare_field_data_residuals_and_units(tmp_path: Path) -> None:
    validation = _validation(
        [
            _observation("P1", "U1", "center", 25, 80, recent_cut=True),
            _observation("P2", "U1", "edge", 25, 180),
            _observation("P3", "U2", "center", 50, 350),
        ]
    )
    report = compare_field_data(validation, _plots(tmp_path / "plots.geojson"), CREATED)
    assert report.status == "provisional"
    assert report.observations_compared == 3
    assert report.plots_compared == 3
    assert report.calibration.cover_multiplier == pytest.approx(1.111)
    assert report.calibration.height_multiplier == pytest.approx(1.017)
    assert report.calibration.treatment_response_status == "not_tested"
    assert report.rows[0].cover_delta_pct == 5.0
    assert report.rows[0].height_delta_cm == -20.0
    assert report.units[0].unit_id == "U1"
    assert report.units[0].n_plots == 2
    assert any("observed cutting" in item for item in report.recommendations)
    assert report.created_utc == CREATED


def test_compare_field_data_marks_missing_metrics_and_unknown_plots(tmp_path: Path) -> None:
    validation = _validation(
        [
            _observation("P1", "U1", "center", None, 80),
            _observation("P2", "U1", "edge", 25, None),
            _observation("MISSING", "U1", "center", 10, 10),
        ]
    )
    report = compare_field_data(validation, _plots(tmp_path / "plots.geojson"), CREATED)
    assert report.observations_compared == 2
    assert report.status == "insufficient"
    assert report.calibration.sample_size_cover == 1
    assert report.calibration.sample_size_height == 1
    assert report.rows[0].status == "partial"
    assert any("MISSING" in warning for warning in report.warnings)
    assert any("more complete" in item for item in report.recommendations)


def test_compare_files_and_errors(tmp_path: Path) -> None:
    validation = _validation([_observation("P1", "U1", "center", 25, 80)])
    observations = tmp_path / "validated.json"
    observations.write_text(validation.model_dump_json(indent=2), encoding="utf-8")
    report = compare_field_files(observations, _plots(tmp_path / "plots.geojson"), CREATED)
    assert report.status == "insufficient"
    with pytest.raises(ValueError, match="FIELD-COMPARE-OBSERVATIONS"):
        compare_field_files(tmp_path / "missing.json", tmp_path / "plots.geojson")
    with pytest.raises(ValueError, match="FIELD-COMPARE-PLOTS"):
        compare_field_files(observations, tmp_path / "missing.geojson")


def test_compare_cli(tmp_path: Path) -> None:
    validation = _validation([_observation("P1", "U1", "center", 25, 80)])
    observations = tmp_path / "validated.json"
    observations.write_text(validation.model_dump_json(indent=2), encoding="utf-8")
    plots = _plots(tmp_path / "plots.geojson")
    out = tmp_path / "comparison.json"
    result = RUNNER.invoke(
        app,
        [
            "field",
            "compare",
            "--observations",
            str(observations),
            "--plots",
            str(plots),
            "--out",
            str(out),
        ],
    )
    assert result.exit_code == 0
    assert out.exists()
    assert "cover_multiplier" in result.stdout
    result = RUNNER.invoke(
        app,
        ["field", "compare", "--observations", str(tmp_path / "bad.json"), "--plots", str(plots)],
    )
    assert result.exit_code == 1
    assert "FIELD-COMPARE-OBSERVATIONS" in result.stderr


def test_compare_status_adequate_and_bias_recommendations(tmp_path: Path) -> None:
    features = []
    observations = []
    for index in range(8):
        plot_id = f"A{index}"
        features.append(
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [-122.6, 49.27]},
                "properties": {
                    "plot_id": plot_id,
                    "unit_id": "U1",
                    "position": "center",
                    "planned_year": 2027,
                    "target_mean_cover_pct": 10.0,
                    "target_max_shrub_height_m": 1.0,
                },
            }
        )
        observations.append(_observation(plot_id, "U1", "center", 50, 300, recent_cut=False))
    plots = tmp_path / "plots.geojson"
    plots.write_text(
        json.dumps({"type": "FeatureCollection", "features": features}),
        encoding="utf-8",
    )
    report = compare_field_data(_validation(observations), plots, CREATED)
    assert report.status == "adequate"
    assert report.calibration.sample_size_cover == 8
    assert report.calibration.sample_size_height == 8
    assert any("underestimates shrub cover" in item for item in report.recommendations)
    assert any("underestimates shrub height" in item for item in report.recommendations)
