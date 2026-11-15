"""Lagrangian budget and crew-hour coordination across spatial clusters.

Cluster subproblems remove the annual budget and crew-hour constraints and add non-negative
shadow prices to their objectives. Subgradient updates raise or lower those prices. The maximum
priced-cluster minimum is a lower bound for the original clustered problem.
"""

from __future__ import annotations

import math
import time
from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from brushline.strategic.decomposition import _clusters
from brushline.strategic.stateful import (
    StatefulConfig,
    StatefulMethod,
    StatefulPeriod,
    StatefulPlan,
    StatefulSegment,
    build_stateful_plan,
)

COORDINATION_SCHEMA_VERSION: Literal["brushline.stateful-coordination.v1"] = (
    "brushline.stateful-coordination.v1"
)


class CoordinationError(ValueError):
    """Raised when coordination inputs or prices are invalid."""


class PriceIteration(BaseModel):
    """One Lagrangian price iteration."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    iteration: int = Field(ge=0)
    cost_price: float = Field(ge=0)
    hours_price: float = Field(ge=0)
    dual_bound: float
    spend: float = Field(ge=0)
    hours: float = Field(ge=0)
    cluster_seconds: float = Field(ge=0)


class CoordinationResult(BaseModel):
    """Lagrangian coordination evidence."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["brushline.stateful-coordination.v1"] = COORDINATION_SCHEMA_VERSION
    instance_id: str
    cluster_count: int = Field(ge=1)
    max_segments_per_cluster: int = Field(ge=1)
    baseline_objective: float
    dual_bound: float
    absolute_gap: float
    relative_gap: float
    iterations: list[PriceIteration] = Field(min_length=1)
    best_iteration: int = Field(ge=0)
    best_cost_price: float = Field(ge=0)
    best_hours_price: float = Field(ge=0)
    created_utc: datetime

    @model_validator(mode="after")
    def _time(self) -> CoordinationResult:
        if self.created_utc.tzinfo is None:
            raise ValueError("created_utc must be timezone-aware")
        return self


def _priced_plan(
    *,
    instance_id: str,
    segments: list[StatefulSegment],
    methods: list[StatefulMethod],
    periods: list[StatefulPeriod],
    cost_price: float,
    hours_price: float,
    max_seconds: float,
    created_utc: datetime | None,
) -> StatefulPlan:
    # The priced subproblem removes the annual constraints; prices carry their shadow value.
    relaxed_periods = [
        StatefulPeriod(year=period.year, budget=1e12, capacity_hours=1e12) for period in periods
    ]
    return build_stateful_plan(
        instance_id=instance_id,
        segments=segments,
        methods=methods,
        periods=relaxed_periods,
        config=StatefulConfig(
            risk_weight=1.0,
            cost_weight=cost_price,
            hours_weight=hours_price,
            max_seconds=max_seconds,
        ),
        created_utc=created_utc,
    )


def coordinate_stateful(
    *,
    instance_id: str,
    segments: list[StatefulSegment],
    methods: list[StatefulMethod],
    periods: list[StatefulPeriod],
    baseline: StatefulPlan,
    max_segments_per_cluster: int = 150,
    iterations: int = 12,
    initial_step: float = 0.5,
    max_seconds_per_cluster: float = 30.0,
    created_utc: datetime | None = None,
) -> CoordinationResult:
    """Run a Lagrangian subgradient bound for the clustered stateful problem.

    Parameters
    ----------
    instance_id : str
        Instance id.
    segments, methods, periods : list
        Full stateful problem.
    baseline : StatefulPlan
        Feasible primal plan used for the gap.
    max_segments_per_cluster : int, optional
        Maximum cluster size.
    iterations : int, optional
        Number of subgradient iterations.
    initial_step : float, optional
        Initial price step.
    max_seconds_per_cluster : float, optional
        Exact MILP limit per cluster per iteration.
    created_utc : datetime, optional
        Creation time.

    Returns
    -------
    CoordinationResult
        Iteration prices and the best dual lower bound.

    Raises
    ------
    CoordinationError
        If inputs are invalid or no priced subproblem can be solved.
    """
    if not segments or not methods or not periods:
        raise CoordinationError("segments, methods, and periods must be non-empty")
    if max_segments_per_cluster < 1 or iterations < 1:
        raise CoordinationError("cluster size and iterations must be positive")
    groups = _clusters(segments, max_segments_per_cluster)
    total_budget = sum(period.budget for period in periods)
    total_capacity = sum(period.capacity_hours for period in periods)
    if total_budget <= 0 or total_capacity <= 0:
        raise CoordinationError("total budget and capacity must be positive")
    cost_price = 0.0
    hours_price = 0.0
    history: list[PriceIteration] = []
    best: PriceIteration | None = None
    for iteration in range(iterations):
        started = time.perf_counter()
        plans = []
        for cluster_index, group in enumerate(groups, start=1):
            plans.append(
                _priced_plan(
                    instance_id=f"{instance_id}-C{cluster_index:03d}",
                    segments=group,
                    methods=methods,
                    periods=periods,
                    cost_price=cost_price,
                    hours_price=hours_price,
                    max_seconds=max_seconds_per_cluster,
                    created_utc=created_utc,
                )
            )
        elapsed = time.perf_counter() - started
        spend = sum(plan.total_cost for plan in plans)
        hours = sum(plan.total_hours for plan in plans)
        # plan.objective = risk + cost_price*cost/1e5 + hours_price*hours/1e5
        dual = (
            sum(plan.objective for plan in plans)
            - cost_price * total_budget / 100000.0
            - hours_price * total_capacity / 100000.0
        )
        row = PriceIteration(
            iteration=iteration,
            cost_price=round(cost_price, 6),
            hours_price=round(hours_price, 6),
            dual_bound=round(dual, 6),
            spend=round(spend, 2),
            hours=round(hours, 2),
            cluster_seconds=round(elapsed, 3),
        )
        history.append(row)
        if best is None or row.dual_bound > best.dual_bound:
            best = row
        step = initial_step / math.sqrt(iteration + 1)
        cost_price = max(
            0.0,
            cost_price + step * (spend - total_budget) / max(total_budget, 1.0),
        )
        hours_price = max(
            0.0,
            hours_price + step * (hours - total_capacity) / max(total_capacity, 1.0),
        )
    assert best is not None
    absolute_gap = baseline.objective - best.dual_bound
    return CoordinationResult(
        instance_id=instance_id,
        cluster_count=len(groups),
        max_segments_per_cluster=max_segments_per_cluster,
        baseline_objective=round(baseline.objective, 6),
        dual_bound=round(best.dual_bound, 6),
        absolute_gap=round(absolute_gap, 6),
        relative_gap=round(absolute_gap / abs(baseline.objective), 6)
        if baseline.objective != 0
        else 0.0,
        iterations=history,
        best_iteration=best.iteration,
        best_cost_price=best.cost_price,
        best_hours_price=best.hours_price,
        created_utc=created_utc or datetime.now(UTC),
    )


__all__ = [
    "COORDINATION_SCHEMA_VERSION",
    "CoordinationError",
    "CoordinationResult",
    "PriceIteration",
    "coordinate_stateful",
]
