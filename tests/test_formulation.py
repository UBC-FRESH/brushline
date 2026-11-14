"""Tests for the P5.1 optimization formulation."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from brushline.model.archive import Objective
from brushline.optimization.formulation import (
    DEFAULT_OBJECTIVES,
    OBJECTIVE_NAMES,
    ConstraintSpec,
    Formulation,
    FormulationError,
    PeriodSpec,
    TreatmentOption,
    Variable,
    build_formulation,
    validate_formulation,
)
from pydantic import ValidationError

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "notes" / "reference" / "p5-formulation.v1.json"
NOW = datetime(2026, 11, 14, tzinfo=UTC)


def _formulation() -> Formulation:
    return Formulation.model_validate_json(FIXTURE.read_text(encoding="utf-8"))


def _build(formulation: Formulation | None = None) -> Formulation:
    base = formulation or _formulation()
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


def test_committed_formulation_is_valid() -> None:
    """The fixture has stable variables and all four objectives."""
    formulation = _formulation()
    report = validate_formulation(formulation)
    assert report.is_valid
    assert report.counts["variables"] == 6
    assert report.counts["segments"] == 2
    assert report.counts["periods"] == 2
    assert report.counts["objectives"] == 4
    assert formulation.variable_count == 6
    assert formulation.initial_assignment() == {
        0: 0,
        1: 0,
        2: 0,
        3: 0,
        4: 0,
        5: 0,
    }
    assert formulation.option_count(0) == 3
    assert formulation.option_at(0, 0) == "none"
    assert {objective.name for objective in formulation.objectives} == set(OBJECTIVE_NAMES)
    assert {objective.direction for objective in formulation.objectives} == {
        "minimize",
        "maximize",
    }


def test_build_reproduces_the_fixture() -> None:
    """Building from the fixture specs reproduces the same variables and constraints."""
    expected = _formulation()
    built = _build(expected)
    assert built.variables == expected.variables
    assert built.constraints == expected.constraints
    assert built.objectives == expected.objectives


def test_allowed_methods_filter_options() -> None:
    """A segment's allowed methods filter its treatment options."""
    formulation = _formulation()
    treatment_variables = [
        variable for variable in formulation.variables if variable.kind == "treatment"
    ]
    s2 = [variable for variable in treatment_variables if variable.target_id == "s2"]
    assert s2
    assert all("manual-l1" not in variable.option_ids for variable in s2)
    s1 = [variable for variable in treatment_variables if variable.target_id == "s1"]
    assert any("manual-l1" in variable.option_ids for variable in s1)


def test_inaccessible_period_creates_access_constraint() -> None:
    """An inaccessible segment/period has an access constraint."""
    formulation = _formulation()
    access = [constraint for constraint in formulation.constraints if constraint.kind == "access"]
    assert len(access) == 1
    assert access[0].target_id == "s2"
    assert access[0].period_id == "p2027"


