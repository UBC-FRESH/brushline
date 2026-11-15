"""Execution uncertainty around a fixed tactical plan.

The sampler varies treatment cost, productive hours, and contractor capacity around a
fixed plan. It does not re-optimize the plan per sample; this is execution sensitivity, not a full
adaptive stochastic program.
"""

from __future__ import annotations

import math
import random
from datetime import UTC, datetime
from typing import Literal

import numpy as np
from pydantic import BaseModel, ConfigDict, Field, model_validator

from brushline.strategic.stateful import StatefulPeriod
from brushline.tactical.program import TacticalAction
from brushline.tactical.resources import ContractorProfile

UNCERTAINTY_SCHEMA_VERSION: Literal["brushline.uncertainty.v1"] = "brushline.uncertainty.v1"


class UncertaintyError(ValueError):
    """Raised when uncertainty inputs are inconsistent."""


class UncertaintyConfig(BaseModel):
    """Distribution settings for the execution sampler."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    samples: int = Field(default=500, ge=1, le=10000)
    seed: int = 7
    cost_sigma: float = Field(default=0.18, ge=0, le=1)
    hours_sigma: float = Field(default=0.15, ge=0, le=1)
    capacity_sigma: float = Field(default=0.15, ge=0, le=1)


class UncertaintyBand(BaseModel):
    """P10/P50/P90 band for one metric."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    p10: float
    p50: float
    p90: float
    mean: float


class UncertaintySample(BaseModel):
    """One sampled execution outcome."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    cost_factor: float = Field(gt=0)
    hours_factor: float = Field(gt=0)
    capacity_factor: float = Field(gt=0)
    total_cost: float = Field(ge=0)
    total_hours: float = Field(ge=0)
    budget_exceeded: float = Field(ge=0)
    capacity_shortfall_hours: float = Field(ge=0)
    contractor_shortfall_hours: float = Field(ge=0)


class SensitivityCase(BaseModel):
    """One deterministic one-at-a-time sensitivity case."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str
    cost_factor: float = Field(gt=0)
    hours_factor: float = Field(gt=0)
    capacity_factor: float = Field(gt=0)
    total_cost: float = Field(ge=0)
    total_hours: float = Field(ge=0)
    budget_exceeded: float = Field(ge=0)
    capacity_shortfall_hours: float = Field(ge=0)
    contractor_shortfall_hours: float = Field(ge=0)


