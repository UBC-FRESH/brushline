"""Typed move operators and feasibility repair for optimization assignments.

Operators propose reversible bundles of assignment changes. Each bundle records the exact before
and after option for every touched variable, so apply and undo are deterministic. Repair removes
access, budget, monitoring-budget, and capacity violations, and tries a treatment option for a
service miss; it never invents a fix for a blocked growth or treatment model.
"""

from __future__ import annotations

import random
from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field, model_validator

from brushline.model.validation import ContractValidation
from brushline.optimization.evaluator import (
    AssignmentChange,
    EvaluationViolation,
    ScheduleEvaluator,
)
from brushline.optimization.formulation import Formulation

OPERATOR_NAMES: tuple[str, ...] = (
    "toggle",
    "method_change",
    "shift",
    "swap",
    "block_move",
    "monitoring_move",
    "destroy_repair",
)


class OperatorError(ValueError):
    """Raised when a move or repair request is inconsistent."""


class OperatorConfig(BaseModel):
    """Operator and repair settings.

    Parameters
    ----------
    max_block_periods : int, optional
        Maximum periods in one block move. Defaults to 3.
    destroy_fraction : float, optional
        Share of variables destroyed before repair. Defaults to 0.2.
    max_repair_steps : int, optional
        Maximum repair changes. Defaults to 100.
    respect_access : bool, optional
        Skip treatment variables in inaccessible periods. Defaults to True.
    locked_variables : list of int, optional
        Variable indices that operators must not change.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    max_block_periods: int = Field(default=3, ge=1, le=10)
    destroy_fraction: float = Field(default=0.2, gt=0, le=1)
    max_repair_steps: int = Field(default=100, ge=1, le=1000)
    respect_access: bool = True
    locked_variables: list[int] = Field(default_factory=list)


class Move(BaseModel):
    """A reversible bundle of assignment changes.

    Parameters
    ----------
    kind : str
        Move kind.
    changes : tuple of AssignmentChange
        Changes in application order.
    description : str, optional
        Human explanation.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    kind: str = Field(min_length=1)
    changes: tuple[AssignmentChange, ...] = Field(min_length=1)
    description: str = ""

    @model_validator(mode="after")
    def _unique_variables(self) -> Move:
        variables = [change.variable for change in self.changes]
        if len(set(variables)) != len(variables):
            raise ValueError("a move may touch each variable only once")
        return self

    def apply(self, assignment: dict[int, int]) -> dict[int, int]:
        """Apply the move to an assignment.

        Parameters
        ----------
        assignment : dict of int to int
            Current assignment.

        Returns
        -------
        dict of int to int
            New assignment.

        Raises
        ------
        OperatorError
            When a before value does not match.
        """
        updated = dict(assignment)
        for change in self.changes:
            if updated.get(change.variable) != change.before:
                raise OperatorError(f"move before value does not match variable {change.variable}")
            updated[change.variable] = change.after
        return updated

    def undo(self, assignment: dict[int, int]) -> dict[int, int]:
        """Undo the move on an assignment.

        Parameters
        ----------
        assignment : dict of int to int
            Current assignment.

        Returns
        -------
        dict of int to int
            Restored assignment.

        Raises
        ------
        OperatorError
            When an after value does not match.
        """
        updated = dict(assignment)
        for change in reversed(self.changes):
            if updated.get(change.variable) != change.after:
                raise OperatorError(f"move after value does not match variable {change.variable}")
            updated[change.variable] = change.before
        return updated


class MoveOperator(Protocol):
    """Protocol for a deterministic, seed-driven operator."""

    name: str

    def propose(self, assignment: dict[int, int], rng: random.Random) -> Move | None:
        """Propose one move, or None when no eligible variable exists."""
        ...


