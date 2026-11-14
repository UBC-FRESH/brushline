"""Search-budget, seed-variance, scaling, and checkpoint certification.

The report never hides a seed or a budget: every point names the requested budget, actual exact
evaluations, seed outcomes, replay flag, and stopping rule. A realistic-corridor global-optimality
claim is explicitly out of scope.
"""

from __future__ import annotations

import statistics
import time
import tracemalloc
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from brushline.optimization.adapter import (
    ADAPTER_VERSION,
    Scalarization,
    SearchSpec,
    fresh_solutions_version,
    replay_checkpoint,
    run_search,
)
from brushline.optimization.evaluator import ScheduleEvaluator

NO_OPTIMALITY_STATEMENT = (
    "Brushline reports a search incumbent with its budget, seed, and stopping rule; "
    "it does not claim global optimality on realistic corridors."
)


class BudgetError(ValueError):
    """Raised when a budget experiment is inconsistent."""


class SeedResult(BaseModel):
    """One seed at one budget.

    Parameters
    ----------
    seed : int
        Seed.
    budget : int
        Requested budget.
    objective : float
        Scalar objective.
    feasible : bool
        Feasibility.
    evaluations : int
        Exact evaluations.
    replay_ok : bool
        Exact replay flag.
    stop_reason : str
        Stop reason.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    seed: int
    budget: int = Field(ge=0)
    objective: float
    feasible: bool
    evaluations: int = Field(ge=0)
    replay_ok: bool
    stop_reason: str


class BudgetPoint(BaseModel):
    """Quality at one budget across seeds.

    Parameters
    ----------
    budget : int
        Requested budget.
    runs : int
        Number of seeds.
    feasible_runs : int
        Feasible seeds.
    best_objective : float or None
        Best feasible objective.
    median_objective : float or None
        Median feasible objective.
    worst_objective : float or None
        Worst feasible objective.
    reach_optimum : bool or None
        Whether every feasible seed reaches a supplied optimum.
    seed_results : list of SeedResult
        Per-seed results.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    budget: int = Field(ge=0)
    runs: int = Field(ge=1)
    feasible_runs: int = Field(ge=0)
    best_objective: float | None = None
    median_objective: float | None = None
    worst_objective: float | None = None
    reach_optimum: bool | None = None
    seed_results: list[SeedResult] = Field(default_factory=list)


class QualityBudgetReport(BaseModel):
    """Quality-versus-budget and seed-variance evidence.

    Parameters
    ----------
    schema_version : {"brushline.optimization-budget.v1"}
        Schema version.
    instance_id : str
        Instance id.
    mode : str
        Search mode.
    scalarization : str
        Scalarization name.
    optimum : float or None
        Known optimum, when supplied.
    points : list of BudgetPoint
        Budget points.
    no_optimality : str
        No-optimality statement.
    created_utc : datetime
        Timezone-aware creation time.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = "brushline.optimization-budget.v1"
    instance_id: str = Field(min_length=1)
    mode: str
    scalarization: str
    optimum: float | None = None
    points: list[BudgetPoint] = Field(min_length=1)
    no_optimality: str = NO_OPTIMALITY_STATEMENT
    created_utc: datetime

    @model_validator(mode="after")
    def _report(self) -> QualityBudgetReport:
        if not self.no_optimality.strip():
            raise ValueError("the no-optimality statement is required")
        if self.created_utc.tzinfo is None:
            raise ValueError("created_utc must be timezone-aware")
        return self


class ScalingPoint(BaseModel):
    """Timing for one instance size.

    Parameters
    ----------
    name : str
        Instance label.
    variables : int
        Variable count.
    runs : int
        Seed runs.
    best_objective : float or None
        Best feasible objective.
    median_seconds : float
        Median wall time.
    max_seconds : float
        Maximum wall time.
    peak_bytes : int
        Peak traced memory across runs.
    replay_ok : bool
        All runs replay.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str = Field(min_length=1)
    variables: int = Field(ge=0)
    runs: int = Field(ge=1)
    best_objective: float | None = None
    median_seconds: float = Field(ge=0)
    max_seconds: float = Field(ge=0)
    peak_bytes: int = Field(ge=0)
    replay_ok: bool


