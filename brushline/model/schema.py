"""Compiled corridor dataset contract and validator.

The dataset is the boundary between ingestion and execution. A dataset directory contains a
``manifest.json`` and one file per table. The manifest names the schema version, the CRS, the units,
the tables, their column contracts, their checksums, and the provenance. The validator checks the
manifest, the table files, the schemas, the keys, the row counts, the checksums, and the content
digest.

The contract is deliberately small in P1.1. The full segment, state, treatment, observation, plan,
run, archive, and timeline tables are added by P1.2 to P1.4.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Literal

import pandas as pd
from pandas.api import types as ptypes
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

DATASET_SCHEMA_VERSION: Literal["brushline.dataset.v1"] = "brushline.dataset.v1"
MANIFEST_NAME: str = "manifest.json"
TABLE_FORMATS: tuple[str, ...] = ("parquet", "csv")
COLUMN_DTYPES: tuple[str, ...] = ("string", "int64", "float64", "bool", "datetime", "date")
REQUIRED_TABLES: tuple[str, ...] = ("segments",)

DType = Literal["string", "int64", "float64", "bool", "datetime", "date"]
TableFormat = Literal["parquet", "csv"]


def file_sha256(path: Path) -> str:
    """Return the SHA-256 digest of a file.

    Parameters
    ----------
    path : Path
        File to hash.

    Returns
    -------
    str
        Lowercase hexadecimal SHA-256 digest.
    """
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


@dataclass(frozen=True)
class DatasetValidation:
    """The outcome of validating one compiled dataset.

    Parameters
    ----------
    dataset : Path
        Resolved dataset directory.
    errors : tuple of str
        Named errors. An empty tuple means the dataset is valid.
    warnings : tuple of str
        Non-fatal findings.
    tables : dict of str to int
        Row count per table that could be read.
    """

    dataset: Path
    errors: tuple[str, ...]
    warnings: tuple[str, ...]
    tables: dict[str, int]

    @property
    def is_valid(self) -> bool:
        """Return whether the dataset passed every check.

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
            The dataset path, validity, errors, warnings, and table row counts.
        """
        return {
            "dataset": str(self.dataset),
            "is_valid": self.is_valid,
            "errors": list(self.errors),
            "warnings": list(self.warnings),
            "tables": dict(sorted(self.tables.items())),
        }


class ColumnSpec(BaseModel):
    """One column in a dataset table.

    Parameters
    ----------
    name : str
        Column name.
    dtype : {"string", "int64", "float64", "bool", "datetime", "date"}
        Logical column type.
    required : bool, optional
        Whether the column must be present. Defaults to ``True``.
    unit : str or None, optional
        Physical unit, when the column has one.
    description : str, optional
        Short human description.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str = Field(min_length=1)
    dtype: DType
    required: bool = True
    unit: str | None = None
    description: str = ""


class TableSpec(BaseModel):
    """One table in a compiled dataset.

    Parameters
    ----------
    name : str
        Logical table name.
    path : str
        Dataset-relative file path.
    format : {"parquet", "csv"}
        File format.
    primary_key : list of str
        Columns that form the primary key.
    columns : list of ColumnSpec
        Column contracts.
    row_count : int
        Expected row count.
    sha256 : str
        Expected SHA-256 of the table file.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str = Field(min_length=1)
    path: str = Field(min_length=1)
    format: TableFormat
    primary_key: list[str] = Field(min_length=1)
    columns: list[ColumnSpec] = Field(min_length=1)
    row_count: int = Field(ge=0)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

    @field_validator("path")
    @classmethod
    def _relative_path(cls, value: str) -> str:
        candidate = Path(value)
        if candidate.is_absolute() or ".." in candidate.parts:
            raise ValueError("table path must be relative and stay inside the dataset")
        return value

    @field_validator("primary_key")
    @classmethod
    def _non_empty_key(cls, value: list[str]) -> list[str]:
        if any(not name for name in value):
            raise ValueError("primary key column names must not be empty")
        if len(set(value)) != len(value):
            raise ValueError("primary key columns must be unique")
        return value

    @field_validator("columns")
    @classmethod
    def _unique_columns(cls, value: list[ColumnSpec]) -> list[ColumnSpec]:
        names = [column.name for column in value]
        if len(set(names)) != len(names):
            raise ValueError("column names must be unique")
        return value


class Provenance(BaseModel):
    """The provenance of a compiled dataset.

    Parameters
    ----------
    source : str
        Source name.
    source_version : str
        Source version or vintage.
    licence : str
        Licence identifier.
    created_by : str
        Person, process, or agent that built the dataset.
    configuration : dict of str to object, optional
        Build configuration values.
    model_cards : list of str, optional
        Model-card identifiers used to derive attributes.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    source: str = Field(min_length=1)
    source_version: str = Field(min_length=1)
    licence: str = Field(min_length=1)
    created_by: str = Field(min_length=1)
    configuration: dict[str, object] = Field(default_factory=dict)
    model_cards: list[str] = Field(default_factory=list)


