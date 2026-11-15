"""Rolling-horizon policy simulation for the stateful network plan.

The policy observes the current year's cost, productivity, and capacity factors, assumes those
conditions persist over the remaining horizon, re-solves the stateful MILP, and commits only the
current year's actions. Annual factors are independent across years. This is an executable
persistence-forecast heuristic, not a stochastic dynamic program or a hindsight optimum.
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

ROLLING_POLICY_SCHEMA_VERSION: Literal["brushline.rolling-policy.v1"] = (
    "brushline.rolling-policy.v1"
)


class RollingPolicyError(ValueError):
    """Raised when a rolling-policy simulation cannot proceed."""


class AnnualFactors(BaseModel):
    """One year's observed conditions."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    year: int
    cost_factor: float = Field(gt=0)
    hours_factor: float = Field(gt=0)
    capacity_factor: float = Field(gt=0)


class RollingYear(BaseModel):
    """One committed year in a rolling-policy episode."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    year: int
    actions: int = Field(ge=0)
    cost: float = Field(ge=0)
    hours: float = Field(ge=0)
    risk: float = Field(ge=0, le=0.95)
    budget_exceeded: float = Field(ge=0)
    capacity_shortfall: float = Field(ge=0)
    status: Literal["optimal", "feasible", "infeasible"]


class RollingEpisode(BaseModel):
    """Fixed versus rolling-policy outcomes for one annual-factor episode."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    index: int = Field(ge=0)
    factors: list[AnnualFactors]
    fixed_cost: float = Field(ge=0)
    fixed_hours: float = Field(ge=0)
    fixed_risk: float = Field(ge=0, le=0.95)
    fixed_budget_exceeded: float = Field(ge=0)
    fixed_capacity_shortfall: float = Field(ge=0)
    fixed_objective: float
    rolling_cost: float = Field(ge=0)
    rolling_hours: float = Field(ge=0)
    rolling_risk: float = Field(ge=0, le=0.95)
    rolling_budget_exceeded: float = Field(ge=0)
    rolling_capacity_shortfall: float = Field(ge=0)
    rolling_objective: float
    regret: float
    years: list[RollingYear]


class RollingBand(BaseModel):
    """P10/P50/P90 band for a rolling-policy metric."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    p10: float
    p50: float
    p90: float
    mean: float


class RollingPolicyResult(BaseModel):
    """Summary of a rolling-horizon policy experiment."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["brushline.rolling-policy.v1"] = ROLLING_POLICY_SCHEMA_VERSION
    instance_id: str
    policy: Literal["persistence-forecast-v1"] = "persistence-forecast-v1"
    lookahead_years: int = Field(ge=1)
    episodes: int = Field(ge=1)
    seed: int
    total_budget: float = Field(ge=0)
    total_capacity_hours: float = Field(ge=0)
    mean_fixed_objective: float
    mean_rolling_objective: float
    mean_regret: float
    p90_regret: float
    probability_rolling_improves: float = Field(ge=0, le=1)
    fixed_budget_violation_probability: float = Field(ge=0, le=1)
    rolling_budget_violation_probability: float = Field(ge=0, le=1)
    fixed_capacity_violation_probability: float = Field(ge=0, le=1)
    rolling_capacity_violation_probability: float = Field(ge=0, le=1)
    fixed_cost_band: RollingBand
    rolling_cost_band: RollingBand
    fixed_hours_band: RollingBand
    rolling_hours_band: RollingBand
    fixed_risk_band: RollingBand
    rolling_risk_band: RollingBand
    episodes_detail: list[RollingEpisode]
    created_utc: datetime

    @model_validator(mode="after")
    def _time(self) -> RollingPolicyResult:
        if self.created_utc.tzinfo is None:
            raise ValueError("created_utc must be timezone-aware")
        return self


def _band(values: list[float]) -> RollingBand:
    array = np.asarray(values, dtype=float)
    return RollingBand(
        p10=round(float(np.percentile(array, 10)), 6),
        p50=round(float(np.percentile(array, 50)), 6),
        p90=round(float(np.percentile(array, 90)), 6),
        mean=round(float(array.mean()), 6),
    )


def _lognormal(rng: random.Random, sigma: float) -> float:
    return math.exp(rng.gauss(-0.5 * sigma**2, sigma))


