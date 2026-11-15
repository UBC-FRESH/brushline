"""Tests for field-observation validation."""

from __future__ import annotations

import csv
import json
from pathlib import Path

from brushline.cli import app
from brushline.field.validation import (
    FIELD_COLUMNS,
    validate_field_csv,
    write_field_validation,
)
from typer.testing import CliRunner

RUNNER = CliRunner()
PLOT = {
    "plot_id": "SW01-C1",
    "unit_id": "SW-01",
    "position": "center",
    "latitude": 49.2708,
    "longitude": -122.6000,
}


def _plots(path: Path) -> Path:
    path.write_text(
        json.dumps(
            {
                "type": "FeatureCollection",
                "features": [
                    {
                        "type": "Feature",
                        "geometry": {
                            "type": "Point",
                            "coordinates": [PLOT["longitude"], PLOT["latitude"]],
                        },
                        "properties": {
                            "plot_id": PLOT["plot_id"],
                            "unit_id": PLOT["unit_id"],
                            "position": PLOT["position"],
                        },
                    },
                    {
                        "type": "Feature",
                        "geometry": {"type": "Point", "coordinates": [-122.6, 49.27]},
                        "properties": {"feature_type": "tower", "tower_id": "t1"},
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    return path


def _row(**updates: object) -> dict[str, object]:
    row: dict[str, object] = {
        "plot_id": "SW01-C1",
        "visit_date": "2026-11-20",
        "observer": "field crew",
        "unit_id": "SW-01",
        "position": "center",
        "latitude": 49.2708,
        "longitude": -122.6000,
        "gps_accuracy_m": 4,
        "shrub_species": "salal",
        "shrub_height_cm": 120,
        "shrub_cover_pct": 35,
        "shrub_stems": 40,
        "recent_cut": "yes",
        "cut_height_cm": 12,
        "row_width_m": 70,
        "tree_species": "Douglas-fir",
        "tree_height_m": 28,
        "tree_distance_m": 18,
        "conductor_clearance_m": 12,
        "photo_ids": "SW01-C1_20261120_01.jpg",
        "notes": "test plot",
    }
    row.update(updates)
    return row


def _csv(path: Path, rows: list[dict[str, object]]) -> Path:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELD_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    return path


def test_valid_field_csv_and_normalized_output(tmp_path: Path) -> None:
    csv_path = _csv(tmp_path / "field.csv", [_row()])
    report = validate_field_csv(csv_path, _plots(tmp_path / "plots.geojson"))
    assert report.valid
    assert report.plots_expected == 1
    assert len(report.observations) == 1
    assert report.observations[0].recent_cut is True
    assert report.observations[0].photo_ids == ["SW01-C1_20261120_01.jpg"]
    output = write_field_validation(report, tmp_path / "validated.json")
    data = json.loads(output.read_text(encoding="utf-8"))
    assert data["valid"] is True
    assert data["observations"][0]["plot_id"] == "SW01-C1"


def test_field_csv_warns_for_distance_and_missing_photos(tmp_path: Path) -> None:
    row = _row(latitude=49.2711, photo_ids="", shrub_height_cm="", shrub_cover_pct="")
    report = validate_field_csv(
        _csv(tmp_path / "field.csv", [row]), _plots(tmp_path / "plots.geojson")
    )
    assert report.valid
    assert any("planned plot" in warning for warning in report.warnings)
    assert any("no photo_ids" in warning for warning in report.warnings)
    assert any("shrub height/cover" in warning for warning in report.warnings)


def test_field_csv_rejects_bad_rows_and_bad_values(tmp_path: Path) -> None:
    plots = _plots(tmp_path / "plots.geojson")
    rows = [
        _row(plot_id="MISSING"),
        _row(plot_id="SW01-C1", unit_id="SW-99"),
        _row(plot_id="SW01-C1", latitude=49.28),
        _row(plot_id="SW01-C1", recent_cut="maybe"),
        _row(plot_id="SW01-C1", visit_date="not-a-date"),
    ]
    report = validate_field_csv(_csv(tmp_path / "field.csv", rows), plots)
    assert not report.valid
    assert any(error.startswith("row 2: FIELD-PLOT") for error in report.errors)
    assert any("unknown plot_id" in error for error in report.errors)
    assert any("does not match planned" in error for error in report.errors)
    assert any("planned plot" in error for error in report.errors)
    assert any("recent_cut" in error for error in report.errors)
    assert any("visit_date" in error for error in report.errors)


def test_field_csv_duplicate_and_missing_columns(tmp_path: Path) -> None:
    plots = _plots(tmp_path / "plots.geojson")
    duplicate = _csv(tmp_path / "duplicate.csv", [_row(), _row()])
    report = validate_field_csv(duplicate, plots)
    assert not report.valid
    assert any("duplicate observation" in error for error in report.errors)
    incomplete = tmp_path / "incomplete.csv"
    incomplete.write_text("plot_id,visit_date\nSW01-C1,2026-11-20\n", encoding="utf-8")
    report = validate_field_csv(incomplete, plots)
    assert not report.valid
    assert any("missing required columns" in error for error in report.errors)


def test_field_cli_valid_and_invalid(tmp_path: Path) -> None:
    plots = _plots(tmp_path / "plots.geojson")
    valid = _csv(tmp_path / "valid.csv", [_row()])
    output = tmp_path / "out.json"
    result = RUNNER.invoke(
        app,
        [
            "field",
            "validate",
            "--csv",
            str(valid),
            "--plots",
            str(plots),
            "--out",
            str(output),
        ],
    )
    assert result.exit_code == 0
    assert output.exists()
    assert "VALID" in result.stdout
    invalid = _csv(tmp_path / "invalid.csv", [_row(plot_id="MISSING")])
    result = RUNNER.invoke(
        app,
        ["field", "validate", "--csv", str(invalid), "--plots", str(plots), "--json"],
    )
    assert result.exit_code == 1
    assert "MISSING" in result.stdout
