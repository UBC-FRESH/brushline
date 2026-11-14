"""Exact schedule evaluation and a conservative incremental path.

The evaluator replays a formulation assignment through the P4 growth and treatment models. It
returns the four-objective vector, hard and soft violations, cost accounts, and a per-segment
period trail. The incremental wrapper applies and undoes typed assignment changes and always
recomputes exactly; global budget, capacity, service, and coupled growth make an unproved delta
unsafe, so the full-evaluation fallback is the declared rule.
"""

from __future__ import annotations

import math
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from brushline.model.corridor import ServiceStandard
from brushline.model.state import FunctionalGroup
from brushline.optimization.formulation import (
    OBJECTIVE_NAMES,
    Formulation,
    MonitoringOption,
    TreatmentOption,
)
from brushline.vegetation.growth import GrowthEnvironment, GrowthError, GrowthRequest, grow
from brushline.vegetation.state_space import StateDistribution
from brushline.vegetation.treatment import TreatmentError, TreatmentRequest, apply_treatment

EVALUATION_SCHEMA_VERSION: Literal["brushline.optimization-evaluation.v1"] = (
    "brushline.optimization-evaluation.v1"
)
EVALUATION_MODES: tuple[str, ...] = ("exact", "full_fallback")


class EvaluatorError(ValueError):
    """Raised when the evaluator or a context is inconsistent."""


class EvaluationConfig(BaseModel):
    """Discount and uncertainty settings.

    Parameters
    ----------
    discount_rate : float
        Annual discount rate from 0 to 1.
    base_year : int or None
        Discount base year. Defaults to the first period.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    discount_rate: float = Field(default=0.0, ge=0, le=1)
    base_year: int | None = None


class SegmentContext(BaseModel):
    """Initial state and site context for one segment.

    Parameters
    ----------
    segment_id : str
        Segment id.
    functional_group : str
        Functional group.
    initial : StateDistribution
        Initial distribution.
    service_standard : ServiceStandard
        Service standard.
    length_m : float
        Segment length in metres.
    environment : GrowthEnvironment, optional
        Growth environment.
    treatment_width_m : float, optional
        Swath width for area and cost. Defaults to 10.
    asset_height_m : float or None, optional
        Conductor or asset height for clearance.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    segment_id: str = Field(min_length=1)
    functional_group: FunctionalGroup
    initial: StateDistribution
    service_standard: ServiceStandard
    length_m: float = Field(gt=0)
    environment: GrowthEnvironment = Field(default_factory=GrowthEnvironment)
    treatment_width_m: float = Field(default=10.0, gt=0)
    asset_height_m: float | None = Field(default=None, gt=0)

    @property
    def area_ha(self) -> float:
        """Return the treated area in hectares.

        Returns
        -------
        float
            Segment length times swath width in hectares.
        """
        return self.length_m * self.treatment_width_m / 10000.0


class EvaluationViolation(BaseModel):
    """One named hard or soft violation.

    Parameters
    ----------
    code : str
        Stable violation code.
    message : str
        Human explanation.
    kind : str
        Constraint kind.
    period_id : str or None
        Period id.
    target_id : str or None
        Segment or span id.
    variable_index : int or None
        Variable index.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    code: str = Field(min_length=1)
    message: str = Field(min_length=1)
    kind: str = Field(min_length=1)
    period_id: str | None = None
    target_id: str | None = None
    variable_index: int | None = None


class SegmentPeriodResult(BaseModel):
    """The state and service result for one segment and period.

    Parameters
    ----------
    segment_id : str
        Segment id.
    period_id : str
        Period id.
    start_state : StateDistribution
        State at period start.
    end_state : StateDistribution
        State at period end.
    treatment_option_id : str or None
        Selected treatment option.
    monitoring_option_id : str or None
        Selected monitoring option.
    treatment_cost : float
        Treatment cost.
    monitoring_cost : float
        Monitoring cost.
    service_attainment : bool
        Whether the mean state meets the service standard.
    risk_probability : float
        Height or clearance exceedance probability.
    uncertainty : float
        One minus confidence at period end.
    height_margin_m : float
        Service height margin, negative when exceeded.
    clearance_margin_m : float or None
        Clearance margin, or None without an asset height.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    segment_id: str
    period_id: str
    start_state: StateDistribution
    end_state: StateDistribution
    treatment_option_id: str | None = None
    monitoring_option_id: str | None = None
    treatment_cost: float = Field(ge=0)
    monitoring_cost: float = Field(ge=0)
    service_attainment: bool
    risk_probability: float = Field(ge=0, le=1)
    uncertainty: float = Field(ge=0, le=1)
    height_margin_m: float
    clearance_margin_m: float | None = None