class UncertaintyResult(BaseModel):
    """Sampled execution bands and deterministic sensitivities."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["brushline.uncertainty.v1"] = UNCERTAINTY_SCHEMA_VERSION
    instance_id: str
    samples: int = Field(ge=1)
    seed: int
    annual_budget: float = Field(ge=0)
    annual_capacity_hours: float = Field(ge=0)
    baseline_cost: float = Field(ge=0)
    baseline_hours: float = Field(ge=0)
    cost_band: UncertaintyBand
    hours_band: UncertaintyBand
    budget_exceeded_band: UncertaintyBand
    capacity_shortfall_band: UncertaintyBand
    contractor_shortfall_band: UncertaintyBand
    probability_budget_exceeded: float = Field(ge=0, le=1)
    probability_capacity_shortfall: float = Field(ge=0, le=1)
    probability_contractor_shortfall: float = Field(ge=0, le=1)
    sensitivity: list[SensitivityCase]
    samples_detail: list[UncertaintySample]
    created_utc: datetime

    @model_validator(mode="after")
    def _time(self) -> UncertaintyResult:
        if self.created_utc.tzinfo is None:
            raise ValueError("created_utc must be timezone-aware")
        return self


def _band(values: list[float]) -> UncertaintyBand:
    if not values:
        raise UncertaintyError("cannot summarize an empty sample")
    array = np.asarray(values, dtype=float)
    return UncertaintyBand(
        p10=round(float(np.percentile(array, 10)), 2),
        p50=round(float(np.percentile(array, 50)), 2),
        p90=round(float(np.percentile(array, 90)), 2),
        mean=round(float(array.mean()), 2),
    )


def _outcome(
    actions: list[TacticalAction],
    periods: list[StatefulPeriod],
    profiles: list[ContractorProfile],
    *,
    cost_factor: float,
    hours_factor: float,
    capacity_factor: float,
) -> UncertaintySample:
    cost_by_year = {period.year: 0.0 for period in periods}
    hours_by_year = {period.year: 0.0 for period in periods}
    contractor_hours: dict[tuple[str, int], float] = {}
    for action in actions:
        cost_by_year[action.year] = cost_by_year.get(action.year, 0.0) + action.cost * cost_factor
        hours = action.capacity_units * hours_factor
        hours_by_year[action.year] = hours_by_year.get(action.year, 0.0) + hours
        key = (action.contractor_id, action.year)
        contractor_hours[key] = contractor_hours.get(key, 0.0) + hours
    budget_exceeded = sum(
        max(0.0, cost_by_year.get(period.year, 0.0) - period.budget) for period in periods
    )
    capacity_shortfall = sum(
        max(0.0, hours_by_year.get(period.year, 0.0) - period.capacity_hours) for period in periods
    )
    profile_map = {profile.contractor_id: profile for profile in profiles}
    contractor_shortfall = 0.0
    for (contractor_id, _year), hours in contractor_hours.items():
        profile = profile_map.get(contractor_id)
        if profile is None:
            contractor_shortfall += hours
            continue
        contractor_shortfall += max(
            0.0,
            hours - profile.annual_capacity_units * capacity_factor,
        )
    return UncertaintySample(
        cost_factor=round(cost_factor, 5),
        hours_factor=round(hours_factor, 5),
        capacity_factor=round(capacity_factor, 5),
        total_cost=round(sum(cost_by_year.values()), 2),
        total_hours=round(sum(hours_by_year.values()), 2),
        budget_exceeded=round(budget_exceeded, 2),
        capacity_shortfall_hours=round(capacity_shortfall, 2),
        contractor_shortfall_hours=round(contractor_shortfall, 2),
    )


def evaluate_uncertainty(
    *,
    instance_id: str,
    actions: list[TacticalAction],
    periods: list[StatefulPeriod],
    profiles: list[ContractorProfile],
    config: UncertaintyConfig | None = None,
    created_utc: datetime | None = None,
) -> UncertaintyResult:
    """Sample cost, hours, and contractor capacity around a fixed plan.

    Parameters
    ----------
    instance_id : str
        Instance id.
    actions : list of TacticalAction
        Fixed tactical plan.
    periods : list of StatefulPeriod
        Annual budgets and crew-hour capacities.
    profiles : list of ContractorProfile
        Contractor capacities.
    config : UncertaintyConfig, optional
        Sampler settings.
    created_utc : datetime, optional
        Creation time.

    Returns
    -------
    UncertaintyResult
        Percentile bands, shortfall probabilities, and one-at-a-time sensitivities.
    """
    if not actions or not periods or not profiles:
        raise UncertaintyError("actions, periods, and profiles must be non-empty")
    rules = config or UncertaintyConfig()
    rng = random.Random(rules.seed)
    annual_budget = sum(period.budget for period in periods)
    annual_capacity = sum(period.capacity_hours for period in periods)
    baseline = _outcome(
        actions, periods, profiles, cost_factor=1.0, hours_factor=1.0, capacity_factor=1.0
    )
    samples = []
    for _ in range(rules.samples):
        samples.append(
            _outcome(
                actions,
                periods,
                profiles,
                cost_factor=math.exp(rng.gauss(-0.5 * rules.cost_sigma**2, rules.cost_sigma)),
                hours_factor=math.exp(rng.gauss(-0.5 * rules.hours_sigma**2, rules.hours_sigma)),
                capacity_factor=math.exp(
                    rng.gauss(-0.5 * rules.capacity_sigma**2, rules.capacity_sigma)
                ),
            )
        )
    cost_values = [item.total_cost for item in samples]
    hours_values = [item.total_hours for item in samples]
    budget_values = [item.budget_exceeded for item in samples]
    capacity_values = [item.capacity_shortfall_hours for item in samples]
    contractor_values = [item.contractor_shortfall_hours for item in samples]
    sensitivity = [
        SensitivityCase(
            name="baseline",
            cost_factor=1.0,
            hours_factor=1.0,
            capacity_factor=1.0,
            total_cost=baseline.total_cost,
            total_hours=baseline.total_hours,
            budget_exceeded=baseline.budget_exceeded,
            capacity_shortfall_hours=baseline.capacity_shortfall_hours,
            contractor_shortfall_hours=baseline.contractor_shortfall_hours,
        ),
        _sensitivity("cost +20%", actions, periods, profiles, cost_factor=1.2),
        _sensitivity("productivity -20%", actions, periods, profiles, hours_factor=1.25),
        _sensitivity("capacity -20%", actions, periods, profiles, capacity_factor=0.8),
        _sensitivity(
            "combined stress",
            actions,
            periods,
            profiles,
            cost_factor=1.2,
            hours_factor=1.25,
            capacity_factor=0.8,
        ),
    ]
    return UncertaintyResult(
        instance_id=instance_id,
        samples=rules.samples,
        seed=rules.seed,
        annual_budget=round(annual_budget, 2),
        annual_capacity_hours=round(annual_capacity, 2),
        baseline_cost=baseline.total_cost,
        baseline_hours=baseline.total_hours,
        cost_band=_band(cost_values),
        hours_band=_band(hours_values),
        budget_exceeded_band=_band(budget_values),
        capacity_shortfall_band=_band(capacity_values),
        contractor_shortfall_band=_band(contractor_values),
        probability_budget_exceeded=sum(item.budget_exceeded > 0 for item in samples)
        / len(samples),
        probability_capacity_shortfall=sum(item.capacity_shortfall_hours > 0 for item in samples)
        / len(samples),
        probability_contractor_shortfall=sum(
            item.contractor_shortfall_hours > 0 for item in samples
        )
        / len(samples),
        sensitivity=sensitivity,
        samples_detail=samples,
        created_utc=created_utc or datetime.now(UTC),
    )


def _sensitivity(
    name: str,
    actions: list[TacticalAction],
    periods: list[StatefulPeriod],
    profiles: list[ContractorProfile],
    *,
    cost_factor: float = 1.0,
    hours_factor: float = 1.0,
    capacity_factor: float = 1.0,
) -> SensitivityCase:
    outcome = _outcome(
        actions,
        periods,
        profiles,
        cost_factor=cost_factor,
        hours_factor=hours_factor,
        capacity_factor=capacity_factor,
    )
    return SensitivityCase(
        name=name,
        cost_factor=cost_factor,
        hours_factor=hours_factor,
        capacity_factor=capacity_factor,
        total_cost=outcome.total_cost,
        total_hours=outcome.total_hours,
        budget_exceeded=outcome.budget_exceeded,
        capacity_shortfall_hours=outcome.capacity_shortfall_hours,
        contractor_shortfall_hours=outcome.contractor_shortfall_hours,
    )


__all__ = [
    "UNCERTAINTY_SCHEMA_VERSION",
    "SensitivityCase",
    "UncertaintyBand",
    "UncertaintyConfig",
    "UncertaintyError",
    "UncertaintyResult",
    "UncertaintySample",
    "evaluate_uncertainty",
]
