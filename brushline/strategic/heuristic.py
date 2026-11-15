"""Fresh Solutions heuristic for the stateful strategic problem.

The adapter exposes one discrete treatment choice per segment-period. Evaluation simulates the
linear risk state, budget, and crew-hour constraints. The heuristic is used when the exact MILP is
too large for the available time; its result is explicitly marked feasible, not optimal.
"""

from __future__ import annotations

import importlib.metadata
import random
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:  # pragma: no cover - optional dependency typing
    from fresh_solutions.contracts import Change, Evaluation

from brushline.strategic.stateful import (
    StatefulConfig,
    StatefulMethod,
    StatefulPeriod,
    StatefulPlan,
    StatefulSegment,
    replay_stateful_choices,
)

HEURISTIC_SCHEMA_VERSION: Literal["brushline.stateful-heuristic.v1"] = (
    "brushline.stateful-heuristic.v1"
)
ADAPTER_NAME = "brushline.strategic.stateful-heuristic.v1"


class HeuristicError(ValueError):
    """Raised when heuristic inputs or a replayed result are inconsistent."""


def _fresh_version() -> str:
    try:
        return importlib.metadata.version("fresh-solutions")
    except importlib.metadata.PackageNotFoundError:
        return "not-installed"


class StatefulHeuristicAdapter:
    """Fresh Solutions adapter over segment-period treatment choices."""

    name = ADAPTER_NAME

    def __init__(
        self,
        segments: list[StatefulSegment],
        methods: list[StatefulMethod],
        periods: list[StatefulPeriod],
        config: StatefulConfig,
    ) -> None:
        self.segments = segments
        self.methods = methods
        self.periods = periods
        self.config = config
        self._options = ["none", *[method.method for method in methods]]
        self._method_index = {method.method: index + 1 for index, method in enumerate(methods)}
        self._period_budget = {period.year: period.budget for period in periods}
        self._period_capacity = {period.year: period.capacity_hours for period in periods}

    @property
    def variable_count(self) -> int:
        """Return the number of segment-period choices."""
        return len(self.segments) * len(self.periods)

    def option_count(self, variable: int) -> int:
        """Return the option count for one segment-period variable."""
        self._validate_variable(variable)
        return len(self._options)

    def option_at(self, variable: int, option: int) -> object:
        """Return the method name for an option."""
        self._validate_variable(variable)
        if not 0 <= option < len(self._options):
            raise HeuristicError("option index out of range")
        return self._options[option]

    def initial_assignment(self) -> dict[int, int]:
        """Seed search with a deterministic risk-per-dollar greedy assignment."""
        assignment = dict.fromkeys(range(self.variable_count), 0)
        risk = [segment.initial_risk for segment in self.segments]
        for period_index, period in enumerate(self.periods):
            risk = [min(0.95, value + self.config.growth_per_year) for value in risk]
            candidates = []
            for segment_index, segment in enumerate(self.segments):
                for method_index, method in enumerate(self.methods):
                    cost = segment.area_ha * method.cost_per_ha
                    hours = segment.area_ha * method.hours_per_ha
                    post = max(0.0, risk[segment_index] - method.risk_reduction)
                    benefit = risk[segment_index] - post
                    score = benefit / max(cost, 1.0)
                    candidates.append((score, segment_index, method_index, cost, hours, post))
            candidates.sort(key=lambda item: (-item[0], item[1], item[2]))
            spent = 0.0
            used_hours = 0.0
            used: set[int] = set()
            for _score, segment_index, method_index, cost, hours, post in candidates:
                if segment_index in used:
                    continue
                if spent + cost > period.budget or used_hours + hours > period.capacity_hours:
                    continue
                used.add(segment_index)
                assignment[segment_index * len(self.periods) + period_index] = method_index + 1
                risk[segment_index] = post
                spent += cost
                used_hours += hours
        return assignment

    def random_assignment(self, rng: random.Random) -> dict[int, int]:
        """Return a random complete assignment."""
        return {
            variable: rng.randrange(len(self._options)) for variable in range(self.variable_count)
        }

    def mutate(
        self, assignment: Mapping[int, int], rate: float, rng: random.Random
    ) -> dict[int, int]:
        """Mutate a fraction of variables without leaving the option range."""
        if not 0 <= rate <= 1:
            raise HeuristicError("mutation rate must be between zero and one")
        result = dict(assignment)
        for variable in result:
            if rng.random() < rate:
                result[variable] = rng.randrange(len(self._options))
        return result

    def crossover(
        self, left: Mapping[int, int], right: Mapping[int, int], rng: random.Random
    ) -> dict[int, int]:
        """Create a random child from two complete assignments."""
        return {
            variable: left[variable] if rng.random() < 0.5 else right[variable]
            for variable in range(self.variable_count)
        }

    def evaluate(self, assignment: Mapping[int, int]) -> Evaluation:
        """Evaluate feasibility, risk, cost, and hours with exact state replay."""
        from fresh_solutions.contracts import Evaluation

        selected = self._selected(assignment)
        actions, years, total_cost, total_hours, mean_risk = replay_stateful_choices(
            self.segments,
            self.methods,
            self.periods,
            self.config,
            selected,
        )
        violations = 0
        for row in years:
            if row.cost > self._period_budget[row.year] + 1e-9:
                violations += 1
            if row.hours > self._period_capacity[row.year] + 1e-9:
                violations += 1
        objective = (
            self.config.risk_weight * mean_risk
            + self.config.cost_weight * total_cost / 100000.0
            + 1_000_000.0 * violations
        )
        return Evaluation(
            objective=objective,
            feasible=violations == 0,
            details={
                "actions": float(len(actions)),
                "cost": total_cost,
                "hours": total_hours,
                "risk": mean_risk,
                "service": 1.0 - mean_risk,
                "violations": float(violations),
            },
        )

    def evaluate_batch(self, assignments: Sequence[Mapping[int, int]]) -> list[Evaluation]:
        """Evaluate a batch of assignments."""
        return [self.evaluate(assignment) for assignment in assignments]

    def propose(self, assignment: Mapping[int, int], rng: random.Random) -> Change | None:
        """Propose one variable-option change."""
        from fresh_solutions.contracts import Change

        variable = rng.randrange(self.variable_count)
        before = assignment[variable]
        after = rng.randrange(len(self._options) - 1)
        if after >= before:
            after += 1
        return Change(variable=variable, before=before, after=after)

    def apply(self, assignment: Mapping[int, int], change: Change) -> dict[int, int]:
        """Apply one validated change."""
        self._validate_change(assignment, change)
        result = dict(assignment)
        result[change.variable] = change.after
        return result

    def undo(self, assignment: Mapping[int, int], change: Change) -> dict[int, int]:
        """Undo one validated change."""
        self._validate_change(assignment, change, reverse=True)
        result = dict(assignment)
        result[change.variable] = change.before
        return result

    def _selected(self, assignment: Mapping[int, int]) -> dict[tuple[int, int, int], bool]:
        if set(assignment) != set(range(self.variable_count)):
            raise HeuristicError("assignment must cover every segment-period variable")
        selected: dict[tuple[int, int, int], bool] = {}
        for variable, option in assignment.items():
            if not 0 <= option < len(self._options):
                raise HeuristicError("option index out of range")
            if option == 0:
                continue
            segment, period = divmod(variable, len(self.periods))
            selected[(segment, period, option - 1)] = True
        return selected

    def _validate_variable(self, variable: int) -> None:
        if not 0 <= variable < self.variable_count:
            raise HeuristicError("variable index out of range")

    def _validate_change(
        self, assignment: Mapping[int, int], change: Change, *, reverse: bool = False
    ) -> None:
        self._validate_variable(change.variable)
        expected = change.after if reverse else change.before
        if assignment[change.variable] != expected:
            raise HeuristicError("change does not match the current assignment")
        if not 0 <= change.after < len(self._options):
            raise HeuristicError("option index out of range")


