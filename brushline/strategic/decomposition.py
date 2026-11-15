"""Spatial cluster decomposition for large stateful strategic problems.

The decomposition allocates each annual budget and crew-hour capacity across connected segment
clusters, solves each cluster with the exact stateful MILP, and replays the aggregate plan. It is a
feasible spatial decomposition, not a proof of global optimality.
"""

from __future__ import annotations

import time
from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from brushline.strategic.stateful import (
    StatefulConfig,
    StatefulError,
    StatefulMethod,
    StatefulPeriod,
    StatefulPlan,
    StatefulSegment,
    build_stateful_plan,
    replay_stateful_choices,
)

DECOMPOSITION_SCHEMA_VERSION: Literal["brushline.stateful-decomposition.v1"] = (
    "brushline.stateful-decomposition.v1"
)


class DecompositionError(ValueError):
    """Raised when cluster inputs are inconsistent."""


class ClusterResult(BaseModel):
    """One solved spatial cluster."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    cluster_id: str
    segment_ids: list[str] = Field(min_length=1)
    budget_total: float = Field(ge=0)
    capacity_total: float = Field(ge=0)
    status: Literal["optimal", "feasible", "infeasible"]
    objective: float | None
    total_cost: float = Field(ge=0)
    total_hours: float = Field(ge=0)
    mean_risk: float | None
    seconds: float = Field(ge=0)
    actions: int = Field(ge=0)


class DecomposedPlan(BaseModel):
    """A replayed aggregate plan assembled from independently solved clusters."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["brushline.stateful-decomposition.v1"] = DECOMPOSITION_SCHEMA_VERSION
    instance_id: str
    cluster_count: int = Field(ge=1)
    max_segments_per_cluster: int = Field(ge=1)
    plan: StatefulPlan
    clusters: list[ClusterResult] = Field(min_length=1)
    gap_to_baseline: float | None
    created_utc: datetime

    @model_validator(mode="after")
    def _time(self) -> DecomposedPlan:
        if self.created_utc.tzinfo is None:
            raise ValueError("created_utc must be timezone-aware")
        return self


def _clusters(segments: list[StatefulSegment], max_segments: int) -> list[list[StatefulSegment]]:
    """Group ordered spans into contiguous clusters."""
    by_span: dict[str, list[StatefulSegment]] = {}
    for segment in segments:
        by_span.setdefault(segment.span_id, []).append(segment)
    clusters: list[list[StatefulSegment]] = []
    current: list[StatefulSegment] = []
    for span_id in sorted(by_span):
        span = sorted(by_span[span_id], key=lambda item: item.segment_id)
        if len(span) > max_segments:
            if current:
                clusters.append(current)
                current = []
            for start in range(0, len(span), max_segments):
                clusters.append(span[start : start + max_segments])
            continue
        if current and len(current) + len(span) > max_segments:
            clusters.append(current)
            current = []
        current.extend(span)
        if len(current) == max_segments:
            clusters.append(current)
            current = []
    if current:
        clusters.append(current)
    return clusters