class DatasetManifest(BaseModel):
    """The manifest of a compiled corridor dataset.

    Parameters
    ----------
    dataset_id : str
        Stable dataset identifier.
    name : str
        Human-readable dataset name.
    description : str
        Short description.
    created_utc : datetime
        Timezone-aware creation time.
    crs : str
        Coordinate reference system.
    units : dict of str to str
        Named units, such as ``length`` and ``area``.
    tables : list of TableSpec
        Table contracts. The ``segments`` table is required.
    provenance : Provenance
        Source and build provenance.
    content_digest : str
        SHA-256 of the canonical content fields.
    """

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["brushline.dataset.v1"] = DATASET_SCHEMA_VERSION
    dataset_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    description: str = ""
    created_utc: datetime
    crs: str = Field(min_length=1)
    units: dict[str, str] = Field(min_length=1)
    tables: list[TableSpec] = Field(min_length=1)
    provenance: Provenance
    content_digest: str = Field(pattern=r"^[0-9a-f]{64}$")

    @field_validator("created_utc")
    @classmethod
    def _timezone_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("created_utc must be timezone-aware")
        return value

    @field_validator("tables")
    @classmethod
    def _required_tables(cls, value: list[TableSpec]) -> list[TableSpec]:
        names = [table.name for table in value]
        if len(set(names)) != len(names):
            raise ValueError("table names must be unique")
        missing = [name for name in REQUIRED_TABLES if name not in names]
        if missing:
            raise ValueError(f"required table(s) missing: {', '.join(missing)}")
        return value

    def table(self, name: str) -> TableSpec:
        """Return one table spec by name.

        Parameters
        ----------
        name : str
            Table name.

        Returns
        -------
        TableSpec
            The matching table spec.

        Raises
        ------
        KeyError
            When the table is not in the manifest.
        """
        for table in self.tables:
            if table.name == name:
                return table
        raise KeyError(name)

    def compute_content_digest(self) -> str:
        """Return the canonical content digest of the manifest.

        The digest covers the schema version, dataset id, CRS, and the table contracts. It does not
        cover ``created_utc`` or the human-readable name and description, so a rebuild with the same
        content keeps the same digest.

        Returns
        -------
        str
            Lowercase hexadecimal SHA-256 digest.
        """
        payload = {
            "schema_version": self.schema_version,
            "dataset_id": self.dataset_id,
            "crs": self.crs,
            "tables": [
                {
                    "name": table.name,
                    "path": table.path,
                    "format": table.format,
                    "primary_key": list(table.primary_key),
                    "row_count": table.row_count,
                    "sha256": table.sha256,
                    "columns": [
                        {
                            "name": column.name,
                            "dtype": column.dtype,
                            "required": column.required,
                            "unit": column.unit,
                        }
                        for column in table.columns
                    ],
                }
                for table in sorted(self.tables, key=lambda item: item.name)
            ],
        }
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()


def load_manifest(root: Path) -> DatasetManifest:
    """Load and validate a dataset manifest.

    Parameters
    ----------
    root : Path
        Dataset directory.

    Returns
    -------
    DatasetManifest
        The parsed manifest.

    Raises
    ------
    FileNotFoundError
        When the manifest file does not exist.
    pydantic.ValidationError
        When the manifest does not satisfy the contract.
    """
    path = Path(root).expanduser().resolve() / MANIFEST_NAME
    return DatasetManifest.model_validate_json(path.read_text(encoding="utf-8"))


def write_manifest(root: Path, manifest: DatasetManifest) -> Path:
    """Write a dataset manifest as sorted, indented JSON.

    Parameters
    ----------
    root : Path
        Dataset directory.
    manifest : DatasetManifest
        Manifest to write.

    Returns
    -------
    Path
        Path of the written manifest.
    """
    path = Path(root).expanduser().resolve() / MANIFEST_NAME
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = manifest.model_dump(mode="json")
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def validate_dataset(root: Path) -> DatasetValidation:
    """Validate a compiled dataset against its manifest.

    Parameters
    ----------
    root : Path
        Dataset directory.

    Returns
    -------
    DatasetValidation
        Errors, warnings, and table row counts. The dataset is valid when ``errors`` is empty.
    """
    resolved = Path(root).expanduser().resolve()
    errors: list[str] = []
    warnings: list[str] = []
    tables: dict[str, int] = {}
    manifest_path = resolved / MANIFEST_NAME
    if not manifest_path.is_file():
        return DatasetValidation(
            resolved,
            (f"DATASET-MANIFEST: no {MANIFEST_NAME} in {resolved}",),
            (),
            {},
        )
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        return DatasetValidation(
            resolved,
            (f"DATASET-MANIFEST: cannot read {MANIFEST_NAME}: {exc}",),
            (),
            {},
        )
    try:
        manifest = DatasetManifest.model_validate(payload)
    except ValidationError as exc:
        return DatasetValidation(resolved, _format_validation_error(exc), (), {})
    if manifest.compute_content_digest() != manifest.content_digest:
        errors.append("DATASET-DIGEST: content_digest does not match the canonical content fields")
    for table in manifest.tables:
        path = (resolved / table.path).resolve()
        if not path.is_relative_to(resolved):
            errors.append(f"DATASET-PATH: {table.name} escapes the dataset: {table.path}")
            continue
        if not path.is_file():
            errors.append(f"DATASET-TABLE: {table.name} is missing: {table.path}")
            continue
        try:
            frame = _read_table(path, table.format)
        except (OSError, ValueError, pd.errors.ParserError) as exc:
            errors.append(f"DATASET-TABLE: {table.name} cannot be read: {exc}")
            continue
        tables[table.name] = len(frame)
        _validate_columns(table, frame, errors, warnings)
        _validate_primary_key(table, frame, errors)
        if len(frame) != table.row_count:
            errors.append(
                f"DATASET-ROW-COUNT: {table.name} has {len(frame)} rows, expected {table.row_count}"
            )
        digest = file_sha256(path)
        if digest != table.sha256:
            errors.append(
                f"DATASET-CHECKSUM: {table.name} sha256 is {digest}, expected {table.sha256}"
            )
    return DatasetValidation(resolved, tuple(errors), tuple(warnings), tables)


