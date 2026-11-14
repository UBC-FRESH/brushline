"""Tiny-instance exhaustive validation for the Brushline optimizer.

The validator enumerates every discrete assignment on a small formulation, finds the best feasible
scalar value, checks exact and batch evaluation agreement, and records a search run's gap and exact
replay. It is a correctness check, not a realistic-corridor optimality claim.
"""

from __future__ import annotations

import itertools
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from brushline.optimization.adapter import SearchRun
from brushline.optimization.evaluator import EvaluationResult, ScheduleEvaluator
from brushline.optimization.formulation import OBJECTIVE_NAMES, Formulation

TINY_OPTIMUM_SCHEMA_VERSION: Literal["brushline.tiny-optimum.v1"] = "brushline.tiny-optimum.v1"
TINY_VALIDATION_SCHEMA_VERSION: Literal["brushline.tiny-validation.v1"] = (
    "brushline.tiny-validation.v1"
)


class TinyValidationError(ValueError):
    """Raised when a tiny validation request is inconsistent."""


class TinyOptimum(BaseModel):
    """The exhaustive optimum of one tiny formulation.

    Parameters
    ----------
    schema_version : {"brushline.tiny-optimum.v1"}
        Schema version.
    formulation_id : str
        Formulation id.
    weights : dict of str to float
        Scalarization weights.
    total_assignments : int
        Enumerated assignments.
    feasible_assignments : int
        Feasible assignments.
    best_assignment : dict of int to int or None
        Best assignment, or None without a feasible assignment.
    objective : float or None
        Best scalar objective.
    objective_vector : dict of str to float or None
        Best four-objective vector.
    ties : int
        Number of feasible assignments at the best scalar value.
    batch_agreement : bool
        Whether exact and batch evaluation agreed for every assignment.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["brushline.tiny-optimum.v1"] = TINY_OPTIMUM_SCHEMA_VERSION
    formulation_id: str = Field(min_length=1)
    weights: dict[str, float]
    total_assignments: int = Field(ge=1)
    feasible_assignments: int = Field(ge=0)
    best_assignment: dict[int, int] | None = None
    objective: float | None = None
    objective_vector: dict[str, float] | None = None
    ties: int = Field(default=0, ge=0)
    batch_agreement: bool = True

    @model_validator(mode="after")
    def _best_shape(self) -> TinyOptimum:
        has_best = (
            self.best_assignment is not None
            and self.objective is not None
            and self.objective_vector is not None
        )
        if self.feasible_assignments and not has_best:
            raise ValueError("a feasible tiny instance needs a best assignment")
        if not self.feasible_assignments and has_best:
            raise ValueError("an infeasible tiny instance cannot have a best assignment")
        return self


class TinyValidationReport(BaseModel):
    """The exhaustive optimum plus optional search evidence.

    Parameters
    ----------
    schema_version : {"brushline.tiny-validation.v1"}
        Schema version.
    instance_id : str
        Instance id.
    optimum : TinyOptimum
        Exhaustive optimum.
    search : SearchRun or None
        Search result.
    gap : float or None
        Search scalar minus optimum scalar.
    reaches_optimum : bool
        Whether the gap is zero.
    replay_ok : bool
        Whether the search assignment replays.
    expected_ok : bool or None
        Whether a committed optimum matched.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["brushline.tiny-validation.v1"] = TINY_VALIDATION_SCHEMA_VERSION
    instance_id: str = Field(min_length=1)
    optimum: TinyOptimum
    search: SearchRun | None = None
    gap: float | None = None
    reaches_optimum: bool = False
    replay_ok: bool = True
    expected_ok: bool | None = None


def enumerate_assignments(formulation: Formulation) -> list[dict[int, int]]:
    """Enumerate every discrete assignment.

    Parameters
    ----------
    formulation : Formulation
        Optimization formulation.

    Returns
    -------
    list of dict of int to int
        Every assignment in stable variable order.
    """
    variables = sorted(formulation.variables, key=lambda item: item.index)
    return [
        {variable.index: option for variable, option in zip(variables, options, strict=True)}
        for options in itertools.product(
            *(range(len(variable.option_ids)) for variable in variables)
        )
    ]


