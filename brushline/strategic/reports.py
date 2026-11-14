"""Strategic report: yearly cost, budget, service, risk, uncertainty, and BAU comparison."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from brushline.strategic.bau import BauComparison, BauPlan
from brushline.strategic.monitoring import MonitoringPolicy
from brushline.strategic.portfolio import PortfolioPeriod, StrategicPortfolio

REPORT_SCHEMA_VERSION: Literal["brushline.strategic-report.v1"] = "brushline.strategic-report.v1"


class ReportError(ValueError):
    """Raised when a strategic report is inconsistent."""


class YearRow(BaseModel):
    """One scope/year report row.

    Parameters
    ----------
    scope : {"optimized", "bau"}
        Report scope.
    year : int
        Calendar year.
    period_id : str
        Period id.
    treatment_cost : float
        Treatment cost.
    monitoring_cost : float
        Allocated monitoring cost.
    total_cost : float
        Total cost.
    budget : float
        Period budget.
    budget_remaining : float
        Budget remaining; negative means an overrun.
    service_attainment : float
        Service.
    risk : float
        Risk.
    uncertainty : float
        Uncertainty.
    monitoring_events : int
        Monitoring events allocated to the year.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    scope: Literal["optimized", "bau"]
    year: int = Field(ge=1900, le=2200)
    period_id: str
    treatment_cost: float = Field(ge=0)
    monitoring_cost: float = Field(ge=0)
    total_cost: float = Field(ge=0)
    budget: float = Field(ge=0)
    budget_remaining: float
    service_attainment: float = Field(ge=0, le=1)
    risk: float = Field(ge=0, le=1)
    uncertainty: float = Field(ge=0, le=1)
    monitoring_events: int = Field(ge=0)

    @model_validator(mode="after")
    def _totals(self) -> YearRow:
        expected = self.treatment_cost + self.monitoring_cost
        if abs(expected - self.total_cost) > 1e-9:
            raise ValueError("total_cost must equal treatment_cost + monitoring_cost")
        return self


