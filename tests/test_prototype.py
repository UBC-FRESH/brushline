"""End-to-end tests for the P1.6 compile and simulate prototype."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest
from brushline.build.compiler import compile_fixture
from brushline.cli import app
from brushline.model.plan import Plan
from brushline.model.schema import validate_dataset
from brushline.sim.engine import read_run_summary, simulate_dataset
from brushline.sim.schedule import load_schedule, schedule_from_plan
from typer.testing import CliRunner

ROOT = Path(__file__).resolve().parents[1] / "examples" / "synthetic-corridor"
RUNNER = CliRunner()


def _compiled(tmp_path: Path) -> Path:
    return compile_fixture(ROOT, tmp_path / "dataset").root


def test_compile_fixture_passes_the_dataset_contract(tmp_path: Path) -> None:
    """The compiled fixture has five segments, five states, and a valid manifest."""
    result = compile_fixture(ROOT, tmp_path / "dataset")
    report = validate_dataset(result.root)
    assert report.is_valid
    assert report.tables == {"segments": 5, "states": 5}
    assert len(result.segments) == 5
    assert len(result.states) == 5


def test_compile_is_deterministic_in_content(tmp_path: Path) -> None:
    """Two compiles of the same fixture have the same content digest."""
    first = compile_fixture(ROOT, tmp_path / "first")
    second = compile_fixture(ROOT, tmp_path / "second")
    assert first.manifest.content_digest == second.manifest.content_digest
    pd.testing.assert_frame_equal(first.segments, second.segments)
    pd.testing.assert_frame_equal(first.states, second.states)


def test_compile_refuses_a_non_empty_directory(tmp_path: Path) -> None:
    """The compiler refuses a non-empty output directory unless force is set."""
    target = tmp_path / "dataset"
    target.mkdir()
    (target / "keep.txt").write_text("keep", encoding="utf-8")
    with pytest.raises(FileExistsError):
        compile_fixture(ROOT, target)
    assert compile_fixture(ROOT, target, force=True).root == target.resolve()
    assert (target / "keep.txt").is_file()


def test_simulate_plan_end_to_end(tmp_path: Path) -> None:
    """The plan replays to five years of accounts and a complete run."""
    dataset = _compiled(tmp_path)
    result = simulate_dataset(dataset, tmp_path / "run", plan=ROOT / "plan.json", years=5)
    assert len(result.accounts) == 35
    assert set(result.accounts["account"]) == {
        "vegetation.mean_height_m",
        "vegetation.mean_cover_pct",
        "vegetation.max_height_m",
        "vegetation.unknown_segments",
        "vegetation.clearing_violations",
        "treatment.cost",
        "treatment.segments",
    }
    assert result.summary["total_cost"] == 5300.0
    assert result.summary["actions_applied"] == 5
    assert result.summary["actions_outside_horizon"] == 0
    assert result.summary["unknown_segments"] == 1
    assert len(result.schedule) == 5
    assert set(result.schedule["status"]) == {"applied"}
    run = read_run_summary(result.run_dir)
    assert run.run_type == "simulate"
    assert run.status == "complete"
    assert all(artifact.available for artifact in run.artifacts)
    assert (result.run_dir / "reports" / "summary.md").is_file()


def test_simulate_is_reproducible_from_a_schedule(tmp_path: Path) -> None:
    """A replayed schedule reproduces the same accounts and state values."""
    dataset = _compiled(tmp_path)
    first = simulate_dataset(dataset, tmp_path / "run-a", plan=ROOT / "plan.json", years=5)
    second = simulate_dataset(
        dataset,
        tmp_path / "run-b",
        schedule=first.run_dir / "schedule.csv",
        years=5,
    )
    pd.testing.assert_frame_equal(first.accounts, second.accounts)
    pd.testing.assert_frame_equal(first.state_values, second.state_values)
    assert first.summary["total_cost"] == second.summary["total_cost"]


def test_simulate_requires_exactly_one_input(tmp_path: Path) -> None:
    """A simulation needs exactly one of plan and schedule."""
    dataset = _compiled(tmp_path)
    with pytest.raises(ValueError, match="exactly one"):
        simulate_dataset(dataset, tmp_path / "run")
    with pytest.raises(ValueError, match="exactly one"):
        simulate_dataset(
            dataset,
            tmp_path / "run",
            plan=ROOT / "plan.json",
            schedule=ROOT / "plan.json",
        )
    with pytest.raises(ValueError, match="at least 1"):
        simulate_dataset(dataset, tmp_path / "run", plan=ROOT / "plan.json", years=0)


def test_schedule_rejects_unknown_segments(tmp_path: Path) -> None:
    """A schedule that references an unknown segment fails."""
    dataset = _compiled(tmp_path)
    schedule = tmp_path / "schedule.csv"
    schedule.write_text(
        "segment_id,year,action_id,method,intensity,efficacy,cost\n"
        "s9,2026,a1,mowing,0.8,0.7,100.0\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="unknown segments"):
        simulate_dataset(dataset, tmp_path / "run", schedule=schedule)


def test_schedule_from_plan_and_loader(tmp_path: Path) -> None:
    """A plan converts to schedule rows and a written schedule loads back."""
    plan = Plan.model_validate_json((ROOT / "plan.json").read_text())
    rows = schedule_from_plan(plan)
    assert len(rows) == 5
    dataset = _compiled(tmp_path)
    result = simulate_dataset(dataset, tmp_path / "run", plan=ROOT / "plan.json")
    loaded = load_schedule(result.run_dir / "schedule.csv")
    assert len(loaded) == 5
    assert loaded[0].action_id == "pa1"


def test_schedule_loader_rejects_missing_columns(tmp_path: Path) -> None:
    """A schedule CSV without the required columns is rejected."""
    schedule = tmp_path / "schedule.csv"
    schedule.write_text("segment_id,year\ns1,2026\n", encoding="utf-8")
    with pytest.raises(ValueError, match="missing columns"):
        load_schedule(schedule)


def test_cli_build_simulate_and_prototype(tmp_path: Path) -> None:
    """The build, simulate, and prototype commands work end to end."""
    dataset = tmp_path / "dataset"
    build = RUNNER.invoke(
        app,
        ["build", "--fixture", str(ROOT), "--out", str(dataset)],
    )
    assert build.exit_code == 0
    assert "content_digest" in build.stdout
    run = tmp_path / "run"
    simulate = RUNNER.invoke(
        app,
        [
            "simulate",
            "--dataset",
            str(dataset),
            "--out",
            str(run),
            "--plan",
            str(ROOT / "plan.json"),
            "--years",
            "3",
        ],
    )
    assert simulate.exit_code == 0
    assert "total_cost" in simulate.stdout
    prototype = tmp_path / "prototype"
    end_to_end = RUNNER.invoke(
        app,
        ["prototype", "--fixture", str(ROOT), "--out", str(prototype), "--years", "3"],
    )
    assert end_to_end.exit_code == 0
    assert (prototype / "run" / "run.json").is_file()
