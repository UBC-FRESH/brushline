"""Tests for the P6.1 single-segment dynamic program."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from brushline.strategic.dynamic_program import (
    DPState,
    DynamicProgram,
    DynamicProgramError,
    StrategicAction,
    Transition,
    solve_dynamic_program,
    validate_dynamic_program,
)
from pydantic import ValidationError

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "notes" / "reference" / "p6-dynamic-program.v1.json"
NOW = datetime(2026, 11, 14, tzinfo=UTC)


def _program() -> DynamicProgram:
    return DynamicProgram.model_validate_json(FIXTURE.read_text(encoding="utf-8"))


def test_fixture_solves_with_a_deterministic_policy() -> None:
    """The fixture has a valid policy and separate expected outcomes."""
    program = _program()
    assert validate_dynamic_program(program).is_valid
    result = solve_dynamic_program(program)
    assert result.program_id == "p6-dp-v1"
    assert result.segment_id == "seg-1"
    assert len(result.policy) == program.horizon * len(program.states)
    assert len(result.values) == program.horizon + 1
    assert result.action_for(0, "shrub") == "mow"
    assert result.action_for(0, "grass") == "none"
    assert result.action_for(0, "unknown") == "none"
    assert result.policy_value == pytest.approx(result.values[0]["shrub"])
    assert result.expected_cost > 0
    assert 0 < result.expected_service_attainment <= 1
    assert 0 <= result.expected_risk <= 1
    assert 0 <= result.expected_uncertainty <= 1
    assert result.action_for(0, "shrub") == solve_dynamic_program(program).action_for(0, "shrub")
    with pytest.raises(KeyError):
        result.action_for(9, "shrub")


def test_program_validation_names_references_and_probabilities() -> None:
    """Unknown refs, missing rows, and bad probabilities are rejected."""
    program = _program()
    cases = [
        program.model_copy(update={"initial_state": "missing"}),
        program.model_copy(update={"terminal_values": {"missing": 0.0}}),
        program.model_copy(
            update={
                "actions": [
                    program.actions[0].model_copy(update={"available_states": ["missing"]}),
                    program.actions[1],
                ]
            }
        ),
        program.model_copy(
            update={
                "transitions": [
                    program.transitions[0].model_copy(update={"from_state": "missing"}),
                    *program.transitions[1:],
                ]
            }
        ),
        program.model_copy(
            update={
                "transitions": [
                    program.transitions[0].model_copy(update={"to_state": "missing"}),
                    *program.transitions[1:],
                ]
            }
        ),
        program.model_copy(
            update={
                "transitions": [
                    program.transitions[0].model_copy(update={"action_id": "missing"}),
                    *program.transitions[1:],
                ]
            }
        ),
        program.model_copy(update={"transitions": program.transitions[1:]}),
        program.model_copy(
            update={
                "transitions": [
                    program.transitions[0].model_copy(update={"probability": 0.6}),
                    *program.transitions[1:],
                ]
            }
        ),
        program.model_copy(
            update={
                "transitions": [
                    program.transitions[0],
                    program.transitions[0],
                    *program.transitions[1:],
                ]
            }
        ),
        program.model_copy(
            update={"states": [program.states[0], program.states[0], program.states[2]]}
        ),
        program.model_copy(
            update={"actions": [program.actions[0], program.actions[0], program.actions[1]]}
        ),
    ]
    for case in cases:
        assert not validate_dynamic_program(case).is_valid
    all_available = program.model_copy(
        update={
            "actions": [
                action.model_copy(update={"available_states": []}) for action in program.actions
            ]
        }
    )
    assert any(
        warning.startswith("DP-AVAILABILITY")
        for warning in validate_dynamic_program(all_available).warnings
    )
    with pytest.raises(DynamicProgramError):
        solve_dynamic_program(cases[0])


def test_invalid_models_and_no_available_action() -> None:
    """Local model rules and a state with no action fail explicitly."""
    with pytest.raises(ValidationError, match="zero cost"):
        StrategicAction(action_id="bad", method=None, cost=1)
    with pytest.raises(ValidationError):
        DPState.model_validate({"state_id": "bad", "state_class": "not-a-class"})
    with pytest.raises(ValidationError):
        Transition(
            from_state="a",
            action_id="x",
            to_state="b",
            probability=0,
            service_attainment=0,
            risk=0,
            uncertainty=0,
        )
    program = _program()
    only_grass = program.model_copy(
        update={
            "actions": [
                action.model_copy(update={"available_states": ["grass"]})
                for action in program.actions
            ],
            "initial_state": "unknown",
        }
    )
    with pytest.raises(DynamicProgramError, match="no available action"):
        solve_dynamic_program(only_grass)
    with pytest.raises(ValidationError):
        DynamicProgram(
            program_id="x",
            segment_id="s",
            states=program.states,
            actions=program.actions,
            transitions=program.transitions,
            horizon=1,
            initial_state="shrub",
            created_utc=datetime(2026, 11, 14),
        )


def test_tie_break_and_terminal_values() -> None:
    """A tie is broken by action id and terminal values enter the value."""
    action_a = StrategicAction(action_id="aaa", label="a")
    action_b = StrategicAction(action_id="bbb", label="b")
    states = [DPState(state_id="one", state_class="shrub")]
    transitions = [
        Transition(
            from_state="one",
            action_id="aaa",
            to_state="one",
            probability=1,
            service_attainment=0.5,
            risk=0,
            uncertainty=0,
        ),
        Transition(
            from_state="one",
            action_id="bbb",
            to_state="one",
            probability=1,
            service_attainment=0.5,
            risk=0,
            uncertainty=0,
        ),
    ]
    tied = DynamicProgram(
        program_id="tie",
        segment_id="s",
        states=states,
        actions=[action_b, action_a],
        transitions=transitions,
        horizon=1,
        discount_rate=0,
        initial_state="one",
        terminal_values={"one": 0.0},
        created_utc=NOW,
    )
    result = solve_dynamic_program(tied)
    assert result.action_for(0, "one") == "aaa"
    terminal = _program().model_copy(update={"terminal_values": {"shrub": 2.0}})
    assert solve_dynamic_program(terminal).values[-1]["shrub"] == 2.0