class EvaluationResult(BaseModel):
    """The exact result of one schedule.

    Parameters
    ----------
    schema_version : {"brushline.optimization-evaluation.v1"}
        Schema version.
    formulation_id : str
        Formulation id.
    assignment : dict of int to int
        Variable-to-option assignment.
    objective_vector : dict of str to float
        Four objectives.
    feasible : bool
        Whether all hard constraints hold.
    violations : list of EvaluationViolation
        Hard violations.
    soft_violations : list of EvaluationViolation
        Soft violations.
    total_cost : float
        Undiscounted total cost.
    discounted_cost : float
        Discounted total cost.
    treatment_cost : float
        Treatment cost.
    monitoring_cost : float
        Monitoring cost.
    period_results : list of SegmentPeriodResult
        Segment-period trail.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["brushline.optimization-evaluation.v1"] = EVALUATION_SCHEMA_VERSION
    formulation_id: str
    assignment: dict[int, int]
    objective_vector: dict[str, float]
    feasible: bool
    violations: list[EvaluationViolation] = Field(default_factory=list)
    soft_violations: list[EvaluationViolation] = Field(default_factory=list)
    total_cost: float = Field(ge=0)
    discounted_cost: float = Field(ge=0)
    treatment_cost: float = Field(ge=0)
    monitoring_cost: float = Field(ge=0)
    period_results: list[SegmentPeriodResult] = Field(default_factory=list)

    @model_validator(mode="after")
    def _objective_shape(self) -> EvaluationResult:
        if set(self.objective_vector) != set(OBJECTIVE_NAMES):
            raise ValueError("objective_vector must contain the four core objectives")
        if any(not math.isfinite(value) for value in self.objective_vector.values()):
            raise ValueError("objective values must be finite")
        return self

    def scalar_objective(self, weights: dict[str, float]) -> float:
        """Return a weighted scalar objective, lower is better.

        Parameters
        ----------
        weights : dict of str to float
            Non-negative objective weights.

        Returns
        -------
        float
            Weighted sum after direction normalization.

        Raises
        ------
        EvaluatorError
            When a weight is unknown or negative.
        """
        if set(weights) != set(OBJECTIVE_NAMES):
            raise EvaluatorError("weights must name the four core objectives")
        if any(value < 0 for value in weights.values()):
            raise EvaluatorError("weights must be non-negative")
        total = 0.0
        for objective in OBJECTIVE_NAMES:
            value = self.objective_vector[objective]
            if objective == "service_attainment":
                value = 1.0 - value
            total += weights[objective] * value
        return total


class AssignmentChange(BaseModel):
    """One reversible assignment change.

    Parameters
    ----------
    variable : int
        Variable index.
    before : int
        Previous option index.
    after : int
        Proposed option index.
    kind : str, optional
        Move kind. Defaults to ``toggle``.
    size : int, optional
        Move size. Defaults to one.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    variable: int = Field(ge=0)
    before: int = Field(ge=0)
    after: int = Field(ge=0)
    kind: str = "toggle"
    size: int = Field(default=1, ge=1)


