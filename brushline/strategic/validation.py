"""Synthetic-corridor validation for a strategic plan.

The validation builds a deterministic 10-year case, solves the optimized portfolio, monitoring
policy, fixed-cycle BAU, report, and scenario, then checks coverage, budget, service, monitoring,
BAU like-for-like status, report totals, and exact scenario replay.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from brushline.strategic.bau import BauConfig, BauPlan, build_bau_plan, compare_bau
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
from brushline.strategic.reports import StrategicReport, build_strategic_report
from brushline.strategic.scenario import (
    ScenarioVersions,
    StrategicScenario,
    build_scenario,
    replay_scenario,
)

VALIDATION_SCHEMA_VERSION: Literal["brushline.strategic-validation.v1"] = (
    "brushline.strategic-validation.v1"
)


class StrategicValidationError(ValueError):
    """Raised when the synthetic case cannot be built."""


class ValidationCheck(BaseModel):
    """One named validation check.

    Parameters
    ----------
    code : str
        Check code.
    passed : bool
        Whether the check passed.
    detail : str
        Human detail.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    code: str = Field(min_length=1)
    passed: bool
    detail: str = ""


class StrategicValidationResult(BaseModel):
    """The synthetic strategic validation result.

    Parameters
    ----------
    schema_version : {"brushline.strategic-validation.v1"}
        Schema version.
    instance_id : str
        Instance id.
    portfolio_id : str
        Optimized portfolio id.
    bau_policy_id : str
        BAU policy id.
    report_id : str
        Report id.
    scenario_id : str
        Scenario id.
    checks : list of ValidationCheck
        Named checks.
    passed : bool
        Whether all checks passed.
    created_utc : datetime
        Timezone-aware time.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["brushline.strategic-validation.v1"] = VALIDATION_SCHEMA_VERSION
    instance_id: str
    portfolio_id: str
    bau_policy_id: str
    report_id: str
    scenario_id: str
    checks: list[ValidationCheck] = Field(min_length=1)
    passed: bool
    created_utc: datetime

    @model_validator(mode="after")
    def _time(self) -> StrategicValidationResult:
        if self.created_utc.tzinfo is None:
            raise ValueError("created_utc must be timezone-aware")
        return self


class SyntheticCase(BaseModel):
    """A complete synthetic strategic case and its validation.

    Parameters
    ----------
    portfolio : StrategicPortfolio
        Optimized portfolio.
    monitoring : MonitoringPolicy
        Monitoring policy.
    bau : BauPlan
        BAU plan.
    report : StrategicReport
        Strategic report.
    scenario : StrategicScenario
        Scenario record.
    validation : StrategicValidationResult
        Validation checks.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    portfolio: StrategicPortfolio
    monitoring: MonitoringPolicy
    bau: BauPlan
    report: StrategicReport
    scenario: StrategicScenario
    validation: StrategicValidationResult


def build_synthetic_case(created_utc: datetime | None = None) -> SyntheticCase:
    """Build the deterministic 10-year synthetic strategic case.

    Parameters
    ----------
    created_utc : datetime, optional
        Creation time.

    Returns
    -------
    SyntheticCase
        Portfolio, monitoring, BAU, report, scenario, and validation.
    """
    created = created_utc or datetime(2026, 11, 14, tzinfo=UTC)
    segments = [
        PortfolioSegment(
            segment_id="seg-1",
            span_id="span-1",
            sequence=0,
            length_m=100,
            base_service=0.2,
            base_risk=0.8,
            base_uncertainty=0.5,
        ),
        PortfolioSegment(
            segment_id="seg-2",
            span_id="span-1",
            sequence=1,
            length_m=120,
            base_service=0.25,
            base_risk=0.75,
            base_uncertainty=0.5,
        ),
        PortfolioSegment(
            segment_id="seg-3",
            span_id="span-1",
            sequence=2,
            length_m=80,
            base_service=0.3,
            base_risk=0.7,
            base_uncertainty=0.5,
        ),
    ]
    periods = [
        PortfolioPeriod(
            period_id=f"p{index + 1}",
            start_year=2026 + index,
            budget=150,
            capacity_by_method={"mowing": 3},
        )
        for index in range(10)
    ]
    options = [
        PortfolioOption(
            option_id=f"{segment.segment_id}-{period.period_id}-mow",
            segment_id=segment.segment_id,
            period_id=period.period_id,
            action_id="mow",
            method="mowing",
            cost=40,
            capacity_units=1,
            service_attainment=0.8,
            risk=0.2,
            uncertainty=0.3,
        )
        for segment in segments
        for period in periods
    ]
    portfolio = build_strategic_portfolio(
        portfolio_id="p6-opt",
        instance_id="synthetic-strategic",
        segments=segments,
        periods=periods,
        options=options,
        config=PortfolioConfig(service_target=0.7, risk_target=0.4),
        created_utc=created,
    )
    monitoring = build_monitoring_policy(
        policy_id="p6-mon",
        instance_id="synthetic-strategic",
        spans=[
            MonitoringSpan(
                span_id="span-1",
                segment_ids=[segment.segment_id for segment in segments],
                baseline_uncertainty=0.5,
                service_risk=0.4,
                route_m=300,
            )
        ],
        options=[
            MonitoringOption(
                option_id="lidar-annual",
                span_id="span-1",
                sensor="lidar",
                route="full",
                interval_years=1,
                sampling_intensity=0.7,
                cost_per_event=20,
                uncertainty_reduction=0.5,
                risk_reduction=0.4,
            )
        ],
        config=MonitoringConfig(horizon_years=10, start_year=2026, budget=400, value_per_unit=1000),
        created_utc=created,
    )
    bau = build_bau_plan(
        policy_id="p6-bau",
        instance_id="synthetic-strategic",
        segments=segments,
        periods=periods,
        options=options,
        config=BauConfig(cycle_years=4, start_year=2026),
        created_utc=created,
    )
    comparison = compare_bau(portfolio, bau, created_utc=created)
    report = build_strategic_report(
        report_id="p6-report",
        instance_id="synthetic-strategic",
        portfolio=portfolio,
        monitoring=monitoring,
        periods=periods,
        bau=bau,
        comparison=comparison,
        created_utc=created,
    )
    versions = ScenarioVersions(
        dataset_version="synthetic-strategic.v1",
        dataset_digest="synthetic-digest",
        state_model="brushline.state-space.v1",
        growth_model="brushline.growth.v1",
        treatment_model="brushline.treatment.v1",
        adapter="brushline.optimization.adapter.v1",
        brushline_version="0.1.0",
    )
    scenario = build_scenario(
        scenario_id="p6-scenario",
        instance_id="synthetic-strategic",
        versions=versions,
        configuration={
            "service_target": 0.7,
            "risk_target": 0.4,
            "budget": 150,
            "horizon_years": 10,
            "bau_cycle_years": 4,
        },
        portfolio=portfolio,
        report=report,
        seed=7,
        budget=150,
        horizon_years=10,
        portfolio_path="runs/strategic/portfolio.json",
        report_path="runs/strategic/report.json",
        archive_path="runs/strategic/pareto.json",
        created_utc=created,
    )
    validation = validate_strategic_plan(
        portfolio=portfolio,
        monitoring=monitoring,
        bau=bau,
        report=report,
        scenario=scenario,
        created_utc=created,
    )
    return SyntheticCase(
        portfolio=portfolio,
        monitoring=monitoring,
        bau=bau,
        report=report,
        scenario=scenario,
        validation=validation,
    )