class OperatorState:
    """Shared eligibility and option helpers.

    Parameters
    ----------
    formulation : Formulation
        Optimization formulation.
    config : OperatorConfig, optional
        Operator settings.
    """

    def __init__(self, formulation: Formulation, config: OperatorConfig | None = None) -> None:
        self.formulation = formulation
        self.config = config or OperatorConfig()
        self.variables = {variable.index: variable for variable in formulation.variables}
        self.treatment_options = {
            option.option_id: option for option in formulation.treatment_options
        }
        self.period_order = {
            period.period_id: index
            for index, period in enumerate(
                sorted(formulation.periods, key=lambda item: item.start_year)
            )
        }
        self.segments = {segment.segment_id: segment for segment in formulation.segments}
        self.locked = set(self.config.locked_variables)
        if any(index not in self.variables for index in self.locked):
            raise OperatorError("locked variable is not in the formulation")

    def eligible(
        self,
        assignment: dict[int, int],
        *,
        kind: str | None = None,
        selected: bool = False,
        multiple_options: bool = False,
    ) -> list[int]:
        """Return eligible variable indices.

        Parameters
        ----------
        assignment : dict of int to int
            Current assignment.
        kind : str or None, optional
            Restrict to ``treatment`` or ``monitoring``.
        selected : bool, optional
            Require a non-``none`` selection.
        multiple_options : bool, optional
            Require at least two options.

        Returns
        -------
        list of int
            Sorted eligible indices.
        """
        indices: list[int] = []
        for index, variable in sorted(self.variables.items()):
            if index in self.locked:
                continue
            if kind is not None and variable.kind != kind:
                continue
            if multiple_options and len(variable.option_ids) < 2:
                continue
            option = assignment.get(index)
            if option is None:
                continue
            if selected and option == 0:
                continue
            if self.config.respect_access and variable.kind == "treatment":
                segment = self.segments[variable.target_id]
                if variable.period_id in segment.inaccessible_period_ids:
                    continue
            indices.append(index)
        return indices

    def option_ids(self, index: int) -> list[str]:
        """Return option ids for one variable.

        Parameters
        ----------
        index : int
            Variable index.

        Returns
        -------
        list of str
            Option ids.
        """
        return list(self.variables[index].option_ids)

    def alternative(
        self,
        index: int,
        assignment: dict[int, int],
        rng: random.Random,
        *,
        different_method: bool = False,
    ) -> int | None:
        """Choose an alternative option index.

        Parameters
        ----------
        index : int
            Variable index.
        assignment : dict of int to int
            Current assignment.
        rng : random.Random
            Random source.
        different_method : bool, optional
            Prefer a treatment option with a different method.

        Returns
        -------
        int or None
            Alternative option index, or None.
        """
        variable = self.variables[index]
        current = assignment[index]
        alternatives = [option for option in range(len(variable.option_ids)) if option != current]
        if different_method and variable.kind == "treatment":
            current_method = self._method(variable.option_ids[current])
            preferred = [
                option
                for option in alternatives
                if self._method(variable.option_ids[option]) not in {None, current_method}
            ]
            alternatives = preferred or alternatives
        if not alternatives:
            return None
        return rng.choice(alternatives)

    def _method(self, option_id: str) -> str | None:
        option = self.treatment_options.get(option_id)
        return None if option is None else option.method


class ToggleOperator:
    """Toggle one variable to a random alternative option."""

    name = "toggle"

    def __init__(self, state: OperatorState) -> None:
        self.state = state

    def propose(self, assignment: dict[int, int], rng: random.Random) -> Move | None:
        """Propose a toggle move.

        Parameters
        ----------
        assignment : dict of int to int
            Current assignment.
        rng : random.Random
            Random source.

        Returns
        -------
        Move or None
            Toggle move, or None.
        """
        candidates = self.state.eligible(assignment, multiple_options=True)
        if not candidates:
            return None
        index = rng.choice(candidates)
        after = self.state.alternative(index, assignment, rng)
        if after is None:
            return None
        return Move(
            kind=self.name,
            changes=(AssignmentChange(variable=index, before=assignment[index], after=after),),
            description="toggle one variable",
        )


