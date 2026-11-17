"""Weather- and outage-aware annual recourse for the rolling policy.

The policy observes each year's cost, hours, and capacity before committing actions. The
forecast-aware case plans against an independent synthetic calendar and executes under the actual
calendar. The calendar-aware case observes the actual calendar and defers unschedulable actions
until every retained action fits it. These are calendar policies, not forecast products or
stochastic dynamic programs.
"""

from __future__ import annotations

import random
from collections import defaultdict
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
from brushline.strategic.two_stage import RecourseBand, _lognormal
from brushline.tactical.shifts import (
    ShiftConfig,
    ShiftCrew,
    ShiftMachine,
    ShiftPlan,
    ShiftWorkItem,
    build_shift_plan,
)

WEATHER_RECOURSE_SCHEMA_VERSION: Literal["brushline.weather-recourse.v1"] = (
    "brushline.weather-recourse.v1"
)


class WeatherRecourseError(ValueError):
    """Raised when weather-recourse inputs are inconsistent."""


class WeatherCalendarConfig(BaseModel):
    """Assumed per-year weather and outage calendar."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    window_days: int = Field(default=75, ge=1, le=366)
    outage_days: list[int] = Field(default_factory=lambda: [11, 12, 13, 14, 15])
    weather_probability: float = Field(default=0.20, ge=0, le=1)
    travel_hours: float = Field(default=0.5, ge=0)
    seed: int = 7

    @model_validator(mode="after")
    def _days(self) -> WeatherCalendarConfig:
        if any(day < 1 or day > self.window_days for day in self.outage_days):
            raise ValueError("outage days must fall inside the calendar window")
        return self


class WeatherCaseSummary(BaseModel):
    """Summary for calendar-naive or calendar-aware execution."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    name: Literal["calendar-naive", "forecast-aware", "calendar-aware"]
    budget_violation_probability: float = Field(ge=0, le=1)
    capacity_violation_probability: float = Field(ge=0, le=1)
    completion_band: RecourseBand
    retained_scope_band: RecourseBand
    risk_band: RecourseBand
    cost_band: RecourseBand
    hours_band: RecourseBand
    mean_deferred_actions: float = Field(ge=0)
    mean_resource_deferred_actions: float = Field(ge=0)
    mean_calendar_deferred_actions: float = Field(ge=0)
    mean_deferred_hours: float = Field(ge=0)
    mean_unscheduled_hours: float = Field(ge=0)
    mean_risk_loss: float = Field(ge=0)