def exhaustive_optimum(
    evaluator: ScheduleEvaluator,
    weights: dict[str, float],
) -> TinyOptimum:
    """Enumerate every assignment and return the best feasible scalar value.

    Parameters
    ----------
    evaluator : ScheduleEvaluator
        Exact evaluator.
    weights : dict of str to float
        Scalarization weights.

    Returns
    -------
    TinyOptimum
        Exhaustive optimum and exact/batch agreement.
    """
    if set(weights) != set(OBJECTIVE_NAMES):
        raise TinyValidationError("weights must name the four core objectives")
    if any(value < 0 for value in weights.values()):
        raise TinyValidationError("weights must be non-negative")
    assignments = enumerate_assignments(evaluator.formulation)
    exact: list[EvaluationResult] = [evaluator.evaluate(item) for item in assignments]
    batch = evaluator.evaluate_batch(assignments)
    batch_agreement = all(left == right for left, right in zip(exact, batch, strict=True))
    feasible = [result for result in exact if result.feasible]
    best: EvaluationResult | None = None
    best_scalar: float | None = None
    ties = 0
    for result in feasible:
        scalar = result.scalar_objective(weights)
        if best_scalar is None or scalar < best_scalar - 1e-12:
            best = result
            best_scalar = scalar
            ties = 1
        elif abs(scalar - best_scalar) <= 1e-12:
            ties += 1
            if best is None or _assignment_key(result.assignment) < _assignment_key(
                best.assignment
            ):
                best = result
    return TinyOptimum(
        formulation_id=evaluator.formulation.formulation_id,
        weights=dict(weights),
        total_assignments=len(assignments),
        feasible_assignments=len(feasible),
        best_assignment=None if best is None else dict(best.assignment),
        objective=best_scalar,
        objective_vector=None if best is None else dict(best.objective_vector),
        ties=ties,
        batch_agreement=batch_agreement,
    )


def _assignment_key(assignment: dict[int, int]) -> tuple[int, ...]:
    return tuple(assignment[index] for index in sorted(assignment))


def validate_tiny_instance(
    evaluator: ScheduleEvaluator,
    *,
    weights: dict[str, float],
    instance_id: str = "tiny",
    search: SearchRun | None = None,
    expected: TinyOptimum | None = None,
) -> TinyValidationReport:
    """Validate exhaustive and optional search results on a tiny instance.

    Parameters
    ----------
    evaluator : ScheduleEvaluator
        Exact evaluator.
    weights : dict of str to float
        Scalarization weights.
    instance_id : str, optional
        Instance id. Defaults to ``tiny``.
    search : SearchRun or None, optional
        Search result to compare.
    expected : TinyOptimum or None, optional
        Committed optimum to compare.

    Returns
    -------
    TinyValidationReport
        Optimum, gap, replay, and expected-match evidence.
    """
    optimum = exhaustive_optimum(evaluator, weights)
    gap: float | None = None
    reaches = False
    replay_ok = True
    if search is not None:
        if optimum.objective is not None:
            if search.feasible:
                gap = search.objective - optimum.objective
                reaches = abs(gap) <= 1e-9
            else:
                gap = None
        replayed = evaluator.evaluate(dict(search.assignment))
        replay_ok = (
            replayed.feasible == search.feasible
            and abs(replayed.scalar_objective(weights) - search.objective) <= 1e-9
        )
    expected_ok: bool | None = None
    if expected is not None:
        expected_ok = (
            expected.best_assignment == optimum.best_assignment
            and expected.objective == optimum.objective
            and expected.total_assignments == optimum.total_assignments
        )
    return TinyValidationReport(
        instance_id=instance_id,
        optimum=optimum,
        search=search,
        gap=gap,
        reaches_optimum=reaches,
        replay_ok=replay_ok,
        expected_ok=expected_ok,
    )


def write_tiny_optimum(optimum: TinyOptimum, path: str | Path) -> Path:
    """Write a tiny optimum as JSON.

    Parameters
    ----------
    optimum : TinyOptimum
        Optimum.
    path : str or Path
        Destination.

    Returns
    -------
    Path
        Written path.
    """
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(optimum.model_dump_json(indent=2) + "\n", encoding="utf-8")
    return destination


def load_tiny_optimum(path: str | Path) -> TinyOptimum:
    """Load a tiny optimum.

    Parameters
    ----------
    path : str or Path
        Source.

    Returns
    -------
    TinyOptimum
        Loaded optimum.
    """
    return TinyOptimum.model_validate_json(Path(path).read_text(encoding="utf-8"))


def write_tiny_validation(report: TinyValidationReport, path: str | Path) -> Path:
    """Write a tiny validation report.

    Parameters
    ----------
    report : TinyValidationReport
        Report.
    path : str or Path
        Destination.

    Returns
    -------
    Path
        Written path.
    """
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(report.model_dump_json(indent=2) + "\n", encoding="utf-8")
    return destination


def load_tiny_validation(path: str | Path) -> TinyValidationReport:
    """Load a tiny validation report.

    Parameters
    ----------
    path : str or Path
        Source.

    Returns
    -------
    TinyValidationReport
        Loaded report.
    """
    return TinyValidationReport.model_validate_json(Path(path).read_text(encoding="utf-8"))


__all__ = [
    "TINY_OPTIMUM_SCHEMA_VERSION",
    "TINY_VALIDATION_SCHEMA_VERSION",
    "TinyOptimum",
    "TinyValidationError",
    "TinyValidationReport",
    "enumerate_assignments",
    "exhaustive_optimum",
    "load_tiny_optimum",
    "load_tiny_validation",
    "validate_tiny_instance",
    "write_tiny_optimum",
    "write_tiny_validation",
]
