"""Tests for the P5.2 exact schedule evaluator."""

from __future__ import annotations

from pathlib import Path

import pytest
from brushline.model.corridor import ServiceStandard
from brushline.optimization.evaluator import (
    AssignmentChange,
    EvaluationConfig,
    EvaluationResult,
    EvaluatorError,
    IncrementalEvaluator,
    ScheduleEvaluator,
    SegmentContext,
)
from brushline.optimization.formulation import (
    Formulation,
    PeriodSpec,
    build_formulation,
)
from brushline.vegetation.growth import GrowthEnvironment
from brushline.vegetation.state_space import StateDistribution
from pydantic import ValidationError

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "notes" / "reference" / "p5-formulation.v1.json"
STANDARD = ServiceStandard(service_standard_id="std1", max_height_m=4.0, min_clearance_m=1.0)


def _formulation() -> Formulation:
    return Formulation.model_validate_json(FIXTURE.read_text(encoding="utf-8"))


def _distribution(
    height: float,
    cover: float,
    density: float,
    confidence: float,
    *,
    height_sd: float = 0.2,
) -> StateDistribution:
    return StateDistribution(
        class_probabilities={"shrub": 0.8, "unknown": 0.2},
        height_m=height,
        height_sd=height_sd,
        cover_pct=cover,
        cover_sd=4,
        density_per_ha=density,
        density_sd=50,
        age_years=1,
        confidence=confidence,
    )


def _contexts() -> list[SegmentContext]:
    return [
        SegmentContext(
            segment_id="s1",
            functional_group="shrub",
            initial=_distribution(1.5, 40, 1000, 0.6),
            service_standard=STANDARD,
            length_m=100,
            asset_height_m=8,
        ),
        SegmentContext(
            segment_id="s2",
            functional_group="grass_herb",
            initial=_distribution(0.4, 70, 0, 0.8),
            service_standard=STANDARD,
            length_m=150,
            asset_height_m=8,
        ),
    ]


def _evaluator(
    formulation: Formulation | None = None,
    contexts: list[SegmentContext] | None = None,
    config: EvaluationConfig | None = None,
) -> ScheduleEvaluator:
    return ScheduleEvaluator(formulation or _formulation(), contexts or _contexts(), config)


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


def _variable_index(formulation: Formulation, kind: str, target_id: str, period_id: str) -> int:
    return next(
        variable.index
        for variable in formulation.variables
        if variable.kind == kind
        and variable.target_id == target_id
        and variable.period_id == period_id
    )


def _option_index(formulation: Formulation, variable_index: int, option_id: str) -> int:
    return formulation.variables[variable_index].option_ids.index(option_id)


def test_initial_evaluation_has_four_objectives() -> None:
    """The no-action plan is exact, feasible, and has no cost."""
    evaluator = _evaluator()
    result = evaluator.evaluate(evaluator.initial_assignment())
    assert result.feasible
    assert result.violations == []
    assert result.soft_violations == []
    assert set(result.objective_vector) == {
        "present_cost",
        "service_risk",
        "service_attainment",
        "uncertainty",
    }
    assert result.objective_vector["present_cost"] == 0
    assert result.objective_vector["service_attainment"] == 1
    assert result.objective_vector["uncertainty"] > 0
    assert result.total_cost == 0
    assert len(result.period_results) == 4


def test_treatment_changes_state_and_cost() -> None:
    """A treatment is applied, charged, and reduces the end state."""
    formulation = _formulation()
    evaluator = _evaluator(formulation)
    assignment = evaluator.initial_assignment()
    variable = _variable_index(formulation, "treatment", "s1", "p2026")
    assignment[variable] = _option_index(formulation, variable, "mow-l1")
    result = evaluator.evaluate(assignment)
    assert result.feasible
    assert result.treatment_cost == pytest.approx(50.0)
    assert result.monitoring_cost == 0
    assert result.total_cost == pytest.approx(50.0)
    baseline = evaluator.evaluate(evaluator.initial_assignment())
    treated = next(
        item
        for item in result.period_results
        if item.segment_id == "s1" and item.period_id == "p2026"
    )
    untreated = next(
        item
        for item in baseline.period_results
        if item.segment_id == "s1" and item.period_id == "p2026"
    )
    assert treated.treatment_option_id == "mow-l1"
    assert treated.end_state.height_m < untreated.end_state.height_m
    assert treated.treatment_cost == pytest.approx(50.0)


