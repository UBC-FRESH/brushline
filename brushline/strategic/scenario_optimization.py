"""Scenario-optimized versus fixed stateful plans.

The comparison re-solves the exact stateful MILP under sampled cost, productivity, and capacity
assumptions, then measures the fixed-plan regret. It is a value-of-adaptivity experiment, not a
stochastic dynamic program.
"""

from __future__ import annotations

import math
import random
from datetime import UTC, datetime
from typing import Literal

import numpy as np
from pydantic import BaseModel, ConfigDict, Field, model_validator

from brushline.strategic.stateful import (
    StatefulConfig,
    StatefulMethod,
    StatefulPeriod,
    StatefulPlan,
    StatefulSegment,
    build_stateful_plan,
)

SCENARIO_OPTIMIZATION_SCHEMA_VERSION: Literal["brushline.scenario-optimization.v1"] = (
    "brushline.scenario-optimization.v1"
)


class ScenarioOptimizationError(ValueError):
    """Raised when scenario inputs are inconsistent."""


class ScenarioOutcome(BaseModel):
    """Fixed versus adaptive outcomes in one scenario."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    index: int = Field(ge=0)
    cost_factor: float = Field(gt=0)
    hours_factor: float = Field(gt=0)
    capacity_factor: float = Field(gt=0)
    fixed_cost: float = Field(ge=0)
    fixed_hours: float = Field(ge=0)
    fixed_budget_exceeded: float = Field(ge=0)
    fixed_capacity_shortfall: float = Field(ge=0)
    fixed_risk: float = Field(ge=0, le=0.95)
    adaptive_cost: float = Field(ge=0)
    adaptive_hours: float = Field(ge=0)
    adaptive_risk: float = Field(ge=0, le=0.95)
    adaptive_status: Literal["optimal", "feasible", "infeasible"]
    fixed_objective: float
    adaptive_objective: float
    regret: float


class ScenarioBand(BaseModel):
    """P10/P50/P90 band for a scenario metric."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    p10: float
    p50: float
    p90: float
    mean: float