class WeatherRecourseResult(BaseModel):
    """Calendar-naive, forecast-aware, and observed-calendar-aware comparison."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["brushline.weather-recourse.v1"] = WEATHER_RECOURSE_SCHEMA_VERSION
    instance_id: str
    episodes: int = Field(ge=1)
    seed: int
    years: list[int]
    solver: Literal["exact", "heuristic"]
    lookahead_years: int = Field(ge=1)
    calendar: WeatherCalendarConfig
    cases: list[WeatherCaseSummary]
    created_utc: datetime

    @model_validator(mode="after")
    def _time(self) -> WeatherRecourseResult:
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


def _fit_resources(
    *,
    actions: list[StatefulAction],
    cost_factor: float,
    hours_factor: float,
    capacity_factor: float,
    budget: float,
    capacity_hours: float,
) -> tuple[list[StatefulAction], set[str], float, float, int, float]:
    """Defer lowest first-year-risk-reduction-per-hour actions until budget/capacity fit."""
    cost = sum(action.cost * cost_factor for action in actions)
    hours = sum(action.hours * hours_factor for action in actions)
    ranked = sorted(
        actions,
        key=lambda action: (
            (action.risk_before - action.risk_after) / max(action.hours, 1e-9),
            action.segment_id,
        ),
    )
    deferred: set[str] = set()
    capacity = capacity_hours * capacity_factor
    while (cost > budget or hours > capacity) and ranked:
        action = ranked.pop(0)
        deferred.add(action.segment_id)
        cost -= action.cost * cost_factor
        hours -= action.hours * hours_factor
    kept = [action for action in actions if action.segment_id not in deferred]
    return (
        kept,
        deferred,
        max(0.0, cost),
        max(0.0, hours),
        len(deferred),
        sum(action.hours for action in actions if action.segment_id in deferred),
    )


def _schedule(
    *,
    actions: list[StatefulAction],
    year: int,
    blocked_days: list[int],
    crews: list[ShiftCrew],
    machines: list[ShiftMachine],
    calendar: WeatherCalendarConfig,
) -> tuple[ShiftPlan, dict[str, float]]:
    """Build a crew calendar and return executed hours by segment."""
    work_items = [
        ShiftWorkItem(
            work_order_id=f"wo-{action.segment_id}-{year}",
            unit_id=action.segment_id,
            method=action.method,
            year=year,
            hours=action.hours,
            travel_hours=calendar.travel_hours,
            priority=1,
        )
        for action in actions
    ]
    plan = build_shift_plan(
        plan_id=f"weather-{year}",
        instance_id="weather-recourse",
        work_items=work_items,
        crews=crews,
        machines=machines,
        config=_shift_config(calendar, year, blocked_days),
    )
    executed: dict[str, float] = defaultdict(float)
    for assignment in plan.assignments:
        segment_id = assignment.work_order_id.removeprefix("wo-").rsplit(f"-{year}", 1)[0]
        executed[segment_id] += assignment.productive_hours
    return plan, dict(executed)


def _shift_config(
    calendar: WeatherCalendarConfig, year: int, blocked_days: list[int]
) -> ShiftConfig:
    return ShiftConfig(
        max_days_per_year=calendar.window_days,
        include_travel=True,
        blocked_days={year: blocked_days},
    )


def _calendar_days(
    *,
    rng: random.Random,
    calendar: WeatherCalendarConfig,
) -> list[int]:
    blocked = set(calendar.outage_days)
    for day in range(1, calendar.window_days + 1):
        if rng.random() < calendar.weather_probability:
            blocked.add(day)
    return sorted(blocked)


def _simulate_case(
    *,
    name: Literal["calendar-naive", "forecast-aware", "calendar-aware"],
    plan: StatefulPlan,
    segments: list[StatefulSegment],
    methods: list[StatefulMethod],
    periods: list[StatefulPeriod],
    config: StatefulConfig,
    episodes: int,
    seed: int,
    solver: Literal["exact", "heuristic"],
    heuristic_iterations: int,
    lookahead_years: int,
    calendar: WeatherCalendarConfig,
    crews: list[ShiftCrew],
    machines: list[ShiftMachine],
) -> WeatherCaseSummary:
    factor_rng = random.Random(seed)
    calendar_rng = random.Random(seed + 10_000)
    forecast_rng = random.Random(seed + 20_000)
    calendars = [
        [_calendar_days(rng=calendar_rng, calendar=calendar) for _ in periods]
        for _ in range(episodes)
    ]
    forecast_calendars = [
        [_calendar_days(rng=forecast_rng, calendar=calendar) for _ in periods]
        for _ in range(episodes)
    ]
    actions_by_year: dict[int, list[StatefulAction]] = {period.year: [] for period in periods}
    for action in plan.actions:
        actions_by_year.setdefault(action.year, []).append(action)
    total_length = sum(segment.length_m for segment in segments)
    length_by_segment = {segment.segment_id: segment.length_m for segment in segments}
    initial = [segment.initial_risk for segment in segments]
    segment_index = {segment.segment_id: index for index, segment in enumerate(segments)}
    costs: list[float] = []
    hours: list[float] = []
    completion: list[float] = []
    retained: list[float] = []
    risks: list[float] = []
    deferred_counts: list[int] = []
    resource_deferred_counts: list[int] = []
    calendar_deferred_counts: list[int] = []
    deferred_hours_values: list[float] = []
    unscheduled_values: list[float] = []
    risk_losses: list[float] = []
    budget_violations = 0
    capacity_violations = 0
    for episode in range(episodes):
        factors = [
            (
                period.year,
                round(_lognormal(factor_rng, 0.18), 5),
                round(_lognormal(factor_rng, 0.15), 5),
                round(_lognormal(factor_rng, 0.15), 5),
            )
            for period in periods
        ]
        risk_state = list(initial)
        total_cost = 0.0
        total_hours = 0.0
        annual_risks: list[float] = []
        annual_completion: list[float] = []
        annual_retained: list[float] = []
        annual_deferred = 0
        annual_resource_deferred = 0
        annual_calendar_deferred = 0
        annual_deferred_hours = 0.0
        annual_unscheduled = 0.0
        annual_risk_loss = 0.0
        annual_budget_violation = False
        annual_capacity_violation = False
        for offset, period in enumerate(periods):
            year = period.year
            cost_factor, hours_factor, capacity_factor = factors[offset][1:]
            if offset == 0:
                actions = list(actions_by_year.get(year, []))
                solve_cost_factor = cost_factor
                solve_hours_factor = hours_factor
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
                if solver == "heuristic":
                    from brushline.strategic.heuristic import build_stateful_heuristic

                    solved = build_stateful_heuristic(
                        instance_id=f"{name}-{episode}-{year}",
                        segments=current_segments,
                        methods=scenario_methods,
                        periods=scenario_periods,
                        config=config,
                        iterations=heuristic_iterations,
                        seed=seed + episode * 10 + offset,
                    )
                else:
                    solved = build_stateful_plan(
                        instance_id=f"{name}-{episode}-{year}",
                        segments=current_segments,
                        methods=scenario_methods,
                        periods=scenario_periods,
                        config=config,
                    )
                actions = [action for action in solved.actions if action.year == year]
                solve_cost_factor = 1.0
                solve_hours_factor = 1.0
            planned_hours = sum(action.hours for action in actions)
            kept, _resource_deferred, _kept_cost, _kept_hours, n_deferred, d_hours = _fit_resources(
                actions=actions,
                cost_factor=solve_cost_factor,
                hours_factor=solve_hours_factor,
                capacity_factor=capacity_factor,
                budget=period.budget,
                capacity_hours=period.capacity_hours,
            )
            annual_deferred += n_deferred
            annual_resource_deferred += n_deferred
            annual_deferred_hours += d_hours
            calendar_deferred: set[str] = set()
            if name in {"forecast-aware", "calendar-aware"}:
                planning_days = (
                    forecast_calendars[episode][offset]
                    if name == "forecast-aware"
                    else calendars[episode][offset]
                )
                while True:
                    active = [
                        action for action in kept if action.segment_id not in calendar_deferred
                    ]
                    shift_plan, _ = _schedule(
                        actions=active,
                        year=year,
                        blocked_days=planning_days,
                        crews=crews,
                        machines=machines,
                        calendar=calendar,
                    )
                    unscheduled = {
                        violation.work_order_id
                        for violation in shift_plan.violations
                        if violation.work_order_id
                    }
                    if not unscheduled:
                        break
                    calendar_deferred.update(
                        work_order.removeprefix("wo-").rsplit(f"-{year}", 1)[0]
                        for work_order in unscheduled
                    )
                    if len(calendar_deferred) >= len(kept):
                        break
            active = [action for action in kept if action.segment_id not in calendar_deferred]
            shift_plan, executed = _schedule(
                actions=active,
                year=year,
                blocked_days=calendars[episode][offset],
                crews=crews,
                machines=machines,
                calendar=calendar,
            )
            executed_fraction = {
                action.segment_id: min(
                    1.0, executed.get(action.segment_id, 0.0) / max(action.hours, 1e-9)
                )
                for action in kept
            }
            annual_deferred += len(calendar_deferred)
            annual_calendar_deferred += len(calendar_deferred)
            annual_deferred_hours += sum(
                action.hours for action in kept if action.segment_id in calendar_deferred
            )
            planned_executed = sum(
                action.hours * executed_fraction.get(action.segment_id, 0.0)
                for action in kept
                if action.segment_id not in calendar_deferred
            )
            annual_completion.append(planned_executed / planned_hours if planned_hours else 1.0)
            retained_hours = sum(
                action.hours for action in kept if action.segment_id not in calendar_deferred
            )
            annual_retained.append(retained_hours / planned_hours if planned_hours else 1.0)
            active_hours_total = sum(action.hours for action in active)
            annual_unscheduled += max(0.0, active_hours_total - planned_executed)
            risk_state = [min(0.95, risk + config.growth_per_year) for risk in risk_state]
            for action in kept:
                if action.segment_id in calendar_deferred:
                    continue
                idx = segment_index.get(action.segment_id)
                if idx is None:
                    continue
                fraction = executed_fraction.get(action.segment_id, 0.0)
                reduction = (action.risk_before - action.risk_after) * fraction
                risk_state[idx] = max(0.0, risk_state[idx] - reduction)
            annual_risks.append(
                sum(risk_state[i] * segments[i].length_m for i in range(len(segments)))
                / total_length
            )
            risk_loss = (
                sum(
                    (action.risk_before - action.risk_after)
                    * (1.0 - executed_fraction.get(action.segment_id, 0.0))
                    * length_by_segment.get(action.segment_id, 0.0)
                    for action in actions
                )
                / total_length
            )
            annual_risk_loss += risk_loss
            active_cost = sum(
                action.cost * (cost_factor if offset == 0 else 1.0) for action in active
            )
            active_hours = sum(
                action.hours * (hours_factor if offset == 0 else 1.0) for action in active
            )
            total_cost += active_cost
            total_hours += active_hours
            annual_budget_violation = annual_budget_violation or active_cost > period.budget
            annual_capacity_violation = (
                annual_capacity_violation or active_hours > period.capacity_hours * capacity_factor
            )
        costs.append(total_cost)
        hours.append(total_hours)
        completion.append(float(np.mean(annual_completion)))
        retained.append(float(np.mean(annual_retained)))
        risks.append(float(np.mean(annual_risks)))
        deferred_counts.append(annual_deferred)
        resource_deferred_counts.append(annual_resource_deferred)
        calendar_deferred_counts.append(annual_calendar_deferred)
        deferred_hours_values.append(annual_deferred_hours)
        unscheduled_values.append(annual_unscheduled)
        risk_losses.append(annual_risk_loss)
        budget_violations += annual_budget_violation
        capacity_violations += annual_capacity_violation
    return WeatherCaseSummary(
        name=name,
        budget_violation_probability=budget_violations / episodes,
        capacity_violation_probability=capacity_violations / episodes,
        completion_band=_band(completion),
        retained_scope_band=_band(retained),
        risk_band=_band(risks),
        cost_band=_band(costs, 2),
        hours_band=_band(hours, 2),
        mean_deferred_actions=round(float(np.mean(deferred_counts)), 3),
        mean_resource_deferred_actions=round(float(np.mean(resource_deferred_counts)), 3),
        mean_calendar_deferred_actions=round(float(np.mean(calendar_deferred_counts)), 3),
        mean_deferred_hours=round(float(np.mean(deferred_hours_values)), 2),
        mean_unscheduled_hours=round(float(np.mean(unscheduled_values)), 2),
        mean_risk_loss=round(float(np.mean(risk_losses)), 6),
    )


def evaluate_weather_recourse(
    *,
    instance_id: str,
    plan: StatefulPlan,
    segments: list[StatefulSegment],
    methods: list[StatefulMethod],
    periods: list[StatefulPeriod],
    crews: list[ShiftCrew],
    machines: list[ShiftMachine],
    config: StatefulConfig | None = None,
    episodes: int = 20,
    seed: int = 7,
    solver: Literal["exact", "heuristic"] = "exact",
    heuristic_iterations: int = 100,
    lookahead_years: int = 2,
    calendar: WeatherCalendarConfig | None = None,
    created_utc: datetime | None = None,
) -> WeatherRecourseResult:
    """Compare calendar-naive, forecast-aware, and calendar-aware annual recourse."""
    if not plan.actions or not segments or not periods:
        raise WeatherRecourseError("plan, segments, and periods must be non-empty")
    if not crews or not machines:
        raise WeatherRecourseError("crews and machines must be non-empty")
    if episodes < 1:
        raise WeatherRecourseError("episodes must be positive")
    rules = config or StatefulConfig(risk_weight=1.0, max_seconds=30)
    calendar_rules = calendar or WeatherCalendarConfig(seed=seed)
    naive = _simulate_case(
        name="calendar-naive",
        plan=plan,
        segments=segments,
        methods=methods,
        periods=periods,
        config=rules,
        episodes=episodes,
        seed=seed,
        solver=solver,
        heuristic_iterations=heuristic_iterations,
        lookahead_years=lookahead_years,
        calendar=calendar_rules,
        crews=crews,
        machines=machines,
    )
    forecast = _simulate_case(
        name="forecast-aware",
        plan=plan,
        segments=segments,
        methods=methods,
        periods=periods,
        config=rules,
        episodes=episodes,
        seed=seed,
        solver=solver,
        heuristic_iterations=heuristic_iterations,
        lookahead_years=lookahead_years,
        calendar=calendar_rules,
        crews=crews,
        machines=machines,
    )
    aware = _simulate_case(
        name="calendar-aware",
        plan=plan,
        segments=segments,
        methods=methods,
        periods=periods,
        config=rules,
        episodes=episodes,
        seed=seed,
        solver=solver,
        heuristic_iterations=heuristic_iterations,
        lookahead_years=lookahead_years,
        calendar=calendar_rules,
        crews=crews,
        machines=machines,
    )
    return WeatherRecourseResult(
        instance_id=instance_id,
        episodes=episodes,
        seed=seed,
        years=[period.year for period in periods],
        solver=solver,
        lookahead_years=lookahead_years,
        calendar=calendar_rules,
        cases=[naive, forecast, aware],
        created_utc=created_utc or datetime.now(UTC),
    )


__all__ = [
    "WEATHER_RECOURSE_SCHEMA_VERSION",
    "WeatherCalendarConfig",
    "WeatherCaseSummary",
    "WeatherRecourseError",
    "WeatherRecourseResult",
    "evaluate_weather_recourse",
]
