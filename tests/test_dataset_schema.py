"""Contract tests for the compiled corridor dataset and its validator."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal, cast

import pandas as pd
import pytest
from brushline.cli import app
from brushline.model.schema import (
    ColumnSpec,
    DatasetManifest,
    Provenance,
    TableSpec,
    _dtype_matches,
    _read_table,
    file_sha256,
    load_manifest,
    validate_dataset,
    write_manifest,
)
from pydantic import ValidationError
from typer.testing import CliRunner

RUNNER = CliRunner()


def _columns() -> list[ColumnSpec]:
    return [
        ColumnSpec(name="segment_id", dtype="string"),
        ColumnSpec(name="corridor_id", dtype="string"),
        ColumnSpec(name="length_m", dtype="float64", unit="m"),
        ColumnSpec(name="geometry_wkt", dtype="string"),
    ]


def _frame() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "segment_id": pd.Series(["s1", "s2"], dtype="string"),
            "corridor_id": pd.Series(["c1", "c1"], dtype="string"),
            "length_m": pd.Series([10.0, 20.0], dtype="float64"),
            "geometry_wkt": pd.Series(
                ["LINESTRING (0 0, 10 0)", "LINESTRING (10 0, 30 0)"],
                dtype="string",
            ),
        }
    )


def _build(
    root: Path,
    *,
    frame: pd.DataFrame | None = None,
    table_format: Literal["parquet", "csv"] = "parquet",
    columns: list[ColumnSpec] | None = None,
    primary_key: list[str] | None = None,
) -> DatasetManifest:
    root.mkdir(parents=True, exist_ok=True)
    data = _frame() if frame is None else frame
    table_path = f"segments.{table_format}"
    target = root / table_path
    if table_format == "parquet":
        data.to_parquet(target, index=False)
    else:
        data.to_csv(target, index=False)
    table = TableSpec(
        name="segments",
        path=table_path,
        format=table_format,
        primary_key=primary_key or ["segment_id"],
        columns=columns or _columns(),
        row_count=len(data),
        sha256=file_sha256(target),
    )
    manifest = DatasetManifest(
        dataset_id="test-corridor",
        name="Test corridor",
        description="A tiny dataset for the contract tests.",
        created_utc=datetime.now(UTC),
        crs="EPSG:3005",
        units={"length": "m", "area": "ha"},
        tables=[table],
        provenance=Provenance(
            source="synthetic",
            source_version="1.0",
            licence="CC0-1.0",
            created_by="tests",
        ),
        content_digest="0" * 64,
    )
    manifest.content_digest = manifest.compute_content_digest()
    write_manifest(root, manifest)
    return manifest


def _read_payload(root: Path) -> dict[str, object]:
    # The manifest is JSON at the test boundary, so the payload is dynamically typed here.
    return cast("dict[str, object]", json.loads((root / "manifest.json").read_text()))


def _write_payload(root: Path, payload: dict[str, object]) -> None:
    (root / "manifest.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _first_table(payload: dict[str, object]) -> dict[str, object]:
    # The table list is JSON at the test boundary, so the element is cast here.
    tables = cast("list[dict[str, object]]", payload["tables"])
    return tables[0]


def test_valid_dataset_passes(tmp_path: Path) -> None:
    """A well-formed dataset passes and reports its table row count."""
    root = tmp_path / "dataset"
    _build(root)
    report = validate_dataset(root)
    assert report.is_valid
    assert report.errors == ()
    assert report.tables == {"segments": 2}


def test_missing_manifest_is_named(tmp_path: Path) -> None:
    """A dataset without a manifest fails with DATASET-MANIFEST."""
    report = validate_dataset(tmp_path)
    assert not report.is_valid
    assert any(message.startswith("DATASET-MANIFEST") for message in report.errors)


def test_invalid_manifest_json_is_named(tmp_path: Path) -> None:
    """A manifest that is not JSON fails with DATASET-MANIFEST."""
    (tmp_path / "manifest.json").write_text("{", encoding="utf-8")
    report = validate_dataset(tmp_path)
    assert any(message.startswith("DATASET-MANIFEST") for message in report.errors)


def test_wrong_schema_version_is_rejected(tmp_path: Path) -> None:
    """A manifest with an unknown schema version fails."""
    root = tmp_path / "dataset"
    _build(root)
    payload = _read_payload(root)
    payload["schema_version"] = "brushline.dataset.v0"
    _write_payload(root, payload)
    report = validate_dataset(root)
    assert any(message.startswith("DATASET-SCHEMA") for message in report.errors)


def test_escaping_table_path_is_rejected(tmp_path: Path) -> None:
    """A table path outside the dataset fails."""
    root = tmp_path / "dataset"
    _build(root)
    payload = _read_payload(root)
    _first_table(payload)["path"] = "../segments.parquet"
    _write_payload(root, payload)
    report = validate_dataset(root)
    assert any(message.startswith("DATASET-SCHEMA") for message in report.errors)


def test_missing_table_file_is_named(tmp_path: Path) -> None:
    """A manifest that names a missing table fails with DATASET-TABLE."""
    root = tmp_path / "dataset"
    _build(root)
    (root / "segments.parquet").unlink()
    report = validate_dataset(root)
    assert any(message.startswith("DATASET-TABLE") for message in report.errors)


def test_checksum_mismatch_is_named(tmp_path: Path) -> None:
    """A changed table file fails the checksum check."""
    root = tmp_path / "dataset"
    _build(root)
    payload = _read_payload(root)
    _first_table(payload)["sha256"] = "0" * 64
    _write_payload(root, payload)
    report = validate_dataset(root)
    assert any(message.startswith("DATASET-CHECKSUM") for message in report.errors)


def test_row_count_mismatch_is_named(tmp_path: Path) -> None:
    """A wrong row count fails with DATASET-ROW-COUNT."""
    root = tmp_path / "dataset"
    _build(root)
    payload = _read_payload(root)
    _first_table(payload)["row_count"] = 3
    _write_payload(root, payload)
    report = validate_dataset(root)
    assert any(message.startswith("DATASET-ROW-COUNT") for message in report.errors)


def test_duplicate_primary_key_is_named(tmp_path: Path) -> None:
    """A duplicate primary key fails with DATASET-KEY."""
    root = tmp_path / "dataset"
    frame = _frame()
    frame.loc[1, "segment_id"] = "s1"
    _build(root, frame=frame)
    report = validate_dataset(root)
    assert any(message.startswith("DATASET-KEY") for message in report.errors)


def test_missing_required_column_is_named(tmp_path: Path) -> None:
    """A missing required column fails with DATASET-COLUMN."""
    root = tmp_path / "dataset"
    _build(root, frame=_frame().drop(columns=["segment_id"]))
    report = validate_dataset(root)
    assert any(message.startswith("DATASET-COLUMN") for message in report.errors)


def test_wrong_dtype_is_named(tmp_path: Path) -> None:
    """A wrong column dtype fails with DATASET-DTYPE."""
    root = tmp_path / "dataset"
    frame = _frame()
    frame["length_m"] = pd.Series(["10", "20"], dtype="string")
    _build(root, frame=frame)
    report = validate_dataset(root)
    assert any(message.startswith("DATASET-DTYPE") for message in report.errors)


def test_bad_content_digest_is_named(tmp_path: Path) -> None:
    """A content digest that does not match the manifest fails."""
    root = tmp_path / "dataset"
    _build(root)
    payload = _read_payload(root)
    payload["content_digest"] = "0" * 64
    _write_payload(root, payload)
    report = validate_dataset(root)
    assert any(message.startswith("DATASET-DIGEST") for message in report.errors)


def test_missing_segments_table_is_rejected(tmp_path: Path) -> None:
    """A manifest without the required segments table fails."""
    root = tmp_path / "dataset"
    _build(root)
    payload = _read_payload(root)
    _first_table(payload)["name"] = "not_segments"
    _write_payload(root, payload)
    report = validate_dataset(root)
    assert any(message.startswith("DATASET-SCHEMA") for message in report.errors)


def test_extra_column_is_a_warning(tmp_path: Path) -> None:
    """An undeclared extra column is reported but does not fail the dataset."""
    root = tmp_path / "dataset"
    frame = _frame()
    frame["notes"] = pd.Series(["a", "b"], dtype="string")
    _build(root, frame=frame)
    report = validate_dataset(root)
    assert report.is_valid
    assert any(message.startswith("DATASET-EXTRA-COLUMN") for message in report.warnings)


def test_content_digest_changes_with_content(tmp_path: Path) -> None:
    """The content digest changes when the identifier changes."""
    root = tmp_path / "dataset"
    manifest = _build(root)
    changed = manifest.model_copy(update={"dataset_id": "other-corridor"})
    assert changed.compute_content_digest() != manifest.compute_content_digest()


def test_manifest_round_trips(tmp_path: Path) -> None:
    """The written manifest loads back with the same identity."""
    root = tmp_path / "dataset"
    manifest = _build(root)
    loaded = load_manifest(root)
    assert loaded.dataset_id == manifest.dataset_id
    assert loaded.schema_version == manifest.schema_version


def test_cli_valid_dataset_exits_zero(tmp_path: Path) -> None:
    """The validate command exits zero on a valid dataset."""
    root = tmp_path / "dataset"
    _build(root)
    result = RUNNER.invoke(app, ["validate", "--dataset", str(root)])
    assert result.exit_code == 0
    assert "VALID" in result.stdout


def test_cli_invalid_dataset_exits_one(tmp_path: Path) -> None:
    """The validate command exits one on an invalid dataset."""
    result = RUNNER.invoke(app, ["validate", "--dataset", str(tmp_path)])
    assert result.exit_code == 1
    assert "INVALID" in result.stdout


def test_cli_json_report_is_machine_readable(tmp_path: Path) -> None:
    """The JSON report carries the validity and the table row counts."""
    root = tmp_path / "dataset"
    _build(root)
    result = RUNNER.invoke(app, ["validate", "--dataset", str(root), "--json"])
    payload = json.loads(result.stdout)
    assert payload["is_valid"] is True
    assert payload["tables"] == {"segments": 2}


def test_cli_reports_warnings(tmp_path: Path) -> None:
    """The text report prints a warnings section for an extra column."""
    root = tmp_path / "dataset"
    frame = _frame()
    frame["notes"] = pd.Series(["a", "b"], dtype="string")
    _build(root, frame=frame)
    result = RUNNER.invoke(app, ["validate", "--dataset", str(root)])
    assert result.exit_code == 0
    assert "warnings:" in result.stdout


def test_manifest_table_lookup(tmp_path: Path) -> None:
    """The manifest returns a table by name and raises on an unknown name."""
    manifest = _build(tmp_path / "dataset")
    assert manifest.table("segments").name == "segments"
    with pytest.raises(KeyError):
        manifest.table("missing")


def test_naive_created_utc_is_rejected(tmp_path: Path) -> None:
    """A naive creation time fails the manifest contract."""
    manifest = _build(tmp_path / "dataset")
    payload = manifest.model_dump()
    payload["created_utc"] = datetime(2026, 1, 1)
    with pytest.raises(ValidationError):
        DatasetManifest.model_validate(payload)


def test_table_spec_rejects_empty_and_duplicate_keys(tmp_path: Path) -> None:
    """The table contract rejects an empty key and a repeated key column."""
    manifest = _build(tmp_path / "dataset")
    table = manifest.table("segments")
    for key in ([""], ["segment_id", "segment_id"]):
        payload = table.model_dump()
        payload["primary_key"] = key
        with pytest.raises(ValidationError):
            TableSpec.model_validate(payload)


def test_table_spec_rejects_duplicate_columns(tmp_path: Path) -> None:
    """The table contract rejects two columns with the same name."""
    manifest = _build(tmp_path / "dataset")
    table = manifest.table("segments")
    payload = table.model_dump()
    payload["columns"] = [table.columns[0].model_dump(), table.columns[0].model_dump()]
    with pytest.raises(ValidationError):
        TableSpec.model_validate(payload)


def test_manifest_rejects_duplicate_table_names(tmp_path: Path) -> None:
    """The manifest rejects two tables with the same name."""
    manifest = _build(tmp_path / "dataset")
    table = manifest.table("segments")
    payload = manifest.model_dump()
    payload["tables"] = [table.model_dump(), table.model_dump()]
    with pytest.raises(ValidationError):
        DatasetManifest.model_validate(payload)


def test_null_primary_key_is_named(tmp_path: Path) -> None:
    """A null primary key fails with DATASET-KEY."""
    root = tmp_path / "dataset"
    frame = _frame()
    frame.loc[0, "segment_id"] = pd.NA
    _build(root, frame=frame)
    report = validate_dataset(root)
    assert any(message.startswith("DATASET-KEY") for message in report.errors)


def test_csv_table_is_supported(tmp_path: Path) -> None:
    """A CSV table validates through the same contract."""
    root = tmp_path / "dataset"
    _build(root, table_format="csv")
    report = validate_dataset(root)
    assert report.is_valid
    assert report.tables == {"segments": 2}


def test_unsupported_table_format_is_rejected(tmp_path: Path) -> None:
    """The reader refuses an unsupported format."""
    with pytest.raises(ValueError, match="unsupported"):
        _read_table(tmp_path / "table", "json")


def test_dtype_matches_bool_datetime_date_and_unknown() -> None:
    """The logical dtype checker covers bool, datetime, date, and an unknown type."""
    assert _dtype_matches(pd.Series([True, False]), "bool")
    assert _dtype_matches(pd.Series(pd.to_datetime(["2026-01-01"])), "datetime")
    assert _dtype_matches(pd.Series(["2026-01-01"], dtype=object), "date")
    assert not _dtype_matches(pd.Series([1.0]), "decimal")