class CheckpointMeasurement(BaseModel):
    """Checkpoint/resume timing and replay.

    Parameters
    ----------
    path : str
        Checkpoint path.
    size_bytes : int
        File size.
    save_seconds : float
        Save time.
    load_seconds : float
        Load and replay time.
    replay_ok : bool
        Replay flag.
    objective : float
        Replayed objective.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    path: str
    size_bytes: int = Field(ge=0)
    save_seconds: float = Field(ge=0)
    load_seconds: float = Field(ge=0)
    replay_ok: bool
    objective: float


class BudgetReport(BaseModel):
    """The complete budget and performance report.

    Parameters
    ----------
    schema_version : {"brushline.optimization-budget-report.v1"}
        Schema version.
    quality : QualityBudgetReport
        Quality and seed evidence.
    scaling : list of ScalingPoint
        Scaling evidence.
    checkpoint : CheckpointMeasurement or None
        Checkpoint evidence.
    adapter_version : str
        Adapter version.
    fresh_solutions_version : str
        Fresh Solutions version.
    no_optimality : str
        No-optimality statement.
    created_utc : datetime
        Timezone-aware creation time.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = "brushline.optimization-budget-report.v1"
    quality: QualityBudgetReport
    scaling: list[ScalingPoint] = Field(default_factory=list)
    checkpoint: CheckpointMeasurement | None = None
    adapter_version: str = ADAPTER_VERSION
    fresh_solutions_version: str
    no_optimality: str = NO_OPTIMALITY_STATEMENT
    created_utc: datetime


def run_budget_curve(
    evaluator: ScheduleEvaluator,
    *,
    instance_id: str,
    budgets: list[int],
    seeds: list[int],
    scalarization: Scalarization | None = None,
    mode: Literal["local"] = "local",
    optimum: float | None = None,
    created_utc: datetime | None = None,
) -> QualityBudgetReport:
    """Run a local-search budget curve across seeds.

    Parameters
    ----------
    evaluator : ScheduleEvaluator
        Exact evaluator.
    instance_id : str
        Instance id.
    budgets : list of int
        Requested local iterations.
    seeds : list of int
        Seeds.
    scalarization : Scalarization, optional
        Objective weights.
    mode : str, optional
        Search mode. Defaults to local.
    optimum : float or None, optional
        Known optimum.
    created_utc : datetime, optional
        Creation time.

    Returns
    -------
    QualityBudgetReport
        Budget and seed evidence.
    """
    if not budgets or any(budget < 0 for budget in budgets):
        raise BudgetError("budgets must be non-empty and non-negative")
    if not seeds:
        raise BudgetError("at least one seed is required")
    points: list[BudgetPoint] = []
    for budget in sorted(set(budgets)):
        seed_results: list[SeedResult] = []
        for seed in seeds:
            spec = SearchSpec(mode=mode, instance_id=instance_id, seed=seed, iterations=budget)
            run = run_search(evaluator, spec, scalarization=scalarization)
            seed_results.append(
                SeedResult(
                    seed=seed,
                    budget=budget,
                    objective=run.objective,
                    feasible=run.feasible,
                    evaluations=run.evaluations,
                    replay_ok=run.replay_ok,
                    stop_reason=run.stop_reason,
                )
            )
        feasible = [item.objective for item in seed_results if item.feasible]
        reach: bool | None = None
        if optimum is not None:
            reach = bool(feasible) and all(abs(value - optimum) <= 1e-9 for value in feasible)
        points.append(
            BudgetPoint(
                budget=budget,
                runs=len(seed_results),
                feasible_runs=len(feasible),
                best_objective=min(feasible) if feasible else None,
                median_objective=statistics.median(feasible) if feasible else None,
                worst_objective=max(feasible) if feasible else None,
                reach_optimum=reach,
                seed_results=seed_results,
            )
        )
    scalar = scalarization or _balanced()
    return QualityBudgetReport(
        instance_id=instance_id,
        mode=mode,
        scalarization=scalar.name,
        optimum=optimum,
        points=points,
        created_utc=created_utc or datetime.now(UTC),
    )


def _balanced() -> Scalarization:
    from brushline.optimization.adapter import SCALARIZATIONS

    return next(item for item in SCALARIZATIONS if item.name == "balanced")


def run_scaling(
    cases: list[tuple[str, ScheduleEvaluator]],
    *,
    instance_id: str,
    seeds: list[int],
    budget: int,
    scalarization: Scalarization | None = None,
) -> list[ScalingPoint]:
    """Measure deterministic local-search timing for each case.

    Parameters
    ----------
    cases : list of (str, ScheduleEvaluator)
        Label and evaluator pairs.
    instance_id : str
        Instance id.
    seeds : list of int
        Seeds.
    budget : int
        Local iterations.
    scalarization : Scalarization, optional
        Objective weights.

    Returns
    -------
    list of ScalingPoint
        Timing and memory by case.
    """
    if not cases or not seeds:
        raise BudgetError("cases and seeds must be non-empty")
    points: list[ScalingPoint] = []
    for name, evaluator in cases:
        seconds: list[float] = []
        objectives: list[float] = []
        replay_ok = True
        peak = 0
        for seed in seeds:
            tracemalloc.start()
            started = time.perf_counter()
            run = run_search(
                evaluator,
                SearchSpec(
                    mode="local",
                    instance_id=instance_id,
                    seed=seed,
                    iterations=budget,
                ),
                scalarization=scalarization,
            )
            seconds.append(time.perf_counter() - started)
            _, run_peak = tracemalloc.get_traced_memory()
            tracemalloc.stop()
            peak = max(peak, run_peak)
            replay_ok = replay_ok and run.replay_ok
            if run.feasible:
                objectives.append(run.objective)
        points.append(
            ScalingPoint(
                name=name,
                variables=evaluator.formulation.variable_count,
                runs=len(seeds),
                best_objective=min(objectives) if objectives else None,
                median_seconds=statistics.median(seconds),
                max_seconds=max(seconds),
                peak_bytes=peak,
                replay_ok=replay_ok,
            )
        )
    return points


