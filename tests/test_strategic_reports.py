"""Tests for the P6.5 strategic reports."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from brushline.strategic.bau import BauConfig, build_bau_plan, compare_bau
from brushline.strategic.monitoring import (
    MonitoringConfig,
    MonitoringOption,
    MonitoringPolicy,
    MonitoringSpan,
    build_monitoring_policy,
)
from brushline.strategic.portfolio import (
    PortfolioConfig,
    PortfolioOption,
    PortfolioPeriod,
    PortfolioSegment,
    StrategicPortfolio,
    build_strategic_portfolio,
)
from brushline.strategic.reports import (
    ReportError,
    StrategicReport,
    YearRow,
    build_strategic_report,
    load_strategic_report,
    write_strategic_report,
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
            budget=400,
            capacity_by_method={"mowing": 2},
        ),
        PortfolioPeriod(
            period_id="p2",
            start_year=2027,
            budget=400,
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


def _portfolio() -> StrategicPortfolio:
    return build_strategic_portfolio(
        portfolio_id="opt",
        instance_id="tiny",
        segments=_segments(),
        periods=_periods(),
        options=_options(),
        config=PortfolioConfig(service_target=0.7),
        created_utc=NOW,
    )


def _monitoring() -> MonitoringPolicy:
    return build_monitoring_policy(
        policy_id="mon",
        instance_id="tiny",
        spans=[
            MonitoringSpan(
                span_id="sp",
                segment_ids=["s1", "s2"],
                baseline_uncertainty=0.5,
                service_risk=0.5,
                route_m=1000,
            )
        ],
        options=[
            MonitoringOption(
                option_id="lidar",
                span_id="sp",
                sensor="lidar",
                route="full",
                interval_years=1,
                sampling_intensity=0.8,
                cost_per_event=100,
                uncertainty_reduction=0.3,
                risk_reduction=0.2,
            )
        ],
        config=MonitoringConfig(horizon_years=2, start_year=2026, budget=400, value_per_unit=1000),
        created_utc=NOW,
    )


def _report() -> StrategicReport:
    portfolio = _portfolio()
    bau = build_bau_plan(
        policy_id="bau",
        instance_id="tiny",
        segments=_segments(),
        periods=_periods(),
        options=_options(),
        config=BauConfig(cycle_years=1, start_year=2026),
        created_utc=NOW,
    )
    comparison = compare_bau(portfolio, bau, created_utc=NOW)
    return build_strategic_report(
        report_id="report",
        instance_id="tiny",
        portfolio=portfolio,
        monitoring=_monitoring(),
        periods=_periods(),
        bau=bau,
        comparison=comparison,
        created_utc=NOW,
    )


def test_report_has_optimized_and_bau_rows_with_monitoring() -> None:
    """Every year has cost, budget, service, risk, and monitoring values."""
    report = _report()
    assert len(report.rows) == 4
    optimized = [row for row in report.rows if row.scope == "optimized"]
    bau = [row for row in report.rows if row.scope == "bau"]
    assert [row.year for row in optimized] == [2026, 2027]
    assert all(row.monitoring_cost == 100 for row in optimized)
    assert all(row.monitoring_events == 1 for row in optimized)
    assert report.optimized_total_cost == 360
    assert report.bau_total_cost == 360
    assert all(row.total_cost == row.treatment_cost + row.monitoring_cost for row in report.rows)
    assert all(row.budget_remaining >= 0 for row in report.rows)
    assert report.comparison is not None
    assert report.comparison.like_for_like
    assert len(report.caveats) == 4
    assert report.created_utc == NOW
    assert bau[0].risk == pytest.approx(0.2)


def test_report_without_bau_and_over_budget() -> None:
    """A missing BAU is explicit; BAU overruns remain visible."""
    portfolio = _portfolio()
    report = build_strategic_report(
        report_id="report",
        instance_id="tiny",
        portfolio=portfolio,
        monitoring=_monitoring(),
        periods=_periods(),
        created_utc=NOW,
    )
    assert report.bau_total_cost is None
    assert report.comparison is None
    assert all(row.scope == "optimized" for row in report.rows)
    # Use a period with a smaller budget for the overrun.
    tight = [
        period.model_copy(update={"budget": 50}) if period.period_id == "p1" else period
        for period in _periods()
    ]
    tight_portfolio = build_strategic_portfolio(
        portfolio_id="opt2",
        instance_id="tiny",
        segments=_segments(),
        periods=tight,
        options=_options(),
        config=PortfolioConfig(service_target=0.2),
        created_utc=NOW,
    )
    bau_tight = build_bau_plan(
        policy_id="bau2",
        instance_id="tiny",
        segments=_segments(),
        periods=tight,
        options=_options(),
        config=BauConfig(cycle_years=1, start_year=2026, enforce_budget=False),
        created_utc=NOW,
    )
    report = build_strategic_report(
        report_id="tight",
        instance_id="tiny",
        portfolio=tight_portfolio,
        monitoring=build_monitoring_policy(
            policy_id="none",
            instance_id="tiny",
            spans=[],
            options=[],
            created_utc=NOW,
        ),
        periods=tight,
        bau=bau_tight,
        created_utc=NOW,
    )
    assert any(row.budget_remaining < 0 for row in report.rows)
    assert report.rows[0].scope == "optimized"


def test_report_errors_and_model_guards(tmp_path: Path) -> None:
    """Mismatched scopes, event years, and row totals fail explicitly."""
    portfolio = _portfolio()
    with pytest.raises(ReportError, match="instance"):
        build_strategic_report(
            report_id="x",
            instance_id="other",
            portfolio=portfolio,
            monitoring=_monitoring(),
            periods=_periods(),
            created_utc=NOW,
        )
    with pytest.raises(ReportError, match="period"):
        build_strategic_report(
            report_id="x",
            instance_id="tiny",
            portfolio=portfolio,
            monitoring=_monitoring(),
            periods=_periods()[:1],
            created_utc=NOW,
        )
    outside = _monitoring().model_copy(
        update={
            "decisions": [_monitoring().decisions[0].model_copy(update={"event_years": [2030]})]
        }
    )
    with pytest.raises(ReportError, match="event year"):
        build_strategic_report(
            report_id="x",
            instance_id="tiny",
            portfolio=portfolio,
            monitoring=outside,
            periods=_periods(),
            created_utc=NOW,
        )
    bau = build_bau_plan(
        policy_id="bau",
        instance_id="other",
        segments=_segments(),
        periods=_periods(),
        options=_options(),
        created_utc=NOW,
    )
    with pytest.raises(ReportError, match="BAU"):
        build_strategic_report(
            report_id="x",
            instance_id="tiny",
            portfolio=portfolio,
            monitoring=_monitoring(),
            periods=_periods(),
            bau=bau,
            created_utc=NOW,
        )
    with pytest.raises(ValidationError):
        YearRow(
            scope="optimized",
            year=2026,
            period_id="p1",
            treatment_cost=10,
            monitoring_cost=1,
            total_cost=20,
            budget=100,
            budget_remaining=90,
            service_attainment=1,
            risk=0,
            uncertainty=0,
            monitoring_events=0,
        )
    report = _report()
    path = tmp_path / "report.json"
    assert write_strategic_report(report, path) == path
    assert load_strategic_report(path) == report
    with pytest.raises(ValidationError):
        StrategicReport(
            report_id="x",
            instance_id="x",
            rows=[report.rows[0]],
            optimized_total_cost=1,
            created_utc=datetime(2026, 11, 14),
        )
