"""Stress-test static frontier plans against annual cost and capacity factors.

This is candidate evaluation, not robust optimization. It asks whether an existing frontier plan,
built to a lower nominal budget, could serve as a fixed multi-year plan against a common actual
budget and capacity.
"""

from __future__ import annotations

import math
import random
from datetime import UTC, datetime
from typing import Literal

import numpy as np
from pydantic import BaseModel, ConfigDict, Field, model_validator

from brushline.strategic.stateful import StatefulConfig, StatefulPeriod, StatefulPlan

STATIC_PLAN_SCHEMA_VERSION: Literal["brushline.static-plan.v1"] = "brushline.static-plan.v1"


class StaticPlanError(ValueError):
    """Raised when static-plan evaluation inputs are inconsistent."""


class StaticPlanCase(BaseModel):
    """One candidate static plan and its nominal budget."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str
    nominal_budget: float = Field(ge=0)
    plan: StatefulPlan


class StaticBand(BaseModel):
    """P10/P50/P90 band."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    p10: float
    p50: float
    p90: float
    mean: float


class StaticPlanSummary(BaseModel):
    """Stress summary for one static candidate."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str
    nominal_budget: float
    cost_band: StaticBand
    hours_band: StaticBand
    risk: float = Field(ge=0, le=0.95)
    budget_violation_probability: float = Field(ge=0, le=1)
    capacity_violation_probability: float = Field(ge=0, le=1)
    mean_objective: float


class StaticPlanEvaluation(BaseModel):
    """Static-plan stress evaluation against a common actual budget."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["brushline.static-plan.v1"] = STATIC_PLAN_SCHEMA_VERSION
    instance_id: str
    episodes: int = Field(ge=1)
    seed: int
    actual_budget: float = Field(ge=0)
    actual_capacity_hours: float = Field(ge=0)
    budget_risk_limit: float = Field(ge=0, le=1)
    recommended: str | None
    plans: list[StaticPlanSummary]
    created_utc: datetime

    @model_validator(mode="after")
    def _time(self) -> StaticPlanEvaluation:
        if self.created_utc.tzinfo is None:
            raise ValueError("created_utc must be timezone-aware")
        return self


def _band(values: list[float]) -> StaticBand:
    array = np.asarray(values, dtype=float)
    return StaticBand(
        p10=round(float(np.percentile(array, 10)), 2),
        p50=round(float(np.percentile(array, 50)), 2),
        p90=round(float(np.percentile(array, 90)), 2),
        mean=round(float(array.mean()), 2),
    )


def _lognormal(rng: random.Random, sigma: float) -> float:
    return math.exp(rng.gauss(-0.5 * sigma**2, sigma))


