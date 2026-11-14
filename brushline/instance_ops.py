"""Thin instance-stage operations used by the Brushline FreshForge provider.

The operations validate or copy the stage artifacts. They are deliberately small: P2.7 replaces the
map-to-instance orchestration, and P3/P5 replace the state seeding and scenario validation with the
real models. The provider nodes call these commands rather than reimplementing them.
"""

from __future__ import annotations

import csv
import json
import shutil
from pathlib import Path
from typing import cast

import yaml

from brushline.build.compiler import CompiledDataset, compile_fixture
from brushline.model.corridor import CorridorNetwork, validate_corridor_network
from brushline.model.demo import DemoManifest, validate_demo_manifest
from brushline.model.state import StateContract, validate_state_contract

AOI_VALIDATION_SCHEMA_VERSION = "brushline.aoi-validation.v1"
SCENARIO_VALIDATION_SCHEMA_VERSION = "brushline.scenario-validation.v1"
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
)


def validate_aoi_file(aoi: Path, out: Path) -> Path:
    """Validate a GeoJSON AOI and write a validation report.

    Parameters
    ----------
    aoi : Path
        GeoJSON Feature or FeatureCollection.
    out : Path
        Output directory.

    Returns
    -------
    Path
        The written ``aoi_validation.json``.

    Raises
    ------
    ValueError
        When the AOI is not valid GeoJSON or has no usable geometry.
    """
    payload = _read_json(aoi)
    kind = payload.get("type")
    if kind == "Feature":
        features = [payload]
    elif kind == "FeatureCollection":
        raw_features = payload.get("features")
        if not isinstance(raw_features, list) or not raw_features:
            raise ValueError("AOI FeatureCollection has no features")
        features = [cast("dict[str, object]", feature) for feature in raw_features]
    else:
        raise ValueError("AOI must be a GeoJSON Feature or FeatureCollection")
    for feature in features:
        geometry = feature.get("geometry")
        if not isinstance(geometry, dict):
            raise ValueError("every AOI feature needs a geometry")
        geometry_type = geometry.get("type")
        if geometry_type not in {
            "Polygon",
            "MultiPolygon",
            "LineString",
            "MultiLineString",
        }:
            raise ValueError(f"unsupported AOI geometry type: {geometry_type!r}")
        if "coordinates" not in geometry:
            raise ValueError("AOI geometry has no coordinates")
    report: dict[str, object] = {
        "schema_version": AOI_VALIDATION_SCHEMA_VERSION,
        "source": str(Path(aoi).expanduser().resolve()),
        "feature_count": len(features),
        "is_valid": True,
    }
    target = Path(out).expanduser().resolve()
    target.mkdir(parents=True, exist_ok=True)
    path = target / "aoi_validation.json"
    _write_json(path, report)
    return path


def segment_corridor_file(corridor: Path, out: Path) -> Path:
    """Validate a corridor graph and write its segment table.

    Parameters
    ----------
    corridor : Path
        ``brushline.corridor.v1`` JSON.
    out : Path
        Output directory.

    Returns
    -------
    Path
        The written ``segments.csv``.

    Raises
    ------
    ValueError
        When the corridor graph is invalid.
    """
    network = CorridorNetwork.model_validate_json(
        Path(corridor).expanduser().read_text(encoding="utf-8")
    )
    report = validate_corridor_network(network)
    if not report.is_valid:
        raise ValueError("; ".join(report.errors))
    target = Path(out).expanduser().resolve()
    target.mkdir(parents=True, exist_ok=True)
    path = target / "segments.csv"
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(SEGMENT_COLUMNS), lineterminator="\n")
        writer.writeheader()
        for segment in network.segments:
            writer.writerow(
                {
                    "segment_id": segment.segment_id,
                    "corridor_id": segment.corridor_id,
                    "length_m": segment.length_m,
                    "geometry_wkt": segment.geometry_wkt,
                    "span_id": segment.span_id,
                    "sequence": segment.sequence,
                    "treatment_unit_id": segment.treatment_unit_id,
                    "service_standard_id": segment.service_standard_id,
                    "access_point_id": segment.access_point_id or "",
                }
            )
    return path