def decompose_stateful(
    *,
    instance_id: str,
    segments: list[StatefulSegment],
    methods: list[StatefulMethod],
    periods: list[StatefulPeriod],
    config: StatefulConfig | None = None,
    max_segments_per_cluster: int = 150,
    baseline: StatefulPlan | None = None,
    created_utc: datetime | None = None,
) -> DecomposedPlan:
    """Solve cluster MILPs under risk-weighted annual budget allocations.

    Parameters
    ----------
    instance_id : str
        Instance id.
    segments, methods, periods : list
        Full stateful problem.
    config : StatefulConfig, optional
        Objective and state settings.
    max_segments_per_cluster : int, optional
        Maximum segments per exact cluster MILP.
    baseline : StatefulPlan, optional
        Heuristic or other baseline for gap reporting.
    created_utc : datetime, optional
        Creation time.

    Returns
    -------
    DecomposedPlan
        Cluster results and the replayed aggregate plan.

    Raises
    ------
    DecompositionError
        If the instance is empty or no cluster can be solved.
    """
    if not segments or not methods or not periods:
        raise DecompositionError("segments, methods, and periods must be non-empty")
    if max_segments_per_cluster < 1:
        raise DecompositionError("max_segments_per_cluster must be positive")
    rules = config or StatefulConfig()
    groups = _clusters(segments, max_segments_per_cluster)
    if not groups:
        raise DecompositionError("no clusters were formed")
    risk_mass = [
        sum(segment.length_m * segment.initial_risk for segment in group) for group in groups
    ]
    total_mass = sum(risk_mass)
    weights = (
        [value / total_mass for value in risk_mass]
        if total_mass > 0
        else [1.0 / len(groups) for _group in groups]
    )
    segment_lookup = {segment.segment_id: index for index, segment in enumerate(segments)}
    method_lookup = {method.method: index for index, method in enumerate(methods)}
    allocations = [[period.budget * weight for period in periods] for weight in weights]
    capacities = [[period.capacity_hours * weight for period in periods] for weight in weights]
    selected: dict[tuple[int, int, int], bool] = {}
    final_plans: list[StatefulPlan] = []
    total_cluster_seconds = 0.0
    rounds = 0
    while rounds < 3:
        rounds += 1
        plans: list[StatefulPlan] = []
        round_times: list[float] = []
        cluster_seconds = 0.0
        for group, budget_values, capacity_values in zip(
            groups, allocations, capacities, strict=True
        ):
            cluster_periods = [
                StatefulPeriod(
                    year=period.year,
                    budget=budget_values[index],
                    capacity_hours=capacity_values[index],
                )
                for index, period in enumerate(periods)
            ]
            started = time.perf_counter()
            plan = build_stateful_plan(
                instance_id=f"{instance_id}-C{len(plans) + 1:03d}",
                segments=group,
                methods=methods,
                periods=cluster_periods,
                config=rules,
                created_utc=created_utc,
            )
            elapsed = time.perf_counter() - started
            cluster_seconds += elapsed
            round_times.append(elapsed)
            plans.append(plan)
        total_cluster_seconds += cluster_seconds
        final_plans = plans
        final_cluster_times = round_times
        spent = [sum(plan.years[index].cost for plan in plans) for index in range(len(periods))]
        used = [sum(plan.years[index].hours for plan in plans) for index in range(len(periods))]
        residual_budget = [
            max(0.0, periods[index].budget - spent[index]) for index in range(len(periods))
        ]
        residual_capacity = [
            max(0.0, periods[index].capacity_hours - used[index]) for index in range(len(periods))
        ]
        if max(residual_budget) <= 1e-6 and max(residual_capacity) <= 1e-6:
            break
        allocations = [
            [
                plans[cluster_index].years[period_index].cost
                + residual_budget[period_index] * weights[cluster_index]
                for period_index in range(len(periods))
            ]
            for cluster_index in range(len(groups))
        ]
        capacities = [
            [
                plans[cluster_index].years[period_index].hours
                + residual_capacity[period_index] * weights[cluster_index]
                for period_index in range(len(periods))
            ]
            for cluster_index in range(len(groups))
        ]
    selected = {}
    for _group, plan in zip(groups, final_plans, strict=True):
        for action in plan.actions:
            selected[
                (
                    segment_lookup[action.segment_id],
                    next(
                        index for index, period in enumerate(periods) if period.year == action.year
                    ),
                    method_lookup[action.method],
                )
            ] = True
    cluster_results = []
    for cluster_index, (group, plan, budget_values, capacity_values) in enumerate(
        zip(groups, final_plans, allocations, capacities, strict=True), start=1
    ):
        cluster_results.append(
            ClusterResult(
                cluster_id=f"C{cluster_index:03d}",
                segment_ids=[segment.segment_id for segment in group],
                budget_total=round(sum(budget_values), 2),
                capacity_total=round(sum(capacity_values), 2),
                status=plan.status,
                objective=plan.objective,
                total_cost=plan.total_cost,
                total_hours=plan.total_hours,
                mean_risk=plan.mean_risk,
                seconds=round(final_cluster_times[cluster_index - 1], 3),
                actions=len(plan.actions),
            )
        )
    actions, years, total_cost, total_hours, mean_risk = replay_stateful_choices(
        segments, methods, periods, rules, selected
    )
    objective = rules.risk_weight * mean_risk + rules.cost_weight * total_cost / 100000.0
    aggregate = StatefulPlan(
        instance_id=instance_id,
        status="feasible",
        solver_status=0,
        solver_message="Spatial cluster decomposition; aggregate replay",
        solver="brushline.cluster-decomposition",
        objective=round(objective, 4),
        total_cost=round(total_cost, 2),
        total_hours=round(total_hours, 2),
        mean_risk=round(mean_risk, 4),
        mean_service=round(1.0 - mean_risk, 4),
        actions=actions,
        years=years,
        replay_ok=True,
        search={
            "cluster_count": len(groups),
            "max_segments_per_cluster": max_segments_per_cluster,
            "cluster_seconds": round(total_cluster_seconds, 3),
            "rounds": rounds,
            "all_clusters_optimal": all(item.status == "optimal" for item in cluster_results),
            "baseline_gap": (
                round((objective - baseline.objective) / abs(baseline.objective), 6)
                if baseline is not None and baseline.objective != 0
                else 0.0
            ),
        },
        created_utc=created_utc or datetime.now(UTC),
    )
    return DecomposedPlan(
        instance_id=instance_id,
        cluster_count=len(groups),
        max_segments_per_cluster=max_segments_per_cluster,
        plan=aggregate,
        clusters=cluster_results,
        gap_to_baseline=(
            (objective - baseline.objective) / abs(baseline.objective)
            if baseline is not None and baseline.objective != 0
            else None
        ),
        created_utc=created_utc or datetime.now(UTC),
    )


