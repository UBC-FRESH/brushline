"""Tests for the P6.2 strategic network portfolio."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from brushline.strategic.portfolio import (
    PortfolioConfig,
    PortfolioError,
    PortfolioOption,
    PortfolioPeriod,
    PortfolioSegment,
    StrategicPortfolio,
    build_strategic_portfolio,
    validate_portfolio_inputs,
)
from pydantic import ValidationError

NOW = datetime(2026, 11, 14, tzinfo=UTC)


def _segments() -> list[PortfolioSegment]:
    return [
        PortfolioSegment(
            segment_id="s1",
            span_id="sp",
            sequence=0,
            length_m=100,
            base_service=0.2,
            base_risk=0.8,
            base_uncertainty=0.5,
        ),
        PortfolioSegment(
            segment_id="s2",
            span_id="sp",
            sequence=1,
            length_m=100,
            base_service=0.3,
            base_risk=0.7,
            base_uncertainty=0.5,
        ),
    ]


def _periods() -> list[PortfolioPeriod]:
    return [
        PortfolioPeriod(
            period_id="p1",
            start_year=2026,
            budget=100,
            capacity_by_method={"mowing": 2, "manual": 2},
        ),
        PortfolioPeriod(
            period_id="p2",
            start_year=2027,
            budget=100,
            capacity_by_method={"mowing": 2, "manual": 2},
        ),
    ]


def _options() -> list[PortfolioOption]:
    options: list[PortfolioOption] = []
    for segment in ("s1", "s2"):
        for period in ("p1", "p2"):
            options.append(
                PortfolioOption(
                    option_id=f"{segment}-{period}-mow",
                    segment_id=segment,
                    period_id=period,
                    action_id="mow",
                    method="mowing",
                    cost=40,
                    capacity_units=1,
                    service_attainment=0.8,
                    risk=0.2,
                    uncertainty=0.3,
                )
            )
            options.append(
                PortfolioOption(
                    option_id=f"{segment}-{period}-manual",
                    segment_id=segment,
                    period_id=period,
                    action_id="manual",
                    method="manual",
                    cost=80,
                    capacity_units=1,
                    service_attainment=0.9,
                    risk=0.15,
                    uncertainty=0.25,
                )
            )
    return options


def _plan(
    config: PortfolioConfig | None = None,
    *,
    segments: list[PortfolioSegment] | None = None,
    periods: list[PortfolioPeriod] | None = None,
    options: list[PortfolioOption] | None = None,
) -> StrategicPortfolio:
    return build_strategic_portfolio(
        portfolio_id="p6-portfolio",
        instance_id="tiny",
        segments=segments if segments is not None else _segments(),
        periods=periods if periods is not None else _periods(),
        options=options if options is not None else _options(),
        config=config,
        created_utc=NOW,
    )


def test_portfolio_meets_service_budget_and_continuity() -> None:
    """A feasible portfolio selects options and reports the vector separately."""
    plan = _plan(PortfolioConfig(service_target=0.7, risk_target=0.4))
    assert plan.feasible
    assert len(plan.selections) == 4
    assert plan.total_cost == 160
    assert plan.service_attainment == pytest.approx(0.8)
    assert plan.risk == pytest.approx(0.2)
    assert plan.uncertainty == pytest.approx(0.3)
    assert plan.continuity_score == pytest.approx(1.0)
    assert plan.baseline_service == pytest.approx(0.25)
    assert plan.baseline_risk == pytest.approx(0.75)
    assert all(item.cost <= item.budget for item in plan.period_summary)
    assert all(item.selected_count == 2 for item in plan.period_summary)
    assert plan.period_summary[0].capacity_used == {"mowing": 2.0}
    assert plan.created_utc == NOW


def test_service_repair_reports_infeasibility_without_hiding_it() -> None:
    """A service target beyond the budget/capacity is a hard violation."""
    periods = [item.model_copy(update={"budget": 40}) for item in _periods()]
    plan = _plan(
        PortfolioConfig(service_target=0.9),
        periods=periods,
    )
    assert not plan.feasible
    assert any(v.code == "PORTFOLIO-SERVICE" for v in plan.violations)
    assert plan.service_attainment < 0.9


def test_capacity_and_risk_targets() -> None:
    """Capacity limits and the soft risk target are reported."""
    periods = [
        item.model_copy(update={"capacity_by_method": {"mowing": 1, "manual": 1}})
        for item in _periods()
    ]
    plan = _plan(
        PortfolioConfig(service_target=0.7),
        periods=periods,
    )
    assert not plan.feasible
    assert any(v.code == "PORTFOLIO-SERVICE" for v in plan.violations)
    risky = _plan(PortfolioConfig(service_target=0.7, risk_target=0.1))
    assert risky.feasible
    assert any(v.code == "PORTFOLIO-RISK" for v in risky.soft_violations)


def test_baseline_and_invalid_inputs() -> None:
    """A no-option plan is explicit; invalid references and models fail."""
    baseline = _plan(PortfolioConfig(service_target=0.2), options=[])
    assert baseline.feasible
    assert baseline.selections == []
    assert baseline.total_cost == 0
    with pytest.raises(PortfolioError):
        _plan(
            options=[
                PortfolioOption(
                    option_id="bad",
                    segment_id="missing",
                    period_id="p1",
                    action_id="none",
                    cost=0,
                    service_attainment=0,
                    risk=1,
                    uncertainty=1,
                )
            ]
        )
    with pytest.raises(PortfolioError):
        _plan(
            options=[
                PortfolioOption(
                    option_id="bad",
                    segment_id="s1",
                    period_id="missing",
                    action_id="none",
                    cost=0,
                    service_attainment=0,
                    risk=1,
                    uncertainty=1,
                )
            ]
        )
    duplicate = _options()[0]
    with pytest.raises(PortfolioError):
        _plan(options=[duplicate, duplicate])
    assert not validate_portfolio_inputs(_segments(), _periods(), [duplicate, duplicate]).is_valid
    with pytest.raises(ValidationError):
        PortfolioOption(
            option_id="bad",
            segment_id="s1",
            period_id="p1",
            action_id="none",
            method=None,
            cost=1,
            service_attainment=0,
            risk=0,
            uncertainty=0,
        )
    with pytest.raises(ValidationError):
        PortfolioConfig(service_target=-1)


def test_sparse_selection_and_local_swap() -> None:
    """A single selected segment has zero continuity; a better swap is applied."""
    options = [
        PortfolioOption(
            option_id="s1-p1-mow",
            segment_id="s1",
            period_id="p1",
            action_id="mow",
            method="mowing",
            cost=80,
            capacity_units=1,
            service_attainment=0.8,
            risk=0.2,
            uncertainty=0.3,
        ),
        PortfolioOption(
            option_id="s1-p1-manual",
            segment_id="s1",
            period_id="p1",
            action_id="manual",
            method="manual",
            cost=70,
            capacity_units=1,
            service_attainment=0.85,
            risk=0.15,
            uncertainty=0.2,
        ),
    ]
    plan = _plan(
        PortfolioConfig(service_target=0.1, continuity_weight=0),
        segments=[_segments()[0]],
        periods=[_periods()[0]],
        options=options,
    )
    assert plan.continuity_score == 0
    assert plan.selections[0].option_id == "s1-p1-manual"
