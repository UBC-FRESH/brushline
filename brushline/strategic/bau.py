"""Business-as-usual strategic baseline.

The baseline expands a fixed cycle or an explicit action calendar into the same segment-period
options used by the optimized portfolio. It is simulated like-for-like and compared on present
cost, service, risk, and uncertainty.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from brushline.strategic.portfolio import (
    PeriodSummary,
    PortfolioOption,
    PortfolioPeriod,
    PortfolioSegment,
    PortfolioSelection,
    PortfolioViolation,
    StrategicPortfolio,
)

BAU_SCHEMA_VERSION: Literal["brushline.strategic-bau.v1"] = "brushline.strategic-bau.v1"


class BauError(ValueError):
    """Raised when a BAU policy or comparison is inconsistent."""


class BauConfig(BaseModel):
    """Fixed-cycle baseline settings.

    Parameters
    ----------
    cycle_years : int
        Treatment cycle.
    start_year : int
        First cycle year.
    action_id : str or None
        Action to apply; None uses the first non-treatment-free option.
    enforce_budget : bool
        Whether budget and capacity violations make the baseline infeasible.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    cycle_years: int = Field(default=4, ge=1, le=30)
    start_year: int = Field(default=2026, ge=1900, le=2200)
    action_id: str | None = None
    enforce_budget: bool = True


class BauPlan(BaseModel):
    """A fixed-cycle business-as-usual plan.

    Parameters
    ----------
    schema_version : {"brushline.strategic-bau.v1"}
        Schema version.
    policy_id : str
        Policy id.
    instance_id : str
        Instance id.
    config : BauConfig
        Baseline settings.
    selections : list of PortfolioSelection
        Selected options.
    period_summary : list of PeriodSummary
        Period totals.
    total_cost : float
        Total cost.
    service_attainment : float
        Service.
    risk : float
        Risk.
    uncertainty : float
        Uncertainty.
    baseline_service : float
        No-treatment service.
    baseline_risk : float
        No-treatment risk.
    baseline_uncertainty : float
        No-treatment uncertainty.
    feasible : bool
        Budget/capacity satisfied.
    violations : list of PortfolioViolation
        Hard violations.
    created_utc : datetime
        Timezone-aware time.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["brushline.strategic-bau.v1"] = BAU_SCHEMA_VERSION
    policy_id: str
    instance_id: str
    config: BauConfig
    selections: list[PortfolioSelection]
    period_summary: list[PeriodSummary]
    total_cost: float = Field(ge=0)
    service_attainment: float = Field(ge=0, le=1)
    risk: float = Field(ge=0, le=1)
    uncertainty: float = Field(ge=0, le=1)
    baseline_service: float = Field(ge=0, le=1)
    baseline_risk: float = Field(ge=0, le=1)
    baseline_uncertainty: float = Field(ge=0, le=1)
    feasible: bool
    violations: list[PortfolioViolation] = Field(default_factory=list)
    created_utc: datetime

    @model_validator(mode="after")
    def _time(self) -> BauPlan:
        if self.created_utc.tzinfo is None:
            raise ValueError("created_utc must be timezone-aware")
        return self


class BauComparison(BaseModel):
    """Optimized-versus-BAU comparison.

    Parameters
    ----------
    optimized_portfolio_id : str
        Optimized portfolio id.
    bau_policy_id : str
        BAU policy id.
    instance_id : str
        Instance id.
    present_cost_delta : float
        BAU cost minus optimized cost.
    service_delta : float
        Optimized service minus BAU service.
    risk_delta : float
        Optimized risk minus BAU risk (negative is better).
    uncertainty_delta : float
        Optimized uncertainty minus BAU uncertainty (negative is better).
    optimized_feasible : bool
        Optimized feasibility.
    bau_feasible : bool
        BAU feasibility.
    like_for_like : bool
        Same instance and period scope.
    caveats : list of str
        Comparison caveats.
    created_utc : datetime
        Timezone-aware time.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    optimized_portfolio_id: str
    bau_policy_id: str
    instance_id: str
    present_cost_delta: float
    service_delta: float
    risk_delta: float
    uncertainty_delta: float
    optimized_feasible: bool
    bau_feasible: bool
    like_for_like: bool
    caveats: list[str] = Field(default_factory=list)
    created_utc: datetime