def compile_dataset_file(fixture: Path, out: Path, *, force: bool = False) -> CompiledDataset:
    """Compile a fixture into a Brushline dataset.

    Parameters
    ----------
    fixture : Path
        Fixture directory.
    out : Path
        Compiled dataset directory.
    force : bool, optional
        Overwrite an existing dataset. Defaults to ``False``.

    Returns
    -------
    CompiledDataset
        The compiled dataset.
    """
    return compile_fixture(fixture, out, force=force)


def seed_state_file(state: Path, out: Path) -> Path:
    """Validate a state contract and write the seed state artifact.

    Parameters
    ----------
    state : Path
        ``brushline.state.v1`` JSON.
    out : Path
        Output directory.

    Returns
    -------
    Path
        The copied ``state.json``.

    Raises
    ------
    ValueError
        When the state contract is invalid.
    """
    contract = StateContract.model_validate_json(
        Path(state).expanduser().read_text(encoding="utf-8")
    )
    report = validate_state_contract(contract)
    if not report.is_valid:
        raise ValueError("; ".join(report.errors))
    target = Path(out).expanduser().resolve()
    target.mkdir(parents=True, exist_ok=True)
    path = target / "state.json"
    shutil.copy2(Path(state).expanduser().resolve(), path)
    return path


def validate_scenario_file(scenario: Path, targets: Path, out: Path) -> Path:
    """Validate the Brushline scenario and targets YAML and write a report.

    Parameters
    ----------
    scenario : Path
        Scenario YAML.
    targets : Path
        Targets YAML.
    out : Path
        Output directory.

    Returns
    -------
    Path
        The written ``scenario_validation.json``.

    Raises
    ------
    ValueError
        When a schema version or a required list is missing.
    """
    scenario_payload = _read_yaml(scenario)
    targets_payload = _read_yaml(targets)
    if scenario_payload.get("schema_version") != "brushline.scenario.v1":
        raise ValueError("scenario schema_version must be brushline.scenario.v1")
    if targets_payload.get("schema_version") != "brushline.targets.v1":
        raise ValueError("targets schema_version must be brushline.targets.v1")
    raw_targets = targets_payload.get("targets")
    if not isinstance(raw_targets, list):
        raise ValueError("targets must be a list")
    report: dict[str, object] = {
        "schema_version": SCENARIO_VALIDATION_SCHEMA_VERSION,
        "scenario": str(Path(scenario).expanduser().resolve()),
        "targets": str(Path(targets).expanduser().resolve()),
        "target_count": len(raw_targets),
        "is_valid": True,
    }
    target = Path(out).expanduser().resolve()
    target.mkdir(parents=True, exist_ok=True)
    path = target / "scenario_validation.json"
    _write_json(path, report)
    return path


def build_demo_file(demo: Path, out: Path) -> Path:
    """Validate a demo manifest and write the demo artifact.

    Parameters
    ----------
    demo : Path
        ``brushline.demo.v1`` JSON.
    out : Path
        Output directory.

    Returns
    -------
    Path
        The copied ``demo.json``.

    Raises
    ------
    ValueError
        When the demo manifest is invalid.
    """
    manifest = DemoManifest.model_validate_json(Path(demo).expanduser().read_text(encoding="utf-8"))
    report = validate_demo_manifest(manifest)
    if not report.is_valid:
        raise ValueError("; ".join(report.errors))
    target = Path(out).expanduser().resolve()
    target.mkdir(parents=True, exist_ok=True)
    path = target / "demo.json"
    shutil.copy2(Path(demo).expanduser().resolve(), path)
    return path


def _read_json(path: Path) -> dict[str, object]:
    value: object = json.loads(Path(path).expanduser().read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} does not contain a JSON object")
    return cast("dict[str, object]", value)


def _read_yaml(path: Path) -> dict[str, object]:
    value: object = yaml.safe_load(Path(path).expanduser().read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} does not contain a YAML mapping")
    return cast("dict[str, object]", value)


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


__all__ = [
    "AOI_VALIDATION_SCHEMA_VERSION",
    "SCENARIO_VALIDATION_SCHEMA_VERSION",
    "SEGMENT_COLUMNS",
    "build_demo_file",
    "compile_dataset_file",
    "seed_state_file",
    "segment_corridor_file",
    "validate_aoi_file",
    "validate_scenario_file",
]
