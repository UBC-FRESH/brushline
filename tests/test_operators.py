"""Tests for the P5.3 move operators and repair."""

from __future__ import annotations

import random
from pathlib import Path

import pytest
from brushline.model.corridor import ServiceStandard
from brushline.optimization.evaluator import (
    AssignmentChange,
    ScheduleEvaluator,
    SegmentContext,
)
from brushline.optimization.formulation import Formulation, build_formulation
from brushline.optimization.operators import (
    BlockMoveOperator,
    MethodChangeOperator,
    MonitoringMoveOperator,
    Move,
    OperatorConfig,
    OperatorError,
    OperatorState,
    RepairOperator,
    ShiftOperator,
    SwapOperator,
    ToggleOperator,
    default_operators,
    repair_assignment,
    validate_move,
)
from brushline.vegetation.growth import GrowthEnvironment
from brushline.vegetation.state_space import StateDistribution
from pydantic import ValidationError

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "notes" / "reference" / "p5-formulation.v1.json"
STANDARD = ServiceStandard(service_standard_id="std1", max_height_m=4.0, min_clearance_m=1.0)


def _formulation() -> Formulation:
    return Formulation.model_validate_json(FIXTURE.read_text(encoding="utf-8"))


def _contexts() -> list[SegmentContext]:
    return [
        SegmentContext(
            segment_id="s1",
            functional_group="shrub",
            initial=StateDistribution(
                class_probabilities={"shrub": 0.8, "unknown": 0.2},
                height_m=1.5,
                height_sd=0.2,
                cover_pct=40,
                cover_sd=4,
                density_per_ha=1000,
                density_sd=50,
                age_years=1,
                confidence=0.6,
            ),
            service_standard=STANDARD,
            length_m=100,
            asset_height_m=8,
        ),
        SegmentContext(
            segment_id="s2",
            functional_group="grass_herb",
            initial=StateDistribution(
                class_probabilities={"grass_herb": 0.8, "unknown": 0.2},
                height_m=0.4,
                height_sd=0.1,
                cover_pct=70,
                cover_sd=4,
                density_per_ha=0,
                density_sd=0,
                age_years=1,
                confidence=0.8,
            ),
            service_standard=STANDARD,
            length_m=150,
            asset_height_m=8,
        ),
    ]


def _evaluator(
    formulation: Formulation | None = None,
    contexts: list[SegmentContext] | None = None,
) -> ScheduleEvaluator:
    return ScheduleEvaluator(formulation or _formulation(), contexts or _contexts())


def _state(evaluator: ScheduleEvaluator, config: OperatorConfig | None = None) -> OperatorState:
    return OperatorState(evaluator.formulation, config)


def _rebuild(formulation: Formulation, **updates: object) -> Formulation:
    base = formulation.model_copy(update=updates)
    return build_formulation(
        formulation_id=base.formulation_id,
        periods=base.periods,
        segments=base.segments,
        spans=base.spans,
        treatment_options=base.treatment_options,
        monitoring_options=base.monitoring_options,
        currency=base.currency,
        created_utc=base.created_utc,
    )


def _variable(formulation: Formulation, kind: str, target: str, period: str) -> int:
    return next(
        variable.index
        for variable in formulation.variables
        if variable.kind == kind and variable.target_id == target and variable.period_id == period
    )


def _option(formulation: Formulation, index: int, option_id: str) -> int:
    return formulation.variables[index].option_ids.index(option_id)


def _selected() -> tuple[ScheduleEvaluator, dict[int, int]]:
    evaluator = _evaluator()
    formulation = evaluator.formulation
    assignment = evaluator.initial_assignment()
    first = _variable(formulation, "treatment", "s1", "p2026")
    second = _variable(formulation, "treatment", "s1", "p2027")
    assignment[first] = _option(formulation, first, "mow-l1")
    assignment[second] = _option(formulation, second, "manual-l1")
    monitor = _variable(formulation, "monitoring", "sp1", "p2026")
    assignment[monitor] = _option(formulation, monitor, "lidar-annual")
    return evaluator, assignment


def test_toggle_apply_undo_and_determinism() -> None:
    """Toggle changes one option, applies, undoes, and repeats with the seed."""
    evaluator, assignment = _selected()
    operator = ToggleOperator(_state(evaluator))
    first = operator.propose(assignment, random.Random(7))
    second = operator.propose(assignment, random.Random(7))
    assert first is not None
    assert first == second
    updated = first.apply(assignment)
    assert updated != assignment
    assert first.undo(updated) == assignment
    assert validate_move(evaluator.formulation, first).is_valid