def build_bau_plan(
    *,
    policy_id: str,
    instance_id: str,
    segments: list[PortfolioSegment],
    periods: list[PortfolioPeriod],
    options: list[PortfolioOption],
    config: BauConfig | None = None,
    created_utc: datetime | None = None,
) -> BauPlan:
    """Expand and simulate a fixed-cycle BAU policy.

    Parameters
    ----------
    policy_id : str
        Policy id.
    instance_id : str
        Instance id.
    segments : list of PortfolioSegment
        Segments.
    periods : list of PortfolioPeriod
        Periods.
    options : list of PortfolioOption
        Options.
    config : BauConfig, optional
        Cycle settings.
    created_utc : datetime, optional
        Creation time.

    Returns
    -------
    BauPlan
        Baseline plan and outcomes.

    Raises
    ------
    BauError
        When an option references an unknown segment or period.
    """
    rules = config or BauConfig()
    segment_ids = {item.segment_id for item in segments}
    period_ids = {item.period_id for item in periods}
    by_key: dict[tuple[str, str], list[PortfolioOption]] = {}
    for option in options:
        if option.segment_id not in segment_ids or option.period_id not in period_ids:
            raise BauError("BAU option references an unknown segment or period")
        by_key.setdefault((option.segment_id, option.period_id), []).append(option)
    for key in by_key:
        by_key[key].sort(key=lambda item: item.option_id)
    selected: dict[tuple[str, str], PortfolioOption] = {}
    for segment in segments:
        for period in periods:
            if period.start_year < rules.start_year:
                continue
            if (period.start_year - rules.start_year) % rules.cycle_years != 0:
                continue
            candidates = [
                option
                for option in by_key.get((segment.segment_id, period.period_id), [])
                if rules.action_id is None or option.action_id == rules.action_id
            ]
            if candidates:
                selected[(segment.segment_id, period.period_id)] = candidates[0]
    violations = _budget_capacity_violations(segments, periods, selected)
    truncated = False
    if rules.enforce_budget:
        while violations and selected:
            key = sorted(selected)[-1]
            del selected[key]
            truncated = True
            violations = _budget_capacity_violations(segments, periods, selected)
        if truncated:
            violations.append(
                PortfolioViolation(
                    code="BAU-TRUNCATED",
                    message="the fixed cycle was truncated to satisfy budget or capacity",
                )
            )
    aggregate = _aggregate(segments, periods, selected)
    summary = _period_summary(segments, periods, selected, aggregate)
    selections = [
        PortfolioSelection(
            option_id=option.option_id,
            segment_id=option.segment_id,
            period_id=option.period_id,
            action_id=option.action_id,
            cost=option.cost,
            service_attainment=option.service_attainment,
            risk=option.risk,
            uncertainty=option.uncertainty,
        )
        for option in sorted(selected.values(), key=lambda item: item.option_id)
    ]
    return BauPlan(
        policy_id=policy_id,
        instance_id=instance_id,
        config=rules,
        selections=selections,
        period_summary=summary,
        total_cost=aggregate[0],
        service_attainment=aggregate[1],
        risk=aggregate[2],
        uncertainty=aggregate[3],
        baseline_service=aggregate[4],
        baseline_risk=aggregate[5],
        baseline_uncertainty=aggregate[6],
        feasible=not violations,
        violations=violations,
        created_utc=created_utc or datetime.now(UTC),
    )


def compare_bau(
    optimized: StrategicPortfolio,
    bau: BauPlan,
    *,
    created_utc: datetime | None = None,
) -> BauComparison:
    """Compare an optimized portfolio with a BAU plan.

    Parameters
    ----------
    optimized : StrategicPortfolio
        Optimized portfolio.
    bau : BauPlan
        BAU plan.
    created_utc : datetime, optional
        Comparison time.

    Returns
    -------
    BauComparison
        Deltas and like-for-like status.
    """
    optimized_periods = [item.period_id for item in optimized.period_summary]
    bau_periods = [item.period_id for item in bau.period_summary]
    like = optimized.instance_id == bau.instance_id and optimized_periods == bau_periods
    return BauComparison(
        optimized_portfolio_id=optimized.portfolio_id,
        bau_policy_id=bau.policy_id,
        instance_id=optimized.instance_id,
        present_cost_delta=bau.total_cost - optimized.total_cost,
        service_delta=optimized.service_attainment - bau.service_attainment,
        risk_delta=optimized.risk - bau.risk,
        uncertainty_delta=optimized.uncertainty - bau.uncertainty,
        optimized_feasible=optimized.feasible,
        bau_feasible=bau.feasible,
        like_for_like=like,
        caveats=[
            "BAU is a fixed-cycle scenario, not a claim about the owner's actual past decisions.",
            "Both plans use the same segment/period options and outcome assumptions.",
            "A like-for-like mismatch is reported; it is not reconciled silently.",
        ],
        created_utc=created_utc or datetime.now(UTC),
    )