def test_validation_names_bad_formulation_fields() -> None:
    """The validator catches indices, refs, options, constraints, and objectives."""
    formulation = _formulation()
    cases: list[tuple[dict[str, object], str]] = [
        (
            {"variables": [formulation.variables[0].model_copy(update={"index": 9})]},
            "FORMULATION-INDEX",
        ),
        (
            {"variables": [formulation.variables[0].model_copy(update={"kind": "other"})]},
            "FORMULATION-KIND",
        ),
        (
            {"variables": [formulation.variables[0].model_copy(update={"period_id": "missing"})]},
            "FORMULATION-REF",
        ),
        (
            {"variables": [formulation.variables[0].model_copy(update={"target_id": "missing"})]},
            "FORMULATION-REF",
        ),
        (
            {
                "variables": [
                    formulation.variables[0].model_copy(update={"option_ids": ["none", "missing"]})
                ]
            },
            "FORMULATION-OPTION",
        ),
        (
            {
                "objectives": [
                    formulation.objectives[0].model_copy(update={"name": "unknown"}),
                    *formulation.objectives[1:],
                ]
            },
            "FORMULATION-OBJECTIVE",
        ),
        (
            {"constraints": [formulation.constraints[0].model_copy(update={"kind": "unknown"})]},
            "FORMULATION-CONSTRAINT",
        ),
        (
            {
                "constraints": [
                    formulation.constraints[0].model_copy(update={"period_id": "missing"})
                ]
            },
            "FORMULATION-CONSTRAINT",
        ),
        (
            {
                "constraints": [
                    formulation.constraints[0].model_copy(
                        update={
                            "kind": "access",
                            "scope": "segment",
                            "target_id": "missing",
                        }
                    )
                ]
            },
            "FORMULATION-CONSTRAINT",
        ),
    ]
    for updates, prefix in cases:
        bad = formulation.model_copy(update=updates)
        assert any(error.startswith(prefix) for error in validate_formulation(bad).errors), prefix
    naive = formulation.model_copy(update={"created_utc": datetime(2026, 11, 14)})
    assert any(error.startswith("FORMULATION-TIME") for error in validate_formulation(naive).errors)
    duplicate = formulation.model_copy(
        update={"variables": [formulation.variables[0], formulation.variables[0]]}
    )
    assert any(
        error.startswith("FORMULATION-ID") for error in validate_formulation(duplicate).errors
    )
    unused = formulation.model_copy(
        update={
            "treatment_options": [
                *formulation.treatment_options,
                TreatmentOption(
                    option_id="unused",
                    method="mowing",
                    intensity=0.1,
                    season="fall",
                    cost_per_ha=1,
                ),
            ]
        }
    )
    assert any(
        warning.startswith("FORMULATION-OPTION")
        for warning in validate_formulation(unused).warnings
    )
    no_monitoring = formulation.model_copy(update={"monitoring_options": []})
    assert any(
        warning.startswith("FORMULATION-EMPTY")
        for warning in validate_formulation(no_monitoring).warnings
    )
    no_treatment = formulation.model_copy(update={"treatment_options": []})
    assert any(
        warning.startswith("FORMULATION-EMPTY")
        for warning in validate_formulation(no_treatment).warnings
    )


def test_period_and_variable_models_validate() -> None:
    """Periods, variables, and constraints enforce their local rules."""
    with pytest.raises(ValidationError, match="end_year"):
        PeriodSpec(
            period_id="p",
            start_year=2027,
            end_year=2026,
            budget=1,
            monitoring_budget=1,
        )
    with pytest.raises(ValidationError, match="capacity"):
        PeriodSpec(
            period_id="p",
            start_year=2026,
            end_year=2026,
            budget=1,
            monitoring_budget=1,
            capacity_by_method={"mowing": -1},
        )
    with pytest.raises(ValidationError, match="first option"):
        Variable(
            index=0,
            kind="treatment",
            target_id="s1",
            period_id="p1",
            option_ids=["mow"],
        )
    with pytest.raises(ValidationError, match="unique"):
        Variable(
            index=0,
            kind="treatment",
            target_id="s1",
            period_id="p1",
            option_ids=["none", "none"],
        )
    with pytest.raises(ValidationError):
        ConstraintSpec(
            constraint_id="c",
            kind="budget",
            scope="period",
            target_id="p1",
            value=-1,
            unit="CAD",
        )


def test_build_rejects_duplicate_segments() -> None:
    """A formulation with duplicate targets fails during build."""
    base = _formulation()
    with pytest.raises(FormulationError, match="duplicate"):
        _build(base.model_copy(update={"segments": [base.segments[0], base.segments[0]]}))


def test_default_objectives_are_the_four_core_dimensions() -> None:
    """The default objective vector names directions and units."""
    assert [objective.name for objective in DEFAULT_OBJECTIVES] == list(OBJECTIVE_NAMES)
    assert all(objective.unit for objective in DEFAULT_OBJECTIVES)
    assert Objective(name="present_cost", direction="minimize", unit="CAD")


def test_validation_names_unknown_monitoring_span() -> None:
    """A monitoring variable with no matching span is named."""
    formulation = _formulation()
    variables = [
        *formulation.variables[:-1],
        formulation.variables[-1].model_copy(update={"target_id": "missing"}),
    ]
    bad = formulation.model_copy(update={"variables": variables})
    assert any(error.startswith("FORMULATION-REF") for error in validate_formulation(bad).errors)
