"""Rolling policy with annual operational recourse.

The first year comes from a fixed nominal plan. Later years are re-solved with the rolling
persistence forecast. In the recourse case, each year's first-year actions are deferred by lowest
first-year risk reduction per hour when observed budget or capacity is exceeded.
"""

from __future__ import annotations

import random
from datetime import UTC, datetime
from typing import Literal

import numpy as np
from pydantic import BaseModel, ConfigDict, Field, model_validator

from brushline.strategic.stateful import (
    StatefulAction,
    StatefulConfig,
    StatefulMethod,
    StatefulPeriod,
    StatefulPlan,
    StatefulSegment,
    build_stateful_plan,
)
from brushline.strategic.two_stage import (
    RecourseBand,
    _defer_to_fit,
    _lognormal,
    evaluate_two_stage_multi,
)

ROLLING_RECOURSE_SCHEMA_VERSION: Literal["brushline.rolling-recourse.v1"] = (
    "brushline.rolling-recourse.v1"
)


class RollingRecourseError(ValueError):
    """Raised when rolling-recourse inputs are inconsistent."""


class RollingCaseSummary(BaseModel):
    """Summary for one policy case."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str
    budget_violation_probability: float = Field(ge=0, le=1)
    capacity_violation_probability: float = Field(ge=0, le=1)
    cost_band: RecourseBand
    hours_band: RecourseBand
    risk_band: RecourseBand
    completion_band: RecourseBand
    mean_deferred_actions: float = Field(ge=0)
    mean_deferred_hours: float = Field(ge=0)
    mean_risk_loss: float = Field(ge=0)


class RollingRecourseResult(BaseModel):
    """Four-policy rolling-recourse comparison."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["brushline.rolling-recourse.v1"] = ROLLING_RECOURSE_SCHEMA_VERSION
    instance_id: str
    episodes: int = Field(ge=1)
    seed: int
    years: list[int]
    lookahead_years: int = Field(ge=1)
    cases: list[RollingCaseSummary]
    created_utc: datetime

    @model_validator(mode="after")
    def _time(self) -> RollingRecourseResult:
        if self.created_utc.tzinfo is None:
            raise ValueError("created_utc must be timezone-aware")
        return self


def _band(values: list[float], digits: int = 6) -> RecourseBand:
    array = np.asarray(values, dtype=float)
    return RecourseBand(
        p10=round(float(np.percentile(array, 10)), digits),
        p50=round(float(np.percentile(array, 50)), digits),
        p90=round(float(np.percentile(array, 90)), digits),
        mean=round(float(array.mean()), digits),
    )