def build_stateful_heuristic(
    *,
    instance_id: str,
    segments: list[StatefulSegment],
    methods: list[StatefulMethod],
    periods: list[StatefulPeriod],
    config: StatefulConfig | None = None,
    iterations: int = 1200,
    seed: int = 7,
    temperature: float = 2.0,
    cooling: float = 0.997,
    created_utc: datetime | None = None,
) -> StatefulPlan:
    """Run Fresh Solutions local search over the stateful assignment.

    Parameters
    ----------
    instance_id : str
        Instance id.
    segments, methods, periods : list
        Stateful problem inputs.
    config : StatefulConfig, optional
        Risk growth and objective weights.
    iterations : int, optional
        Local-search iterations.
    seed : int, optional
        Deterministic search seed.
    temperature, cooling : float, optional
        Annealing schedule.
    created_utc : datetime, optional
        Creation time.

    Returns
    -------
    StatefulPlan
        Feasible heuristic plan and search provenance.

    Raises
    ------
    HeuristicError
        If the search cannot produce a feasible assignment.
    """
    from fresh_solutions import SearchConfig, run_local_search

    if not segments or not methods or not periods:
        raise HeuristicError("segments, methods, and periods must be non-empty")
    rules = config or StatefulConfig()
    adapter = StatefulHeuristicAdapter(segments, methods, periods, rules)
    result = run_local_search(
        adapter,
        SearchConfig(
            iterations=iterations,
            seed=seed,
            temperature=temperature,
            cooling=cooling,
        ),
    )
    if not result.feasible:
        raise HeuristicError("heuristic search did not find a feasible assignment")
    selected = adapter._selected(result.assignment)
    actions, years, total_cost, total_hours, mean_risk = replay_stateful_choices(
        segments, methods, periods, rules, selected
    )
    objective = rules.risk_weight * mean_risk + rules.cost_weight * total_cost / 100000.0
    return StatefulPlan(
        instance_id=instance_id,
        status="feasible",
        solver_status=0,
        solver_message="Fresh Solutions local search; feasible heuristic incumbent",
        solver="fresh-solutions/local-search",
        objective=round(objective, 4),
        total_cost=round(total_cost, 2),
        total_hours=round(total_hours, 2),
        mean_risk=round(mean_risk, 4),
        mean_service=round(1.0 - mean_risk, 4),
        actions=actions,
        years=years,
        replay_ok=abs(objective - result.objective) <= 1e-4,
        search={
            "adapter": ADAPTER_NAME,
            "fresh_solutions_version": _fresh_version(),
            "seed": seed,
            "iterations": iterations,
            "evaluations": result.evaluations,
            "accepted": result.accepted,
        },
        created_utc=created_utc or datetime.now(UTC),
    )


__all__ = [
    "ADAPTER_NAME",
    "HEURISTIC_SCHEMA_VERSION",
    "HeuristicError",
    "StatefulHeuristicAdapter",
    "build_stateful_heuristic",
]
