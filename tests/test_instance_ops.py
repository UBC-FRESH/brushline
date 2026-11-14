"""Tests for the thin instance-stage operations and their CLI commands."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from brushline.cli import app
from brushline.instance_ops import (
    build_demo_file,
    compile_dataset_file,
    seed_state_file,
    segment_corridor_file,
    validate_aoi_file,
    validate_scenario_file,
)
from brushline.instance_template import TEMPLATE_ROOT
from brushline.model.schema import validate_dataset
from typer.testing import CliRunner

ROOT = Path(__file__).resolve().parents[1] / "examples" / "synthetic-corridor"
RUNNER = CliRunner()


def _geojson(path: Path) -> Path:
    path.write_text(
        json.dumps(
            {
                "type": "FeatureCollection",
                "features": [
                    {
                        "type": "Feature",
                        "properties": {},
                        "geometry": {
                            "type": "Polygon",
                            "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 0]]],
                        },
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    return path


def test_validate_aoi_writes_the_report(tmp_path: Path) -> None:
    """A valid AOI writes a report with the feature count."""
    target = validate_aoi_file(_geojson(tmp_path / "aoi.geojson"), tmp_path / "out")
    payload = json.loads(target.read_text(encoding="utf-8"))
    assert payload["is_valid"] is True
    assert payload["feature_count"] == 1


def test_validate_aoi_rejects_a_non_feature(tmp_path: Path) -> None:
    """A JSON object without a Feature type is rejected."""
    path = tmp_path / "aoi.json"
    path.write_text('{"type": "Point"}', encoding="utf-8")
    with pytest.raises(ValueError, match="Feature"):
        validate_aoi_file(path, tmp_path / "out")


def test_segment_corridor_writes_five_segments(tmp_path: Path) -> None:
    """The fixture corridor writes the five-segment table."""
    target = segment_corridor_file(ROOT / "corridor.json", tmp_path / "out")
    lines = target.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 6
    assert lines[0].startswith("segment_id")


def test_compile_dataset_writes_a_valid_manifest(tmp_path: Path) -> None:
    """The fixture compiles and validates through the dataset contract."""
    result = compile_dataset_file(ROOT, tmp_path / "dataset")
    assert validate_dataset(result.root).is_valid
    assert result.manifest.dataset_id.endswith("-compiled")


def test_seed_state_writes_the_state_copy(tmp_path: Path) -> None:
    """The state contract validates and the seed artifact is written."""
    target = seed_state_file(ROOT / "state.json", tmp_path / "out")
    assert target.is_file()
    assert json.loads(target.read_text(encoding="utf-8"))["schema_version"] == "brushline.state.v1"


def test_validate_scenario_writes_the_report(tmp_path: Path) -> None:
    """The template scenario and targets validate."""
    target = validate_scenario_file(
        TEMPLATE_ROOT / "config" / "brushline" / "scenario.yaml",
        TEMPLATE_ROOT / "config" / "brushline" / "targets.yaml",
        tmp_path / "out",
    )
    payload = json.loads(target.read_text(encoding="utf-8"))
    assert payload["is_valid"] is True
    assert payload["target_count"] == 0


def test_validate_scenario_rejects_a_bad_schema(tmp_path: Path) -> None:
    """A scenario with the wrong schema version is rejected."""
    scenario = tmp_path / "scenario.yaml"
    scenario.write_text("schema_version: wrong\n", encoding="utf-8")
    targets = tmp_path / "targets.yaml"
    targets.write_text("schema_version: brushline.targets.v1\ntargets: []\n", encoding="utf-8")
    with pytest.raises(ValueError, match="schema_version"):
        validate_scenario_file(scenario, targets, tmp_path / "out")


def test_build_demo_writes_the_demo_copy(tmp_path: Path) -> None:
    """The fixture demo manifest validates and is written."""
    target = build_demo_file(ROOT / "demo.json", tmp_path / "out")
    assert target.is_file()
    assert json.loads(target.read_text(encoding="utf-8"))["id"] == "synthetic-corridor"


def test_cli_instance_stage_commands(tmp_path: Path) -> None:
    """The six instance stage commands run through the CLI."""
    aoi = _geojson(tmp_path / "aoi.geojson")
    commands = [
        ["instance", "validate-aoi", "--aoi", str(aoi), "--out", str(tmp_path / "aoi-out")],
        [
            "instance",
            "segment-corridor",
            "--corridor",
            str(ROOT / "corridor.json"),
            "--out",
            str(tmp_path / "segments-out"),
        ],
        [
            "instance",
            "compile-dataset",
            "--fixture",
            str(ROOT),
            "--out",
            str(tmp_path / "dataset-out"),
        ],
        [
            "instance",
            "seed-state",
            "--state",
            str(ROOT / "state.json"),
            "--out",
            str(tmp_path / "state-out"),
        ],
        [
            "instance",
            "validate-scenario",
            "--scenario",
            str(TEMPLATE_ROOT / "config" / "brushline" / "scenario.yaml"),
            "--targets",
            str(TEMPLATE_ROOT / "config" / "brushline" / "targets.yaml"),
            "--out",
            str(tmp_path / "scenario-out"),
        ],
        [
            "instance",
            "build-demo",
            "--demo",
            str(ROOT / "demo.json"),
            "--out",
            str(tmp_path / "demo-out"),
        ],
    ]
    for command in commands:
        result = RUNNER.invoke(app, command)
        assert result.exit_code == 0, (command, result.stdout, result.stderr)


def test_cli_instance_stage_error_exits_one(tmp_path: Path) -> None:
    """A bad AOI exits with status 1."""
    bad = tmp_path / "bad.json"
    bad.write_text("{}", encoding="utf-8")
    result = RUNNER.invoke(
        app,
        ["instance", "validate-aoi", "--aoi", str(bad), "--out", str(tmp_path / "out")],
    )
    assert result.exit_code == 1
    assert "error:" in result.stderr


def test_validate_aoi_accepts_a_feature_and_rejects_bad_geometry(tmp_path: Path) -> None:
    """A single Feature is accepted; an empty collection or bad geometry is rejected."""
    feature = tmp_path / "feature.json"
    feature.write_text(
        json.dumps(
            {
                "type": "Feature",
                "geometry": {"type": "Polygon", "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 0]]]},
            }
        ),
        encoding="utf-8",
    )
    assert validate_aoi_file(feature, tmp_path / "feature-out").is_file()

    cases = [
        {"type": "FeatureCollection", "features": []},
        {"type": "Feature", "geometry": None},
        {"type": "Feature", "geometry": {"type": "Point", "coordinates": [0, 0]}},
        {"type": "Feature", "geometry": {"type": "Polygon"}},
    ]
    for index, payload in enumerate(cases):
        path = tmp_path / f"bad-{index}.json"
        path.write_text(json.dumps(payload), encoding="utf-8")
        with pytest.raises(ValueError, match=r"AOI|geometry|feature"):
            validate_aoi_file(path, tmp_path / f"bad-out-{index}")


def test_segment_corridor_rejects_an_invalid_graph(tmp_path: Path) -> None:
    """A corridor file that does not satisfy the graph contract is rejected."""
    path = tmp_path / "corridor.json"
    path.write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError, match="validation error"):
        segment_corridor_file(path, tmp_path / "out")


def test_seed_state_rejects_an_invalid_contract(tmp_path: Path) -> None:
    """A state file that does not satisfy the contract is rejected."""
    path = tmp_path / "state.json"
    path.write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError, match="validation error"):
        seed_state_file(path, tmp_path / "out")


def test_scenario_rejects_targets_schema_and_non_list_targets(tmp_path: Path) -> None:
    """The targets schema and the targets list are both required."""
    scenario = tmp_path / "scenario.yaml"
    scenario.write_text("schema_version: brushline.scenario.v1\n", encoding="utf-8")
    wrong_schema = tmp_path / "wrong-schema.yaml"
    wrong_schema.write_text("schema_version: wrong\ntargets: []\n", encoding="utf-8")
    with pytest.raises(ValueError, match="targets schema_version"):
        validate_scenario_file(scenario, wrong_schema, tmp_path / "out-a")
    wrong_list = tmp_path / "wrong-list.yaml"
    wrong_list.write_text("schema_version: brushline.targets.v1\ntargets: {}\n", encoding="utf-8")
    with pytest.raises(ValueError, match="targets must be a list"):
        validate_scenario_file(scenario, wrong_list, tmp_path / "out-b")


def test_demo_and_json_helpers_reject_non_objects(tmp_path: Path) -> None:
    """A demo or AOI file that is not a JSON object is rejected."""
    bad_demo = tmp_path / "demo.json"
    bad_demo.write_text("[]", encoding="utf-8")
    with pytest.raises(ValueError, match="validation error"):
        build_demo_file(bad_demo, tmp_path / "out")
    bad_aoi = tmp_path / "aoi.json"
    bad_aoi.write_text("[]", encoding="utf-8")
    with pytest.raises(ValueError, match="JSON object"):
        validate_aoi_file(bad_aoi, tmp_path / "out")
