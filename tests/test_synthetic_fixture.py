"""Tests for the deterministic synthetic corridor fixture."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import cast

import pytest
from brushline.cli import app
from brushline.fixtures.synthetic import generate_fixture, load_fixture_manifest
from brushline.model.archive import ParetoArchive, validate_pareto_archive
from brushline.model.corridor import CorridorNetwork, validate_corridor_network
from brushline.model.demo import DemoManifest, validate_demo_manifest
from brushline.model.plan import Plan, validate_plan
from brushline.model.run import RunManifest, validate_run_manifest
from brushline.model.schema import validate_dataset
from brushline.model.state import StateContract, validate_state_contract
from brushline.model.timeline import OperationsTimeline, TimelineEvent, validate_timeline
from typer.testing import CliRunner

ROOT = Path(__file__).resolve().parents[1] / "examples" / "synthetic-corridor"
RUNNER = CliRunner()


def _manifest() -> dict[str, object]:
    return load_fixture_manifest(ROOT)


def _artifact_map(manifest: dict[str, object]) -> dict[str, str]:
    artifacts = cast("list[dict[str, str]]", manifest["artifacts"])
    return {item["path"]: item["sha256"] for item in artifacts}


def _timeline(root: Path) -> OperationsTimeline:
    rows: list[dict[str, object]] = []
    for line in (root / "operations_timeline.jsonl").read_text(encoding="utf-8").splitlines():
        value = json.loads(line)
        if not isinstance(value, dict):
            raise ValueError("timeline row is not an object")
        rows.append(cast("dict[str, object]", value))
    return OperationsTimeline(
        run_id="run-2026",
        events=[TimelineEvent.model_validate(row) for row in rows],
        created_utc=datetime(2026, 11, 14, tzinfo=UTC),
        created_by="tests",
    )


def test_committed_fixture_matches_the_generator(tmp_path: Path) -> None:
    """The committed fixture has the same artifact digests and content digest as a fresh build."""
    fresh = generate_fixture(tmp_path / "fixture")
    manifest = _manifest()
    assert fresh.artifacts == _artifact_map(manifest)
    assert fresh.content_digest == manifest["content_digest"]
    assert fresh.expected == manifest["expected"]


def test_fixture_is_deterministic(tmp_path: Path) -> None:
    """Two fresh builds produce the same content digest."""
    first = generate_fixture(tmp_path / "first")
    second = generate_fixture(tmp_path / "second")
    assert first.content_digest == second.content_digest
    assert first.artifacts == second.artifacts


def test_dataset_contract() -> None:
    """The committed dataset validates against the dataset contract."""
    report = validate_dataset(ROOT / "dataset")
    assert report.is_valid
    assert report.tables == {"segments": 5}


def test_corridor_contract() -> None:
    """The committed corridor graph validates and records the access gap."""
    network = CorridorNetwork.model_validate_json((ROOT / "corridor.json").read_text())
    report = validate_corridor_network(network)
    assert report.is_valid
    assert report.counts["corridors"] == 2
    assert report.counts["segments"] == 5
    assert any(message.startswith("CORRIDOR-ACCESS") for message in report.warnings)


def test_state_contract() -> None:
    """The committed state contract validates and records the monitoring gap."""
    contract = StateContract.model_validate_json((ROOT / "state.json").read_text())
    report = validate_state_contract(
        contract,
        required_segment_ids={"s1", "s2", "s3", "s4", "s5"},
    )
    assert report.is_valid
    assert len(contract.states) == 5
    assert any(state.state_class == "unknown" for state in contract.states)
    assert any(message.startswith("STATE-UNCERTAIN") for message in report.warnings)
    assert any(message.startswith("STATE-COVERAGE") for message in report.warnings)


def test_plan_contract() -> None:
    """The committed plan validates and has the expected total."""
    plan = Plan.model_validate_json((ROOT / "plan.json").read_text())
    report = validate_plan(plan, known_segment_ids={"s1", "s2", "s3", "s4", "s5"})
    assert report.is_valid
    assert report.counts["total_cost"] == 5300.0


def test_archive_contract() -> None:
    """The committed Pareto archive validates and keeps three members."""
    archive = ParetoArchive.model_validate_json((ROOT / "pareto.json").read_text())
    report = validate_pareto_archive(archive)
    assert report.is_valid
    assert report.counts["members"] == 3


def test_timeline_contract() -> None:
    """The committed timeline validates and has five events."""
    report = validate_timeline(
        _timeline(ROOT),
        known_segment_ids={"s1", "s2", "s3", "s4", "s5"},
    )
    assert report.is_valid
    assert report.counts["events"] == 5


def test_run_and_demo_contracts() -> None:
    """The committed run and demo manifests validate."""
    run = RunManifest.model_validate_json((ROOT / "run.json").read_text())
    assert validate_run_manifest(run).is_valid
    demo = DemoManifest.model_validate_json((ROOT / "demo.json").read_text())
    assert validate_demo_manifest(demo).is_valid


def test_tiny_optimum_is_correct() -> None:
    """The tiny instance's known optimum is the minimum weighted penalty."""
    payload = json.loads((ROOT / "tiny_optimum.json").read_text(encoding="utf-8"))
    objective = cast("dict[str, float]", payload["objective"])
    options = cast("list[dict[str, object]]", payload["options"])
    penalties = {
        cast("str", option["option_id"]): (
            objective["cost_weight"]
            * float(cast("float", option["cost"]))
            / objective["cost_scale"]
            + objective["risk_weight"] * float(cast("float", option["risk"]))
        )
        for option in options
    }
    best = min(penalties, key=lambda name: penalties[name])
    assert best == "mow-2026"
    assert payload["optimum"] == best
    assert abs(penalties[best] - cast("float", payload["optimum_penalty"])) < 1e-9