def validate_strategic_plan(
    *,
    portfolio: StrategicPortfolio,
    monitoring: MonitoringPolicy,
    bau: BauPlan,
    report: StrategicReport,
    scenario: StrategicScenario,
    created_utc: datetime | None = None,
) -> StrategicValidationResult:
    """Validate a strategic plan against the P6 acceptance checks.

    Parameters
    ----------
    portfolio : StrategicPortfolio
        Optimized portfolio.
    monitoring : MonitoringPolicy
        Monitoring policy.
    bau : BauPlan
        BAU plan.
    report : StrategicReport
        Report.
    scenario : StrategicScenario
        Scenario.
    created_utc : datetime, optional
        Result time.

    Returns
    -------
    StrategicValidationResult
        Named checks and pass/fail.
    """
    optimized_rows = [row for row in report.rows if row.scope == "optimized"]
    bau_rows = [row for row in report.rows if row.scope == "bau"]
    checks = [
        ValidationCheck(
            code="COVERAGE",
            passed=len(optimized_rows) == 10 and len(bau_rows) == 10,
            detail=f"optimized={len(optimized_rows)} bau={len(bau_rows)}",
        ),
        ValidationCheck(
            code="BUDGET",
            passed=all(row.budget_remaining >= -1e-9 for row in optimized_rows),
            detail="optimized rows within period budget",
        ),
        ValidationCheck(
            code="SERVICE",
            passed=portfolio.service_attainment >= portfolio.config.service_target - 1e-9,
            detail=(
                f"service={portfolio.service_attainment:.3f} "
                f"target={portfolio.config.service_target:.3f}"
            ),
        ),
        ValidationCheck(
            code="MONITORING",
            passed=monitoring.total_cost <= monitoring.budget + 1e-9 and bool(monitoring.decisions),
            detail=f"cost={monitoring.total_cost:.2f} decisions={len(monitoring.decisions)}",
        ),
        ValidationCheck(
            code="BAU",
            passed=report.comparison is not None
            and report.comparison.like_for_like
            and bau.feasible,
            detail="BAU is like-for-like and feasible",
        ),
        ValidationCheck(
            code="TOTALS",
            passed=abs(report.optimized_total_cost - sum(row.total_cost for row in optimized_rows))
            <= 1e-9,
            detail="optimized report total matches yearly rows",
        ),
        ValidationCheck(
            code="REPLAY",
            passed=replay_scenario(scenario, portfolio=portfolio, report=report).ok,
            detail="scenario portfolio/report digests replay",
        ),
    ]
    return StrategicValidationResult(
        instance_id=portfolio.instance_id,
        portfolio_id=portfolio.portfolio_id,
        bau_policy_id=bau.policy_id,
        report_id=report.report_id,
        scenario_id=scenario.scenario_id,
        checks=checks,
        passed=all(check.passed for check in checks),
        created_utc=created_utc or datetime.now(UTC),
    )


def write_validation(result: StrategicValidationResult, path: str | Path) -> Path:
    """Write a strategic validation result.

    Parameters
    ----------
    result : StrategicValidationResult
        Result.
    path : str or Path
        Destination.

    Returns
    -------
    Path
        Written path.
    """
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(result.model_dump_json(indent=2) + "\n", encoding="utf-8")
    return destination


def load_validation(path: str | Path) -> StrategicValidationResult:
    """Load a strategic validation result.

    Parameters
    ----------
    path : str or Path
        Source.

    Returns
    -------
    StrategicValidationResult
        Result.
    """
    return StrategicValidationResult.model_validate_json(Path(path).read_text(encoding="utf-8"))


__all__ = [
    "VALIDATION_SCHEMA_VERSION",
    "StrategicValidationError",
    "StrategicValidationResult",
    "SyntheticCase",
    "ValidationCheck",
    "build_synthetic_case",
    "load_validation",
    "validate_strategic_plan",
    "write_validation",
]