def evaluate_static_plans(
    *,
    instance_id: str,
    plans: list[StaticPlanCase],
    periods: list[StatefulPeriod],
    config: StatefulConfig | None = None,
    episodes: int = 20,
    seed: int = 7,
    cost_sigma: float = 0.18,
    hours_sigma: float = 0.15,
    capacity_sigma: float = 0.15,
    budget_risk_limit: float = 0.05,
    created_utc: datetime | None = None,
) -> StaticPlanEvaluation:
    """Evaluate candidate static plans under common annual-factor episodes.

    Parameters
    ----------
    instance_id : str
        Instance id.
    plans : list of StaticPlanCase
        Candidate plans with nominal budgets.
    periods : list of StatefulPeriod
        Actual annual budget and capacity constraints.
    config : StatefulConfig, optional
        Objective weights.
    episodes : int, optional
        Number of factor episodes.
    seed : int, optional
        Deterministic sampler seed.
    cost_sigma, hours_sigma, capacity_sigma : float, optional
        Lognormal sigmas.
    budget_risk_limit : float, optional
        Maximum budget-violation probability for the recommended candidate.
    created_utc : datetime, optional
        Creation time.

    Returns
    -------
    StaticPlanEvaluation
        Candidate cost/risk bands, violation probabilities, and recommendation.

    Raises
    ------
    StaticPlanError
        If inputs are empty or invalid.
    """
    if not plans or not periods:
        raise StaticPlanError("plans and periods must be non-empty")
    if episodes < 1:
        raise StaticPlanError("episodes must be positive")
    if len({period.year for period in periods}) != len(periods):
        raise StaticPlanError("period years must be unique")
    rules = config or StatefulConfig()
    total_budget = sum(period.budget for period in periods)
    total_capacity = sum(period.capacity_hours for period in periods)
    rng = random.Random(seed)
    factor_sets = [
        [
            (
                period.year,
                _lognormal(rng, cost_sigma),
                _lognormal(rng, hours_sigma),
                _lognormal(rng, capacity_sigma),
            )
            for period in periods
        ]
        for _ in range(episodes)
    ]
    summaries: list[StaticPlanSummary] = []
    for case in plans:
        costs: list[float] = []
        hours: list[float] = []
        budget_violations: list[bool] = []
        capacity_violations: list[bool] = []
        objectives: list[float] = []
        risk = case.plan.mean_risk
        for factors in factor_sets:
            factor_by_year = {
                year: (cost_factor, hours_factor, capacity_factor)
                for year, cost_factor, hours_factor, capacity_factor in factors
            }
            cost_by_year = {period.year: 0.0 for period in periods}
            hours_by_year = {period.year: 0.0 for period in periods}
            for action in case.plan.actions:
                cost_factor, hours_factor, _capacity_factor = factor_by_year[action.year]
                cost_by_year[action.year] += action.cost * cost_factor
                hours_by_year[action.year] += action.hours * hours_factor
            budget_exceeded = sum(
                max(0.0, cost_by_year[period.year] - period.budget) for period in periods
            )
            capacity_shortfall = sum(
                max(
                    0.0,
                    hours_by_year[period.year]
                    - period.capacity_hours * factor_by_year[period.year][2],
                )
                for period in periods
            )
            total_cost = sum(cost_by_year.values())
            total_hours = sum(hours_by_year.values())
            costs.append(total_cost)
            hours.append(total_hours)
            budget_violations.append(budget_exceeded > 0)
            capacity_violations.append(capacity_shortfall > 0)
            penalty = budget_exceeded / max(total_budget, 1.0) + capacity_shortfall / max(
                total_capacity, 1.0
            )
            objectives.append(
                rules.risk_weight * risk
                + rules.cost_weight * total_cost / 100000.0
                + rules.hours_weight * total_hours / 100000.0
                + penalty
            )
        summaries.append(
            StaticPlanSummary(
                name=case.name,
                nominal_budget=case.nominal_budget,
                cost_band=_band(costs),
                hours_band=_band(hours),
                risk=risk,
                budget_violation_probability=sum(budget_violations) / episodes,
                capacity_violation_probability=sum(capacity_violations) / episodes,
                mean_objective=round(float(np.mean(objectives)), 6),
            )
        )
    eligible = [
        summary
        for summary in summaries
        if summary.budget_violation_probability <= budget_risk_limit
        and summary.capacity_violation_probability == 0
    ]
    recommended = min(eligible, key=lambda summary: summary.risk).name if eligible else None
    return StaticPlanEvaluation(
        instance_id=instance_id,
        episodes=episodes,
        seed=seed,
        actual_budget=round(total_budget, 2),
        actual_capacity_hours=round(total_capacity, 2),
        budget_risk_limit=budget_risk_limit,
        recommended=recommended,
        plans=summaries,
        created_utc=created_utc or datetime.now(UTC),
    )


__all__ = [
    "STATIC_PLAN_SCHEMA_VERSION",
    "StaticBand",
    "StaticPlanCase",
    "StaticPlanError",
    "StaticPlanEvaluation",
    "StaticPlanSummary",
    "evaluate_static_plans",
]
