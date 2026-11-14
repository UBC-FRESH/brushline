"""Cross-contract tests: round-trips, CLI/Python parity, artifact checks, and the contract index."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd
from brushline.build.compiler import compile_fixture
from brushline.cli import app
from brushline.fixtures.synthetic import load_fixture_manifest
from brushline.model.archive import ParetoArchive
from brushline.model.corridor import CorridorNetwork
from brushline.model.demo import DemoManifest
from brushline.model.plan import Plan
from brushline.model.run import RunManifest
from brushline.model.schema import DatasetManifest, file_sha256, validate_dataset
from brushline.model.state import StateContract
from brushline.model.timeline import OperationsTimeline, TimelineEvent
from brushline.sim.engine import simulate_dataset
from typer.testing import CliRunner

ROOT = Path(__file__).resolve().parents[1] / "examples" / "synthetic-corridor"
DOCS = Path(__file__).resolve().parents[1] / "docs"
RUNNER = CliRunner()


def _timeline() -> OperationsTimeline:
    rows: list[dict[str, object]] = []
    for line in (ROOT / "operations_timeline.jsonl").read_text(encoding="utf-8").splitlines():
        value = json.loads(line)
        if not isinstance(value, dict):
            raise ValueError("timeline row is not an object")
        rows.append(value)
    return OperationsTimeline(
        run_id="run-2026",
        events=[TimelineEvent.model_validate(row) for row in rows],
        created_utc=datetime(2026, 11, 14, tzinfo=UTC),
        created_by="tests",
    )


def test_dataset_manifest_round_trip() -> None:
    """The dataset manifest round-trips through JSON."""
    manifest = DatasetManifest.model_validate_json((ROOT / "dataset" / "manifest.json").read_text())
    assert DatasetManifest.model_validate_json(manifest.model_dump_json()) == manifest


def test_corridor_round_trip() -> None:
    """The corridor graph round-trips through JSON."""
    network = CorridorNetwork.model_validate_json((ROOT / "corridor.json").read_text())
    assert CorridorNetwork.model_validate_json(network.model_dump_json()) == network


def test_state_round_trip() -> None:
    """The state contract round-trips through JSON."""
    contract = StateContract.model_validate_json((ROOT / "state.json").read_text())
    assert StateContract.model_validate_json(contract.model_dump_json()) == contract


def test_plan_round_trip() -> None:
    """The plan round-trips through JSON."""
    plan = Plan.model_validate_json((ROOT / "plan.json").read_text())
    assert Plan.model_validate_json(plan.model_dump_json()) == plan


def test_run_round_trip() -> None:
    """The run manifest round-trips through JSON."""
    run = RunManifest.model_validate_json((ROOT / "run.json").read_text())
    assert RunManifest.model_validate_json(run.model_dump_json()) == run


def test_archive_round_trip() -> None:
    """The Pareto archive round-trips through JSON."""
    archive = ParetoArchive.model_validate_json((ROOT / "pareto.json").read_text())
    assert ParetoArchive.model_validate_json(archive.model_dump_json()) == archive


def test_timeline_round_trip() -> None:
    """The operations timeline round-trips through JSON."""
    timeline = _timeline()
    assert OperationsTimeline.model_validate_json(timeline.model_dump_json()) == timeline


def test_demo_round_trip() -> None:
    """The demo manifest round-trips through JSON."""
    demo = DemoManifest.model_validate_json((ROOT / "demo.json").read_text())
    assert DemoManifest.model_validate_json(demo.model_dump_json()) == demo


def test_cli_validate_matches_the_python_api() -> None:
    """The CLI validate report matches the Python validator report."""
    result = RUNNER.invoke(
        app,
        ["validate", "--dataset", str(ROOT / "dataset"), "--json"],
    )
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    report = validate_dataset(ROOT / "dataset").to_dict()
    assert payload["is_valid"] == report["is_valid"]
    assert payload["tables"] == report["tables"]
    assert payload["errors"] == report["errors"]
    assert payload["warnings"] == report["warnings"]


def test_cli_build_matches_the_python_compile(tmp_path: Path) -> None:
    """The build command and the Python compiler produce the same dataset content."""
    cli_target = tmp_path / "cli-dataset"
    result = RUNNER.invoke(
        app,
        ["build", "--fixture", str(ROOT), "--out", str(cli_target)],
    )
    assert result.exit_code == 0
    python_result = compile_fixture(ROOT, tmp_path / "python-dataset")
    cli_manifest = DatasetManifest.model_validate_json((cli_target / "manifest.json").read_text())
    assert cli_manifest.content_digest == python_result.manifest.content_digest
    pd.testing.assert_frame_equal(
        pd.read_parquet(cli_target / "segments.parquet"),
        python_result.segments,
        check_dtype=False,
    )
    pd.testing.assert_frame_equal(
        pd.read_parquet(cli_target / "states.parquet"),
        python_result.states,
        check_dtype=False,
    )


def test_cli_simulate_matches_the_python_api(tmp_path: Path) -> None:
    """The simulate command and the Python simulator write the same account values."""
    dataset = compile_fixture(ROOT, tmp_path / "dataset").root
    cli_run = tmp_path / "cli-run"
    result = RUNNER.invoke(
        app,
        [
            "simulate",
            "--dataset",
            str(dataset),
            "--out",
            str(cli_run),
            "--plan",
            str(ROOT / "plan.json"),
            "--years",
            "5",
        ],
    )
    assert result.exit_code == 0
    python_run = simulate_dataset(dataset, tmp_path / "python-run", plan=ROOT / "plan.json")
    pd.testing.assert_frame_equal(
        pd.read_csv(cli_run / "account_values.csv"),
        python_run.accounts,
    )
    pd.testing.assert_frame_equal(
        pd.read_csv(cli_run / "state_values.csv"),
        python_run.state_values,
    )


def test_run_artifact_checksums_match() -> None:
    """Every available run artifact has the checksum recorded in run.json."""
    run = RunManifest.model_validate_json((ROOT / "run.json").read_text())
    for artifact in run.artifacts:
        assert artifact.available
        assert artifact.sha256 == file_sha256(ROOT / artifact.path)


def test_contract_index_lists_every_contract() -> None:
    """The contract index names the dataset, corridor, state, and artifact contracts."""
    text = (DOCS / "reference" / "contract-index.rst").read_text(encoding="utf-8")
    for name in (
        "brushline.dataset.v1",
        "brushline.corridor.v1",
        "brushline.state.v1",
        "brushline.plan.v1",
        "brushline.run.v1",
        "brushline.pareto.v1",
        "brushline.timeline.v1",
        "brushline.demo.v1",
    ):
        assert name in text


def test_llms_index_links_the_contract_pages() -> None:
    """The agent-facing index links each reference page."""
    text = (DOCS / "llms.txt").read_text(encoding="utf-8")
    for page in (
        "reference/compiled-dataset.html",
        "reference/corridor-contract.html",
        "reference/state-contract.html",
        "reference/artifacts.html",
        "reference/synthetic-fixture.html",
        "reference/prototype.html",
    ):
        assert page in text


def test_fixture_manifest_matches_the_committed_fixture() -> None:
    """The fixture manifest's content digest covers the committed artifact list."""
    manifest = load_fixture_manifest(ROOT)
    artifacts = manifest["artifacts"]
    assert isinstance(artifacts, list)
    assert len(artifacts) == 16
    assert manifest["seed"] == 20261114