class StrategicReport(BaseModel):
    """A deterministic strategic report.

    Parameters
    ----------
    schema_version : {"brushline.strategic-report.v1"}
        Schema version.
    report_id : str
        Report id.
    instance_id : str
        Instance id.
    rows : list of YearRow
        Optimized and optional BAU rows.
    optimized_total_cost : float
        Optimized total cost.
    bau_total_cost : float or None
        BAU total cost.
    comparison : BauComparison or None
        Optimized/BAU comparison.
    caveats : list of str
        Report caveats.
    created_utc : datetime
        Timezone-aware time.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["brushline.strategic-report.v1"] = REPORT_SCHEMA_VERSION
    report_id: str
    instance_id: str
    rows: list[YearRow] = Field(min_length=1)
    optimized_total_cost: float = Field(ge=0)
    bau_total_cost: float | None = Field(default=None, ge=0)
    comparison: BauComparison | None = None
    caveats: list[str] = Field(default_factory=list)
    created_utc: datetime

    @model_validator(mode="after")
    def _time(self) -> StrategicReport:
        if self.created_utc.tzinfo is None:
            raise ValueError("created_utc must be timezone-aware")
        return self


def build_strategic_report(
    *,
    report_id: str,
    instance_id: str,
    portfolio: StrategicPortfolio,
    monitoring: MonitoringPolicy,
    periods: list[PortfolioPeriod],
    bau: BauPlan | None = None,
    comparison: BauComparison | None = None,
    created_utc: datetime | None = None,
) -> StrategicReport:
    """Build optimized and optional BAU yearly rows.

    Parameters
    ----------
    report_id : str
        Report id.
    instance_id : str
        Instance id.
    portfolio : StrategicPortfolio
        Optimized portfolio.
    monitoring : MonitoringPolicy
        Monitoring policy.
    periods : list of PortfolioPeriod
        Period definitions for year mapping.
    bau : BauPlan or None, optional
        BAU plan.
    comparison : BauComparison or None, optional
        Comparison record.
    created_utc : datetime, optional
        Creation time.

    Returns
    -------
    StrategicReport
        Yearly rows and totals.

    Raises
    ------
    ReportError
        When period or instance references are inconsistent.
    """
    period_map = {period.period_id: period for period in periods}
    summaries = {summary.period_id: summary for summary in portfolio.period_summary}
    if set(summaries) != set(period_map):
        raise ReportError("portfolio and period definitions do not match")
    if portfolio.instance_id != instance_id:
        raise ReportError("portfolio instance does not match the report")
    if bau is not None and bau.instance_id != instance_id:
        raise ReportError("BAU instance does not match the report")
    period_years = {period.start_year for period in periods}
    monitoring_by_year: dict[int, tuple[float, int]] = {}
    for decision in monitoring.decisions:
        if not decision.event_years:
            continue
        per_event = decision.total_cost / len(decision.event_years)
        for year in decision.event_years:
            if year not in period_years:
                raise ReportError(f"monitoring event year {year} is outside the report periods")
            cost, count = monitoring_by_year.get(year, (0.0, 0))
            monitoring_by_year[year] = (cost + per_event, count + 1)
    rows: list[YearRow] = []
    optimized_total = 0.0
    bau_total = 0.0
    bau_summaries = (
        {summary.period_id: summary for summary in bau.period_summary} if bau is not None else {}
    )
    if bau is not None and set(bau_summaries) != set(period_map):
        raise ReportError("BAU and period definitions do not match")
    for period in periods:
        summary = summaries[period.period_id]
        monitoring_cost, events = monitoring_by_year.get(period.start_year, (0.0, 0))
        if monitoring_cost > summary.budget + 1e-9:
            raise ReportError("monitoring cost exceeds the period budget")
        total = summary.cost + monitoring_cost
        rows.append(
            YearRow(
                scope="optimized",
                year=period.start_year,
                period_id=period.period_id,
                treatment_cost=summary.cost,
                monitoring_cost=monitoring_cost,
                total_cost=total,
                budget=period.budget,
                budget_remaining=period.budget - total,
                service_attainment=summary.service_attainment,
                risk=summary.risk,
                uncertainty=summary.uncertainty,
                monitoring_events=events,
            )
        )
        optimized_total += total
        if bau is not None:
            bau_summary = bau_summaries[period.period_id]
            bau_rows_cost = bau_summary.cost + monitoring_cost
            rows.append(
                YearRow(
                    scope="bau",
                    year=period.start_year,
                    period_id=period.period_id,
                    treatment_cost=bau_summary.cost,
                    monitoring_cost=monitoring_cost,
                    total_cost=bau_rows_cost,
                    budget=period.budget,
                    budget_remaining=period.budget - bau_rows_cost,
                    service_attainment=bau_summary.service_attainment,
                    risk=bau_summary.risk,
                    uncertainty=bau_summary.uncertainty,
                    monitoring_events=events,
                )
            )
            bau_total += bau_rows_cost
    return StrategicReport(
        report_id=report_id,
        instance_id=instance_id,
        rows=rows,
        optimized_total_cost=optimized_total,
        bau_total_cost=bau_total if bau is not None else None,
        comparison=comparison,
        caveats=[
            "Costs are scenario costs, not a financial forecast or a bid.",
            "Monitoring cost is allocated evenly across its scheduled event years.",
            "Service, risk, and uncertainty are period means from the declared model and options.",
            "A BAU comparison is a scenario comparison, not a causal claim.",
        ],
        created_utc=created_utc or datetime.now(UTC),
    )


def write_strategic_report(report: StrategicReport, path: str | Path) -> Path:
    """Write a strategic report as JSON.

    Parameters
    ----------
    report : StrategicReport
        Report.
    path : str or Path
        Destination.

    Returns
    -------
    Path
        Written path.
    """
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(report.model_dump_json(indent=2) + "\n", encoding="utf-8")
    return destination


def load_strategic_report(path: str | Path) -> StrategicReport:
    """Load a strategic report.

    Parameters
    ----------
    path : str or Path
        Source.

    Returns
    -------
    StrategicReport
        Loaded report.
    """
    return StrategicReport.model_validate_json(Path(path).read_text(encoding="utf-8"))


__all__ = [
    "REPORT_SCHEMA_VERSION",
    "ReportError",
    "StrategicReport",
    "YearRow",
    "build_strategic_report",
    "load_strategic_report",
    "write_strategic_report",
]
