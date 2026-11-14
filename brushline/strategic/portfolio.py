"""Strategic network portfolio selection.

The portfolio chooses at most one strategic option for each segment and period under period
budgets, method capacities, a service-level target, a risk target, and a spatial-continuity
preference. It uses a deterministic service-repair pass followed by budget-preserving improvement
and local swaps.
"""

from __future__ import annotations

import itertools
from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from brushline.model.state import TreatmentMethod
from brushline.model.validation import ContractValidation, check_duplicates

PORTFOLIO_SCHEMA_VERSION: Literal["brushline.strategic-portfolio.v1"] = (
    "brushline.strategic-portfolio.v1"
)


class PortfolioError(ValueError):
    """Raised when portfolio data or constraints are inconsistent."""


class PortfolioSegment(BaseModel):
    """One segment in a strategic portfolio.

    Parameters
    ----------
    segment_id : str
        Segment id.
    span_id : str
        Span id.
    sequence : int
        Position within the span.
    length_m : float
        Segment length.
    base_service : float
        No-treatment service attainment.
    base_risk : float
        No-treatment risk.
    base_uncertainty : float
        No-treatment uncertainty.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    segment_id: str = Field(min_length=1)
    span_id: str = Field(min_length=1)
    sequence: int = Field(ge=0)
    length_m: float = Field(gt=0)
    base_service: float = Field(ge=0, le=1)
    base_risk: float = Field(ge=0, le=1)
    base_uncertainty: float = Field(ge=0, le=1)


class PortfolioPeriod(BaseModel):
    """One strategic period.

    Parameters
    ----------
    period_id : str
        Period id.
    start_year : int
        Year.
    budget : float
        Treatment budget.
    capacity_by_method : dict of str to float
        Capacity units by method.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    period_id: str = Field(min_length=1)
    start_year: int = Field(ge=1900, le=2200)
    budget: float = Field(ge=0)
    capacity_by_method: dict[str, float] = Field(default_factory=dict)


class PortfolioOption(BaseModel):
    """One selectable segment-period option.

    Parameters
    ----------
    option_id : str
        Stable option id.
    segment_id : str
        Segment id.
    period_id : str
        Period id.
    action_id : str
        Strategic action id.
    method : str or None
        Treatment method.
    cost : float
        Cost.
    capacity_units : float
        Capacity consumption.
    service_attainment : float
        Service outcome.
    risk : float
        Risk outcome.
    uncertainty : float
        Uncertainty outcome.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    option_id: str = Field(min_length=1)
    segment_id: str = Field(min_length=1)
    period_id: str = Field(min_length=1)
    action_id: str = Field(min_length=1)
    method: TreatmentMethod | None = None
    cost: float = Field(ge=0)
    capacity_units: float = Field(default=0, ge=0)
    service_attainment: float = Field(ge=0, le=1)
    risk: float = Field(ge=0, le=1)
    uncertainty: float = Field(ge=0, le=1)

    @model_validator(mode="after")
    def _method(self) -> PortfolioOption:
        if self.method is None and self.cost != 0:
            raise ValueError("a no-treatment option must have zero cost")
        return self


class PortfolioConfig(BaseModel):
    """Portfolio weights and targets.

    Parameters
    ----------
    service_target : float
        Hard aggregate service target.
    risk_target : float
        Soft aggregate risk target.
    service_weight : float
        Objective weight.
    risk_weight : float
        Objective weight.
    uncertainty_weight : float
        Objective weight.
    cost_weight : float
        Objective weight per cost unit.
    continuity_weight : float
        Penalty for missing adjacent treatment pairs.
    max_steps : int
        Maximum improvement steps.
    seed : int
        Deterministic scenario seed.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    service_target: float = Field(default=0.5, ge=0, le=1)
    risk_target: float = Field(default=1.0, ge=0, le=1)
    service_weight: float = Field(default=1.0, ge=0)
    risk_weight: float = Field(default=1.0, ge=0)
    uncertainty_weight: float = Field(default=0.5, ge=0)
    cost_weight: float = Field(default=0.001, ge=0)
    continuity_weight: float = Field(default=0.1, ge=0)
    max_steps: int = Field(default=100, ge=1, le=10000)
    seed: int = 1


