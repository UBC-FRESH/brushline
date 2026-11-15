"""Stateful multi-period strategic optimization.

This is a linearized mixed-integer formulation. Risk is the decision state; each treatment
reduces risk immediately, and untreated risk grows between periods. The model is exact for
that linear state definition and is independently replayed after the solve.
"""

from __future__ import annotations

import math
from datetime import UTC, datetime
from typing import Any, Literal

import numpy as np
from pydantic import BaseModel, ConfigDict, Field, model_validator
from scipy.optimize import Bounds, LinearConstraint, milp  # type: ignore[import-untyped]  # scipy has no bundled stubs
from scipy.sparse import coo_matrix  # type: ignore[import-untyped]  # scipy has no bundled stubs

from brushline.model.state import TreatmentMethod

STATEFUL_SCHEMA_VERSION: Literal["brushline.stateful-strategic.v1"] = (
    "brushline.stateful-strategic.v1"
)


class StatefulError(ValueError):
    """Raised when a stateful strategic instance cannot be solved."""


class StatefulSegment(BaseModel):
    """One segment in the stateful problem."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    segment_id: str = Field(min_length=1)
    span_id: str = Field(min_length=1)
    length_m: float = Field(gt=0)
    area_ha: float = Field(gt=0)
    initial_risk: float = Field(ge=0, le=0.95)


class StatefulMethod(BaseModel):
    """One treatment method and its linear state effect."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    method: TreatmentMethod
    cost_per_ha: float = Field(ge=0)
    hours_per_ha: float = Field(ge=0)
    risk_reduction: float = Field(ge=0, le=0.95)


class StatefulPeriod(BaseModel):
    """One annual period and its constraints."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    year: int = Field(ge=1900, le=2200)
    budget: float = Field(ge=0)
    capacity_hours: float = Field(ge=0)


class StatefulConfig(BaseModel):
    """Objective and state-growth settings."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    risk_weight: float = Field(default=1.0, ge=0)
    cost_weight: float = Field(default=0.0, ge=0)
    growth_per_year: float = Field(default=0.03, ge=0, le=0.5)
    max_mean_risk: float | None = Field(default=None, ge=0, le=0.95)
    max_seconds: float = Field(default=60.0, gt=0)

    @model_validator(mode="after")
    def _weights(self) -> StatefulConfig:
        if self.risk_weight == 0 and self.cost_weight == 0:
            raise ValueError("at least one objective weight must be positive")
        return self


class StatefulAction(BaseModel):
    """One selected segment-period treatment."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    segment_id: str
    year: int
    method: TreatmentMethod
    cost: float = Field(ge=0)
    hours: float = Field(ge=0)
    risk_before: float = Field(ge=0, le=0.95)
    risk_after: float = Field(ge=0, le=0.95)


class StatefulYear(BaseModel):
    """One year's results."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    year: int
    cost: float = Field(ge=0)
    hours: float = Field(ge=0)
    risk: float = Field(ge=0, le=0.95)
    service: float = Field(ge=0, le=1)
    actions: int = Field(ge=0)