def test_fixture_expected_counts_match_the_contracts() -> None:
    """The manifest's expected counts match the committed artifacts."""
    expected = cast("dict[str, object]", _manifest()["expected"])
    corridor = CorridorNetwork.model_validate_json((ROOT / "corridor.json").read_text())
    state = StateContract.model_validate_json((ROOT / "state.json").read_text())
    plan = Plan.model_validate_json((ROOT / "plan.json").read_text())
    archive = ParetoArchive.model_validate_json((ROOT / "pareto.json").read_text())
    timeline = _timeline(ROOT)
    assert expected["corridors"] == len(corridor.corridors)
    assert expected["segments"] == len(corridor.segments)
    assert expected["states"] == len(state.states)
    assert expected["treatments"] == len(state.treatments)
    assert expected["observations"] == len(state.observations)
    assert expected["structures"] == len(corridor.structures)
    assert expected["plan_actions"] == len(plan.actions)
    assert expected["pareto_members"] == len(archive.members)
    assert expected["timeline_events"] == len(timeline.events)


def test_generate_fixture_refuses_a_non_empty_directory(tmp_path: Path) -> None:
    """The generator refuses a non-empty directory unless force is set."""
    target = tmp_path / "fixture"
    target.mkdir()
    (target / "keep.txt").write_text("keep", encoding="utf-8")
    with pytest.raises(FileExistsError):
        generate_fixture(target)
    result = generate_fixture(target, force=True)
    assert (target / "keep.txt").is_file()
    assert (target / "fixture.json").is_file()
    assert result.root == target.resolve()


def test_load_fixture_manifest_rejects_a_non_object(tmp_path: Path) -> None:
    """A fixture manifest that is not a JSON object is rejected."""
    (tmp_path / "fixture.json").write_text("[]", encoding="utf-8")
    with pytest.raises(ValueError, match="JSON object"):
        load_fixture_manifest(tmp_path)


def test_cli_generates_the_fixture(tmp_path: Path) -> None:
    """The fixture command writes a valid fixture."""
    target = tmp_path / "fixture"
    result = RUNNER.invoke(app, ["fixture", "--out", str(target)])
    assert result.exit_code == 0
    assert "content_digest" in result.stdout
    assert (target / "fixture.json").is_file()
    assert generate_fixture(target, force=True).content_digest == _manifest()["content_digest"]