class PortfolioViolation(BaseModel):
    """One named portfolio violation.

    Parameters
    ----------
    code : str
        Violation code.
    message : str
        Human explanation.
    period_id : str or None
        Period.
    segment_id : str or None
        Segment.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    code: str = Field(min_length=1)
    message: str = Field(min_length=1)
    period_id: str | None = None
    segment_id: str | None = None


class PortfolioSelection(BaseModel):
    """One selected option.

    Parameters
    ----------
    option_id : str
        Option id.
    segment_id : str
        Segment id.
    period_id : str
        Period id.
    action_id : str
        Action id.
    cost : float
        Cost.
    service_attainment : float
        Service outcome.
    risk : float
        Risk outcome.
    uncertainty : float
        Uncertainty outcome.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    option_id: str
    segment_id: str
    period_id: str
    action_id: str
    cost: float = Field(ge=0)
    service_attainment: float = Field(ge=0, le=1)
    risk: float = Field(ge=0, le=1)
    uncertainty: float = Field(ge=0, le=1)


class PeriodSummary(BaseModel):
    """One period's portfolio totals.

    Parameters
    ----------
    period_id : str
        Period.
    cost : float
        Selected cost.
    budget : float
        Period budget.
    capacity_used : dict of str to float
        Capacity used by method.
    service_attainment : float
        Length-weighted service.
    risk : float
        Length-weighted risk.
    uncertainty : float
        Length-weighted uncertainty.
    selected_count : int
        Selected options.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    period_id: str
    cost: float = Field(ge=0)
    budget: float = Field(ge=0)
    capacity_used: dict[str, float] = Field(default_factory=dict)
    service_attainment: float = Field(ge=0, le=1)
    risk: float = Field(ge=0, le=1)
    uncertainty: float = Field(ge=0, le=1)
    selected_count: int = Field(ge=0)


class StrategicPortfolio(BaseModel):
    """A solved strategic portfolio.

    Parameters
    ----------
    schema_version : {"brushline.strategic-portfolio.v1"}
        Schema version.
    portfolio_id : str
        Portfolio id.
    instance_id : str
        Instance id.
    config : PortfolioConfig
        Weights and targets.
    selections : list of PortfolioSelection
        Selected options.
    period_summary : list of PeriodSummary
        Period totals.
    total_cost : float
        Total cost.
    service_attainment : float
        Aggregate service.
    risk : float
        Aggregate risk.
    uncertainty : float
        Aggregate uncertainty.
    baseline_service : float
        No-treatment service.
    baseline_risk : float
        No-treatment risk.
    baseline_uncertainty : float
        No-treatment uncertainty.
    continuity_score : float
        Share of adjacent pairs with both treatments selected.
    objective : float
        Weighted portfolio objective.
    feasible : bool
        Hard constraints satisfied.
    violations : list of PortfolioViolation
        Hard violations.
    soft_violations : list of PortfolioViolation
        Soft violations.
    created_utc : datetime
        Timezone-aware creation time.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["brushline.strategic-portfolio.v1"] = PORTFOLIO_SCHEMA_VERSION
    portfolio_id: str
    instance_id: str
    config: PortfolioConfig
    selections: list[PortfolioSelection]
    period_summary: list[PeriodSummary]
    total_cost: float = Field(ge=0)
    service_attainment: float = Field(ge=0, le=1)
    risk: float = Field(ge=0, le=1)
    uncertainty: float = Field(ge=0, le=1)
    baseline_service: float = Field(ge=0, le=1)
    baseline_risk: float = Field(ge=0, le=1)
    baseline_uncertainty: float = Field(ge=0, le=1)
    continuity_score: float = Field(ge=0, le=1)
    objective: float
    feasible: bool
    violations: list[PortfolioViolation] = Field(default_factory=list)
    soft_violations: list[PortfolioViolation] = Field(default_factory=list)
    created_utc: datetime