def test_monitoring_is_charged_once_and_reduces_uncertainty() -> None:
    """A span monitoring cost is charged once and benefits every segment."""
    formulation = _formulation()
    evaluator = _evaluator(formulation)
    assignment = evaluator.initial_assignment()
    variable = _variable_index(formulation, "monitoring", "sp1", "p2026")
    assignment[variable] = _option_index(formulation, variable, "lidar-annual")
    result = evaluator.evaluate(assignment)
    baseline = evaluator.evaluate(evaluator.initial_assignment())
    assert result.monitoring_cost == pytest.approx(2000.0)
    assert result.total_cost == pytest.approx(2000.0)
    assert sum(item.monitoring_cost for item in result.period_results) == pytest.approx(2000.0)
    assert result.objective_vector["uncertainty"] < baseline.objective_vector["uncertainty"]
    assert all(
        item.monitoring_option_id == "lidar-annual"
        for item in result.period_results
        if item.period_id == "p2026"
    )


def test_budget_capacity_and_monitoring_budget_violations() -> None:
    """Hard resource limits are named and make the plan infeasible."""
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
    tight = _rebuild(formulation, periods=periods)
    evaluator = _evaluator(tight)
    assignment = evaluator.initial_assignment()
    treatment = _variable_index(tight, "treatment", "s1", "p2026")
    assignment[treatment] = _option_index(tight, treatment, "mow-l1")
    monitoring = _variable_index(tight, "monitoring", "sp1", "p2026")
    assignment[monitoring] = _option_index(tight, monitoring, "lidar-annual")
    result = evaluator.evaluate(assignment)
    assert not result.feasible
    codes = {violation.code for violation in result.violations}
    assert "EVALUATION-BUDGET" in codes
    assert "EVALUATION-CAPACITY" in codes
    assert "EVALUATION-MONITORING-BUDGET" in codes


def test_access_violation_and_service_hardness() -> None:
    """Access is hard; service is hard or soft according to the constraint."""
    formulation = _formulation()
    evaluator = _evaluator(formulation)
    assignment = evaluator.initial_assignment()
    variable = _variable_index(formulation, "treatment", "s2", "p2027")
    assignment[variable] = _option_index(formulation, variable, "mow-l1")
    result = evaluator.evaluate(assignment)
    assert any(violation.code == "EVALUATION-ACCESS" for violation in result.violations)

    high = _contexts()
    high[0] = high[0].model_copy(
        update={
            "initial": _distribution(1.5, 40, 1000, 0.6, height_sd=0),
            "service_standard": ServiceStandard(
                service_standard_id="std1", max_height_m=1.0, min_clearance_m=1.0
            ),
        }
    )
    hard = _evaluator(formulation, high).evaluate(evaluator.initial_assignment())
    assert not hard.feasible
    assert any(violation.code == "EVALUATION-SERVICE" for violation in hard.violations)
    assert hard.objective_vector["service_risk"] == pytest.approx(0.4, abs=0.01)

    soft_constraints = [
        constraint.model_copy(update={"hard": False})
        if constraint.kind == "service"
        else constraint
        for constraint in formulation.constraints
    ]
    soft_formulation = formulation.model_copy(update={"constraints": soft_constraints})
    soft = _evaluator(soft_formulation, high).evaluate(evaluator.initial_assignment())
    assert soft.feasible
    assert any(violation.code == "EVALUATION-SERVICE" for violation in soft.soft_violations)


