"""Fresh Solutions adapter and exact replay for Brushline schedules.

The adapter maps the Brushline formulation onto the Fresh Solutions ``ProblemAdapter`` contract
and scalarizes the four-objective vector for single-objective search. Every reported incumbent is
replayed through the exact evaluator; a mismatch is an error, not a warning.

Fresh Solutions is optional. Importing this module does not import it; search calls do.
"""

from __future__ import annotations

import importlib.metadata
import random
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from brushline.optimization.evaluator import (
    ScheduleEvaluator,
)
from brushline.optimization.formulation import OBJECTIVE_NAMES
from brushline.optimization.operators import (
    Move,
    OperatorConfig,
    OperatorState,
    default_operators,
    repair_assignment,
)

if TYPE_CHECKING:  # pragma: no cover - typing only
    from fresh_solutions.contracts import Change, Evaluation

ADAPTER_NAME = "brushline.optimization.adapter.v1"
ADAPTER_VERSION = "p5.4"
INFEASIBLE_PENALTY = 1.0e9
SCALARIZATION_NAMES: tuple[str, ...] = (
    "cost_first",
    "risk_first",
    "service_first",
    "uncertainty_first",
    "balanced",
)


class AdapterError(ValueError):
    """Raised when the adapter, search, or replay is inconsistent."""


class Scalarization(BaseModel):
    """One non-negative objective weighting.

    Parameters
    ----------
    name : str
        Scalarization name.
    weights : dict of str to float
        Weights for the four objectives.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str = Field(min_length=1)
    weights: dict[str, float]

    @model_validator(mode="after")
    def _weights(self) -> Scalarization:
        if set(self.weights) != set(OBJECTIVE_NAMES):
            raise ValueError("weights must name the four core objectives")
        if any(value < 0 for value in self.weights.values()):
            raise ValueError("weights must be non-negative")
        if abs(sum(self.weights.values())) <= 1e-12:
            raise ValueError("weights must not all be zero")
        return self


SCALARIZATIONS: tuple[Scalarization, ...] = (
    Scalarization(
        name="cost_first",
        weights={
            "present_cost": 0.7,
            "service_risk": 0.1,
            "service_attainment": 0.1,
            "uncertainty": 0.1,
        },
    ),
    Scalarization(
        name="risk_first",
        weights={
            "present_cost": 0.1,
            "service_risk": 0.7,
            "service_attainment": 0.1,
            "uncertainty": 0.1,
        },
    ),
    Scalarization(
        name="service_first",
        weights={
            "present_cost": 0.1,
            "service_risk": 0.1,
            "service_attainment": 0.7,
            "uncertainty": 0.1,
        },
    ),
    Scalarization(
        name="uncertainty_first",
        weights={
            "present_cost": 0.1,
            "service_risk": 0.1,
            "service_attainment": 0.1,
            "uncertainty": 0.7,
        },
    ),
    Scalarization(
        name="balanced",
        weights={
            "present_cost": 0.25,
            "service_risk": 0.25,
            "service_attainment": 0.25,
            "uncertainty": 0.25,
        },
    ),
)


class SearchSpec(BaseModel):
    """Search budget and stopping settings.

    Parameters
    ----------
    mode : {"local", "population", "hybrid", "convergence"}
        Search mode.
    instance_id : str
        Stable instance id.
    seed : int
        Random seed.
    iterations : int
        Local-search iterations.
    temperature : float
        Initial temperature.
    cooling : float
        Cooling factor.
    population : int
        Population size.
    generations : int
        Generations.
    mutation_rate : float
        Mutation rate.
    elite_fraction : float
        Elite fraction.
    tournament_size : int
        Tournament size.
    random_fraction : float
        Random initial population fraction.
    local_iterations : int
        Local-refinement iterations per convergence round.
    patience_rounds : int
        Convergence patience.
    min_relative_improvement : float
        Convergence improvement threshold.
    max_rounds : int
        Maximum convergence rounds.
    max_evaluations : int
        Maximum convergence evaluations.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    mode: Literal["local", "population", "hybrid", "convergence"] = "local"
    instance_id: str = Field(min_length=1)
    seed: int = 1
    iterations: int = Field(default=100, ge=0)
    temperature: float = Field(default=1.0, gt=0)
    cooling: float = Field(default=0.999, gt=0, le=1)
    population: int = Field(default=16, ge=2)
    generations: int = Field(default=5, ge=0)
    mutation_rate: float = Field(default=0.1, ge=0, le=1)
    elite_fraction: float = Field(default=0.1, ge=0, lt=1)
    tournament_size: int = Field(default=3, ge=1)
    random_fraction: float = Field(default=0.2, ge=0, le=1)
    local_iterations: int = Field(default=30, ge=1)
    patience_rounds: int = Field(default=2, ge=1)
    min_relative_improvement: float = Field(default=1e-4, ge=0)
    max_rounds: int = Field(default=3, ge=1)
    max_evaluations: int = Field(default=1000, ge=1)

    @property
    def requested_budget(self) -> int:
        """Return the requested evaluation budget.

        Returns
        -------
        int
            Requested iterations, population work, or convergence cap.
        """
        if self.mode == "local":
            return self.iterations + 1
        if self.mode == "population":
            return self.population * (self.generations + 1)
        if self.mode == "hybrid":
            return self.population * (self.generations + 1) + self.iterations + 1
        return self.max_evaluations