def validate_portfolio_inputs(
    segments: list[PortfolioSegment],
    periods: list[PortfolioPeriod],
    options: list[PortfolioOption],
) -> ContractValidation:
    """Validate segment/period references, option uniqueness, and non-negativity.

    Parameters
    ----------
    segments : list of PortfolioSegment
        Segments.
    periods : list of PortfolioPeriod
        Periods.
    options : list of PortfolioOption
        Options.

    Returns
    -------
    ContractValidation
        Errors and counts.
    """
    errors: list[str] = []
    warnings: list[str] = []
    check_duplicates("PORTFOLIO", "segment", [item.segment_id for item in segments], errors)
    check_duplicates("PORTFOLIO", "period", [item.period_id for item in periods], errors)
    check_duplicates("PORTFOLIO", "option", [item.option_id for item in options], errors)
    segment_ids = {item.segment_id for item in segments}
    period_ids = {item.period_id for item in periods}
    for option in options:
        if option.segment_id not in segment_ids:
            errors.append(f"PORTFOLIO-SEGMENT: option {option.option_id} has unknown segment")
        if option.period_id not in period_ids:
            errors.append(f"PORTFOLIO-PERIOD: option {option.option_id} has unknown period")
    keys = [(item.segment_id, item.period_id, item.option_id) for item in options]
    check_duplicates("PORTFOLIO", "segment-period-option", [str(item) for item in keys], errors)
    if not options:
        warnings.append("PORTFOLIO-EMPTY: no options are available")
    return ContractValidation(
        tuple(errors),
        tuple(warnings),
        {"segments": len(segments), "periods": len(periods), "options": len(options)},
    )


def build_strategic_portfolio(
    *,
    portfolio_id: str,
    instance_id: str,
    segments: list[PortfolioSegment],
    periods: list[PortfolioPeriod],
    options: list[PortfolioOption],
    config: PortfolioConfig | None = None,
    created_utc: datetime | None = None,
) -> StrategicPortfolio:
    """Build and improve a strategic portfolio.

    Parameters
    ----------
    portfolio_id : str
        Portfolio id.
    instance_id : str
        Instance id.
    segments : list of PortfolioSegment
        Segments.
    periods : list of PortfolioPeriod
        Periods.
    options : list of PortfolioOption
        Selectable options.
    config : PortfolioConfig, optional
        Targets and weights.
    created_utc : datetime, optional
        Creation time.

    Returns
    -------
    StrategicPortfolio
        Selected portfolio and report.

    Raises
    ------
    PortfolioError
        When inputs are invalid.
    """
    validation = validate_portfolio_inputs(segments, periods, options)
    if not validation.is_valid:
        raise PortfolioError("; ".join(validation.errors))
    rules = config or PortfolioConfig()
    by_key: dict[tuple[str, str], list[PortfolioOption]] = {}
    for option in options:
        by_key.setdefault((option.segment_id, option.period_id), []).append(option)
    for key in by_key:
        by_key[key].sort(key=lambda item: item.option_id)
    selected: dict[tuple[str, str], PortfolioOption] = {}
    period_map = {item.period_id: item for item in periods}
    for _ in range(rules.max_steps):
        current = _aggregate(segments, periods, selected, rules)
        if current.service < rules.service_target - 1e-12:
            candidate = _best_feasible(
                segments,
                periods,
                by_key,
                selected,
                rules,
                service_priority=True,
            )
        else:
            candidate = _best_feasible(
                segments,
                periods,
                by_key,
                selected,
                rules,
                service_priority=False,
            )
        if candidate is None:
            break
        key = (candidate.segment_id, candidate.period_id)
        if selected.get(key) == candidate:
            break
        selected[key] = candidate
    # Try swap improvements for the same segment and period.
    for _ in range(rules.max_steps):
        current = _aggregate(segments, periods, selected, rules)
        best: tuple[float, PortfolioOption, tuple[str, str]] | None = None
        for key, choice in list(selected.items()):
            for candidate in by_key.get(key, []):
                if candidate.option_id == choice.option_id:
                    continue
                trial = dict(selected)
                trial[key] = candidate
                if not _resources_ok(segments, periods, trial, rules, period_map):
                    continue
                score = _aggregate(segments, periods, trial, rules).objective
                if score > current.objective + 1e-12 and (best is None or score > best[0] + 1e-12):
                    best = (score, candidate, key)
        if best is None:
            break
        _, candidate, key = best
        selected[key] = candidate
    summary = _aggregate(segments, periods, selected, rules)
    violations = list(summary.violations)
    soft = list(summary.soft_violations)
    period_summary = []
    for period in periods:
        period_selection = [
            item for (segment, period_id), item in selected.items() if period_id == period.period_id
        ]
        period_summary.append(
            PeriodSummary(
                period_id=period.period_id,
                cost=sum(item.cost for item in period_selection),
                budget=period.budget,
                capacity_used=_capacity_used(period_selection),
                service_attainment=_weighted_period(
                    segments, period.period_id, selected, "service"
                ),
                risk=_weighted_period(segments, period.period_id, selected, "risk"),
                uncertainty=_weighted_period(segments, period.period_id, selected, "uncertainty"),
                selected_count=len(period_selection),
            )
        )
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
    return StrategicPortfolio(
        portfolio_id=portfolio_id,
        instance_id=instance_id,
        config=rules,
        selections=selections,
        period_summary=period_summary,
        total_cost=summary.cost,
        service_attainment=summary.service,
        risk=summary.risk,
        uncertainty=summary.uncertainty,
        baseline_service=summary.baseline_service,
        baseline_risk=summary.baseline_risk,
        baseline_uncertainty=summary.baseline_uncertainty,
        continuity_score=summary.continuity,
        objective=summary.objective,
        feasible=not violations,
        violations=violations,
        soft_violations=soft,
        created_utc=created_utc or datetime.now(UTC),
    )