class MethodChangeOperator:
    """Change one selected treatment to an option with a different method."""

    name = "method_change"

    def __init__(self, state: OperatorState) -> None:
        self.state = state

    def propose(self, assignment: dict[int, int], rng: random.Random) -> Move | None:
        """Propose a method change.

        Parameters
        ----------
        assignment : dict of int to int
            Current assignment.
        rng : random.Random
            Random source.

        Returns
        -------
        Move or None
            Method change, or None.
        """
        candidates = self.state.eligible(
            assignment, kind="treatment", selected=True, multiple_options=True
        )
        candidates = [
            index
            for index in candidates
            if any(
                self.state._method(self.state.option_ids(index)[option])
                not in {None, self.state._method(self.state.option_ids(index)[assignment[index]])}
                for option in range(len(self.state.option_ids(index)))
                if option != assignment[index]
            )
        ]
        if not candidates:
            return None
        index = rng.choice(candidates)
        after = self.state.alternative(index, assignment, rng, different_method=True)
        if after is None:
            return None
        return Move(
            kind=self.name,
            changes=(AssignmentChange(variable=index, before=assignment[index], after=after),),
            description="change the treatment method",
        )


class ShiftOperator:
    """Shift one selected treatment to the adjacent period for the same segment."""

    name = "shift"

    def __init__(self, state: OperatorState) -> None:
        self.state = state

    def propose(self, assignment: dict[int, int], rng: random.Random) -> Move | None:
        """Propose a period shift.

        Parameters
        ----------
        assignment : dict of int to int
            Current assignment.
        rng : random.Random
            Random source.

        Returns
        -------
        Move or None
            Period shift, or None.
        """
        candidates = self.state.eligible(assignment, kind="treatment", selected=True)
        pairs: list[tuple[int, int]] = []
        for index in candidates:
            variable = self.state.variables[index]
            option_id = variable.option_ids[assignment[index]]
            for candidate in self.state.variables.values():
                if (
                    candidate.kind == "treatment"
                    and candidate.target_id == variable.target_id
                    and abs(
                        self.state.period_order[candidate.period_id]
                        - self.state.period_order[variable.period_id]
                    )
                    == 1
                    and option_id in candidate.option_ids
                    and candidate.index not in self.state.locked
                    and not (
                        self.state.config.respect_access
                        and candidate.period_id
                        in self.state.segments[candidate.target_id].inaccessible_period_ids
                    )
                ):
                    pairs.append((index, candidate.index))
        if not pairs:
            return None
        source, target = rng.choice(sorted(pairs))
        option_id = self.state.variables[source].option_ids[assignment[source]]
        target_after = self.state.variables[target].option_ids.index(option_id)
        return Move(
            kind=self.name,
            changes=(
                AssignmentChange(variable=source, before=assignment[source], after=0),
                AssignmentChange(
                    variable=target,
                    before=assignment[target],
                    after=target_after,
                ),
            ),
            description="shift a treatment to the adjacent period",
        )