def _format_validation_error(exc: ValidationError) -> tuple[str, ...]:
    """Render Pydantic validation errors as named dataset errors.

    Parameters
    ----------
    exc : pydantic.ValidationError
        The validation error.

    Returns
    -------
    tuple of str
        One ``DATASET-SCHEMA`` error per Pydantic error.
    """
    messages: list[str] = []
    for item in exc.errors():
        location = ".".join(str(part) for part in item["loc"])
        messages.append(f"DATASET-SCHEMA: {location}: {item['msg']}")
    return tuple(messages)


def _read_table(path: Path, table_format: str) -> pd.DataFrame:
    """Read one table file.

    Parameters
    ----------
    path : Path
        Table file.
    table_format : {"parquet", "csv"}
        File format.

    Returns
    -------
    pandas.DataFrame
        The table.

    Raises
    ------
    ValueError
        When the format is not supported.
    """
    if table_format == "parquet":
        return pd.read_parquet(path)
    if table_format == "csv":
        return pd.read_csv(path)
    raise ValueError(f"unsupported table format: {table_format}")


def _validate_columns(
    table: TableSpec,
    frame: pd.DataFrame,
    errors: list[str],
    warnings: list[str],
) -> None:
    """Check required columns, dtypes, and extra columns.

    Parameters
    ----------
    table : TableSpec
        Table contract.
    frame : pandas.DataFrame
        Loaded table.
    errors : list of str
        Error accumulator.
    warnings : list of str
        Warning accumulator.
    """
    declared = {column.name for column in table.columns}
    for column in table.columns:
        if column.name not in frame.columns:
            if column.required:
                errors.append(f"DATASET-COLUMN: {table.name} is missing column {column.name}")
            continue
        if not _dtype_matches(frame[column.name], column.dtype):
            errors.append(
                f"DATASET-DTYPE: {table.name}.{column.name} is {frame[column.name].dtype}, "
                f"expected {column.dtype}"
            )
    for name in frame.columns:
        if name not in declared:
            warnings.append(f"DATASET-EXTRA-COLUMN: {table.name} has undeclared column {name}")


def _validate_primary_key(table: TableSpec, frame: pd.DataFrame, errors: list[str]) -> None:
    """Check that the primary key is present, non-null, and unique.

    Parameters
    ----------
    table : TableSpec
        Table contract.
    frame : pandas.DataFrame
        Loaded table.
    errors : list of str
        Error accumulator.
    """
    missing = [name for name in table.primary_key if name not in frame.columns]
    if missing:
        return
    for name in table.primary_key:
        if frame[name].isna().any():
            errors.append(f"DATASET-KEY: {table.name}.{name} has null key values")
    if frame.duplicated(subset=table.primary_key).any():
        errors.append(
            f"DATASET-KEY: {table.name} has duplicate primary key values "
            f"({', '.join(table.primary_key)})"
        )


def _dtype_matches(series: pd.Series, dtype: str) -> bool:
    """Return whether a pandas series satisfies a logical dtype.

    Parameters
    ----------
    series : pandas.Series
        Series to check.
    dtype : {"string", "int64", "float64", "bool", "datetime", "date"}
        Logical type.

    Returns
    -------
    bool
        ``True`` when the series matches.
    """
    if dtype == "string":
        return bool(ptypes.is_string_dtype(series.dtype))
    if dtype == "int64":
        return bool(ptypes.is_integer_dtype(series.dtype))
    if dtype == "float64":
        return bool(ptypes.is_float_dtype(series.dtype))
    if dtype == "bool":
        return bool(ptypes.is_bool_dtype(series.dtype))
    if dtype == "datetime":
        return bool(ptypes.is_datetime64_any_dtype(series.dtype))
    if dtype == "date":
        return bool(
            ptypes.is_datetime64_any_dtype(series.dtype) or ptypes.is_object_dtype(series.dtype)
        )
    return False