def repair_stateful_clusters(
    *,
    instance_id: str,
    segments: list[StatefulSegment],
    methods: list[StatefulMethod],
    periods: list[StatefulPeriod],
    baseline: StatefulPlan,
    config: StatefulConfig | None = None,
    max_segments_per_cluster: int = 150,
    created_utc: datetime | None = None,
) -> DecomposedPlan:
    """Repair a baseline plan one budget-preserving spatial cluster at a time.

    Each cluster receives exactly the annual budget and crew-hours consumed by the baseline in that
    cluster, then is solved with the exact stateful MILP. The baseline remains the fallback if a
    cluster solve fails. This is fix-and-optimize; it does not reallocate the global budget.
    """
    if not segments or not methods or not periods:
        raise DecompositionError("segments, methods, and periods must be non-empty")
    if max_segments_per_cluster < 1:
        raise DecompositionError("max_segments_per_cluster must be positive")
    rules = config or StatefulConfig()
    groups = _clusters(segments, max_segments_per_cluster)
    segment_lookup = {segment.segment_id: index for index, segment in enumerate(segments)}
    method_lookup = {method.method: index for index, method in enumerate(methods)}
    cluster_segment_ids = [{segment.segment_id for segment in group} for group in groups]
    baseline_selected: dict[tuple[int, int, int], bool] = {}
    baseline_actions_by_cluster: list[list[tuple[int, int, int]]] = [[] for _group in groups]
    for action in baseline.actions:
        period_index = next(
            index for index, period in enumerate(periods) if period.year == action.year
        )
        key = (
            segment_lookup[action.segment_id],
            period_index,
            method_lookup[action.method],
        )
        baseline_selected[key] = True
        for cluster_index, ids in enumerate(cluster_segment_ids):
            if action.segment_id in ids:
                baseline_actions_by_cluster[cluster_index].append(key)
                break
    selected: dict[tuple[int, int, int], bool] = {}
    cluster_results: list[ClusterResult] = []
    total_seconds = 0.0
    for cluster_index, group in enumerate(groups):
        cluster_id = f"C{cluster_index + 1:03d}"
        cluster_keys = baseline_actions_by_cluster[cluster_index]
        cluster_actions = [
            action
            for action in baseline.actions
            if action.segment_id in cluster_segment_ids[cluster_index]
        ]
        budgets = [0.0] * len(periods)
        capacities = [0.0] * len(periods)
        for action, key in zip(cluster_actions, cluster_keys, strict=False):
            budgets[key[1]] += action.cost
            capacities[key[1]] += action.hours
        cluster_periods = [
            StatefulPeriod(
                year=period.year,
                budget=budgets[index] + 1e-6,
                capacity_hours=capacities[index] + 1e-6,
            )
            for index, period in enumerate(periods)
        ]
        started = time.perf_counter()
        try:
            cluster_plan = build_stateful_plan(
                instance_id=f"{instance_id}-{cluster_id}",
                segments=group,
                methods=methods,
                periods=cluster_periods,
                config=rules,
                created_utc=created_utc,
            )
            use_exact = True
        except StatefulError:
            cluster_plan = None
            use_exact = False
        elapsed = time.perf_counter() - started
        total_seconds += elapsed
        if use_exact and cluster_plan is not None:
            for action in cluster_plan.actions:
                selected[
                    (
                        segment_lookup[action.segment_id],
                        next(
                            index
                            for index, period in enumerate(periods)
                            if period.year == action.year
                        ),
                        method_lookup[action.method],
                    )
                ] = True
            status = cluster_plan.status
            total_cost = cluster_plan.total_cost
            total_hours = cluster_plan.total_hours
            objective = cluster_plan.objective
            mean_risk = cluster_plan.mean_risk
            actions_count = len(cluster_plan.actions)
        else:
            for key in cluster_keys:
                selected[key] = True
            status = "feasible"
            total_cost = sum(action.cost for action in cluster_actions)
            total_hours = sum(action.hours for action in cluster_actions)
            objective = None
            mean_risk = None
            actions_count = len(cluster_actions)
        cluster_results.append(
            ClusterResult(
                cluster_id=cluster_id,
                segment_ids=[segment.segment_id for segment in group],
                budget_total=round(sum(budgets), 2),
                capacity_total=round(sum(capacities), 2),
                status=status,
                objective=objective,
                total_cost=total_cost,
                total_hours=total_hours,
                mean_risk=mean_risk,
                seconds=round(elapsed, 3),
                actions=actions_count,
            )
        )
    actions, years, total_cost, total_hours, mean_risk = replay_stateful_choices(
        segments, methods, periods, rules, selected
    )
    objective = rules.risk_weight * mean_risk + rules.cost_weight * total_cost / 100000.0
    aggregate = StatefulPlan(
        instance_id=instance_id,
        status="feasible",
        solver_status=0,
        solver_message="Budget-preserving spatial cluster repair",
        solver="brushline.cluster-repair",
        objective=round(objective, 4),
        total_cost=round(total_cost, 2),
        total_hours=round(total_hours, 2),
        mean_risk=round(mean_risk, 4),
        mean_service=round(1.0 - mean_risk, 4),
        actions=actions,
        years=years,
        replay_ok=True,
        search={
            "cluster_count": len(groups),
            "max_segments_per_cluster": max_segments_per_cluster,
            "cluster_seconds": round(total_seconds, 3),
            "baseline_gap": (
                round((objective - baseline.objective) / abs(baseline.objective), 6)
                if baseline.objective != 0
                else 0.0
            ),
        },
        created_utc=created_utc or datetime.now(UTC),
    )
    return DecomposedPlan(
        instance_id=instance_id,
        cluster_count=len(groups),
        max_segments_per_cluster=max_segments_per_cluster,
        plan=aggregate,
        clusters=cluster_results,
        gap_to_baseline=(
            (objective - baseline.objective) / abs(baseline.objective)
            if baseline.objective != 0
            else None
        ),
        created_utc=created_utc or datetime.now(UTC),
    )


__all__ = [
    "DECOMPOSITION_SCHEMA_VERSION",
    "ClusterResult",
    "DecomposedPlan",
    "DecompositionError",
    "decompose_stateful",
    "repair_stateful_clusters",
]