class _Aggregate(BaseModel):
    cost: float
    service: float
    risk: float
    uncertainty: float
    baseline_service: float
    baseline_risk: float
    baseline_uncertainty: float
    continuity: float
    objective: float
    violations: list[PortfolioViolation]
    soft_violations: list[PortfolioViolation]


def _aggregate(
    segments: list[PortfolioSegment],
    periods: list[PortfolioPeriod],
    selected: dict[tuple[str, str], PortfolioOption],
    rules: PortfolioConfig,
) -> _Aggregate:
    total_weight = sum(item.length_m for item in segments) * max(len(periods), 1)
    service = 0.0
    risk = 0.0
    uncertainty = 0.0
    cost = 0.0
    for segment in segments:
        for period in periods:
            choice = selected.get((segment.segment_id, period.period_id))
            value_service = choice.service_attainment if choice else segment.base_service
            value_risk = choice.risk if choice else segment.base_risk
            value_uncertainty = choice.uncertainty if choice else segment.base_uncertainty
            weight = segment.length_m / max(total_weight, 1e-12)
            service += weight * value_service
            risk += weight * value_risk
            uncertainty += weight * value_uncertainty
            cost += choice.cost if choice else 0.0
    continuity = _continuity(segments, selected)
    objective = (
        rules.service_weight * service
        - rules.risk_weight * risk
        - rules.uncertainty_weight * uncertainty
        - rules.cost_weight * cost
        - rules.continuity_weight * (1.0 - continuity)
    )
    violations = _resource_violations(segments, periods, selected)
    if service < rules.service_target - 1e-12:
        violations.append(
            PortfolioViolation(
                code="PORTFOLIO-SERVICE",
                message=f"service {service:.3f} is below target {rules.service_target:.3f}",
            )
        )
    soft = []
    if risk > rules.risk_target + 1e-12:
        soft.append(
            PortfolioViolation(
                code="PORTFOLIO-RISK",
                message=f"risk {risk:.3f} is above target {rules.risk_target:.3f}",
            )
        )
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
    return _Aggregate(
        cost=cost,
        service=service,
        risk=risk,
        uncertainty=uncertainty,
        baseline_service=baseline_service,
        baseline_risk=baseline_risk,
        baseline_uncertainty=baseline_uncertainty,
        continuity=continuity,
        objective=objective,
        violations=violations,
        soft_violations=soft,
    )


def _best_feasible(
    segments: list[PortfolioSegment],
    periods: list[PortfolioPeriod],
    by_key: dict[tuple[str, str], list[PortfolioOption]],
    selected: dict[tuple[str, str], PortfolioOption],
    rules: PortfolioConfig,
    *,
    service_priority: bool,
) -> PortfolioOption | None:
    current = _aggregate(segments, periods, selected, rules)
    best: tuple[float, PortfolioOption] | None = None
    for key, options in by_key.items():
        for candidate in options:
            if selected.get(key) == candidate:
                continue
            trial = dict(selected)
            trial[key] = candidate
            if not _resources_ok(
                segments, periods, trial, rules, {p.period_id: p for p in periods}
            ):
                continue
            result = _aggregate(segments, periods, trial, rules)
            if service_priority:
                gain = candidate.service_attainment - (
                    selected[key].service_attainment
                    if key in selected
                    else next(
                        item.base_service
                        for item in segments
                        if item.segment_id == candidate.segment_id
                    )
                )
                if gain <= 0:
                    continue
                score = gain / max(candidate.cost, 1.0)
            else:
                score = result.objective - current.objective
            if (
                best is None
                or score > best[0] + 1e-12
                or (abs(score - best[0]) <= 1e-12 and candidate.option_id < best[1].option_id)
            ):
                best = (score, candidate)
    if best is None or (not service_priority and best[0] <= 1e-12):
        return None
    return best[1]


