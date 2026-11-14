"""Tests for the P6.4 business-as-usual baseline."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from brushline.strategic.bau import (
    BauConfig,
    BauError,
    BauPlan,
    build_bau_plan,
    compare_bau,
)
from brushline.strategic.portfolio import (
    PortfolioConfig,
    PortfolioOption,
    PortfolioPeriod,
    PortfolioSegment,
    StrategicPortfolio,
    build_strategic_portfolio,
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
            capacity_by_method={"mowing": 2},
        ),
        PortfolioPeriod(
            period_id="p2",
            start_year=2027,
            budget=100,
            capacity_by_method={"mowing": 2},
        ),
    ]


def _options() -> list[PortfolioOption]:
    return [
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
        for segment in ("s1", "s2")
        for period in ("p1", "p2")
    ]


def _bau(
    config: BauConfig | None = None,
    *,
    options: list[PortfolioOption] | None = None,
) -> BauPlan:
    return build_bau_plan(
        policy_id="bau-v1",
        instance_id="tiny",
        segments=_segments(),
        periods=_periods(),
        options=_options() if options is None else options,
        config=config,
        created_utc=NOW,
    )


def _optimized() -> StrategicPortfolio:
    return build_strategic_portfolio(
        portfolio_id="opt-v1",
        instance_id="tiny",
        segments=_segments(),
        periods=_periods(),
        options=_options(),
        config=PortfolioConfig(service_target=0.7),
        created_utc=NOW,
    )


def test_annual_bau_is_like_for_like_and_comparable() -> None:
    """A one-year cycle matches the optimized plan at the same options."""
    optimized = _optimized()
    bau = _bau(BauConfig(cycle_years=1, start_year=2026))
    assert bau.feasible
    assert len(bau.selections) == 4
    assert bau.total_cost == 160
    assert bau.service_attainment == pytest.approx(0.8)
    assert bau.risk == pytest.approx(0.2)
    assert bau.uncertainty == pytest.approx(0.3)
    comparison = compare_bau(optimized, bau, created_utc=NOW)
    assert comparison.like_for_like
    assert comparison.present_cost_delta == pytest.approx(0)
    assert comparison.service_delta == pytest.approx(0)
    assert comparison.risk_delta == pytest.approx(0)
    assert comparison.uncertainty_delta == pytest.approx(0)
    assert comparison.optimized_feasible
    assert comparison.bau_feasible


def test_fixed_cycle_reports_a_weaker_baseline() -> None:
    """A four-year cycle only treats the first period and reports the difference."""
    bau = _bau(BauConfig(cycle_years=4, start_year=2026))
    assert bau.feasible
    assert len(bau.selections) == 2
    assert bau.total_cost == 80
    assert bau.service_attainment == pytest.approx(0.525)
    comparison = compare_bau(_optimized(), bau, created_utc=NOW)
    assert comparison.like_for_like
    assert comparison.present_cost_delta == pytest.approx(-80)
    assert comparison.service_delta == pytest.approx(0.275)


def test_budget_truncation_and_unenforced_violations() -> None:
    """Budget enforcement is explicit; disabling it reports the violations."""
    periods = [item.model_copy(update={"budget": 50}) for item in _periods()]
    bau = build_bau_plan(
        policy_id="bau-v1",
        instance_id="tiny",
        segments=_segments(),
        periods=periods,
        options=_options(),
        config=BauConfig(cycle_years=1, start_year=2026),
        created_utc=NOW,
    )
    assert not bau.feasible
    assert any(v.code == "BAU-TRUNCATED" for v in bau.violations)
    assert all(item.cost <= 50 for item in bau.period_summary)
    unenforced = build_bau_plan(
        policy_id="bau-v1",
        instance_id="tiny",
        segments=_segments(),
        periods=periods,
        options=_options(),
        config=BauConfig(cycle_years=1, start_year=2026, enforce_budget=False),
        created_utc=NOW,
    )
    assert not unenforced.feasible
    assert any(v.code == "BAU-BUDGET" for v in unenforced.violations)


def test_capacity_and_action_filters() -> None:
    """Capacity limits and an explicit action id are respected."""
    periods = [item.model_copy(update={"capacity_by_method": {"mowing": 1}}) for item in _periods()]
    bau = build_bau_plan(
        policy_id="bau-v1",
        instance_id="tiny",
        segments=_segments(),
        periods=periods,
        options=_options(),
        config=BauConfig(cycle_years=1, start_year=2026),
        created_utc=NOW,
    )
    assert not bau.feasible
    assert any(v.code == "BAU-TRUNCATED" for v in bau.violations)
    missing_action = _bau(BauConfig(cycle_years=1, start_year=2026, action_id="manual"))
    assert missing_action.selections == []


def test_empty_and_invalid_inputs() -> None:
    """No options and mismatched segments are explicit."""
    empty = _bau(options=[])
    assert empty.selections == []
    assert empty.feasible
    with pytest.raises(BauError):
        build_bau_plan(
            policy_id="bau-v1",
            instance_id="tiny",
            segments=_segments(),
            periods=_periods(),
            options=[
                PortfolioOption(
                    option_id="bad",
                    segment_id="missing",
                    period_id="p1",
                    action_id="mow",
                    method="mowing",
                    cost=1,
                    service_attainment=1,
                    risk=0,
                    uncertainty=0,
                )
            ],
            created_utc=NOW,
        )
    with pytest.raises(ValidationError):
        BauConfig(cycle_years=0)
    other = _optimized().model_copy(update={"instance_id": "other"})
    assert not compare_bau(other, _bau(), created_utc=NOW).like_for_like