def _aggregate(
    segments: list[PortfolioSegment],
    periods: list[PortfolioPeriod],
    selected: dict[tuple[str, str], PortfolioOption],
) -> tuple[float, float, float, float, float, float, float]:
    total_weight = sum(item.length_m for item in segments) * max(len(periods), 1)
    cost = 0.0
    service = 0.0
    risk = 0.0
    uncertainty = 0.0
    for segment in segments:
        for period in periods:
            choice = selected.get((segment.segment_id, period.period_id))
            weight = segment.length_m / max(total_weight, 1e-12)
            service += weight * (choice.service_attainment if choice else segment.base_service)
            risk += weight * (choice.risk if choice else segment.base_risk)
            uncertainty += weight * (choice.uncertainty if choice else segment.base_uncertainty)
            cost += choice.cost if choice else 0.0
    baseline_weight = sum(item.length_m for item in segments) * max(len(periods), 1)
    baseline_service = (
        sum(item.base_service * item.length_m for item in segments)
        * len(periods)
        / max(baseline_weight, 1e-12)
    )
    baseline_risk = (
        sum(item.base_risk * item.length_m for item in segments)
        * len(periods)
        / max(baseline_weight, 1e-12)
    )
    baseline_uncertainty = (
        sum(item.base_uncertainty * item.length_m for item in segments)
        * len(periods)
        / max(baseline_weight, 1e-12)
    )
    return (
        cost,
        service,
        risk,
        uncertainty,
        baseline_service,
        baseline_risk,
        baseline_uncertainty,
    )


def _period_summary(
    segments: list[PortfolioSegment],
    periods: list[PortfolioPeriod],
    selected: dict[tuple[str, str], PortfolioOption],
    aggregate: tuple[float, float, float, float, float, float, float],
) -> list[PeriodSummary]:
    summaries: list[PeriodSummary] = []
    total_length = sum(item.length_m for item in segments)
    for period in periods:
        choices = [
            option for (_, period_id), option in selected.items() if period_id == period.period_id
        ]
        service = 0.0
        risk = 0.0
        uncertainty = 0.0
        for segment in segments:
            option = selected.get((segment.segment_id, period.period_id))
            weight = segment.length_m / max(total_length, 1e-12)
            service += weight * (option.service_attainment if option else segment.base_service)
            risk += weight * (option.risk if option else segment.base_risk)
            uncertainty += weight * (option.uncertainty if option else segment.base_uncertainty)
        used: dict[str, float] = {}
        for option in choices:
            method = option.method or "none"
            used[method] = used.get(method, 0.0) + option.capacity_units
        summaries.append(
            PeriodSummary(
                period_id=period.period_id,
                cost=sum(item.cost for item in choices),
                budget=period.budget,
                capacity_used=used,
                service_attainment=service,
                risk=risk,
                uncertainty=uncertainty,
                selected_count=len(choices),
            )
        )
    return summaries


def _budget_capacity_violations(
    segments: list[PortfolioSegment],
    periods: list[PortfolioPeriod],
    selected: dict[tuple[str, str], PortfolioOption],
) -> list[PortfolioViolation]:
    violations: list[PortfolioViolation] = []
    for period in periods:
        choices = [
            option for (_, period_id), option in selected.items() if period_id == period.period_id
        ]
        cost = sum(item.cost for item in choices)
        if cost > period.budget + 1e-9:
            violations.append(
                PortfolioViolation(
                    code="BAU-BUDGET",
                    message=f"cost {cost:.2f} exceeds budget {period.budget:.2f}",
                    period_id=period.period_id,
                )
            )
        used: dict[str, float] = {}
        for option in choices:
            method = option.method or "none"
            used[method] = used.get(method, 0.0) + option.capacity_units
        for method_name, value in used.items():
            capacity = period.capacity_by_method.get(method_name, 0.0)
            if value > capacity + 1e-9:
                violations.append(
                    PortfolioViolation(
                        code="BAU-CAPACITY",
                        message=(f"{method_name} capacity {value:.2f} exceeds {capacity:.2f}"),
                        period_id=period.period_id,
                    )
                )
    return violations


__all__ = [
    "BAU_SCHEMA_VERSION",
    "BauComparison",
    "BauConfig",
    "BauError",
    "BauPlan",
    "build_bau_plan",
    "compare_bau",
]