def _resources_ok(
    segments: list[PortfolioSegment],
    periods: list[PortfolioPeriod],
    selected: dict[tuple[str, str], PortfolioOption],
    rules: PortfolioConfig,
    period_map: dict[str, PortfolioPeriod],
) -> bool:
    for period in periods:
        period_cost = sum(
            option.cost
            for (segment_id, period_id), option in selected.items()
            if period_id == period.period_id
        )
        if period_cost > period.budget + 1e-9:
            return False
        used = _capacity_used(
            [option for (_, period_id), option in selected.items() if period_id == period.period_id]
        )
        for method, value in used.items():
            capacity = period.capacity_by_method.get(method, 0.0)
            if value > capacity + 1e-9:
                return False
    return True


def _capacity_used(options: list[PortfolioOption]) -> dict[str, float]:
    used: dict[str, float] = {}
    for option in options:
        method = option.method or "none"
        used[method] = used.get(method, 0.0) + option.capacity_units
    return used


def _resource_violations(
    segments: list[PortfolioSegment],
    periods: list[PortfolioPeriod],
    selected: dict[tuple[str, str], PortfolioOption],
) -> list[PortfolioViolation]:
    violations: list[PortfolioViolation] = []
    for period in periods:
        period_options = [
            option for (_, period_id), option in selected.items() if period_id == period.period_id
        ]
        cost = sum(option.cost for option in period_options)
        if cost > period.budget + 1e-9:
            violations.append(
                PortfolioViolation(
                    code="PORTFOLIO-BUDGET",
                    message=f"cost {cost:.2f} exceeds budget {period.budget:.2f}",
                    period_id=period.period_id,
                )
            )
        for method, used in _capacity_used(period_options).items():
            capacity = period.capacity_by_method.get(method, 0.0)
            if used > capacity + 1e-9:
                violations.append(
                    PortfolioViolation(
                        code="PORTFOLIO-CAPACITY",
                        message=f"{method} capacity {used:.2f} exceeds {capacity:.2f}",
                        period_id=period.period_id,
                    )
                )
    return violations


def _continuity(
    segments: list[PortfolioSegment], selected: dict[tuple[str, str], PortfolioOption]
) -> float:
    pairs = 0
    hits = 0
    by_span: dict[str, list[PortfolioSegment]] = {}
    for segment in segments:
        by_span.setdefault(segment.span_id, []).append(segment)
    periods = {period_id for _, period_id in selected}
    for span_segments in by_span.values():
        ordered = sorted(span_segments, key=lambda item: item.sequence)
        for left, right in itertools.pairwise(ordered):
            for period_id in periods:
                pairs += 1
                if (left.segment_id, period_id) in selected and (
                    right.segment_id,
                    period_id,
                ) in selected:
                    hits += 1
    return 0.0 if pairs == 0 else hits / pairs


def _weighted_period(
    segments: list[PortfolioSegment],
    period_id: str,
    selected: dict[tuple[str, str], PortfolioOption],
    field: str,
) -> float:
    total = sum(item.length_m for item in segments)
    value = 0.0
    for segment in segments:
        choice = selected.get((segment.segment_id, period_id))
        if choice is None:
            base = {
                "service": segment.base_service,
                "risk": segment.base_risk,
                "uncertainty": segment.base_uncertainty,
            }[field]
        else:
            base = getattr(choice, field if field != "service" else "service_attainment")
        value += segment.length_m * base
    return min(1.0, max(0.0, value / max(total, 1e-12)))


__all__ = [
    "PORTFOLIO_SCHEMA_VERSION",
    "PeriodSummary",
    "PortfolioConfig",
    "PortfolioError",
    "PortfolioOption",
    "PortfolioPeriod",
    "PortfolioSegment",
    "PortfolioSelection",
    "PortfolioViolation",
    "StrategicPortfolio",
    "build_strategic_portfolio",
    "validate_portfolio_inputs",
]
