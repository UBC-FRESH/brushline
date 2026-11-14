"""Compile the synthetic corridor fixture into a validated Brushline dataset.

The compiler reads the fixture's dataset, corridor graph, and state contract, joins the service
standards and corridor attributes onto the segments, and writes the compiled segments and states
tables plus a dataset manifest. It is the smallest end-to-end compile path; the production compiler
is P2 and P3.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

from brushline.model.corridor import CorridorNetwork, validate_corridor_network
from brushline.model.schema import (
    ColumnSpec,
    DatasetManifest,
    Provenance,
    TableSpec,
    file_sha256,
    load_manifest,
    validate_dataset,
    write_manifest,
)
from brushline.model.state import StateContract, validate_state_contract

SEGMENT_COLUMNS: tuple[str, ...] = (
    "segment_id",
    "corridor_id",
    "length_m",
    "geometry_wkt",
    "span_id",
    "sequence",
    "treatment_unit_id",
    "service_standard_id",
    "access_point_id",
    "max_height_m",
    "min_clearance_m",
)
STATE_COLUMNS: tuple[str, ...] = (
    "segment_id",
    "state_year",
    "functional_group",
    "state_class",
    "height_m",
    "cover_pct",
    "density_per_ha",
    "age_years",
    "uncertainty_confidence",
    "source",
    "source_version",
)


@dataclass(frozen=True)
class CompiledDataset:
    """The output of one fixture compile.

    Parameters
    ----------
    root : Path
        Compiled dataset directory.
    manifest : DatasetManifest
        Dataset manifest.
    segments : pandas.DataFrame
        Compiled segment table.
    states : pandas.DataFrame
        Compiled state table.
    """

    root: Path
    manifest: DatasetManifest
    segments: pd.DataFrame
    states: pd.DataFrame


def compile_fixture(
    fixture_root: Path,
    out: Path,
    *,
    force: bool = False,
) -> CompiledDataset:
    """Compile the synthetic fixture into a validated dataset.

    Parameters
    ----------
    fixture_root : Path
        Fixture directory, such as ``examples/synthetic-corridor``.
    out : Path
        Compiled dataset directory.
    force : bool, optional
        Overwrite an existing dataset directory. Defaults to ``False``.

    Returns
    -------
    CompiledDataset
        The compiled directory, manifest, segments, and states.

    Raises
    ------
    FileExistsError
        When the output directory is not empty and ``force`` is false.
    ValueError
        When a source contract fails validation.
    """
    fixture = Path(fixture_root).expanduser().resolve()
    source_report = validate_dataset(fixture / "dataset")
    if not source_report.is_valid:
        raise ValueError("; ".join(source_report.errors))
    source_manifest = load_manifest(fixture / "dataset")
    segments_source = pd.read_csv(
        fixture / "dataset" / "segments.csv",
        dtype={
            "segment_id": "string",
            "corridor_id": "string",
            "geometry_wkt": "string",
        },
    )
    network = CorridorNetwork.model_validate_json((fixture / "corridor.json").read_text())
    network_report = validate_corridor_network(network)
    if not network_report.is_valid:
        raise ValueError("; ".join(network_report.errors))
    states_source = StateContract.model_validate_json((fixture / "state.json").read_text())
    state_report = validate_state_contract(
        states_source,
        required_segment_ids=set(segments_source["segment_id"].astype(str)),
    )
    if not state_report.is_valid:
        raise ValueError("; ".join(state_report.errors))

    standards = pd.DataFrame(
        [
            {
                "service_standard_id": standard.service_standard_id,
                "max_height_m": standard.max_height_m,
                "min_clearance_m": standard.min_clearance_m,
            }
            for standard in network.service_standards
        ]
    )
    corridor_rows = pd.DataFrame(
        [
            {
                "segment_id": segment.segment_id,
                "span_id": segment.span_id,
                "sequence": segment.sequence,
                "treatment_unit_id": segment.treatment_unit_id,
                "service_standard_id": segment.service_standard_id,
                "access_point_id": segment.access_point_id,
            }
            for segment in network.segments
        ]
    )
    segments = segments_source.merge(
        corridor_rows,
        on="segment_id",
        how="left",
        validate="one_to_one",
    ).merge(standards, on="service_standard_id", how="left", validate="many_to_one")
    if segments[["span_id", "max_height_m", "min_clearance_m"]].isna().any().any():
        raise ValueError("a segment is missing a span or a service standard")
    segments["access_point_id"] = segments["access_point_id"].astype("string")
    segments["sequence"] = segments["sequence"].astype("int64")
    segments = segments[list(SEGMENT_COLUMNS)]

    states = pd.DataFrame(
        [
            {
                "segment_id": state.segment_id,
                "state_year": state.state_year,
                "functional_group": state.functional_group,
                "state_class": state.state_class,
                "height_m": state.height_m,
                "cover_pct": state.cover_pct,
                "density_per_ha": state.density_per_ha,
                "age_years": state.age_years,
                "uncertainty_confidence": state.uncertainty.confidence,
                "source": state.source,
                "source_version": state.source_version,
            }
            for state in states_source.states
        ]
    )
    states["density_per_ha"] = states["density_per_ha"].astype("float64")
    states["age_years"] = states["age_years"].astype("float64")
    states = states[list(STATE_COLUMNS)]

    target = Path(out).expanduser().resolve()
    if target.exists() and any(target.iterdir()) and not force:
        raise FileExistsError(f"{target} is not empty; pass force=True to overwrite")
    target.mkdir(parents=True, exist_ok=True)
    segments_path = target / "segments.parquet"
    states_path = target / "states.parquet"
    segments.to_parquet(segments_path, index=False)
    states.to_parquet(states_path, index=False)

    manifest = DatasetManifest(
        dataset_id=f"{source_manifest.dataset_id}-compiled",
        name="Synthetic corridor compiled dataset",
        description="The P1.6 prototype compile of the synthetic corridor fixture.",
        created_utc=datetime.now(UTC),
        crs=source_manifest.crs,
        units=source_manifest.units,
        tables=[
            TableSpec(
                name="segments",
                path="segments.parquet",
                format="parquet",
                primary_key=["segment_id"],
                columns=_segment_columns(),
                row_count=len(segments),
                sha256=file_sha256(segments_path),
            ),
            TableSpec(
                name="states",
                path="states.parquet",
                format="parquet",
                primary_key=["segment_id", "state_year", "functional_group"],
                columns=_state_columns(),
                row_count=len(states),
                sha256=file_sha256(states_path),
            ),
        ],
        provenance=Provenance(
            source="synthetic-corridor",
            source_version="1.0",
            licence="CC0-1.0",
            created_by="brushline.build.compiler",
            configuration={"compiler": "p1.6-prototype"},
        ),
        content_digest="0" * 64,
    )
    manifest.content_digest = manifest.compute_content_digest()
    write_manifest(target, manifest)
    return CompiledDataset(target, manifest, segments, states)


def _segment_columns() -> list[ColumnSpec]:
    return [
        ColumnSpec(name="segment_id", dtype="string"),
        ColumnSpec(name="corridor_id", dtype="string"),
        ColumnSpec(name="length_m", dtype="float64", unit="m"),
        ColumnSpec(name="geometry_wkt", dtype="string"),
        ColumnSpec(name="span_id", dtype="string"),
        ColumnSpec(name="sequence", dtype="int64"),
        ColumnSpec(name="treatment_unit_id", dtype="string"),
        ColumnSpec(name="service_standard_id", dtype="string"),
        ColumnSpec(name="access_point_id", dtype="string", required=False),
        ColumnSpec(name="max_height_m", dtype="float64", unit="m"),
        ColumnSpec(name="min_clearance_m", dtype="float64", unit="m"),
    ]


def _state_columns() -> list[ColumnSpec]:
    return [
        ColumnSpec(name="segment_id", dtype="string"),
        ColumnSpec(name="state_year", dtype="int64"),
        ColumnSpec(name="functional_group", dtype="string"),
        ColumnSpec(name="state_class", dtype="string"),
        ColumnSpec(name="height_m", dtype="float64", unit="m"),
        ColumnSpec(name="cover_pct", dtype="float64", unit="%"),
        ColumnSpec(name="density_per_ha", dtype="float64", unit="stems/ha", required=False),
        ColumnSpec(name="age_years", dtype="float64", unit="years", required=False),
        ColumnSpec(name="uncertainty_confidence", dtype="float64"),
        ColumnSpec(name="source", dtype="string"),
        ColumnSpec(name="source_version", dtype="string"),
    ]


__all__ = [
    "SEGMENT_COLUMNS",
    "STATE_COLUMNS",
    "CompiledDataset",
    "compile_fixture",
]
