"""Two-stage first-year recourse for a fixed stateful plan.

The first-stage plan is fixed. After annual cost, productivity, and capacity factors are observed,
the second stage defers whole actions by lowest first-year risk reduction per hour until the annual
budget and crew-hour capacity are satisfied. This is an operational recourse evaluation, not a
stochastic dynamic program.
"""

from __future__ import annotations

import math
import random
from datetime import UTC, datetime
from typing import Literal

import numpy as np
from pydantic import BaseModel, ConfigDict, Field, model_validator

from brushline.strategic.stateful import StatefulAction, StatefulPlan, StatefulSegment

TWO_STAGE_SCHEMA_VERSION: Literal["brushline.two-stage.v1"] = "brushline.two-stage.v1"


class TwoStageError(ValueError):
    """Raised when two-stage inputs are inconsistent."""


class RecourseFactors(BaseModel):
    """Observed first-year factors."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    cost_factor: float = Field(gt=0)
    hours_factor: float = Field(gt=0)
    capacity_factor: float = Field(gt=0)


class RecourseOutcome(BaseModel):
    """Static versus recourse result for one scenario."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    index: int = Field(ge=0)
    factors: RecourseFactors
    static_cost: float = Field(ge=0)
    static_hours: float = Field(ge=0)
    static_budget_exceeded: float = Field(ge=0)
    static_capacity_shortfall: float = Field(ge=0)
    static_risk: float = Field(ge=0, le=0.95)
    static_completion: float = Field(ge=0, le=1)
    recourse_cost: float = Field(ge=0)
    recourse_hours: float = Field(ge=0)
    recourse_budget_exceeded: float = Field(ge=0)
    recourse_capacity_shortfall: float = Field(ge=0)
    recourse_risk: float = Field(ge=0, le=0.95)
    recourse_completion: float = Field(ge=0, le=1)
    deferred_actions: int = Field(ge=0)
    deferred_hours: float = Field(ge=0)
    risk_loss: float = Field(ge=0)


class RecourseBand(BaseModel):
    """P10/P50/P90 band."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    p10: float
    p50: float
    p90: float
    mean: float


class TwoStageResult(BaseModel):
    """Two-stage recourse evaluation summary."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["brushline.two-stage.v1"] = TWO_STAGE_SCHEMA_VERSION
    instance_id: str
    year: int
    episodes: int = Field(ge=1)
    seed: int
    first_stage_actions: int = Field(ge=0)
    budget: float = Field(ge=0)
    capacity_hours: float = Field(ge=0)
    static_budget_violation_probability: float = Field(ge=0, le=1)
    static_capacity_violation_probability: float = Field(ge=0, le=1)
    recourse_budget_violation_probability: float = Field(ge=0, le=1)
    recourse_capacity_violation_probability: float = Field(ge=0, le=1)
    static_cost_band: RecourseBand
    recourse_cost_band: RecourseBand
    static_hours_band: RecourseBand
    recourse_hours_band: RecourseBand
    static_risk_band: RecourseBand
    recourse_risk_band: RecourseBand
    static_completion_band: RecourseBand
    recourse_completion_band: RecourseBand
    mean_deferred_actions: float
    mean_deferred_hours: float
    mean_risk_loss: float
    outcomes: list[RecourseOutcome]
    created_utc: datetime

    @model_validator(mode="after")
    def _time(self) -> TwoStageResult:
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


def _lognormal(rng: random.Random, sigma: float) -> float:
    return math.exp(rng.gauss(-0.5 * sigma**2, sigma))