class SwapOperator:
    """Swap options between two eligible variables of the same kind."""

    name = "swap"

    def __init__(self, state: OperatorState) -> None:
        self.state = state

    def propose(self, assignment: dict[int, int], rng: random.Random) -> Move | None:
        """Propose a swap.

        Parameters
        ----------
        assignment : dict of int to int
            Current assignment.
        rng : random.Random
            Random source.

        Returns
        -------
        Move or None
            Swap, or None.
        """
        candidates = self.state.eligible(assignment)
        by_kind: dict[str, list[int]] = {}
        for index in candidates:
            by_kind.setdefault(self.state.variables[index].kind, []).append(index)
        pairs: list[tuple[int, int]] = []
        for indices in by_kind.values():
            for left_position, left in enumerate(indices):
                for right in indices[left_position + 1 :]:
                    left_option = self.state.variables[left].option_ids[assignment[left]]
                    right_option = self.state.variables[right].option_ids[assignment[right]]
                    if (
                        left_option != right_option
                        and left_option in self.state.variables[right].option_ids
                        and right_option in self.state.variables[left].option_ids
                    ):
                        pairs.append((left, right))
        if not pairs:
            return None
        left, right = rng.choice(sorted(pairs))
        left_before = assignment[left]
        right_before = assignment[right]
        left_after = self.state.variables[left].option_ids.index(
            self.state.variables[right].option_ids[right_before]
        )
        right_after = self.state.variables[right].option_ids.index(
            self.state.variables[left].option_ids[left_before]
        )
        return Move(
            kind=self.name,
            changes=(
                AssignmentChange(variable=left, before=left_before, after=left_after),
                AssignmentChange(variable=right, before=right_before, after=right_after),
            ),
            description="swap two assignments",
        )


class BlockMoveOperator:
    """Set a contiguous period block for one segment to one treatment option."""

    name = "block_move"

    def __init__(self, state: OperatorState) -> None:
        self.state = state

    def propose(self, assignment: dict[int, int], rng: random.Random) -> Move | None:
        """Propose a block move.

        Parameters
        ----------
        assignment : dict of int to int
            Current assignment.
        rng : random.Random
            Random source.

        Returns
        -------
        Move or None
            Block move, or None.
        """
        blocks: list[tuple[int, ...]] = []
        for segment in self.state.formulation.segments:
            variables = sorted(
                [
                    variable
                    for variable in self.state.variables.values()
                    if variable.kind == "treatment"
                    and variable.target_id == segment.segment_id
                    and variable.index not in self.state.locked
                    and not (
                        self.state.config.respect_access
                        and variable.period_id in segment.inaccessible_period_ids
                    )
                ],
                key=lambda item: self.state.period_order[item.period_id],
            )
            for start in range(len(variables)):
                for length in range(1, self.state.config.max_block_periods + 1):
                    block = tuple(item.index for item in variables[start : start + length])
                    if len(block) == length:
                        blocks.append(block)
        if not blocks:
            return None
        block = rng.choice(blocks)
        option_ids = self.state.variables[block[0]].option_ids
        option = rng.choice(list(range(1, len(option_ids))) or [0])
        option_id = option_ids[option]
        changes_list: list[AssignmentChange] = []
        for index in block:
            target_ids = self.state.variables[index].option_ids
            after = target_ids.index(option_id) if option_id in target_ids else 0
            changes_list.append(
                AssignmentChange(
                    variable=index,
                    before=assignment[index],
                    after=after,
                )
            )
        changes = tuple(changes_list)
        if all(change.before == change.after for change in changes):
            return None
        return Move(
            kind=self.name,
            changes=changes,
            description="set a contiguous treatment block",
        )


class MonitoringMoveOperator:
    """Change one monitoring option."""

    name = "monitoring_move"

    def __init__(self, state: OperatorState) -> None:
        self.state = state

    def propose(self, assignment: dict[int, int], rng: random.Random) -> Move | None:
        """Propose a monitoring move.

        Parameters
        ----------
        assignment : dict of int to int
            Current assignment.
        rng : random.Random
            Random source.

        Returns
        -------
        Move or None
            Monitoring move, or None.
        """
        candidates = self.state.eligible(assignment, kind="monitoring", multiple_options=True)
        if not candidates:
            return None
        index = rng.choice(candidates)
        after = self.state.alternative(index, assignment, rng)
        if after is None:
            return None
        return Move(
            kind=self.name,
            changes=(AssignmentChange(variable=index, before=assignment[index], after=after),),
            description="change the monitoring option",
        )