class StatefulPlan(BaseModel):
    """A solved and replayed stateful strategic plan."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["brushline.stateful-strategic.v1"] = STATEFUL_SCHEMA_VERSION
    instance_id: str
    status: Literal["optimal", "feasible", "infeasible"]
    solver_status: int
    solver_message: str
    solver: str
    objective: float
    total_cost: float = Field(ge=0)
    total_hours: float = Field(ge=0)
    mean_risk: float = Field(ge=0, le=0.95)
    mean_service: float = Field(ge=0, le=1)
    actions: list[StatefulAction]
    years: list[StatefulYear]
    replay_ok: bool
    search: dict[str, str | int | float | bool] = Field(default_factory=dict)
    created_utc: datetime


def _build_problem(
    segments: list[StatefulSegment],
    methods: list[StatefulMethod],
    periods: list[StatefulPeriod],
    config: StatefulConfig,
) -> tuple[
    np.ndarray,
    np.ndarray,
    Any,
    Any,
    np.ndarray,
    np.ndarray,
    list[tuple[int, int, int]],
]:  # scipy returns untyped sparse/Bounds objects
    """Assemble the linearized MILP arrays."""
    n_segments = len(segments)
    n_periods = len(periods)
    n_methods = len(methods)
    n_x = n_segments * n_periods * n_methods
    n_r = n_segments * n_periods
    n_variables = n_x + n_r
    x_index: list[tuple[int, int, int]] = [
        (segment, period, method)
        for segment in range(n_segments)
        for period in range(n_periods)
        for method in range(n_methods)
    ]

    def x_i(segment: int, period: int, method: int) -> int:
        return (segment * n_periods + period) * n_methods + method

    def r_i(segment: int, period: int) -> int:
        return n_x + segment * n_periods + period

    c = np.zeros(n_variables)
    total_length = sum(segment.length_m for segment in segments)
    for segment in range(n_segments):
        for period in range(n_periods):
            c[r_i(segment, period)] = (
                config.risk_weight * segments[segment].length_m / total_length / n_periods
            )
            for method in range(n_methods):
                c[x_i(segment, period, method)] = (
                    config.cost_weight
                    * segments[segment].area_ha
                    * methods[method].cost_per_ha
                    / 100000.0
                )
    lower = np.zeros(n_variables)
    upper = np.zeros(n_variables)
    integrality = np.zeros(n_variables)
    upper[n_x:] = 0.95
    upper[:n_x] = 1.0
    integrality[:n_x] = 1

    rows: list[int] = []
    cols: list[int] = []
    values: list[float] = []
    row_lower: list[float] = []
    row_upper: list[float] = []

    def add_row(entries: list[tuple[int, float]], low: float, high: float) -> None:
        row = len(row_lower)
        for column, value in entries:
            rows.append(row)
            cols.append(column)
            values.append(value)
        row_lower.append(low)
        row_upper.append(high)

    for segment in range(n_segments):
        for period in range(n_periods):
            entries = [(x_i(segment, period, method), 1.0) for method in range(n_methods)]
            add_row(entries, 0.0, 1.0)
            entries = [(r_i(segment, period), 1.0)]
            if period > 0:
                entries.append((r_i(segment, period - 1), -1.0))
            for method in range(n_methods):
                entries.append((x_i(segment, period, method), methods[method].risk_reduction))
            if period == 0:
                add_row(entries, segments[segment].initial_risk + config.growth_per_year, np.inf)
            else:
                add_row(entries, config.growth_per_year, np.inf)
    for period in range(n_periods):
        add_row(
            [
                (
                    x_i(segment, period, method),
                    segments[segment].area_ha * methods[method].cost_per_ha,
                )
                for segment in range(n_segments)
                for method in range(n_methods)
            ],
            0.0,
            periods[period].budget,
        )
        add_row(
            [
                (
                    x_i(segment, period, method),
                    segments[segment].area_ha * methods[method].hours_per_ha,
                )
                for segment in range(n_segments)
                for method in range(n_methods)
            ],
            0.0,
            periods[period].capacity_hours,
        )
        if config.max_mean_risk is not None:
            add_row(
                [
                    (r_i(segment, period), segments[segment].length_m / total_length)
                    for segment in range(n_segments)
                ],
                0.0,
                config.max_mean_risk,
            )
    matrix = coo_matrix((values, (rows, cols)), shape=(len(row_lower), n_variables)).tocsr()
    return (
        c,
        integrality,
        Bounds(lower, upper),
        matrix,
        np.asarray(row_lower),
        np.asarray(row_upper),
        x_index,
    )


def replay_stateful_choices(
    segments: list[StatefulSegment],
    methods: list[StatefulMethod],
    periods: list[StatefulPeriod],
    config: StatefulConfig,
    selected: dict[tuple[int, int, int], bool],
) -> tuple[list[StatefulAction], list[StatefulYear], float, float, float]:
    """Replay the solved choices with the same linear state equations."""
    risks = [segment.initial_risk for segment in segments]
    actions: list[StatefulAction] = []
    years: list[StatefulYear] = []
    total_cost = 0.0
    total_hours = 0.0
    annual_risks: list[float] = []
    for period_index, period in enumerate(periods):
        for segment_index in range(len(segments)):
            risks[segment_index] = min(0.95, risks[segment_index] + config.growth_per_year)
        cost = 0.0
        hours = 0.0
        for segment_index, segment in enumerate(segments):
            for method_index, method in enumerate(methods):
                if not selected.get((segment_index, period_index, method_index), False):
                    continue
                before = risks[segment_index]
                risks[segment_index] = max(0.0, before - method.risk_reduction)
                item_cost = segment.area_ha * method.cost_per_ha
                item_hours = segment.area_ha * method.hours_per_ha
                cost += item_cost
                hours += item_hours
                total_cost += item_cost
                total_hours += item_hours
                actions.append(
                    StatefulAction(
                        segment_id=segment.segment_id,
                        year=period.year,
                        method=method.method,
                        cost=round(item_cost, 2),
                        hours=round(item_hours, 2),
                        risk_before=round(before, 4),
                        risk_after=round(risks[segment_index], 4),
                    )
                )
        mean_risk = sum(
            risks[index] * segment.length_m for index, segment in enumerate(segments)
        ) / sum(segment.length_m for segment in segments)
        years.append(
            StatefulYear(
                year=period.year,
                cost=round(cost, 2),
                hours=round(hours, 2),
                risk=round(mean_risk, 4),
                service=round(1.0 - mean_risk, 4),
                actions=sum(
                    1 for key, value in selected.items() if key[1] == period_index and value
                ),
            )
        )
        annual_risks.append(mean_risk)
    mean_risk = sum(annual_risks) / len(annual_risks)
    return actions, years, total_cost, total_hours, mean_risk


def build_stateful_plan(
    *,
    instance_id: str,
    segments: list[StatefulSegment],
    methods: list[StatefulMethod],
    periods: list[StatefulPeriod],
    config: StatefulConfig | None = None,
    created_utc: datetime | None = None,
) -> StatefulPlan:
    """Solve the linearized stateful strategic MILP and replay the result.

    Parameters
    ----------
    instance_id : str
        Instance id.
    segments : list of StatefulSegment
        Segments and initial risk.
    methods : list of StatefulMethod
        Treatment methods.
    periods : list of StatefulPeriod
        Annual budgets and capacity.
    config : StatefulConfig, optional
        Objective weights and state growth.
    created_utc : datetime, optional
        Creation time.

    Returns
    -------
    StatefulPlan
        Selected actions, annual outcomes, and replay status.

    Raises
    ------
    StatefulError
        If the instance is empty, duplicate, or infeasible.
    """
    if not segments or not methods or not periods:
        raise StatefulError("segments, methods, and periods must be non-empty")
    if len({item.segment_id for item in segments}) != len(segments):
        raise StatefulError("segment ids must be unique")
    if len({item.year for item in periods}) != len(periods):
        raise StatefulError("period years must be unique")
    rules = config or StatefulConfig()
    c, integrality, bounds, matrix, row_lower, row_upper, x_index = _build_problem(
        segments, methods, periods, rules
    )
    result = milp(
        c,
        integrality=integrality,
        bounds=bounds,
        constraints=LinearConstraint(matrix, row_lower, row_upper),
        options={"time_limit": rules.max_seconds},
    )
    if result.x is None:
        raise StatefulError(f"stateful MILP infeasible: {result.message}")
    selected = {key: bool(result.x[index] > 0.5) for index, key in enumerate(x_index)}
    actions, years, total_cost, total_hours, mean_risk = replay_stateful_choices(
        segments, methods, periods, rules, selected
    )
    if rules.max_mean_risk is not None and mean_risk > rules.max_mean_risk + 1e-5:
        raise StatefulError("replayed plan exceeds the maximum mean risk")
    objective = rules.risk_weight * mean_risk + rules.cost_weight * total_cost / 100000.0
    replay_ok = math.isclose(objective, float(result.fun), rel_tol=2e-4, abs_tol=2e-4)
    return StatefulPlan(
        instance_id=instance_id,
        status="optimal" if result.success else "feasible",
        solver_status=int(result.status),
        solver_message=str(result.message),
        solver="scipy.optimize.milp/HiGHS",
        objective=round(objective, 4),
        total_cost=round(total_cost, 2),
        total_hours=round(total_hours, 2),
        mean_risk=round(mean_risk, 4),
        mean_service=round(1.0 - mean_risk, 4),
        actions=actions,
        years=years,
        replay_ok=replay_ok,
        created_utc=created_utc or datetime.now(UTC),
    )


__all__ = [
    "STATEFUL_SCHEMA_VERSION",
    "StatefulAction",
    "StatefulConfig",
    "StatefulError",
    "StatefulMethod",
    "StatefulPeriod",
    "StatefulPlan",
    "StatefulSegment",
    "StatefulYear",
    "build_stateful_plan",
    "replay_stateful_choices",
]