def test_method_change_changes_the_method() -> None:
    """A method change selects a different treatment method."""
    evaluator, assignment = _selected()
    operator = MethodChangeOperator(_state(evaluator))
    move = operator.propose(assignment, random.Random(2))
    assert move is not None
    change = move.changes[0]
    before_id = evaluator.formulation.variables[change.variable].option_ids[change.before]
    after_id = evaluator.formulation.variables[change.variable].option_ids[change.after]
    methods = {
        option.option_id: option.method for option in evaluator.formulation.treatment_options
    }
    assert methods[before_id] != methods[after_id]


def test_monitoring_move_and_swap() -> None:
    """Monitoring and swap operators change the intended variables."""
    evaluator, assignment = _selected()
    monitoring = MonitoringMoveOperator(_state(evaluator))
    move = monitoring.propose(assignment, random.Random(3))
    assert move is not None
    assert evaluator.formulation.variables[move.changes[0].variable].kind == "monitoring"
    assert move.apply(assignment) != assignment

    swap = SwapOperator(_state(evaluator)).propose(assignment, random.Random(4))
    assert swap is not None
    assert len(swap.changes) == 2
    updated = swap.apply(assignment)
    left, right = swap.changes
    left_variable = evaluator.formulation.variables[left.variable]
    right_variable = evaluator.formulation.variables[right.variable]
    assert (
        left_variable.option_ids[updated[left.variable]] == right_variable.option_ids[right.before]
    )
    assert (
        right_variable.option_ids[updated[right.variable]] == left_variable.option_ids[left.before]
    )
    assert swap.undo(updated) == assignment


def test_shift_moves_treatment_to_adjacent_period() -> None:
    """A shift clears the source period and selects the target period."""
    evaluator, assignment = _selected()
    move = ShiftOperator(_state(evaluator)).propose(assignment, random.Random(5))
    assert move is not None
    updated = move.apply(assignment)
    source, target = move.changes
    assert updated[source.variable] == 0
    assert updated[target.variable] == target.after
    assert target.after > 0


def test_block_move_sets_a_contiguous_block() -> None:
    """A block move touches one segment across adjacent periods."""
    evaluator = _evaluator()
    assignment = evaluator.initial_assignment()
    move = BlockMoveOperator(_state(evaluator)).propose(assignment, random.Random(8))
    assert move is not None
    assert move.kind == "block_move"
    segment_ids = {
        evaluator.formulation.variables[change.variable].target_id for change in move.changes
    }
    assert len(segment_ids) == 1
    assert any(change.after > 0 for change in move.changes)
    assert move.undo(move.apply(assignment)) == assignment


def test_operators_return_none_when_no_move_exists() -> None:
    """No eligible variable or alternative option returns None."""
    evaluator = _evaluator()
    assignment = evaluator.initial_assignment()
    state = _state(evaluator)
    assert MethodChangeOperator(state).propose(assignment, random.Random(1)) is None
    assert ShiftOperator(state).propose(assignment, random.Random(1)) is None
    locked = OperatorConfig(locked_variables=list(assignment))
    locked_state = _state(evaluator, locked)
    assert ToggleOperator(locked_state).propose(assignment, random.Random(1)) is None


def test_inaccessible_and_locked_variables_are_skipped() -> None:
    """Access and locked-variable rules remove candidates."""
    evaluator, assignment = _selected()
    formulation = evaluator.formulation
    inaccessible = _variable(formulation, "treatment", "s2", "p2027")
    assignment[inaccessible] = _option(formulation, inaccessible, "mow-l1")
    others = [index for index in assignment if index != inaccessible]
    locked = OperatorConfig(locked_variables=others)
    assert ToggleOperator(_state(evaluator, locked)).propose(assignment, random.Random(9)) is None
    relaxed = OperatorConfig(locked_variables=others, respect_access=False)
    move = ToggleOperator(_state(evaluator, relaxed)).propose(assignment, random.Random(9))
    assert move is not None
    assert move.changes[0].variable == inaccessible
    all_locked = OperatorConfig(locked_variables=list(assignment))
    assert (
        ToggleOperator(_state(evaluator, all_locked)).propose(assignment, random.Random(9)) is None
    )