def evaluate_two_stage(
    *,
    instance_id: str,
    plan: StatefulPlan,
    segments: list[StatefulSegment],
    budget: float,
    capacity_hours: float,
    episodes: int = 100,
    seed: int = 23,
    cost_sigma: float = 0.18,
    hours_sigma: float = 0.15,
    capacity_sigma: float = 0.15,
    created_utc: datetime | None = None,
) -> TwoStageResult:
    """Evaluate static execution versus first-year deferral recourse.

    Parameters
    ----------
    instance_id : str
        Instance id.
    plan : StatefulPlan
        Fixed first-stage plan.
    segments : list of StatefulSegment
        Segments with lengths and risk state.
    budget : float
        Annual budget.
    capacity_hours : float
        Annual crew-hour capacity.
    episodes : int, optional
        Number of factor scenarios.
    seed : int, optional
        Deterministic sampler seed.
    cost_sigma, hours_sigma, capacity_sigma : float, optional
        Lognormal sigmas.
    created_utc : datetime, optional
        Creation time.

    Returns
    -------
    TwoStageResult
        Static and recourse bands and violation probabilities.

    Raises
    ------
    TwoStageError
        If inputs are inconsistent.
    """
    if not segments or not plan.actions:
        raise TwoStageError("segments and first-stage actions must be non-empty")
    if episodes < 1:
        raise TwoStageError("episodes must be positive")
    if budget < 0 or capacity_hours < 0:
        raise TwoStageError("budget and capacity must be non-negative")
    year = plan.years[0].year
    actions = [action for action in plan.actions if action.year == year]
    if not actions:
        raise TwoStageError("first-stage plan has no actions in the first year")
    length_by_segment = {segment.segment_id: segment.length_m for segment in segments}
    total_length = sum(length_by_segment.values())
    year_risk = next((row.risk for row in plan.years if row.year == year), plan.mean_risk)
    rng = random.Random(seed)
    outcomes: list[RecourseOutcome] = []
    for index in range(episodes):
        factors = RecourseFactors(
            cost_factor=round(_lognormal(rng, cost_sigma), 5),
            hours_factor=round(_lognormal(rng, hours_sigma), 5),
            capacity_factor=round(_lognormal(rng, capacity_sigma), 5),
        )
        static_cost = sum(action.cost * factors.cost_factor for action in actions)
        static_hours = sum(action.hours * factors.hours_factor for action in actions)
        static_budget = max(0.0, static_cost - budget)
        static_capacity = max(0.0, static_hours - capacity_hours * factors.capacity_factor)
        total_hours = sum(action.hours for action in actions)
        ranked = sorted(
            actions,
            key=lambda action: (
                (action.risk_before - action.risk_after) / max(action.hours, 1e-9),
                action.segment_id,
            ),
        )
        deferred: list[StatefulAction] = []
        recourse_cost = static_cost
        recourse_hours = static_hours
        while (
            recourse_cost > budget or recourse_hours > capacity_hours * factors.capacity_factor
        ) and ranked:
            action = ranked.pop(0)
            deferred.append(action)
            recourse_cost -= action.cost * factors.cost_factor
            recourse_hours -= action.hours * factors.hours_factor
        risk_loss = (
            sum(
                (action.risk_before - action.risk_after)
                * length_by_segment.get(action.segment_id, 0.0)
                for action in deferred
            )
            / total_length
        )
        deferred_hours = sum(action.hours for action in deferred)
        outcomes.append(
            RecourseOutcome(
                index=index,
                factors=factors,
                static_cost=round(static_cost, 2),
                static_hours=round(static_hours, 2),
                static_budget_exceeded=round(static_budget, 2),
                static_capacity_shortfall=round(static_capacity, 2),
                static_risk=round(year_risk, 6),
                static_completion=1.0,
                recourse_cost=round(max(0.0, recourse_cost), 2),
                recourse_hours=round(max(0.0, recourse_hours), 2),
                recourse_budget_exceeded=round(
                    max(0.0, recourse_cost - budget),
                    2,
                ),
                recourse_capacity_shortfall=round(
                    max(0.0, recourse_hours - capacity_hours * factors.capacity_factor),
                    2,
                ),
                recourse_risk=round(min(0.95, year_risk + risk_loss), 6),
                recourse_completion=round(
                    1.0 - deferred_hours / total_hours if total_hours else 1.0, 6
                ),
                deferred_actions=len(deferred),
                deferred_hours=round(deferred_hours, 2),
                risk_loss=round(risk_loss, 6),
            )
        )
    return TwoStageResult(
        instance_id=instance_id,
        year=year,
        episodes=episodes,
        seed=seed,
        first_stage_actions=len(actions),
        budget=round(budget, 2),
        capacity_hours=round(capacity_hours, 2),
        static_budget_violation_probability=sum(
            item.static_budget_exceeded > 0 for item in outcomes
        )
        / episodes,
        static_capacity_violation_probability=sum(
            item.static_capacity_shortfall > 0 for item in outcomes
        )
        / episodes,
        recourse_budget_violation_probability=sum(
            item.recourse_budget_exceeded > 0 for item in outcomes
        )
        / episodes,
        recourse_capacity_violation_probability=sum(
            item.recourse_capacity_shortfall > 0 for item in outcomes
        )
        / episodes,
        static_cost_band=_band([item.static_cost for item in outcomes], 2),
        recourse_cost_band=_band([item.recourse_cost for item in outcomes], 2),
        static_hours_band=_band([item.static_hours for item in outcomes], 2),
        recourse_hours_band=_band([item.recourse_hours for item in outcomes], 2),
        static_risk_band=_band([item.static_risk for item in outcomes]),
        recourse_risk_band=_band([item.recourse_risk for item in outcomes]),
        static_completion_band=_band([item.static_completion for item in outcomes]),
        recourse_completion_band=_band([item.recourse_completion for item in outcomes]),
        mean_deferred_actions=round(
            float(np.mean([item.deferred_actions for item in outcomes])), 3
        ),
        mean_deferred_hours=round(float(np.mean([item.deferred_hours for item in outcomes])), 2),
        mean_risk_loss=round(float(np.mean([item.risk_loss for item in outcomes])), 6),
        outcomes=outcomes,
        created_utc=created_utc or datetime.now(UTC),
    )


__all__ = [
    "TWO_STAGE_SCHEMA_VERSION",
    "RecourseBand",
    "RecourseFactors",
    "RecourseOutcome",
    "TwoStageError",
    "TwoStageResult",
    "evaluate_two_stage",
]
