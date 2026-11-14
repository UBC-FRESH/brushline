"""Tests for the P5.7 budget, scaling, and checkpoint report."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from brushline.model.corridor import ServiceStandard
from brushline.optimization.budget import (
    NO_OPTIMALITY_STATEMENT,
    BudgetError,
    BudgetPoint,
    CheckpointMeasurement,
    QualityBudgetReport,
    ScalingPoint,
    measure_checkpoint,
    run_budget_curve,
    run_budget_report,
    run_scaling,
)
from brushline.optimization.evaluator import ScheduleEvaluator, SegmentContext
from brushline.optimization.formulation import Formulation
from brushline.optimization.validation import load_tiny_optimum
from brushline.vegetation.state_space import StateDistribution
from pydantic import ValidationError

ROOT = Path(__file__).resolve().parents[1]
FORMULATION = ROOT / "notes" / "reference" / "p5-formulation.v1.json"
OPTIMUM = ROOT / "notes" / "reference" / "p5-tiny-optimum.v1.json"


def _distribution(h: float, c: float, d: float, conf: float, sd: float = 0.2) -> StateDistribution:
    return StateDistribution(
        class_probabilities={"shrub": 0.8, "unknown": 0.2},
        height_m=h,
        height_sd=sd,
        cover_pct=c,
        cover_sd=4,
        density_per_ha=d,
        density_sd=50,
        age_years=1,
        confidence=conf,
    )


def _evaluator(service_height: float = 2.0) -> ScheduleEvaluator:
    formulation = Formulation.model_validate_json(FORMULATION.read_text(encoding="utf-8"))
    return ScheduleEvaluator(
        formulation,
        [
            SegmentContext(
                segment_id="s1",
                functional_group="shrub",
                initial=_distribution(2.0, 40, 1000, 0.6),
                service_standard=ServiceStandard(
                    service_standard_id="std1",
                    max_height_m=service_height,
                    min_clearance_m=1.0,
                ),
                length_m=100,
                asset_height_m=8,
            ),
            SegmentContext(
                segment_id="s2",
                functional_group="grass_herb",
                initial=_distribution(0.4, 70, 0, 0.8, sd=0.1),
                service_standard=ServiceStandard(
                    service_standard_id="std1",
                    max_height_m=4.0,
                    min_clearance_m=1.0,
                ),
                length_m=150,
                asset_height_m=8,
            ),
        ],
    )


def test_budget_curve_records_budgets_and_seed_variance() -> None:
    """Every budget and seed is visible, with median/best/worst values."""
    optimum = load_tiny_optimum(OPTIMUM).objective or 0.0
    report = run_budget_curve(
        _evaluator(),
        instance_id="tiny",
        budgets=[10, 10, 1],
        seeds=[1, 2],
        optimum=optimum,
        created_utc=datetime(2026, 11, 14, tzinfo=UTC),
    )
    assert [point.budget for point in report.points] == [1, 10]
    assert all(point.runs == 2 for point in report.points)
    assert all(len(point.seed_results) == 2 for point in report.points)
    for point in report.points:
        feasible = [item.objective for item in point.seed_results if item.feasible]
        if feasible:
            assert point.best_objective == min(feasible)
            assert point.worst_objective == max(feasible)
            assert point.median_objective is not None
        assert point.reach_optimum in {True, False, None}
    assert report.no_optimality == NO_OPTIMALITY_STATEMENT
    assert report.scalarization == "balanced"


def test_scaling_and_checkpoint_measurements(tmp_path: Path) -> None:
    """Scaling and checkpoint reports record timing, size, and replay."""
    evaluator = _evaluator()
    scaling = run_scaling(
        [("six-variables", evaluator), ("same", evaluator)],
        instance_id="tiny",
        seeds=[1],
        budget=5,
    )
    assert len(scaling) == 2
    assert all(point.variables == 6 for point in scaling)
    assert all(point.median_seconds >= 0 for point in scaling)
    assert all(point.peak_bytes > 0 for point in scaling)
    assert all(point.replay_ok for point in scaling)
    measurement = measure_checkpoint(
        evaluator,
        path=tmp_path / "checkpoint.json",
        instance_id="tiny",
        seed=1,
        iterations=5,
    )
    assert measurement.size_bytes > 0
    assert measurement.replay_ok
    assert measurement.objective
    assert measurement.save_seconds >= 0
    assert measurement.load_seconds >= 0


def test_complete_budget_report(tmp_path: Path) -> None:
    """The complete report composes quality, scaling, checkpoint, and caveat."""
    report = run_budget_report(
        _evaluator(),
        instance_id="tiny",
        budgets=[5],
        seeds=[1],
        checkpoint_path=tmp_path / "checkpoint.json",
        created_utc=datetime(2026, 11, 14, tzinfo=UTC),
    )
    assert report.quality.points
    assert report.scaling
    assert report.checkpoint is not None
    assert report.checkpoint.replay_ok
    assert report.no_optimality
    assert report.fresh_solutions_version


def test_budget_errors_and_model_guards() -> None:
    """Empty inputs, naive times, and bad records fail explicitly."""
    with pytest.raises(BudgetError):
        run_budget_curve(_evaluator(), instance_id="tiny", budgets=[], seeds=[1])
    with pytest.raises(BudgetError):
        run_budget_curve(_evaluator(), instance_id="tiny", budgets=[1], seeds=[])
    with pytest.raises(BudgetError):
        run_budget_curve(_evaluator(), instance_id="tiny", budgets=[-1], seeds=[1])
    with pytest.raises(BudgetError):
        run_scaling([], instance_id="tiny", seeds=[1], budget=1)
    with pytest.raises(ValidationError):
        QualityBudgetReport(
            instance_id="tiny",
            mode="local",
            scalarization="balanced",
            points=[],
            created_utc=datetime(2026, 11, 14),
        )
    with pytest.raises(ValidationError):
        QualityBudgetReport(
            instance_id="tiny",
            mode="local",
            scalarization="balanced",
            points=[BudgetPoint(budget=1, runs=1, feasible_runs=0, seed_results=[])],
            no_optimality=" ",
            created_utc=datetime(2026, 11, 14, tzinfo=UTC),
        )
    with pytest.raises(ValidationError):
        ScalingPoint(
            name="x",
            variables=1,
            runs=1,
            median_seconds=-1,
            max_seconds=0,
            peak_bytes=0,
            replay_ok=True,
        )
    with pytest.raises(ValidationError):
        CheckpointMeasurement(
            path="x",
            size_bytes=-1,
            save_seconds=0,
            load_seconds=0,
            replay_ok=True,
            objective=0,
        )