def test_blocked_growth_and_treatment_are_hard_violations() -> None:
    """Out-of-domain and unknown states are blocked, not extrapolated."""
    formulation = _formulation()
    evaluator = _evaluator(formulation)
    outside = _contexts()
    outside[0] = outside[0].model_copy(
        update={
            "environment": GrowthEnvironment(
                in_domain=False, domain_reason="outside the prototype domain"
            )
        }
    )
    blocked = _evaluator(formulation, outside).evaluate(evaluator.initial_assignment())
    assert not blocked.feasible
    assert any(violation.code == "EVALUATION-GROWTH" for violation in blocked.violations)

    assignment = evaluator.initial_assignment()
    variable = _variable_index(formulation, "treatment", "s1", "p2026")
    assignment[variable] = _option_index(formulation, variable, "mow-l1")
    blocked_treatment = _evaluator(formulation, outside).evaluate(assignment)
    assert any(
        violation.code == "EVALUATION-TREATMENT" for violation in blocked_treatment.violations
    )

    unknown = _contexts()
    unknown[0] = unknown[0].model_copy(update={"functional_group": "unknown"})
    unknown_assignment = evaluator.initial_assignment()
    unknown_assignment[variable] = _option_index(formulation, variable, "mow-l1")
    unknown_result = _evaluator(formulation, unknown).evaluate(unknown_assignment)
    assert any(violation.code == "EVALUATION-TREATMENT" for violation in unknown_result.violations)


def test_long_period_treatment_error_is_named() -> None:
    """An overlong regrowth horizon becomes a named treatment violation."""
    formulation = _formulation()
    periods = [
        PeriodSpec(
            period_id="p2026",
            start_year=2026,
            end_year=2050,
            budget=100000,
            monitoring_budget=10000,
            capacity_by_method={"mowing": 30, "manual": 20},
        ),
        formulation.periods[1],
    ]
    long_formulation = _rebuild(formulation, periods=periods)
    evaluator = _evaluator(long_formulation)
    assignment = evaluator.initial_assignment()
    variable = _variable_index(long_formulation, "treatment", "s1", "p2026")
    assignment[variable] = _option_index(long_formulation, variable, "mow-l1")
    result = evaluator.evaluate(assignment)
    assert any(violation.code == "EVALUATION-TREATMENT" for violation in result.violations)


def test_discount_and_batch_and_scalarization() -> None:
    """Discounting, batch order, and scalarization are deterministic."""
    formulation = _formulation()
    evaluator = _evaluator(formulation, config=EvaluationConfig(discount_rate=0.1, base_year=2026))
    assignment = evaluator.initial_assignment()
    variable = _variable_index(formulation, "treatment", "s1", "p2027")
    assignment[variable] = _option_index(formulation, variable, "mow-l1")
    result = evaluator.evaluate(assignment)
    assert result.total_cost == pytest.approx(50.0)
    assert result.discounted_cost == pytest.approx(50.0 / 1.1)
    batch = evaluator.evaluate_batch([evaluator.initial_assignment(), assignment])
    assert batch[1] == result
    assert batch[0].total_cost == 0
    weights = dict.fromkeys(result.objective_vector, 0.25)
    expected = sum(
        weights[name]
        * (
            1.0 - result.objective_vector[name]
            if name == "service_attainment"
            else result.objective_vector[name]
        )
        for name in weights
    )
    assert result.scalar_objective(weights) == pytest.approx(expected)
    with pytest.raises(EvaluatorError):
        result.scalar_objective({"present_cost": 1})
    with pytest.raises(EvaluatorError):
        result.scalar_objective({**weights, "present_cost": -1})


def test_incremental_apply_and_undo_are_exact() -> None:
    """Apply/undo restores the exact assignment and evaluation."""
    formulation = _formulation()
    evaluator = _evaluator(formulation)
    incremental = IncrementalEvaluator(evaluator)
    baseline = incremental.evaluation
    variable = _variable_index(formulation, "monitoring", "sp1", "p2026")
    change = AssignmentChange(
        variable=variable,
        before=0,
        after=_option_index(formulation, variable, "field-sample"),
    )
    updated = incremental.apply(change)
    assert incremental.mode == "full_fallback"
    assert incremental.fallbacks == 1
    assert updated.monitoring_cost == pytest.approx(1000.0)
    restored = incremental.undo(change)
    assert restored == baseline
    assert incremental.assignment == evaluator.initial_assignment()
    with pytest.raises(EvaluatorError):
        incremental.apply(change.model_copy(update={"before": 99}))
    with pytest.raises(EvaluatorError):
        incremental.undo(change.model_copy(update={"after": 99}))