def _simulate_rolling_case(
    *,
    case_name: str,
    plan: StatefulPlan,
    segments: list[StatefulSegment],
    methods: list[StatefulMethod],
    periods: list[StatefulPeriod],
    config: StatefulConfig,
    episodes: int,
    seed: int,
    lookahead_years: int,
    defer: bool,
) -> RollingCaseSummary:
    rng = random.Random(seed)
    lengths = [segment.length_m for segment in segments]
    total_length = sum(lengths)
    segment_index = {segment.segment_id: index for index, segment in enumerate(segments)}
    actions_by_year: dict[int, list[StatefulAction]] = {period.year: [] for period in periods}
    for action in plan.actions:
        actions_by_year.setdefault(action.year, []).append(action)
    risks = [segment.initial_risk for segment in segments]
    costs: list[float] = []
    hours: list[float] = []
    risk_values: list[float] = []
    completions: list[float] = []
    budget_violations = 0
    capacity_violations = 0
    deferred_counts: list[int] = []
    deferred_hours_values: list[float] = []
    risk_losses: list[float] = []
    for _episode in range(episodes):
        # Generate the same factor stream as the fixed-future comparison.
        factors = [
            (
                period.year,
                round(_lognormal(rng, 0.18), 5),
                round(_lognormal(rng, 0.15), 5),
                round(_lognormal(rng, 0.15), 5),
            )
            for period in periods
        ]
        risk_state = list(risks)
        total_cost = 0.0
        total_hours = 0.0
        annual_risks: list[float] = []
        annual_completions: list[float] = []
        annual_budget_violation = False
        annual_capacity_violation = False
        annual_deferred = 0
        annual_deferred_hours = 0.0
        annual_risk_loss = 0.0
        for offset, period in enumerate(periods):
            factor = factors[offset]
            cost_factor, hours_factor, capacity_factor = factor[1], factor[2], factor[3]
            if offset == 0:
                actions = list(actions_by_year.get(period.year, []))
                planned_hours = sum(action.hours for action in actions)
            else:
                current_segments = [
                    segment.model_copy(update={"initial_risk": risk_state[index]})
                    for index, segment in enumerate(segments)
                ]
                scenario_methods = [
                    method.model_copy(
                        update={
                            "cost_per_ha": method.cost_per_ha * cost_factor,
                            "hours_per_ha": method.hours_per_ha * hours_factor,
                        }
                    )
                    for method in methods
                ]
                scenario_periods = [
                    item.model_copy(
                        update={"capacity_hours": item.capacity_hours * capacity_factor}
                    )
                    for item in periods[offset : offset + lookahead_years]
                ]
                solved = build_stateful_plan(
                    instance_id=f"{case_name}-{_episode}-{period.year}",
                    segments=current_segments,
                    methods=scenario_methods,
                    periods=scenario_periods,
                    config=config,
                )
                actions = [action for action in solved.actions if action.year == period.year]
                planned_hours = sum(action.hours for action in actions)
            if defer:
                (
                    cost,
                    hours_used,
                    budget_exceeded,
                    capacity_shortfall,
                    deferred_actions,
                    deferred_hours,
                    risk_loss,
                ) = _defer_to_fit(
                    actions=actions,
                    cost_factor=cost_factor if offset == 0 else 1.0,
                    hours_factor=hours_factor if offset == 0 else 1.0,
                    capacity_factor=capacity_factor,
                    budget=period.budget,
                    capacity_hours=period.capacity_hours,
                    length_by_segment={
                        segment.segment_id: segment.length_m for segment in segments
                    },
                    total_length=total_length,
                )
            else:
                cost = sum(
                    action.cost * (cost_factor if offset == 0 else 1.0) for action in actions
                )
                hours_used = sum(
                    action.hours * (hours_factor if offset == 0 else 1.0) for action in actions
                )
                budget_exceeded = max(0.0, cost - period.budget)
                capacity_shortfall = max(0.0, hours_used - period.capacity_hours * capacity_factor)
                deferred_actions = 0
                deferred_hours = 0.0
                risk_loss = 0.0
            grown = [min(0.95, risk + config.growth_per_year) for risk in risk_state]
            # Reconstruct the deferred set explicitly from action risk/hours order.
            ranked = sorted(
                actions,
                key=lambda action: (
                    (action.risk_before - action.risk_after) / max(action.hours, 1e-9),
                    action.segment_id,
                ),
            )
            deferred_set: set[str] = set()
            if defer:
                remaining_cost = sum(action.cost * cost_factor for action in actions)
                remaining_hours = sum(action.hours * hours_factor for action in actions)
                for action in ranked:
                    if (
                        remaining_cost <= period.budget
                        and remaining_hours <= period.capacity_hours * capacity_factor
                    ):
                        break
                    deferred_set.add(action.segment_id)
                    remaining_cost -= action.cost * cost_factor
                    remaining_hours -= action.hours * hours_factor
            for risk_index in range(len(segments)):
                risk_state[risk_index] = grown[risk_index]
            for action in actions:
                if action.segment_id in deferred_set:
                    continue
                action_index = segment_index.get(action.segment_id)
                if action_index is None:
                    continue
                reduction = action.risk_before - action.risk_after
                risk_state[action_index] = max(0.0, risk_state[action_index] - reduction)
            annual_risk = (
                sum(risk_state[index] * segment.length_m for index, segment in enumerate(segments))
                / total_length
            )
            annual_risks.append(annual_risk)
            annual_completions.append(
                1.0 - deferred_hours / planned_hours if planned_hours else 1.0
            )
            annual_budget_violation = annual_budget_violation or budget_exceeded > 0
            annual_capacity_violation = annual_capacity_violation or capacity_shortfall > 0
            annual_deferred += deferred_actions
            annual_deferred_hours += deferred_hours
            annual_risk_loss += risk_loss
            total_cost += cost
            total_hours += hours_used
        costs.append(total_cost)
        hours.append(total_hours)
        risk_values.append(float(np.mean(annual_risks)))
        completions.append(float(np.mean(annual_completions)))
        budget_violations += annual_budget_violation
        capacity_violations += annual_capacity_violation
        deferred_counts.append(annual_deferred)
        deferred_hours_values.append(annual_deferred_hours)
        risk_losses.append(annual_risk_loss)
    return RollingCaseSummary(
        name=case_name,
        budget_violation_probability=budget_violations / episodes,
        capacity_violation_probability=capacity_violations / episodes,
        cost_band=_band(costs, 2),
        hours_band=_band(hours, 2),
        risk_band=_band(risk_values),
        completion_band=_band(completions),
        mean_deferred_actions=round(float(np.mean(deferred_counts)), 3),
        mean_deferred_hours=round(float(np.mean(deferred_hours_values)), 2),
        mean_risk_loss=round(float(np.mean(risk_losses)), 6),
    )