def test_repair_budget_capacity_and_monitoring() -> None:
    """Repair removes resource violations deterministically."""
    formulation = _formulation()
    periods = [
        formulation.periods[0].model_copy(
            update={
                "budget": 0.01,
                "monitoring_budget": 0.01,
                "capacity_by_method": {"mowing": 0.01, "manual": 0.01},
            }
        ),
        formulation.periods[1],
    ]
    tight = formulation.model_copy(update={"periods": periods})
    tight = build_formulation(
        formulation_id=tight.formulation_id,
        periods=tight.periods,
        segments=tight.segments,
        spans=tight.spans,
        treatment_options=tight.treatment_options,
        monitoring_options=tight.monitoring_options,
        currency=tight.currency,
        created_utc=tight.created_utc,
    )
    evaluator = _evaluator(tight)
    assignment = evaluator.initial_assignment()
    treatment = _variable(tight, "treatment", "s1", "p2026")
    monitor = _variable(tight, "monitoring", "sp1", "p2026")
    assignment[treatment] = _option(tight, treatment, "mow-l1")
    assignment[monitor] = _option(tight, monitor, "lidar-annual")
    repaired = repair_assignment(evaluator, assignment)
    assert repaired.feasible
    assert repaired.assignment[treatment] == 0
    assert repaired.assignment[monitor] == 0
    assert repaired.changes


def test_repair_access_and_service() -> None:
    """Access is cleared and a service miss can add a treatment."""
    evaluator, assignment = _selected()
    formulation = evaluator.formulation
    inaccessible = _variable(formulation, "treatment", "s2", "p2027")
    assignment[inaccessible] = _option(formulation, inaccessible, "mow-l1")
    repaired = repair_assignment(evaluator, assignment)
    assert repaired.feasible
    assert repaired.assignment[inaccessible] == 0

    contexts = _contexts()
    contexts[0] = contexts[0].model_copy(
        update={
            "initial": contexts[0].initial.model_copy(update={"height_m": 5.0}),
            "service_standard": ServiceStandard(
                service_standard_id="std1", max_height_m=4.0, min_clearance_m=1.0
            ),
        }
    )
    service_evaluator = _evaluator(contexts=contexts)
    service_assignment = service_evaluator.initial_assignment()
    repaired = repair_assignment(service_evaluator, service_assignment)
    assert repaired.feasible


def test_repair_operator_and_suite_are_seeded() -> None:
    """The repair operator and suite return deterministic typed moves."""
    evaluator = _evaluator()
    assignment = evaluator.initial_assignment()
    operator = RepairOperator(_state(evaluator), evaluator)
    assert operator.propose(assignment, random.Random(1)) is None
    suite = default_operators(evaluator)
    moves = [operate.propose(assignment, random.Random(1)) for operate in suite]
    assert len(moves) == 7
    move = next(item for item in moves if item is not None)
    assert isinstance(move, Move)


def test_move_validation_and_errors() -> None:
    """Move bundles reject duplicate variables and bad apply/undo states."""
    evaluator, assignment = _selected()
    with pytest.raises(ValidationError, match="once"):
        Move(
            kind="bad",
            changes=(
                AssignmentChange(variable=0, before=0, after=1),
                AssignmentChange(variable=0, before=1, after=0),
            ),
        )
    move = Move(
        kind="one",
        changes=(AssignmentChange(variable=0, before=0, after=1),),
    )
    with pytest.raises(OperatorError):
        move.apply(assignment)
    with pytest.raises(OperatorError):
        move.undo(evaluator.initial_assignment())
    bad = Move(
        kind="bad",
        changes=(AssignmentChange(variable=99, before=0, after=1),),
    )
    assert not validate_move(evaluator.formulation, bad).is_valid
    invalid = Move(
        kind="bad",
        changes=(AssignmentChange(variable=0, before=0, after=99),),
    )
    assert not validate_move(evaluator.formulation, invalid).is_valid
    with pytest.raises(OperatorError, match="locked"):
        default_operators(evaluator, OperatorConfig(locked_variables=[99]))
    with pytest.raises(ValidationError):
        OperatorConfig(max_block_periods=0)


def test_operator_helper_edges(monkeypatch: pytest.MonkeyPatch) -> None:
    """Eligibility, alternatives, block, and monitoring edge branches are covered."""
    evaluator = _evaluator()
    assignment = evaluator.initial_assignment()
    state = _state(evaluator)
    assert state.eligible({}) == []
    empty_formulation = _rebuild(evaluator.formulation, treatment_options=[])
    empty_state = _state(_evaluator(empty_formulation))
    empty_assignment = {variable.index: 0 for variable in empty_formulation.variables}
    assert all(
        empty_formulation.variables[index].kind != "treatment"
        for index in empty_state.eligible(empty_assignment, multiple_options=True)
    )
    assert BlockMoveOperator(empty_state).propose(empty_assignment, random.Random(1)) is None
    no_treatment = next(
        variable for variable in empty_formulation.variables if variable.kind == "treatment"
    )
    assert (
        empty_state.alternative(no_treatment.index, {no_treatment.index: 0}, random.Random(1))
        is None
    )

    locked_treatments = OperatorConfig(
        locked_variables=[
            variable.index
            for variable in evaluator.formulation.variables
            if variable.kind == "treatment"
        ]
    )
    assert (
        BlockMoveOperator(_state(evaluator, locked_treatments)).propose(
            assignment, random.Random(1)
        )
        is None
    )

    monitors = [
        variable.index
        for variable in evaluator.formulation.variables
        if variable.kind == "monitoring"
    ]
    locked_monitoring = OperatorConfig(locked_variables=monitors)
    assert (
        MonitoringMoveOperator(_state(evaluator, locked_monitoring)).propose(
            assignment, random.Random(1)
        )
        is None
    )

    for operator in (
        ToggleOperator(state),
        MethodChangeOperator(state),
        MonitoringMoveOperator(state),
    ):
        monkeypatch.setattr(state, "alternative", lambda *args, **kwargs: None)
        assert operator.propose(assignment, random.Random(1)) is None


