"""Tests for the P7.1 tactical program."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from brushline.tactical.program import (
    TacticalAction,
    TacticalConfig,
    TacticalError,
    TacticalProgram,
    TreatmentUnit,
    build_tactical_program,
    validate_tactical_inputs,
)
from pydantic import ValidationError

NOW = datetime(2026, 11, 14, tzinfo=UTC)


def _units() -> list[TreatmentUnit]:
    return [
        TreatmentUnit(
            unit_id="u1",
            span_id="sp1",
            segment_ids=["s1", "s2"],
            area_ha=2.0,
            allowed_methods=["mowing"],
            allowed_seasons=["spring", "summer"],
        ),
        TreatmentUnit(
            unit_id="u2",
            span_id="sp1",
            segment_ids=["s3"],
            area_ha=1.0,
            allowed_methods=["manual"],
            allowed_seasons=["fall"],
        ),
    ]


def _actions() -> list[TacticalAction]:
    return [
        TacticalAction(
            action_id="a1",
            unit_id="u1",
            year=2026,
            season="spring",
            method="mowing",
            contractor_id="c1",
            cost=100,
            capacity_units=1,
        ),
        TacticalAction(
            action_id="a2",
            unit_id="u2",
            year=2026,
            season="fall",
            method="manual",
            contractor_id="c2",
            cost=50,
            capacity_units=1,
        ),
    ]


def _program(
    config: TacticalConfig | None = None,
    units: list[TreatmentUnit] | None = None,
    actions: list[TacticalAction] | None = None,
) -> TacticalProgram:
    return build_tactical_program(
        program_id="p7",
        instance_id="tiny",
        units=units if units is not None else _units(),
        actions=actions if actions is not None else _actions(),
        config=config
        or TacticalConfig(
            horizon_years=2,
            start_year=2026,
            budget_by_year={2026: 200, 2027: 100},
        ),
        created_utc=NOW,
    )


def test_tactical_program_is_feasible_and_traceable() -> None:
    """A valid program records costs, budgets, and contractor allocation."""
    program = _program()
    assert program.feasible
    assert program.total_cost == 150
    assert program.cost_by_year == {2026: 150}
    assert program.contractor_allocation == {"c1": 1, "c2": 1}
    assert [action.action_id for action in program.actions] == ["a1", "a2"]
    assert program.created_utc == NOW
    assert validate_tactical_inputs(_units(), _actions()).is_valid


def test_budget_method_season_and_year_violations() -> None:
    """Every hard tactical rule is named when broken."""
    actions = _actions()
    program = _program(
        TacticalConfig(horizon_years=2, start_year=2026, budget_by_year={2026: 10}),
        actions=actions,
    )
    assert not program.feasible
    assert any(v.code == "TACTICAL-BUDGET" for v in program.violations)
    bad_method = actions[0].model_copy(update={"method": "manual"})
    bad_season = actions[1].model_copy(update={"season": "spring"})
    bad_year = actions[0].model_copy(update={"year": 2030})
    for action in (bad_method, bad_season, bad_year):
        program = _program(actions=[action])
        assert not program.feasible
        assert program.violations


def test_invalid_references_and_empty_program() -> None:
    """Unknown refs, duplicates, and empty actions are explicit."""
    bad = _actions()[0].model_copy(update={"unit_id": "missing"})
    with pytest.raises(TacticalError):
        _program(actions=[bad])
    duplicate = _actions()[0]
    with pytest.raises(TacticalError):
        _program(actions=[duplicate, duplicate])
    assert not validate_tactical_inputs(_units(), [bad]).is_valid
    empty = _program(actions=[])
    assert empty.feasible
    assert empty.actions == []
    assert validate_tactical_inputs(_units(), []).warnings != ()


def test_config_and_model_guards() -> None:
    """Horizon, budgets, unit area, and action fields are guarded."""
    with pytest.raises(ValidationError):
        TacticalConfig(horizon_years=6)
    with pytest.raises(ValidationError):
        TacticalConfig(budget_by_year={2026: -1})
    with pytest.raises(ValidationError):
        TreatmentUnit(
            unit_id="u",
            span_id="sp",
            segment_ids=[],
            area_ha=1,
        )
    with pytest.raises(ValidationError):
        TacticalAction(
            action_id="a",
            unit_id="u",
            year=2026,
            season="spring",
            method="mowing",
            contractor_id="c",
            cost=1,
            capacity_units=0,
        )