def evaluate_rolling_recourse(
    *,
    instance_id: str,
    plan: StatefulPlan,
    segments: list[StatefulSegment],
    methods: list[StatefulMethod],
    periods: list[StatefulPeriod],
    config: StatefulConfig | None = None,
    episodes: int = 20,
    seed: int = 7,
    lookahead_years: int = 2,
    created_utc: datetime | None = None,
) -> RollingRecourseResult:
    """Compare static, fixed-future recourse, rolling-only, and rolling recourse."""
    if not plan.actions or not segments or not periods:
        raise RollingRecourseError("plan, segments, and periods must be non-empty")
    if episodes < 1:
        raise RollingRecourseError("episodes must be positive")
    rules = config or StatefulConfig(risk_weight=1.0, max_seconds=30)
    fixed = evaluate_two_stage_multi(
        instance_id=instance_id,
        plan=plan,
        segments=segments,
        periods=periods,
        episodes=episodes,
        seed=seed,
        created_utc=created_utc,
    )
    rolling_only = _simulate_rolling_case(
        case_name="rolling-only",
        plan=plan,
        segments=segments,
        methods=methods,
        periods=periods,
        config=rules,
        episodes=episodes,
        seed=seed,
        lookahead_years=lookahead_years,
        defer=False,
    )
    rolling_recourse = _simulate_rolling_case(
        case_name="rolling-recourse",
        plan=plan,
        segments=segments,
        methods=methods,
        periods=periods,
        config=rules,
        episodes=episodes,
        seed=seed,
        lookahead_years=lookahead_years,
        defer=True,
    )
    static_case = RollingCaseSummary(
        name="static-fixed",
        budget_violation_probability=fixed.static_budget_violation_probability,
        capacity_violation_probability=fixed.static_capacity_violation_probability,
        cost_band=fixed.static_cost_band,
        hours_band=fixed.static_hours_band,
        risk_band=fixed.static_risk_band,
        completion_band=fixed.static_completion_band,
        mean_deferred_actions=0.0,
        mean_deferred_hours=0.0,
        mean_risk_loss=0.0,
    )
    fixed_case = RollingCaseSummary(
        name="fixed-future-recourse",
        budget_violation_probability=fixed.recourse_budget_violation_probability,
        capacity_violation_probability=fixed.recourse_capacity_violation_probability,
        cost_band=fixed.recourse_cost_band,
        hours_band=fixed.recourse_hours_band,
        risk_band=fixed.recourse_risk_band,
        completion_band=fixed.recourse_completion_band,
        mean_deferred_actions=fixed.mean_deferred_actions,
        mean_deferred_hours=fixed.mean_deferred_hours,
        mean_risk_loss=fixed.mean_risk_loss,
    )
    return RollingRecourseResult(
        instance_id=instance_id,
        episodes=episodes,
        seed=seed,
        years=[period.year for period in periods],
        lookahead_years=lookahead_years,
        cases=[static_case, fixed_case, rolling_only, rolling_recourse],
        created_utc=created_utc or datetime.now(UTC),
    )


__all__ = [
    "ROLLING_RECOURSE_SCHEMA_VERSION",
    "RollingCaseSummary",
    "RollingRecourseError",
    "RollingRecourseResult",
    "evaluate_rolling_recourse",
]