def test_block_same_option_returns_none() -> None:
    """A block whose option is already selected returns no move."""
    evaluator = _evaluator()
    formulation = _rebuild(evaluator.formulation, treatment_options=[])
    state = _state(_evaluator(formulation))
    none_assignment = {variable.index: 0 for variable in formulation.variables}
    assert BlockMoveOperator(state).propose(none_assignment, random.Random(1)) is None


def test_repair_change_edge_cases(monkeypatch: pytest.MonkeyPatch) -> None:
    """Repair returns None for non-repairable or already-clear violations."""
    from brushline.optimization.evaluator import EvaluationViolation
    from brushline.optimization.operators import _repair_change

    evaluator = _evaluator()
    state = _state(evaluator)
    assignment = evaluator.initial_assignment()
    treatment = _variable(evaluator.formulation, "treatment", "s1", "p2026")
    access = EvaluationViolation(
        code="EVALUATION-ACCESS",
        message="blocked",
        kind="access",
        variable_index=treatment,
    )
    assert _repair_change(evaluator, state, assignment, access) is None
    locked_state = _state(evaluator, OperatorConfig(locked_variables=[treatment]))
    assignment[treatment] = 1
    assert _repair_change(evaluator, locked_state, assignment, access) is None
    capacity = EvaluationViolation(
        code="EVALUATION-CAPACITY",
        message="full",
        kind="capacity",
        period_id="p2026",
        target_id="mowing",
    )
    assert _repair_change(evaluator, state, evaluation_zero(evaluator), capacity) is None
    service = EvaluationViolation(
        code="EVALUATION-SERVICE",
        message="miss",
        kind="service",
        period_id="p2026",
        target_id="missing",
    )
    assert _repair_change(evaluator, state, assignment, service) is None
    service = EvaluationViolation(
        code="EVALUATION-SERVICE",
        message="miss",
        kind="service",
        period_id="p2026",
        target_id="s1",
    )
    assert _repair_change(evaluator, locked_state, assignment, service) is None

    outside = _contexts()
    outside[0] = outside[0].model_copy(
        update={"environment": GrowthEnvironment(in_domain=False, domain_reason="outside")}
    )
    blocked = repair_assignment(_evaluator(contexts=outside), evaluator.initial_assignment())
    assert not blocked.feasible

    tight = _rebuild(
        evaluator.formulation,
        periods=[
            evaluator.formulation.periods[0].model_copy(
                update={"budget": 0.01, "monitoring_budget": 0.01}
            ),
            evaluator.formulation.periods[1],
        ],
    )
    tight_evaluator = _evaluator(tight)
    selected = tight_evaluator.initial_assignment()
    selected[treatment] = 1
    monitor = _variable(tight, "monitoring", "sp1", "p2026")
    selected[monitor] = 1
    limited = repair_assignment(
        tight_evaluator,
        selected,
        OperatorConfig(max_repair_steps=1),
    )
    assert not limited.feasible

    import brushline.optimization.operators as operators_module

    original = _selected()[1]
    monkeypatch.setattr(
        operators_module,
        "repair_assignment",
        lambda evaluator, assignment, config=None: type(
            "R", (), {"assignment": original, "feasible": True, "changes": [], "remaining": []}
        )(),
    )
    operator = RepairOperator(state, evaluator)
    assert operator.propose(original, random.Random(1)) is None


def evaluation_zero(evaluator: ScheduleEvaluator) -> dict[int, int]:
    """Return the no-action assignment."""
    return evaluator.initial_assignment()


def test_apply_and_undo_helpers() -> None:
    """The public apply and undo helpers delegate to the typed move."""
    evaluator, assignment = _selected()
    move = ToggleOperator(_state(evaluator)).propose(assignment, random.Random(1))
    assert move is not None
    from brushline.optimization.operators import apply_move, undo_move

    updated = apply_move(assignment, move)
    assert undo_move(updated, move) == assignment