def _annual_factors(
    *,
    rng: random.Random,
    years: list[int],
    cost_sigma: float,
    hours_sigma: float,
    capacity_sigma: float,
) -> list[AnnualFactors]:
    return [
        AnnualFactors(
            year=year,
            cost_factor=round(_lognormal(rng, cost_sigma), 5),
            hours_factor=round(_lognormal(rng, hours_sigma), 5),
            capacity_factor=round(_lognormal(rng, capacity_sigma), 5),
        )
        for year in years
    ]


def _objective(
    *,
    risk: float,
    cost: float,
    hours: float,
    budget_exceeded: float,
    capacity_shortfall: float,
    total_budget: float,
    total_capacity: float,
    config: StatefulConfig,
) -> float:
    penalty = budget_exceeded / max(total_budget, 1.0) + capacity_shortfall / max(
        total_capacity, 1.0
    )
    return (
        config.risk_weight * risk
        + config.cost_weight * cost / 100000.0
        + config.hours_weight * hours / 100000.0
        + penalty
    )


def _fixed_outcome(
    *,
    fixed: StatefulPlan,
    periods: list[StatefulPeriod],
    factors: list[AnnualFactors],
) -> tuple[float, float, float, float, float]:
    costs: dict[int, float] = {period.year: 0.0 for period in periods}
    hours: dict[int, float] = {period.year: 0.0 for period in periods}
    for action in fixed.actions:
        factor = next(
            (item for item in factors if item.year == action.year),
            AnnualFactors(
                year=action.year,
                cost_factor=1.0,
                hours_factor=1.0,
                capacity_factor=1.0,
            ),
        )
        costs[action.year] = costs.get(action.year, 0.0) + action.cost * factor.cost_factor
        hours[action.year] = hours.get(action.year, 0.0) + action.hours * factor.hours_factor
    budget_exceeded = 0.0
    capacity_shortfall = 0.0
    for period in periods:
        factor = next(item for item in factors if item.year == period.year)
        budget_exceeded += max(0.0, costs.get(period.year, 0.0) - period.budget)
        capacity_shortfall += max(
            0.0,
            hours.get(period.year, 0.0) - period.capacity_hours * factor.capacity_factor,
        )
    total_cost = sum(costs.values())
    total_hours = sum(hours.values())
    annual_risk = {row.year: row.risk for row in fixed.years}
    risk_values = [annual_risk[period.year] for period in periods if period.year in annual_risk]
    fixed_risk = sum(risk_values) / len(risk_values) if risk_values else fixed.mean_risk
    return total_cost, total_hours, fixed_risk, budget_exceeded, capacity_shortfall