class RepairResult(BaseModel):
    """The result of a deterministic feasibility repair.

    Parameters
    ----------
    assignment : dict of int to int
        Repaired assignment.
    changes : list of AssignmentChange
        Applied repair changes.
    feasible : bool
        Whether all hard violations were removed.
    remaining : list of EvaluationViolation
        Remaining hard violations.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    assignment: dict[int, int]
    changes: list[AssignmentChange] = Field(default_factory=list)
    feasible: bool
    remaining: list[EvaluationViolation] = Field(default_factory=list)


def repair_assignment(
    evaluator: ScheduleEvaluator,
    assignment: dict[int, int],
    config: OperatorConfig | None = None,
) -> RepairResult:
    """Repair resource and access violations deterministically.

    Parameters
    ----------
    evaluator : ScheduleEvaluator
        Exact evaluator.
    assignment : dict of int to int
        Starting assignment.
    config : OperatorConfig, optional
        Repair settings.

    Returns
    -------
    RepairResult
        Repaired assignment, changes, feasibility, and remaining violations.
    """
    rules = config or OperatorConfig()
    state = OperatorState(evaluator.formulation, rules)
    current = dict(assignment)
    changes: list[AssignmentChange] = []
    for _ in range(rules.max_repair_steps):
        result = evaluator.evaluate(current)
        if result.feasible:
            return RepairResult(assignment=current, changes=changes, feasible=True)
        violation = result.violations[0]
        change = _repair_change(evaluator, state, current, violation)
        if change is None:
            return RepairResult(
                assignment=current,
                changes=changes,
                feasible=False,
                remaining=result.violations,
            )
        current[change.variable] = change.after
        changes.append(change)
    final = evaluator.evaluate(current)
    return RepairResult(
        assignment=current,
        changes=changes,
        feasible=final.feasible,
        remaining=final.violations,
    )


def _repair_change(
    evaluator: ScheduleEvaluator,
    state: OperatorState,
    assignment: dict[int, int],
    violation: EvaluationViolation,
) -> AssignmentChange | None:
    if violation.code == "EVALUATION-ACCESS" and violation.variable_index is not None:
        index = violation.variable_index
        if index in state.locked or assignment.get(index) == 0:
            return None
        return AssignmentChange(variable=index, before=assignment[index], after=0)
    if violation.code in {
        "EVALUATION-BUDGET",
        "EVALUATION-MONITORING-BUDGET",
        "EVALUATION-CAPACITY",
    }:
        if violation.code == "EVALUATION-MONITORING-BUDGET":
            candidates = [
                index
                for index in state.eligible(assignment, kind="monitoring", selected=True)
                if state.variables[index].period_id == violation.period_id
            ]
        else:
            candidates = [
                index
                for index in state.eligible(assignment, kind="treatment", selected=True)
                if state.variables[index].period_id == violation.period_id
                and (
                    violation.code != "EVALUATION-CAPACITY"
                    or state._method(state.variables[index].option_ids[assignment[index]])
                    == violation.target_id
                )
            ]
        if not candidates:
            return None
        index = sorted(candidates)[-1]
        return AssignmentChange(variable=index, before=assignment[index], after=0)
    if violation.code == "EVALUATION-SERVICE" and violation.target_id is not None:
        variable = next(
            (
                item
                for item in state.variables.values()
                if item.kind == "treatment"
                and item.target_id == violation.target_id
                and item.period_id == violation.period_id
            ),
            None,
        )
        if variable is None or len(variable.option_ids) < 2:
            return None
        if variable.index in state.locked:
            return None
        before = assignment[variable.index]
        after = next(
            (option for option in range(1, len(variable.option_ids)) if option != before),
            None,
        )
        if after is None:  # pragma: no cover - guarded by the option-count check above
            return None
        return AssignmentChange(variable=variable.index, before=before, after=after)
    return None


class RepairOperator:
    """Reset a random subset and repair feasibility."""

    name = "destroy_repair"

    def __init__(
        self,
        state: OperatorState,
        evaluator: ScheduleEvaluator,
    ) -> None:
        self.state = state
        self.evaluator = evaluator

    def propose(self, assignment: dict[int, int], rng: random.Random) -> Move | None:
        """Propose a destroy-repair move.

        Parameters
        ----------
        assignment : dict of int to int
            Current assignment.
        rng : random.Random
            Random source.

        Returns
        -------
        Move or None
            Destroy-repair move, or None.
        """
        candidates = self.state.eligible(assignment, selected=True)
        if not candidates:
            return None
        count = max(1, round(len(candidates) * self.state.config.destroy_fraction))
        destroyed = set(rng.sample(candidates, min(count, len(candidates))))
        current = dict(assignment)
        for index in destroyed:
            current[index] = 0
        repaired = repair_assignment(self.evaluator, current, self.state.config)
        changed = [
            AssignmentChange(
                variable=index,
                before=assignment[index],
                after=repaired.assignment[index],
            )
            for index in sorted(assignment)
            if assignment[index] != repaired.assignment[index]
        ]
        if not changed:
            return None
        return Move(
            kind=self.name,
            changes=tuple(changed),
            description="destroy a subset and repair feasibility",
        )


def default_operators(
    evaluator: ScheduleEvaluator, config: OperatorConfig | None = None
) -> tuple[MoveOperator, ...]:
    """Return the default operator portfolio.

    Parameters
    ----------
    evaluator : ScheduleEvaluator
        Exact evaluator.
    config : OperatorConfig, optional
        Operator settings.

    Returns
    -------
    tuple of MoveOperator
        Toggle, method change, shift, swap, block, monitoring, and repair operators.
    """
    state = OperatorState(evaluator.formulation, config)
    return (
        ToggleOperator(state),
        MethodChangeOperator(state),
        ShiftOperator(state),
        SwapOperator(state),
        BlockMoveOperator(state),
        MonitoringMoveOperator(state),
        RepairOperator(state, evaluator),
    )


def apply_move(assignment: dict[int, int], move: Move) -> dict[int, int]:
    """Apply a move.

    Parameters
    ----------
    assignment : dict of int to int
        Current assignment.
    move : Move
        Move to apply.

    Returns
    -------
    dict of int to int
        New assignment.
    """
    return move.apply(assignment)


def undo_move(assignment: dict[int, int], move: Move) -> dict[int, int]:
    """Undo a move.

    Parameters
    ----------
    assignment : dict of int to int
        Current assignment.
    move : Move
        Move to undo.

    Returns
    -------
    dict of int to int
        Restored assignment.
    """
    return move.undo(assignment)


def validate_move(formulation: Formulation, move: Move) -> ContractValidation:
    """Validate that every touched option exists.

    Parameters
    ----------
    formulation : Formulation
        Formulation.
    move : Move
        Move to validate.

    Returns
    -------
    ContractValidation
        Errors and counts.
    """
    errors: list[str] = []
    variables = {variable.index: variable for variable in formulation.variables}
    for change in move.changes:
        variable = variables.get(change.variable)
        if variable is None:
            errors.append(f"MOVE-VARIABLE: unknown variable {change.variable}")
            continue
        for option in (change.before, change.after):
            if option < 0 or option >= len(variable.option_ids):
                errors.append(f"MOVE-OPTION: variable {change.variable} option {option} is invalid")
    return ContractValidation(tuple(errors), (), {"changes": len(move.changes)})


__all__ = [
    "OPERATOR_NAMES",
    "BlockMoveOperator",
    "MethodChangeOperator",
    "MonitoringMoveOperator",
    "Move",
    "MoveOperator",
    "OperatorConfig",
    "OperatorError",
    "OperatorState",
    "RepairOperator",
    "RepairResult",
    "ShiftOperator",
    "SwapOperator",
    "ToggleOperator",
    "apply_move",
    "default_operators",
    "repair_assignment",
    "undo_move",
    "validate_move",
]