class ScheduleEvaluator:
    """Exact evaluator for one formulation and its segment contexts.

    Parameters
    ----------
    formulation : Formulation
        Optimization formulation.
    contexts : list of SegmentContext
        One context per segment.
    config : EvaluationConfig, optional
        Discount settings.

    Raises
    ------
    EvaluatorError
        When a segment context is missing, duplicated, or unknown.
    """

    def __init__(
        self,
        formulation: Formulation,
        contexts: list[SegmentContext],
        config: EvaluationConfig | None = None,
    ) -> None:
        self.formulation = formulation
        self.config = config or EvaluationConfig()
        self._contexts = {context.segment_id: context for context in contexts}
        if len(self._contexts) != len(contexts):
            raise EvaluatorError("segment contexts must be unique")
        expected = {segment.segment_id for segment in formulation.segments}
        if set(self._contexts) != expected:
            raise EvaluatorError("segment contexts must cover every segment")
        for segment in formulation.segments:
            if abs(self._contexts[segment.segment_id].length_m - segment.length_m) > 1e-9:
                raise EvaluatorError(f"context length does not match segment {segment.segment_id}")
        self._treatment = {option.option_id: option for option in formulation.treatment_options}
        self._monitoring = {option.option_id: option for option in formulation.monitoring_options}
        self._periods = {period.period_id: period for period in formulation.periods}
        self._variables = {variable.index: variable for variable in formulation.variables}
        self._treatment_variable = {
            (variable.target_id, variable.period_id): variable.index
            for variable in formulation.variables
            if variable.kind == "treatment"
        }
        self._monitoring_variable = {
            (variable.target_id, variable.period_id): variable.index
            for variable in formulation.variables
            if variable.kind == "monitoring"
        }
        self._span_segments = {span.span_id: span.segment_ids for span in formulation.spans}
        self._constraints = {
            (constraint.kind, constraint.period_id, constraint.target_id): constraint
            for constraint in formulation.constraints
        }

    def _validate_assignment(self, assignment: dict[int, int]) -> list[EvaluationViolation]:
        violations: list[EvaluationViolation] = []
        expected = set(self._variables)
        if set(assignment) != expected:
            missing = sorted(expected - set(assignment))
            extra = sorted(set(assignment) - expected)
            violations.append(
                EvaluationViolation(
                    code="EVALUATION-ASSIGNMENT",
                    message=(
                        f"assignment must cover every variable; missing={missing} extra={extra}"
                    ),
                    kind="assignment",
                )
            )
            return violations
        for index, option in assignment.items():
            variable = self._variables[index]
            if not isinstance(option, int) or option < 0 or option >= len(variable.option_ids):
                violations.append(
                    EvaluationViolation(
                        code="EVALUATION-OPTION",
                        message=f"variable {index} has invalid option {option!r}",
                        kind="option",
                        variable_index=index,
                    )
                )
        return violations

    def evaluate(self, assignment: dict[int, int]) -> EvaluationResult:
        """Evaluate one complete assignment exactly.

        Parameters
        ----------
        assignment : dict of int to int
            Variable-to-option assignment.

        Returns
        -------
        EvaluationResult
            Exact objectives, feasibility, costs, violations, and trail.
        """
        violations = self._validate_assignment(assignment)
        normalized = {int(index): int(option) for index, option in assignment.items()}
        if violations:
            return EvaluationResult(
                formulation_id=self.formulation.formulation_id,
                assignment=normalized,
                objective_vector=dict.fromkeys(OBJECTIVE_NAMES, 0.0),
                feasible=False,
                violations=violations,
                total_cost=0.0,
                discounted_cost=0.0,
                treatment_cost=0.0,
                monitoring_cost=0.0,
            )
        return self._evaluate(normalized)

    def evaluate_batch(self, assignments: list[dict[int, int]]) -> list[EvaluationResult]:
        """Evaluate a batch exactly and in order.

        Parameters
        ----------
        assignments : list of dict of int to int
            Assignments.

        Returns
        -------
        list of EvaluationResult
            One result per assignment.
        """
        return [self.evaluate(assignment) for assignment in assignments]

    def initial_assignment(self) -> dict[int, int]:
        """Return the no-action assignment.

        Returns
        -------
        dict of int to int
            Every variable at option 0.
        """
        return self.formulation.initial_assignment()

    def _evaluate(self, assignment: dict[int, int]) -> EvaluationResult:
        hard: list[EvaluationViolation] = []
        soft: list[EvaluationViolation] = []
        treatment_cost = 0.0
        monitoring_cost = 0.0
        method_areas: dict[tuple[str, str], float] = {}
        results: list[SegmentPeriodResult] = []
        periods = sorted(self.formulation.periods, key=lambda item: item.start_year)
        base_year = self.config.base_year or periods[0].start_year
        monitoring_selection: dict[tuple[str, str], MonitoringOption] = {}
        for span in self.formulation.spans:
            for period in periods:
                monitor_index = self._monitoring_variable.get((span.span_id, period.period_id))
                if monitor_index is None or assignment[monitor_index] == 0:
                    continue
                option_id = self.formulation.option_at(monitor_index, assignment[monitor_index])
                monitoring_selection[(span.span_id, period.period_id)] = self._monitoring[option_id]
                monitoring_cost += self._monitoring[option_id].cost_per_span
        for segment in self.formulation.segments:
            context = self._contexts[segment.segment_id]
            current = context.initial
            for period in periods:
                duration = max(1, period.end_year - period.start_year + 1)
                start = current
                treatment_option: TreatmentOption | None = None
                monitoring_option: MonitoringOption | None = None
                segment_treatment_cost = 0.0
                segment_monitoring_cost = 0.0
                treatment_index = self._treatment_variable.get(
                    (segment.segment_id, period.period_id)
                )
                if treatment_index is not None:
                    option_index = assignment[treatment_index]
                    if option_index > 0:
                        option_id = self.formulation.option_at(treatment_index, option_index)
                        treatment_option = self._treatment[option_id]
                        if period.period_id in segment.inaccessible_period_ids:
                            hard.append(
                                EvaluationViolation(
                                    code="EVALUATION-ACCESS",
                                    message=(
                                        f"{segment.segment_id} is inaccessible in "
                                        f"{period.period_id}"
                                    ),
                                    kind="access",
                                    period_id=period.period_id,
                                    target_id=segment.segment_id,
                                    variable_index=treatment_index,
                                )
                            )
                        current, segment_treatment_cost = self._apply_treatment(
                            context,
                            current,
                            period.period_id,
                            duration,
                            treatment_option,
                            treatment_index,
                            hard,
                        )
                        treatment_cost += segment_treatment_cost
                        method_key = (period.period_id, treatment_option.method)
                        method_areas[method_key] = (
                            method_areas.get(method_key, 0.0) + context.area_ha
                        )
                    else:
                        current = self._grow(
                            context,
                            current,
                            period.period_id,
                            duration,
                            treatment_index,
                            hard,
                        )
                else:
                    current = self._grow(context, current, period.period_id, duration, None, hard)
                for span in self.formulation.spans:
                    if segment.segment_id not in span.segment_ids:
                        continue
                    monitoring_option = monitoring_selection.get((span.span_id, period.period_id))
                    if monitoring_option is None:
                        continue
                    current = self._monitor(current, monitoring_option)
                    segment_monitoring_cost += monitoring_option.cost_per_span / len(
                        span.segment_ids
                    )
                risk = self._risk(context, current)
                attainment = self._attainment(context, current)
                uncertainty = max(0.0, 1.0 - current.confidence)
                height_margin = context.service_standard.max_height_m - current.height_m
                clearance_margin = (
                    None
                    if context.asset_height_m is None
                    else context.asset_height_m
                    - current.height_m
                    - context.service_standard.min_clearance_m
                )
                results.append(
                    SegmentPeriodResult(
                        segment_id=segment.segment_id,
                        period_id=period.period_id,
                        start_state=start,
                        end_state=current,
                        treatment_option_id=(
                            None if treatment_option is None else treatment_option.option_id
                        ),
                        monitoring_option_id=(
                            None if monitoring_option is None else monitoring_option.option_id
                        ),
                        treatment_cost=segment_treatment_cost,
                        monitoring_cost=segment_monitoring_cost,
                        service_attainment=attainment,
                        risk_probability=risk,
                        uncertainty=uncertainty,
                        height_margin_m=height_margin,
                        clearance_margin_m=clearance_margin,
                    )
                )
                service_constraint = self._constraints.get(("service", None, segment.segment_id))
                if not attainment:
                    target = hard if service_constraint is None or service_constraint.hard else soft
                    target.append(
                        EvaluationViolation(
                            code="EVALUATION-SERVICE",
                            message=(
                                f"{segment.segment_id} misses the service standard in "
                                f"{period.period_id}"
                            ),
                            kind="service",
                            period_id=period.period_id,
                            target_id=segment.segment_id,
                        )
                    )
        for period in periods:
            treatment_spent = sum(
                result.treatment_cost for result in results if result.period_id == period.period_id
            )
            monitoring_spent = sum(
                result.monitoring_cost for result in results if result.period_id == period.period_id
            )
            budget = self._constraints.get(("budget", period.period_id, period.period_id))
            if budget is not None and treatment_spent > budget.value + 1e-9:
                hard.append(
                    EvaluationViolation(
                        code="EVALUATION-BUDGET",
                        message=(
                            f"treatment cost {treatment_spent:.2f} exceeds budget "
                            f"{budget.value:.2f} in {period.period_id}"
                        ),
                        kind="budget",
                        period_id=period.period_id,
                        target_id=period.period_id,
                    )
                )
            monitoring_budget = self._constraints.get(
                ("monitoring_budget", period.period_id, period.period_id)
            )
            if monitoring_budget is not None and monitoring_spent > monitoring_budget.value + 1e-9:
                hard.append(
                    EvaluationViolation(
                        code="EVALUATION-MONITORING-BUDGET",
                        message=(
                            f"monitoring cost {monitoring_spent:.2f} exceeds budget "
                            f"{monitoring_budget.value:.2f} in {period.period_id}"
                        ),
                        kind="monitoring_budget",
                        period_id=period.period_id,
                        target_id=period.period_id,
                    )
                )
        for (period_id, method), area in method_areas.items():
            capacity = self._constraints.get(("capacity", period_id, method))
            if capacity is not None and area > capacity.value + 1e-9:
                hard.append(
                    EvaluationViolation(
                        code="EVALUATION-CAPACITY",
                        message=(
                            f"{method} area {area:.3f} ha exceeds capacity "
                            f"{capacity.value:.3f} ha in {period_id}"
                        ),
                        kind="capacity",
                        period_id=period_id,
                        target_id=method,
                    )
                )
        total_cost = treatment_cost + monitoring_cost
        discounted = 0.0
        for period in periods:
            period_treatment = sum(
                result.treatment_cost for result in results if result.period_id == period.period_id
            )
            period_monitoring = sum(
                result.monitoring_cost for result in results if result.period_id == period.period_id
            )
            factor = 1.0 / (1.0 + self.config.discount_rate) ** (period.start_year - base_year)
            discounted += (period_treatment + period_monitoring) * factor
        length = sum(segment.length_m for segment in self.formulation.segments)
        exposure = max(length * len(periods), 1e-9)
        risk = (
            sum(
                result.risk_probability * self._segment_length(result.segment_id)
                for result in results
            )
            / exposure
        )
        attainment_fraction = (
            sum(
                (1.0 if result.service_attainment else 0.0)
                * self._segment_length(result.segment_id)
                for result in results
            )
            / exposure
        )
        uncertainty = (
            sum(result.uncertainty * self._segment_length(result.segment_id) for result in results)
            / exposure
        )
        return EvaluationResult(
            formulation_id=self.formulation.formulation_id,
            assignment=assignment,
            objective_vector={
                "present_cost": discounted,
                "service_risk": risk,
                "service_attainment": attainment_fraction,
                "uncertainty": uncertainty,
            },
            feasible=not hard,
            violations=hard,
            soft_violations=soft,
            total_cost=total_cost,
            discounted_cost=discounted,
            treatment_cost=treatment_cost,
            monitoring_cost=monitoring_cost,
            period_results=results,
        )

    def _segment_length(self, segment_id: str) -> float:
        for segment in self.formulation.segments:
            if segment.segment_id == segment_id:
                return segment.length_m
        raise EvaluatorError(f"unknown segment {segment_id!r}")

    def _apply_treatment(
        self,
        context: SegmentContext,
        current: StateDistribution,
        period_id: str,
        duration: int,
        option: TreatmentOption,
        variable_index: int,
        hard: list[EvaluationViolation],
    ) -> tuple[StateDistribution, float]:
        try:
            request = TreatmentRequest(
                segment_id=context.segment_id,
                functional_group=context.functional_group,
                current=current,
                method=option.method,
                season=option.season,
                intensity=option.intensity,
                quantity_ha=self._area_ha(context),
                regrowth_years=max(0, duration - 1),
                environment=context.environment,
            )
            result = apply_treatment(request)
        except (TreatmentError, ValidationError) as exc:
            hard.append(
                EvaluationViolation(
                    code="EVALUATION-TREATMENT",
                    message=str(exc),
                    kind="treatment",
                    period_id=period_id,
                    target_id=context.segment_id,
                    variable_index=variable_index,
                )
            )
            return current, 0.0
        if result.status != "applied" or result.next is None:
            hard.append(
                EvaluationViolation(
                    code="EVALUATION-TREATMENT",
                    message=result.reason or "treatment transition was blocked",
                    kind="treatment",
                    period_id=period_id,
                    target_id=context.segment_id,
                    variable_index=variable_index,
                )
            )
            return current, 0.0
        cost = option.cost_per_ha * self._area_ha(context) + option.fixed_cost
        return result.next, cost

    def _grow(
        self,
        context: SegmentContext,
        current: StateDistribution,
        period_id: str,
        duration: int,
        variable_index: int | None,
        hard: list[EvaluationViolation],
    ) -> StateDistribution:
        if context.functional_group == "unknown":
            return current
        try:
            result = grow(
                GrowthRequest(
                    segment_id=context.segment_id,
                    functional_group=context.functional_group,
                    current=current,
                    years=duration,
                    environment=context.environment,
                )
            )
        except (GrowthError, ValidationError) as exc:
            hard.append(
                EvaluationViolation(
                    code="EVALUATION-GROWTH",
                    message=str(exc),
                    kind="growth",
                    period_id=period_id,
                    target_id=context.segment_id,
                    variable_index=variable_index,
                )
            )
            return current
        if result.status != "grown" or result.next is None:
            hard.append(
                EvaluationViolation(
                    code="EVALUATION-GROWTH",
                    message=result.reason or "growth was blocked",
                    kind="growth",
                    period_id=period_id,
                    target_id=context.segment_id,
                    variable_index=variable_index,
                )
            )
            return current
        return result.next

    @staticmethod
    def _monitor(current: StateDistribution, option: MonitoringOption) -> StateDistribution:
        factor = max(0.0, 1.0 - 0.5 * option.sampling_intensity)
        return current.model_copy(
            update={
                "height_sd": current.height_sd * factor,
                "cover_sd": current.cover_sd * factor,
                "density_sd": current.density_sd * factor,
                "confidence": min(1.0, 1.0 - (1.0 - current.confidence) * factor),
            }
        )

    @staticmethod
    def _risk(context: SegmentContext, state: StateDistribution) -> float:
        return max(
            _exceedance(state.height_m, state.height_sd, context.service_standard.max_height_m),
            _exceedance(
                state.height_m,
                state.height_sd,
                (
                    context.asset_height_m - context.service_standard.min_clearance_m
                    if context.asset_height_m is not None
                    else float("inf")
                ),
            ),
        )

    @staticmethod
    def _attainment(context: SegmentContext, state: StateDistribution) -> bool:
        if state.height_m > context.service_standard.max_height_m + 1e-9:
            return False
        if context.asset_height_m is not None:
            clearance = context.asset_height_m - state.height_m
            if clearance < context.service_standard.min_clearance_m - 1e-9:
                return False
        return True

    @staticmethod
    def _area_ha(context: SegmentContext) -> float:
        return context.area_ha