def simulate_rolling_policy(
    *,
    instance_id: str,
    segments: list[StatefulSegment],
    methods: list[StatefulMethod],
    periods: list[StatefulPeriod],
    fixed: StatefulPlan,
    config: StatefulConfig | None = None,
    episodes: int = 30,
    lookahead_years: int | None = None,
    seed: int = 7,
    cost_sigma: float = 0.18,
    hours_sigma: float = 0.15,
    capacity_sigma: float = 0.15,
    max_seconds_per_solve: float = 30.0,
    created_utc: datetime | None = None,
) -> RollingPolicyResult:
    """Simulate a persistence-forecast rolling-horizon policy.

    At each year the policy sees that year's multiplicative factors, assumes they persist
    over the remaining horizon, re-solves the stateful MILP, and commits only that year's
    actions. It does not observe future annual factors.

    Parameters
    ----------
    instance_id : str
        Instance id.
    segments, methods, periods : list
        Nominal stateful problem.
    fixed : StatefulPlan
        Fixed nominal plan used as the comparison policy.
    config : StatefulConfig, optional
        Objective weights and growth.
    episodes : int, optional
        Number of simulated annual-factor episodes.
    lookahead_years : int, optional
        Number of years in each re-solve. The current year is always committed; the default
        solves the remaining horizon. A shorter window is faster and more myopic.
    seed : int, optional
        Deterministic sampler seed.
    cost_sigma, hours_sigma, capacity_sigma : float, optional
        Lognormal sigmas.
    max_seconds_per_solve : float, optional
        MILP limit per annual re-solve.
    created_utc : datetime, optional
        Creation time.

    Returns
    -------
    RollingPolicyResult
        Fixed and rolling outcomes, bands, and regret.

    Raises
    ------
    RollingPolicyError
        If inputs are empty, an episode fails to solve, or an annual solve is infeasible.
    """
    if not segments or not methods or not periods:
        raise RollingPolicyError("segments, methods, and periods must be non-empty")
    if episodes < 1:
        raise RollingPolicyError("episodes must be positive")
    window = len(periods) if lookahead_years is None else lookahead_years
    if window < 1:
        raise RollingPolicyError("lookahead_years must be positive")
    if len({period.year for period in periods}) != len(periods):
        raise RollingPolicyError("period years must be unique")
    rules = config or StatefulConfig()
    years = [period.year for period in periods]
    total_budget = sum(period.budget for period in periods)
    total_capacity = sum(period.capacity_hours for period in periods)
    rng = random.Random(seed)
    outcomes: list[RollingEpisode] = []
    fixed_objectives: list[float] = []
    rolling_objectives: list[float] = []
    regrets: list[float] = []
    for episode_index in range(episodes):
        factors = _annual_factors(
            rng=rng,
            years=years,
            cost_sigma=cost_sigma,
            hours_sigma=hours_sigma,
            capacity_sigma=capacity_sigma,
        )
        fixed_cost, fixed_hours, fixed_risk, fixed_budget, fixed_capacity = _fixed_outcome(
            fixed=fixed, periods=periods, factors=factors
        )
        fixed_objective = _objective(
            risk=fixed_risk,
            cost=fixed_cost,
            hours=fixed_hours,
            budget_exceeded=fixed_budget,
            capacity_shortfall=fixed_capacity,
            total_budget=total_budget,
            total_capacity=total_capacity,
            config=rules,
        )
        risks = [segment.initial_risk for segment in segments]
        rolling_years: list[RollingYear] = []
        rolling_cost = 0.0
        rolling_hours = 0.0
        rolling_budget = 0.0
        rolling_capacity = 0.0
        annual_risks: list[float] = []
        total_length = sum(segment.length_m for segment in segments)
        for offset, period in enumerate(periods):
            factor = factors[offset]
            scenario_segments = [
                segment.model_copy(update={"initial_risk": risks[index]})
                for index, segment in enumerate(segments)
            ]
            scenario_methods = [
                method.model_copy(
                    update={
                        "cost_per_ha": method.cost_per_ha * factor.cost_factor,
                        "hours_per_ha": method.hours_per_ha * factor.hours_factor,
                    }
                )
                for method in methods
            ]
            scenario_periods = [
                item.model_copy(
                    update={
                        "capacity_hours": item.capacity_hours * factor.capacity_factor,
                    }
                )
                for item in periods[offset : offset + window]
            ]
            try:
                plan = build_stateful_plan(
                    instance_id=f"{instance_id}-rolling-{episode_index}-{period.year}",
                    segments=scenario_segments,
                    methods=scenario_methods,
                    periods=scenario_periods,
                    config=StatefulConfig(
                        risk_weight=rules.risk_weight,
                        cost_weight=rules.cost_weight,
                        hours_weight=rules.hours_weight,
                        growth_per_year=rules.growth_per_year,
                        max_mean_risk=rules.max_mean_risk,
                        max_seconds=max_seconds_per_solve,
                    ),
                    created_utc=created_utc,
                )
            except Exception as exc:  # pragma: no cover - defensive solver boundary
                raise RollingPolicyError(
                    f"episode {episode_index} year {period.year} failed: {exc}"
                ) from exc
            if plan.status == "infeasible":
                raise RollingPolicyError(
                    f"episode {episode_index} year {period.year} is infeasible"
                )
            year_actions = [action for action in plan.actions if action.year == period.year]
            year_cost = sum(action.cost for action in year_actions)
            year_hours = sum(action.hours for action in year_actions)
            year_budget = max(0.0, year_cost - period.budget)
            year_capacity = max(
                0.0,
                year_hours - period.capacity_hours * factor.capacity_factor,
            )
            grown = [min(0.95, risk + rules.growth_per_year) for risk in risks]
            treated = {action.segment_id: action.risk_after for action in year_actions}
            risks = [
                treated.get(segment.segment_id, grown[index])
                for index, segment in enumerate(segments)
            ]
            annual_risk = (
                sum(risks[index] * segment.length_m for index, segment in enumerate(segments))
                / total_length
            )
            annual_risks.append(annual_risk)
            rolling_cost += year_cost
            rolling_hours += year_hours
            rolling_budget += year_budget
            rolling_capacity += year_capacity
            rolling_years.append(
                RollingYear(
                    year=period.year,
                    actions=len(year_actions),
                    cost=round(year_cost, 2),
                    hours=round(year_hours, 2),
                    risk=round(annual_risk, 6),
                    budget_exceeded=round(year_budget, 2),
                    capacity_shortfall=round(year_capacity, 2),
                    status=plan.status,
                )
            )
        rolling_risk = sum(annual_risks) / len(annual_risks)
        rolling_objective = _objective(
            risk=rolling_risk,
            cost=rolling_cost,
            hours=rolling_hours,
            budget_exceeded=rolling_budget,
            capacity_shortfall=rolling_capacity,
            total_budget=total_budget,
            total_capacity=total_capacity,
            config=rules,
        )
        regret = fixed_objective - rolling_objective
        outcomes.append(
            RollingEpisode(
                index=episode_index,
                factors=factors,
                fixed_cost=round(fixed_cost, 2),
                fixed_hours=round(fixed_hours, 2),
                fixed_risk=round(fixed_risk, 6),
                fixed_budget_exceeded=round(fixed_budget, 2),
                fixed_capacity_shortfall=round(fixed_capacity, 2),
                fixed_objective=round(fixed_objective, 6),
                rolling_cost=round(rolling_cost, 2),
                rolling_hours=round(rolling_hours, 2),
                rolling_risk=round(rolling_risk, 6),
                rolling_budget_exceeded=round(rolling_budget, 2),
                rolling_capacity_shortfall=round(rolling_capacity, 2),
                rolling_objective=round(rolling_objective, 6),
                regret=round(regret, 6),
                years=rolling_years,
            )
        )
        fixed_objectives.append(fixed_objective)
        rolling_objectives.append(rolling_objective)
        regrets.append(regret)
    return RollingPolicyResult(
        instance_id=instance_id,
        lookahead_years=window,
        episodes=episodes,
        seed=seed,
        total_budget=round(total_budget, 2),
        total_capacity_hours=round(total_capacity, 2),
        mean_fixed_objective=round(float(np.mean(fixed_objectives)), 6),
        mean_rolling_objective=round(float(np.mean(rolling_objectives)), 6),
        mean_regret=round(float(np.mean(regrets)), 6),
        p90_regret=round(float(np.percentile(regrets, 90)), 6),
        probability_rolling_improves=sum(value > 1e-9 for value in regrets) / len(regrets),
        fixed_budget_violation_probability=sum(item.fixed_budget_exceeded > 0 for item in outcomes)
        / len(outcomes),
        rolling_budget_violation_probability=sum(
            item.rolling_budget_exceeded > 0 for item in outcomes
        )
        / len(outcomes),
        fixed_capacity_violation_probability=sum(
            item.fixed_capacity_shortfall > 0 for item in outcomes
        )
        / len(outcomes),
        rolling_capacity_violation_probability=sum(
            item.rolling_capacity_shortfall > 0 for item in outcomes
        )
        / len(outcomes),
        fixed_cost_band=_band([item.fixed_cost for item in outcomes]),
        rolling_cost_band=_band([item.rolling_cost for item in outcomes]),
        fixed_hours_band=_band([item.fixed_hours for item in outcomes]),
        rolling_hours_band=_band([item.rolling_hours for item in outcomes]),
        fixed_risk_band=_band([item.fixed_risk for item in outcomes]),
        rolling_risk_band=_band([item.rolling_risk for item in outcomes]),
        episodes_detail=outcomes,
        created_utc=created_utc or datetime.now(UTC),
    )


__all__ = [
    "ROLLING_POLICY_SCHEMA_VERSION",
    "AnnualFactors",
    "RollingBand",
    "RollingEpisode",
    "RollingPolicyError",
    "RollingPolicyResult",
    "RollingYear",
    "simulate_rolling_policy",
]