def test_invalid_assignments_and_contexts() -> None:
    """Invalid assignments and contexts fail explicitly."""
    formulation = _formulation()
    evaluator = _evaluator(formulation)
    missing = evaluator.evaluate({0: 0})
    assert not missing.feasible
    assert missing.violations[0].code == "EVALUATION-ASSIGNMENT"
    invalid = evaluator.initial_assignment()
    invalid[0] = 99
    result = evaluator.evaluate(invalid)
    assert not result.feasible
    assert any(violation.code == "EVALUATION-OPTION" for violation in result.violations)
    with pytest.raises(EvaluatorError, match="unique"):
        ScheduleEvaluator(formulation, [_contexts()[0], _contexts()[0]])
    with pytest.raises(EvaluatorError, match="cover"):
        ScheduleEvaluator(formulation, [_contexts()[0]])
    mismatched = _contexts()
    mismatched[0] = mismatched[0].model_copy(update={"length_m": 99})
    with pytest.raises(EvaluatorError, match="length"):
        ScheduleEvaluator(formulation, mismatched)


def test_result_and_context_models_validate() -> None:
    """The objective vector and context fields are guarded."""
    evaluator = _evaluator()
    result = evaluator.evaluate(evaluator.initial_assignment())
    payload = result.model_dump()
    payload["objective_vector"] = {"present_cost": 1.0}
    with pytest.raises(ValidationError):
        EvaluationResult.model_validate(payload)
    with pytest.raises(ValidationError):
        SegmentContext(
            segment_id="s1",
            functional_group="shrub",
            initial=_distribution(1.0, 10, 10, 0.5),
            service_standard=STANDARD,
            length_m=0,
        )
    with pytest.raises(ValidationError):
        SegmentContext(
            segment_id="s1",
            functional_group="shrub",
            initial=_distribution(1.0, 10, 10, 0.5),
            service_standard=STANDARD,
            length_m=1,
            asset_height_m=0,
        )
    with pytest.raises(ValidationError):
        EvaluationConfig(discount_rate=-1)


def test_missing_context_branches_and_nonfinite_objective() -> None:
    """Fallback branches, clearance-only service checks, and finite guards are covered."""
    formulation = _formulation()
    no_treatment = formulation.model_copy(
        update={
            "variables": [
                variable
                for variable in formulation.variables
                if not (
                    variable.kind == "treatment"
                    and variable.target_id == "s1"
                    and variable.period_id == "p2026"
                )
            ]
        }
    )
    evaluator = _evaluator(no_treatment)
    assert evaluator.evaluate(evaluator.initial_assignment()).feasible

    span_formulation = formulation.model_copy(
        update={"spans": [formulation.spans[0].model_copy(update={"segment_ids": ["s1"]})]}
    )
    evaluator = _evaluator(span_formulation)
    assert evaluator.evaluate(evaluator.initial_assignment()).feasible

    contexts = _contexts()
    contexts[0] = contexts[0].model_copy(update={"asset_height_m": None})
    assert (
        _evaluator(formulation, contexts)
        .evaluate(_evaluator(formulation, contexts).initial_assignment())
        .feasible
    )

    contexts = _contexts()
    contexts[0] = contexts[0].model_copy(update={"asset_height_m": 3.2})
    contexts[0] = contexts[0].model_copy(
        update={
            "service_standard": ServiceStandard(
                service_standard_id="std1", max_height_m=4.0, min_clearance_m=2.0
            )
        }
    )
    clearance = _evaluator(formulation, contexts).evaluate(
        _evaluator(formulation, contexts).initial_assignment()
    )
    assert any(violation.code == "EVALUATION-SERVICE" for violation in clearance.violations)

    evaluator = _evaluator()
    result = evaluator.evaluate(evaluator.initial_assignment())
    payload = result.model_dump()
    payload["objective_vector"] = {
        **result.objective_vector,
        "present_cost": float("inf"),
    }
    with pytest.raises(ValidationError):
        EvaluationResult.model_validate(payload)
    with pytest.raises(EvaluatorError, match="unknown segment"):
        evaluator._segment_length("missing")
    from brushline.optimization.evaluator import _exceedance

    assert _exceedance(2.0, 0.0, 1.0) == 1.0
    assert _exceedance(0.0, 0.0, 1.0) == 0.0
    assert _exceedance(0.0, 1.0, float("inf")) == 0.0