def measure_checkpoint(
    evaluator: ScheduleEvaluator,
    *,
    path: str | Path,
    instance_id: str,
    seed: int,
    iterations: int,
    scalarization: Scalarization | None = None,
) -> CheckpointMeasurement:
    """Save, load, and replay one checkpoint.

    Parameters
    ----------
    evaluator : ScheduleEvaluator
        Exact evaluator.
    path : str or Path
        Destination.
    instance_id : str
        Instance id.
    seed : int
        Seed.
    iterations : int
        Local iterations.
    scalarization : Scalarization, optional
        Objective weights.

    Returns
    -------
    CheckpointMeasurement
        Timing, size, and replay evidence.
    """
    destination = Path(path)
    started = time.perf_counter()
    run_search(
        evaluator,
        SearchSpec(mode="local", instance_id=instance_id, seed=seed, iterations=iterations),
        scalarization=scalarization,
        checkpoint_path=destination,
    )
    save_seconds = time.perf_counter() - started
    load_started = time.perf_counter()
    replay = replay_checkpoint(evaluator, destination, scalarization=scalarization)
    load_seconds = time.perf_counter() - load_started
    return CheckpointMeasurement(
        path=str(destination),
        size_bytes=destination.stat().st_size,
        save_seconds=save_seconds,
        load_seconds=load_seconds,
        replay_ok=replay.replay_ok,
        objective=replay.objective,
    )


def run_budget_report(
    evaluator: ScheduleEvaluator,
    *,
    instance_id: str,
    budgets: list[int],
    seeds: list[int],
    scaling_cases: list[tuple[str, ScheduleEvaluator]] | None = None,
    checkpoint_path: str | Path | None = None,
    scalarization: Scalarization | None = None,
    optimum: float | None = None,
    created_utc: datetime | None = None,
) -> BudgetReport:
    """Build the complete budget, scaling, and checkpoint report.

    Parameters
    ----------
    evaluator : ScheduleEvaluator
        Exact evaluator.
    instance_id : str
        Instance id.
    budgets : list of int
        Local budgets.
    seeds : list of int
        Seeds.
    scaling_cases : list of (str, ScheduleEvaluator) or None, optional
        Scaling cases. Defaults to the primary case.
    checkpoint_path : str or Path, optional
        Checkpoint path.
    scalarization : Scalarization, optional
        Objective weights.
    optimum : float or None, optional
        Known optimum.
    created_utc : datetime, optional
        Creation time.

    Returns
    -------
    BudgetReport
        Complete evidence.
    """
    quality = run_budget_curve(
        evaluator,
        instance_id=instance_id,
        budgets=budgets,
        seeds=seeds,
        scalarization=scalarization,
        optimum=optimum,
        created_utc=created_utc,
    )
    scaling = run_scaling(
        scaling_cases or [(instance_id, evaluator)],
        instance_id=instance_id,
        seeds=seeds[:1],
        budget=max(budgets),
        scalarization=scalarization,
    )
    checkpoint = None
    if checkpoint_path is not None:
        checkpoint = measure_checkpoint(
            evaluator,
            path=checkpoint_path,
            instance_id=instance_id,
            seed=seeds[0],
            iterations=max(budgets),
            scalarization=scalarization,
        )
    return BudgetReport(
        quality=quality,
        scaling=scaling,
        checkpoint=checkpoint,
        fresh_solutions_version=fresh_solutions_version(),
        created_utc=created_utc or datetime.now(UTC),
    )


__all__ = [
    "NO_OPTIMALITY_STATEMENT",
    "BudgetError",
    "BudgetPoint",
    "BudgetReport",
    "CheckpointMeasurement",
    "QualityBudgetReport",
    "ScalingPoint",
    "SeedResult",
    "measure_checkpoint",
    "run_budget_curve",
    "run_budget_report",
    "run_scaling",
]