class ScenarioOptimizationResult(BaseModel):
    """Scenario-optimized planning summary."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["brushline.scenario-optimization.v1"] = (
        SCENARIO_OPTIMIZATION_SCHEMA_VERSION
    )
    instance_id: str
    scenarios: int = Field(ge=1)
    seed: int
    nominal_fixed_objective: float
    mean_fixed_objective: float
    mean_adaptive_objective: float
    mean_regret: float
    p90_regret: float
    probability_adaptation_improves: float = Field(ge=0, le=1)
    fixed_budget_violation_probability: float = Field(ge=0, le=1)
    fixed_capacity_violation_probability: float = Field(ge=0, le=1)
    fixed_cost_band: ScenarioBand
    adaptive_cost_band: ScenarioBand
    fixed_hours_band: ScenarioBand
    adaptive_hours_band: ScenarioBand
    fixed_risk_band: ScenarioBand
    adaptive_risk_band: ScenarioBand
    outcomes: list[ScenarioOutcome]
    created_utc: datetime

    @model_validator(mode="after")
    def _time(self) -> ScenarioOptimizationResult:
        if self.created_utc.tzinfo is None:
            raise ValueError("created_utc must be timezone-aware")
        return self


def _band(values: list[float]) -> ScenarioBand:
    array = np.asarray(values, dtype=float)
    return ScenarioBand(
        p10=round(float(np.percentile(array, 10)), 6),
        p50=round(float(np.percentile(array, 50)), 6),
        p90=round(float(np.percentile(array, 90)), 6),
        mean=round(float(array.mean()), 6),
    )


def _lognormal(rng: random.Random, sigma: float) -> float:
    return math.exp(rng.gauss(-0.5 * sigma**2, sigma))


def _fixed_outcome(
    fixed: StatefulPlan,
    periods: list[StatefulPeriod],
    *,
    cost_factor: float,
    hours_factor: float,
    capacity_factor: float,
    risk_weight: float,
    cost_weight: float,
    hours_weight: float,
) -> tuple[float, float, float, float, float]:
    cost_by_year = {period.year: 0.0 for period in periods}
    hours_by_year = {period.year: 0.0 for period in periods}
    for action in fixed.actions:
        cost_by_year[action.year] = cost_by_year.get(action.year, 0.0) + action.cost * cost_factor
        hours_by_year[action.year] = (
            hours_by_year.get(action.year, 0.0) + action.hours * hours_factor
        )
    budget_exceeded = sum(
        max(0.0, cost_by_year.get(period.year, 0.0) - period.budget) for period in periods
    )
    capacity_shortfall = sum(
        max(
            0.0,
            hours_by_year.get(period.year, 0.0) - period.capacity_hours * capacity_factor,
        )
        for period in periods
    )
    total_cost = sum(cost_by_year.values())
    total_hours = sum(hours_by_year.values())
    total_budget = sum(period.budget for period in periods)
    total_capacity = sum(period.capacity_hours for period in periods)
    penalty = budget_exceeded / max(total_budget, 1.0) + capacity_shortfall / max(
        total_capacity, 1.0
    )
    objective = (
        risk_weight * fixed.mean_risk
        + cost_weight * total_cost / 100000.0
        + hours_weight * total_hours / 100000.0
        + penalty
    )
    return total_cost, total_hours, budget_exceeded, capacity_shortfall, objective


def optimize_scenarios(
    *,
    instance_id: str,
    segments: list[StatefulSegment],
    methods: list[StatefulMethod],
    periods: list[StatefulPeriod],
    fixed: StatefulPlan,
    config: StatefulConfig | None = None,
    scenarios: int = 30,
    seed: int = 7,
    cost_sigma: float = 0.18,
    hours_sigma: float = 0.15,
    capacity_sigma: float = 0.15,
    max_seconds_per_solve: float = 60.0,
    created_utc: datetime | None = None,
) -> ScenarioOptimizationResult:
    """Re-solve the exact stateful plan under sampled scenarios.

    Parameters
    ----------
    instance_id : str
        Instance id.
    segments, methods, periods : list
        Nominal stateful problem.
    fixed : StatefulPlan
        Fixed plan being tested.
    config : StatefulConfig, optional
        Objective weights.
    scenarios : int, optional
        Number of sampled scenarios.
    seed : int, optional
        Deterministic sampler seed.
    cost_sigma, hours_sigma, capacity_sigma : float, optional
        Lognormal sigmas.
    max_seconds_per_solve : float, optional
        MILP limit per scenario.
    created_utc : datetime, optional
        Creation time.

    Returns
    -------
    ScenarioOptimizationResult
        Fixed and adaptive outcomes, bands, and regret.

    Raises
    ------
    ScenarioOptimizationError
        If inputs are empty or a scenario cannot be solved.
    """
    if not segments or not methods or not periods:
        raise ScenarioOptimizationError("segments, methods, and periods must be non-empty")
    if scenarios < 1:
        raise ScenarioOptimizationError("scenarios must be positive")
    rules = config or StatefulConfig()
    rng = random.Random(seed)
    outcomes: list[ScenarioOutcome] = []
    fixed_objectives = []
    adaptive_objectives = []
    regrets = []
    for index in range(scenarios):
        cost_factor = _lognormal(rng, cost_sigma)
        hours_factor = _lognormal(rng, hours_sigma)
        capacity_factor = _lognormal(rng, capacity_sigma)
        fixed_cost, fixed_hours, fixed_budget, fixed_capacity, fixed_objective = _fixed_outcome(
            fixed,
            periods,
            cost_factor=cost_factor,
            hours_factor=hours_factor,
            capacity_factor=capacity_factor,
            risk_weight=rules.risk_weight,
            cost_weight=rules.cost_weight,
            hours_weight=rules.hours_weight,
        )
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
            period.model_copy(update={"capacity_hours": period.capacity_hours * capacity_factor})
            for period in periods
        ]
        try:
            adaptive = build_stateful_plan(
                instance_id=f"{instance_id}-scenario-{index}",
                segments=segments,
                methods=scenario_methods,
                periods=scenario_periods,
                config=StatefulConfig(
                    risk_weight=rules.risk_weight,
                    cost_weight=rules.cost_weight,
                    hours_weight=rules.hours_weight,
                    growth_per_year=rules.growth_per_year,
                    max_seconds=max_seconds_per_solve,
                ),
                created_utc=created_utc,
            )
        except Exception as exc:  # pragma: no cover - defensive solver boundary
            raise ScenarioOptimizationError(f"scenario {index} failed: {exc}") from exc
        adaptive_cost = adaptive.total_cost
        adaptive_hours = adaptive.total_hours
        adaptive_objective = (
            rules.risk_weight * adaptive.mean_risk
            + rules.cost_weight * adaptive_cost / 100000.0
            + rules.hours_weight * adaptive_hours / 100000.0
        )
        regret = fixed_objective - adaptive_objective
        outcomes.append(
            ScenarioOutcome(
                index=index,
                cost_factor=round(cost_factor, 5),
                hours_factor=round(hours_factor, 5),
                capacity_factor=round(capacity_factor, 5),
                fixed_cost=round(fixed_cost, 2),
                fixed_hours=round(fixed_hours, 2),
                fixed_budget_exceeded=round(fixed_budget, 2),
                fixed_capacity_shortfall=round(fixed_capacity, 2),
                fixed_risk=fixed.mean_risk,
                adaptive_cost=round(adaptive_cost, 2),
                adaptive_hours=round(adaptive_hours, 2),
                adaptive_risk=adaptive.mean_risk,
                adaptive_status=adaptive.status,
                fixed_objective=round(fixed_objective, 6),
                adaptive_objective=round(adaptive_objective, 6),
                regret=round(regret, 6),
            )
        )
        fixed_objectives.append(fixed_objective)
        adaptive_objectives.append(adaptive_objective)
        regrets.append(regret)
    return ScenarioOptimizationResult(
        instance_id=instance_id,
        scenarios=scenarios,
        seed=seed,
        nominal_fixed_objective=round(
            rules.risk_weight * fixed.mean_risk
            + rules.cost_weight * fixed.total_cost / 100000.0
            + rules.hours_weight * fixed.total_hours / 100000.0,
            6,
        ),
        mean_fixed_objective=round(float(np.mean(fixed_objectives)), 6),
        mean_adaptive_objective=round(float(np.mean(adaptive_objectives)), 6),
        mean_regret=round(float(np.mean(regrets)), 6),
        p90_regret=round(float(np.percentile(regrets, 90)), 6),
        probability_adaptation_improves=sum(value > 1e-9 for value in regrets) / len(regrets),
        fixed_budget_violation_probability=sum(
            outcome.fixed_budget_exceeded > 0 for outcome in outcomes
        )
        / len(outcomes),
        fixed_capacity_violation_probability=sum(
            outcome.fixed_capacity_shortfall > 0 for outcome in outcomes
        )
        / len(outcomes),
        fixed_cost_band=_band([outcome.fixed_cost for outcome in outcomes]),
        adaptive_cost_band=_band([outcome.adaptive_cost for outcome in outcomes]),
        fixed_hours_band=_band([outcome.fixed_hours for outcome in outcomes]),
        adaptive_hours_band=_band([outcome.adaptive_hours for outcome in outcomes]),
        fixed_risk_band=_band([outcome.fixed_risk for outcome in outcomes]),
        adaptive_risk_band=_band([outcome.adaptive_risk for outcome in outcomes]),
        outcomes=outcomes,
        created_utc=created_utc or datetime.now(UTC),
    )


__all__ = [
    "SCENARIO_OPTIMIZATION_SCHEMA_VERSION",
    "ScenarioBand",
    "ScenarioOptimizationError",
    "ScenarioOptimizationResult",
    "ScenarioOutcome",
    "optimize_scenarios",
]
