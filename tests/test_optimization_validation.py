"""Tests for the P5.6 tiny-instance exhaustive validation."""

from __future__ import annotations

from pathlib import Path

import pytest
from brushline.model.corridor import ServiceStandard
from brushline.optimization.adapter import SCALARIZATIONS, SearchSpec, run_search
from brushline.optimization.evaluator import ScheduleEvaluator, SegmentContext
from brushline.optimization.formulation import Formulation
from brushline.optimization.validation import (
    TinyOptimum,
    TinyValidationError,
    TinyValidationReport,
    enumerate_assignments,
    exhaustive_optimum,
    load_tiny_optimum,
    load_tiny_validation,
    validate_tiny_instance,
    write_tiny_optimum,
    write_tiny_validation,
)
from brushline.vegetation.state_space import StateDistribution
from pydantic import ValidationError

ROOT = Path(__file__).resolve().parents[1]
FORMULATION = ROOT / "notes" / "reference" / "p5-formulation.v1.json"
OPTIMUM = ROOT / "notes" / "reference" / "p5-tiny-optimum.v1.json"
BALANCED = next(item.weights for item in SCALARIZATIONS if item.name == "balanced")


def _distribution(
    height: float, cover: float, density: float, confidence: float, sd: float = 0.2
) -> StateDistribution:
    return StateDistribution(
        class_probabilities={"shrub": 0.8, "unknown": 0.2},
        height_m=height,
        height_sd=sd,
        cover_pct=cover,
        cover_sd=4,
        density_per_ha=density,
        density_sd=50,
        age_years=1,
        confidence=confidence,
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


def test_enumerate_assignments_is_complete_and_stable() -> None:
    """The enumerator covers every variable and option exactly once."""
    evaluator = _evaluator()
    assignments = enumerate_assignments(evaluator.formulation)
    assert len(assignments) == 324
    assert len({tuple(sorted(item.items())) for item in assignments}) == 324
    assert all(set(item) == set(range(6)) for item in assignments)
    assert assignments[0] == {0: 0, 1: 0, 2: 0, 3: 0, 4: 0, 5: 0}


def test_committed_optimum_matches_exhaustive_search() -> None:
    """The committed known optimum is exactly the enumerated best."""
    expected = load_tiny_optimum(OPTIMUM)
    optimum = exhaustive_optimum(_evaluator(), BALANCED)
    assert optimum.total_assignments == 324
    assert optimum.feasible_assignments == 72
    assert optimum.ties == 1
    assert optimum.batch_agreement
    assert optimum.best_assignment == expected.best_assignment
    assert optimum.objective == pytest.approx(expected.objective or 0.0)
    assert optimum.objective_vector is not None
    assert optimum.objective_vector["present_cost"] == 100.0
    assert optimum.best_assignment == {0: 1, 1: 1, 2: 0, 3: 0, 4: 0, 5: 0}


def test_tiny_search_reaches_optimum_and_replays() -> None:
    """A local search reaches the tiny optimum and replays exactly."""
    evaluator = _evaluator()
    run = run_search(
        evaluator,
        SearchSpec(mode="local", instance_id="tiny", seed=7, iterations=100),
    )
    report = validate_tiny_instance(
        evaluator,
        weights=BALANCED,
        instance_id="tiny",
        search=run,
        expected=load_tiny_optimum(OPTIMUM),
    )
    assert report.reaches_optimum
    assert report.gap == pytest.approx(0.0)
    assert report.replay_ok
    assert report.expected_ok is True
    assert report.search is not None


def test_gap_and_replay_failures_are_reported_not_hidden() -> None:
    """A worse or non-replaying search result is reported explicitly."""
    evaluator = _evaluator()
    run = run_search(
        evaluator,
        SearchSpec(mode="local", instance_id="tiny", seed=7, iterations=100),
    )
    worse = run.model_copy(
        update={
            "objective": run.objective + 1.0,
            "assignment": evaluator.initial_assignment(),
        }
    )
    report = validate_tiny_instance(evaluator, weights=BALANCED, search=worse)
    assert report.gap is not None
    assert report.gap > 0
    assert not report.reaches_optimum
    assert not report.replay_ok
    mismatch = load_tiny_optimum(OPTIMUM).model_copy(update={"objective": 0.0})
    report = validate_tiny_instance(evaluator, weights=BALANCED, expected=mismatch)
    assert report.expected_ok is False


def test_infeasible_tiny_instance_has_no_best_assignment() -> None:
    """An instance with no feasible assignment is explicit."""
    evaluator = _evaluator(service_height=0.01)
    optimum = exhaustive_optimum(evaluator, BALANCED)
    assert optimum.feasible_assignments == 0
    assert optimum.best_assignment is None
    assert optimum.objective is None
    with pytest.raises(ValidationError):
        TinyOptimum(
            formulation_id="x",
            weights=BALANCED,
            total_assignments=1,
            feasible_assignments=0,
            best_assignment={0: 0},
            objective=0.0,
            objective_vector=dict.fromkeys(BALANCED, 0.0),
        )


def test_tiny_reports_and_optima_round_trip(tmp_path: Path) -> None:
    """The optimum and validation reports round-trip as JSON."""
    evaluator = _evaluator()
    optimum = exhaustive_optimum(evaluator, BALANCED)
    optimum_path = tmp_path / "optimum.json"
    assert write_tiny_optimum(optimum, optimum_path) == optimum_path
    assert load_tiny_optimum(optimum_path) == optimum
    report = validate_tiny_instance(
        evaluator,
        weights=BALANCED,
        expected=optimum,
    )
    report_path = tmp_path / "validation.json"
    assert write_tiny_validation(report, report_path) == report_path
    assert load_tiny_validation(report_path) == report
    assert isinstance(report, TinyValidationReport)
    with pytest.raises(TinyValidationError):
        exhaustive_optimum(evaluator, {"present_cost": 1.0})
    with pytest.raises(TinyValidationError):
        exhaustive_optimum(evaluator, {**BALANCED, "present_cost": -1.0})


def test_tie_and_no_optimum_edges() -> None:
    """Ties, missing best assignments, and infeasible searches are explicit."""
    evaluator = _evaluator()
    with pytest.raises(ValidationError):
        TinyOptimum(
            formulation_id="x",
            weights=BALANCED,
            total_assignments=1,
            feasible_assignments=1,
        )
    tied = exhaustive_optimum(evaluator, dict.fromkeys(BALANCED, 0.0))
    assert tied.ties > 1
    infeasible_run = run_search(
        evaluator,
        SearchSpec(mode="local", instance_id="tiny", seed=7, iterations=1),
    )
    assert not infeasible_run.feasible
    infeasible_report = validate_tiny_instance(evaluator, weights=BALANCED, search=infeasible_run)
    assert infeasible_report.gap is None
    no_optimum_evaluator = _evaluator(service_height=0.01)
    no_optimum_run = run_search(
        no_optimum_evaluator,
        SearchSpec(mode="local", instance_id="tiny", seed=7, iterations=1),
    )
    no_optimum_report = validate_tiny_instance(
        no_optimum_evaluator, weights=BALANCED, search=no_optimum_run
    )
    assert no_optimum_report.gap is None