def _exceedance(mean: float, sd: float, threshold: float) -> float:
    if not math.isfinite(threshold):
        return 0.0
    if sd <= 0:
        return 1.0 if mean > threshold else 0.0
    return 0.5 * (1.0 - math.erf((threshold - mean) / (sd * math.sqrt(2.0))))


class IncrementalEvaluator:
    """Resident assignment with exact apply/undo and a declared full fallback.

    Parameters
    ----------
    evaluator : ScheduleEvaluator
        Exact evaluator.
    assignment : dict of int to int or None, optional
        Starting assignment. None uses the no-action assignment.
    """

    def __init__(
        self,
        evaluator: ScheduleEvaluator,
        assignment: dict[int, int] | None = None,
    ) -> None:
        self.evaluator = evaluator
        self._assignment = dict(
            evaluator.initial_assignment() if assignment is None else assignment
        )
        self._evaluation = evaluator.evaluate(self._assignment)
        self._mode = "exact"
        self._fallbacks = 0
        self._cache: dict[tuple[int, ...], EvaluationResult] = {
            self._key(self._assignment): self._evaluation
        }

    @staticmethod
    def _key(assignment: dict[int, int]) -> tuple[int, ...]:
        return tuple(assignment[index] for index in sorted(assignment))

    @property
    def assignment(self) -> dict[int, int]:
        """Return a copy of the current assignment.

        Returns
        -------
        dict of int to int
            Assignment copy.
        """
        return dict(self._assignment)

    @property
    def evaluation(self) -> EvaluationResult:
        """Return the current exact evaluation.

        Returns
        -------
        EvaluationResult
            Current evaluation.
        """
        return self._evaluation

    @property
    def mode(self) -> str:
        """Return the last evaluation mode.

        Returns
        -------
        str
            ``exact`` or ``full_fallback``.
        """
        return self._mode

    @property
    def fallbacks(self) -> int:
        """Return the full-recomputation count.

        Returns
        -------
        int
            Number of fallback evaluations.
        """
        return self._fallbacks

    def apply(self, change: AssignmentChange) -> EvaluationResult:
        """Apply one change and recompute exactly.

        Parameters
        ----------
        change : AssignmentChange
            Change to apply.

        Returns
        -------
        EvaluationResult
            New exact result.

        Raises
        ------
        EvaluatorError
            When the change does not match the resident assignment.
        """
        if self._assignment.get(change.variable) != change.before:
            raise EvaluatorError("change.before does not match the resident assignment")
        assignment = dict(self._assignment)
        assignment[change.variable] = change.after
        return self._commit(assignment, "full_fallback")

    def undo(self, change: AssignmentChange) -> EvaluationResult:
        """Undo one change and recompute exactly.

        Parameters
        ----------
        change : AssignmentChange
            Change to undo.

        Returns
        -------
        EvaluationResult
            Restored exact result.

        Raises
        ------
        EvaluatorError
            When the change does not match the resident assignment.
        """
        if self._assignment.get(change.variable) != change.after:
            raise EvaluatorError("change.after does not match the resident assignment")
        assignment = dict(self._assignment)
        assignment[change.variable] = change.before
        return self._commit(assignment, "full_fallback")

    def _commit(self, assignment: dict[int, int], mode: str) -> EvaluationResult:
        key = self._key(assignment)
        cached = self._cache.get(key)
        if cached is None:
            self._fallbacks += 1
            cached = self.evaluator.evaluate(assignment)
            self._cache[key] = cached
        self._assignment = assignment
        self._evaluation = cached
        self._mode = mode
        return cached


__all__ = [
    "EVALUATION_MODES",
    "EVALUATION_SCHEMA_VERSION",
    "AssignmentChange",
    "EvaluationConfig",
    "EvaluationResult",
    "EvaluationViolation",
    "EvaluatorError",
    "IncrementalEvaluator",
    "ScheduleEvaluator",
    "SegmentContext",
    "SegmentPeriodResult",
]