class SearchRun(BaseModel):
    """A replayable search result.

    Parameters
    ----------
    schema_version : {"brushline.optimization-search.v1"}
        Schema version.
    mode : str
        Search mode.
    instance_id : str
        Instance id.
    adapter : str
        Adapter name and version.
    fresh_solutions_version : str
        Fresh Solutions version.
    seed : int
        Seed.
    budget : int
        Requested budget.
    assignment : dict of int to int
        Incumbent assignment.
    objective : float
        Scalarized objective.
    objective_vector : dict of str to float
        Four objective values.
    feasible : bool
        Feasibility.
    evaluations : int
        Exact evaluations.
    history : list of float
        Best objective history.
    stop_reason : str
        Stopping reason.
    checkpoint_path : str or None
        Checkpoint path.
    evidence : dict
        Replayable evidence record.
    replay_ok : bool
        Whether exact replay matched.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["brushline.optimization-search.v1"] = "brushline.optimization-search.v1"
    mode: str
    instance_id: str
    adapter: str
    fresh_solutions_version: str
    seed: int
    budget: int = Field(ge=0)
    assignment: dict[int, int]
    objective: float
    objective_vector: dict[str, float]
    feasible: bool
    evaluations: int = Field(ge=0)
    history: list[float] = Field(default_factory=list)
    stop_reason: str
    checkpoint_path: str | None = None
    evidence: dict[str, Any]
    replay_ok: bool

    @model_validator(mode="after")
    def _objectives(self) -> SearchRun:
        if self.adapter != ADAPTER_NAME:
            raise ValueError("unexpected adapter name")
        if set(self.objective_vector) != set(OBJECTIVE_NAMES):
            raise ValueError("objective_vector must contain the four core objectives")
        if not self.replay_ok:
            raise ValueError("a reported incumbent must replay exactly")
        return self


class BrushlineAdapter:
    """Fresh Solutions adapter over a Brushline formulation and evaluator.

    Parameters
    ----------
    evaluator : ScheduleEvaluator
        Exact evaluator.
    scalarization : Scalarization, optional
        Objective weights. Defaults to balanced.
    operator_config : OperatorConfig, optional
        Operator settings.
    name : str, optional
        Adapter name. Defaults to ``ADAPTER_NAME``.
    """

    def __init__(
        self,
        evaluator: ScheduleEvaluator,
        scalarization: Scalarization | None = None,
        operator_config: OperatorConfig | None = None,
        name: str = ADAPTER_NAME,
    ) -> None:
        self.evaluator = evaluator
        self.scalarization = scalarization or Scalarization(
            name="balanced",
            weights={
                "present_cost": 0.25,
                "service_risk": 0.25,
                "service_attainment": 0.25,
                "uncertainty": 0.25,
            },
        )
        self.operator_config = operator_config or OperatorConfig()
        self.name = name

    @property
    def variable_count(self) -> int:
        """Return the variable count.

        Returns
        -------
        int
            Number of variables.
        """
        return self.evaluator.formulation.variable_count

    def option_count(self, variable: int) -> int:
        """Return the option count for a variable.

        Parameters
        ----------
        variable : int
            Variable index.

        Returns
        -------
        int
            Option count.
        """
        return self.evaluator.formulation.option_count(variable)

    def option_at(self, variable: int, option: int) -> str:
        """Return the option id at a position.

        Parameters
        ----------
        variable : int
            Variable index.
        option : int
            Option index.

        Returns
        -------
        str
            Option id.
        """
        return self.evaluator.formulation.option_at(variable, option)

    def initial_assignment(self) -> dict[int, int]:
        """Return the no-action assignment.

        Returns
        -------
        dict of int to int
            Assignment.
        """
        return self.evaluator.initial_assignment()

    def random_assignment(self, rng: random.Random) -> dict[int, int]:
        """Return a repaired random assignment.

        Parameters
        ----------
        rng : random.Random
            Random source.

        Returns
        -------
        dict of int to int
            Assignment.
        """
        assignment = {
            variable.index: rng.randrange(len(variable.option_ids))
            for variable in self.evaluator.formulation.variables
        }
        return repair_assignment(self.evaluator, assignment, self.operator_config).assignment

    def mutate(
        self,
        assignment: Mapping[int, int],
        rate: float,
        rng: random.Random,
    ) -> dict[int, int]:
        """Mutate a repaired assignment.

        Parameters
        ----------
        assignment : dict of int to int
            Starting assignment.
        rate : float
            Per-variable mutation probability.
        rng : random.Random
            Random source.

        Returns
        -------
        dict of int to int
            Mutated and repaired assignment.

        Raises
        ------
        AdapterError
            When the rate is outside [0, 1].
        """
        if not 0.0 <= rate <= 1.0:
            raise AdapterError("mutation rate must be in [0, 1]")
        locked = set(self.operator_config.locked_variables)
        mutated = dict(assignment)
        for variable in self.evaluator.formulation.variables:
            if variable.index in locked or rng.random() >= rate:
                continue
            if self.operator_config.respect_access and variable.kind == "treatment":
                segment = next(
                    item
                    for item in self.evaluator.formulation.segments
                    if item.segment_id == variable.target_id
                )
                if variable.period_id in segment.inaccessible_period_ids:
                    continue
            option = rng.randrange(len(variable.option_ids))
            mutated[variable.index] = option
        return repair_assignment(self.evaluator, mutated, self.operator_config).assignment

    def crossover(
        self,
        left: Mapping[int, int],
        right: Mapping[int, int],
        rng: random.Random,
    ) -> dict[int, int]:
        """Uniformly cross two assignments and repair the child.

        Parameters
        ----------
        left : dict of int to int
            First parent.
        right : dict of int to int
            Second parent.
        rng : random.Random
            Random source.

        Returns
        -------
        dict of int to int
            Child assignment.
        """
        child = {
            variable.index: (left[variable.index] if rng.random() < 0.5 else right[variable.index])
            for variable in self.evaluator.formulation.variables
        }
        return repair_assignment(self.evaluator, child, self.operator_config).assignment

    def evaluate(self, assignment: Mapping[int, int]) -> Evaluation:
        """Return the scalarized exact evaluation.

        Parameters
        ----------
        assignment : dict of int to int
            Assignment.

        Returns
        -------
        Evaluation
            Fresh Solutions evaluation.
        """
        from fresh_solutions.contracts import Evaluation

        result = self.evaluator.evaluate(dict(assignment))
        scalar = result.scalar_objective(self.scalarization.weights)
        if not result.feasible:
            scalar += INFEASIBLE_PENALTY * max(1, len(result.violations))
        return Evaluation(
            objective=scalar,
            feasible=result.feasible,
            details={
                **result.objective_vector,
                "total_cost": result.total_cost,
                "violations": float(len(result.violations)),
            },
        )

    def evaluate_batch(self, assignments: Sequence[Mapping[int, int]]) -> list[Evaluation]:
        """Return exact batch evaluations.

        Parameters
        ----------
        assignments : list of dict of int to int
            Assignments.

        Returns
        -------
        list of Evaluation
            Evaluations in input order.
        """
        return [self.evaluate(assignment) for assignment in assignments]

    def propose(self, assignment: Mapping[int, int], rng: random.Random) -> Change | None:
        """Propose one single-variable reversible change.

        Parameters
        ----------
        assignment : mapping of int to int
            Assignment.
        rng : random.Random
            Random source.

        Returns
        -------
        Change or None
            Change, or None when no single-variable move exists.
        """
        from fresh_solutions.contracts import Change

        operators = list(default_operators(self.evaluator, self.operator_config))
        rng.shuffle(operators)
        for operator in operators:
            move = operator.propose(dict(assignment), rng)
            if move is not None and len(move.changes) == 1:
                change = move.changes[0]
                return Change(
                    variable=change.variable,
                    before=change.before,
                    after=change.after,
                    kind=move.kind,
                )
        return None

    def propose_move(self, assignment: Mapping[int, int], rng: random.Random) -> Move | None:
        """Propose any typed Brushline move, including compound moves.

        Parameters
        ----------
        assignment : mapping of int to int
            Assignment.
        rng : random.Random
            Random source.

        Returns
        -------
        Move or None
            Move, or None.
        """
        operators = list(default_operators(self.evaluator, self.operator_config))
        rng.shuffle(operators)
        for operator in operators:
            move = operator.propose(dict(assignment), rng)
            if move is not None:
                return move
        return None

    def apply(self, assignment: Mapping[int, int], change: Change) -> dict[int, int]:
        """Apply one change.

        Parameters
        ----------
        assignment : dict of int to int
            Assignment.
        change : Change
            Change.

        Returns
        -------
        dict of int to int
            New assignment.
        """
        if assignment.get(change.variable) != change.before:
            raise AdapterError("change.before does not match the assignment")
        updated = dict(assignment)
        updated[change.variable] = change.after
        return updated

    def undo(self, assignment: Mapping[int, int], change: Change) -> dict[int, int]:
        """Undo one change.

        Parameters
        ----------
        assignment : dict of int to int
            Assignment.
        change : Change
            Change.

        Returns
        -------
        dict of int to int
            Restored assignment.
        """
        if assignment.get(change.variable) != change.after:
            raise AdapterError("change.after does not match the assignment")
        updated = dict(assignment)
        updated[change.variable] = change.before
        return updated

    def _state(self) -> OperatorState:
        return OperatorState(self.evaluator.formulation, self.operator_config)


def fresh_solutions_version() -> str:
    """Return the installed Fresh Solutions version.

    Returns
    -------
    str
        Version, or ``not-installed``.
    """
    try:
        return importlib.metadata.version("fresh-solutions")
    except importlib.metadata.PackageNotFoundError:
        return "not-installed"


def run_search(
    evaluator: ScheduleEvaluator,
    spec: SearchSpec,
    *,
    scalarization: Scalarization | None = None,
    operator_config: OperatorConfig | None = None,
    checkpoint_path: str | Path | None = None,
) -> SearchRun:
    """Run a Fresh Solutions search and replay the incumbent exactly.

    Parameters
    ----------
    evaluator : ScheduleEvaluator
        Exact evaluator.
    spec : SearchSpec
        Search settings.
    scalarization : Scalarization, optional
        Objective weights.
    operator_config : OperatorConfig, optional
        Operator settings.
    checkpoint_path : str or Path, optional
        Checkpoint destination.

    Returns
    -------
    SearchRun
        Replayable result.

    Raises
    ------
    AdapterError
        When Fresh Solutions is unavailable or replay does not match.
    """
    from fresh_solutions.checkpoint import SearchCheckpoint
    from fresh_solutions.contracts import EvidenceRecord
    from fresh_solutions.convergence import ConvergenceConfig, run_to_convergence
    from fresh_solutions.engine import SearchConfig, run_local_search
    from fresh_solutions.population import (
        PopulationConfig,
        run_hybrid_search,
        run_population_search,
    )

    adapter = BrushlineAdapter(evaluator, scalarization, operator_config)
    if spec.mode == "local":
        local = run_local_search(
            adapter,
            SearchConfig(
                iterations=spec.iterations,
                seed=spec.seed,
                temperature=spec.temperature,
                cooling=spec.cooling,
            ),
        )
        assignment = dict(local.assignment)
        objective = local.objective
        feasible = local.feasible
        evaluations = local.evaluations
        history = list(local.history)
        generation = spec.iterations
        stop_reason = "budget"
    elif spec.mode == "population":
        population_config = PopulationConfig(
            population=spec.population,
            generations=spec.generations,
            seed=spec.seed,
            mutation_rate=spec.mutation_rate,
            elite_fraction=spec.elite_fraction,
            tournament_size=spec.tournament_size,
            random_fraction=spec.random_fraction,
        )
        population = run_population_search(adapter, population_config)
        assignment = dict(population.assignment)
        objective = population.objective
        feasible = population.feasible
        evaluations = population.evaluations
        history = list(population.history)
        generation = spec.generations
        stop_reason = "budget"
    elif spec.mode == "hybrid":
        population_config = PopulationConfig(
            population=spec.population,
            generations=spec.generations,
            seed=spec.seed,
            mutation_rate=spec.mutation_rate,
            elite_fraction=spec.elite_fraction,
            tournament_size=spec.tournament_size,
            random_fraction=spec.random_fraction,
        )
        local_config = SearchConfig(
            iterations=spec.iterations,
            seed=spec.seed + 1,
            temperature=spec.temperature,
            cooling=spec.cooling,
        )
        hybrid = run_hybrid_search(adapter, population_config, local_config)
        assignment = dict(hybrid.assignment)
        objective = hybrid.objective
        feasible = hybrid.feasible
        evaluations = hybrid.evaluations
        history = list(hybrid.history)
        generation = hybrid.population_generations + hybrid.local_iterations
        stop_reason = "budget"
    else:
        convergence = ConvergenceConfig(
            local_iterations_per_round=spec.local_iterations,
            patience_rounds=spec.patience_rounds,
            min_relative_improvement=spec.min_relative_improvement,
            max_rounds=spec.max_rounds,
            max_evaluations=spec.max_evaluations,
        )
        population_config = PopulationConfig(
            population=spec.population,
            generations=spec.generations,
            seed=spec.seed,
            mutation_rate=spec.mutation_rate,
            elite_fraction=spec.elite_fraction,
            tournament_size=spec.tournament_size,
            random_fraction=spec.random_fraction,
        )
        local_config = SearchConfig(
            iterations=spec.local_iterations,
            seed=spec.seed,
            temperature=spec.temperature,
            cooling=spec.cooling,
        )
        converged = run_to_convergence(adapter, population_config, local_config, convergence)
        assignment = dict(converged.assignment)
        objective = converged.objective
        feasible = converged.feasible
        evaluations = converged.evaluations
        history = list(converged.history)
        generation = converged.rounds
        stop_reason = converged.stop_reason

    exact = evaluator.evaluate(assignment)
    replay = adapter.evaluate(assignment)
    replay_ok = (
        abs(replay.objective - objective) <= 1e-9
        and replay.feasible == feasible
        and exact.feasible == feasible
    )
    if not replay_ok:
        raise AdapterError("reported incumbent does not replay exactly")
    evidence = EvidenceRecord(
        instance=spec.instance_id,
        adapter=adapter.name,
        assignment=dict(assignment),
        objective=objective,
        feasible=feasible,
        seed=spec.seed,
        metadata={
            "mode": spec.mode,
            "adapter_version": ADAPTER_VERSION,
            "fresh_solutions": fresh_solutions_version(),
            "scalarization": adapter.scalarization.name,
        },
    )
    evidence.verify(adapter)
    destination: str | None = None
    if checkpoint_path is not None:
        path = Path(checkpoint_path)
        SearchCheckpoint(
            assignment=assignment,
            seed=spec.seed,
            generation=generation,
            objective=objective,
            metadata=evidence.metadata,
        ).save(path)
        destination = str(path)
    return SearchRun(
        mode=spec.mode,
        instance_id=spec.instance_id,
        adapter=adapter.name,
        fresh_solutions_version=fresh_solutions_version(),
        seed=spec.seed,
        budget=spec.requested_budget,
        assignment=assignment,
        objective=objective,
        objective_vector=exact.objective_vector,
        feasible=feasible,
        evaluations=evaluations,
        history=history,
        stop_reason=stop_reason,
        checkpoint_path=destination,
        evidence=evidence.to_dict(),
        replay_ok=replay_ok,
    )


def replay_checkpoint(
    evaluator: ScheduleEvaluator,
    checkpoint_path: str | Path,
    *,
    scalarization: Scalarization | None = None,
) -> SearchRun:
    """Load a checkpoint and build a replayable, verified search run.

    Parameters
    ----------
    evaluator : ScheduleEvaluator
        Exact evaluator.
    checkpoint_path : str or Path
        Checkpoint path.
    scalarization : Scalarization, optional
        Objective weights.

    Returns
    -------
    SearchRun
        Verified replay result.
    """
    from fresh_solutions.checkpoint import SearchCheckpoint

    checkpoint = SearchCheckpoint.load(checkpoint_path)
    adapter = BrushlineAdapter(evaluator, scalarization)
    evaluation = checkpoint.verify(adapter)
    exact = evaluator.evaluate(dict(checkpoint.assignment))
    return SearchRun(
        mode="checkpoint",
        instance_id=str(checkpoint.metadata.get("instance", "checkpoint")),
        adapter=adapter.name,
        fresh_solutions_version=fresh_solutions_version(),
        seed=checkpoint.seed,
        budget=0,
        assignment=dict(checkpoint.assignment.items()),
        objective=evaluation.objective,
        objective_vector=exact.objective_vector,
        feasible=evaluation.feasible,
        evaluations=0,
        history=[],
        stop_reason="checkpoint",
        checkpoint_path=str(checkpoint_path),
        evidence={
            "instance": checkpoint.metadata.get("instance", "checkpoint"),
            "adapter": adapter.name,
            "assignment": {str(key): value for key, value in sorted(checkpoint.assignment.items())},
            "objective": evaluation.objective,
            "feasible": evaluation.feasible,
            "seed": checkpoint.seed,
            "metadata": dict(checkpoint.metadata),
        },
        replay_ok=True,
    )


__all__ = [
    "ADAPTER_NAME",
    "ADAPTER_VERSION",
    "INFEASIBLE_PENALTY",
    "SCALARIZATIONS",
    "SCALARIZATION_NAMES",
    "AdapterError",
    "BrushlineAdapter",
    "Scalarization",
    "SearchRun",
    "SearchSpec",
    "fresh_solutions_version",
    "replay_checkpoint",
    "run_search",
]
