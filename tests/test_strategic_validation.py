"""Tests for the P6.7 synthetic strategic validation."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest
from brushline.strategic.validation import (
    StrategicValidationResult,
    ValidationCheck,
    build_synthetic_case,
    load_validation,
    validate_strategic_plan,
    write_validation,
)
from pydantic import ValidationError

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "notes" / "reference" / "p6-validation.v1.json"


def test_synthetic_case_passes_budget_service_bau_and_replay() -> None:
    """The committed synthetic case meets every P6 acceptance check."""
    case = build_synthetic_case()
    assert case.validation.passed
    assert {check.code for check in case.validation.checks} == {
        "COVERAGE",
        "BUDGET",
        "SERVICE",
        "MONITORING",
        "BAU",
        "TOTALS",
        "REPLAY",
    }
    assert case.portfolio.feasible
    assert case.portfolio.total_cost == 920
    assert case.portfolio.service_attainment >= case.portfolio.config.service_target
    assert case.bau.feasible
    assert case.report.comparison is not None
    assert case.report.comparison.like_for_like
    assert len(case.report.rows) == 20
    assert case.scenario.portfolio_digest
    second = build_synthetic_case()
    assert second.scenario.portfolio_digest == case.scenario.portfolio_digest
    assert second.scenario.report_digest == case.scenario.report_digest
    assert second.validation == case.validation


def test_committed_validation_fixture_loads() -> None:
    """The committed validation fixture is a passing result."""
    result = load_validation(FIXTURE)
    assert result.passed
    assert result.portfolio_id == "p6-opt"
    assert result.bau_policy_id == "p6-bau"
    assert result.report_id == "p6-report"
    assert result.scenario_id == "p6-scenario"


def test_each_check_fails_explicitly() -> None:
    """A failed service, budget, monitoring, BAU, total, or replay check is visible."""
    case = build_synthetic_case()
    service = case.portfolio.model_copy(update={"service_attainment": 0.1})
    result = validate_strategic_plan(
        portfolio=service,
        monitoring=case.monitoring,
        bau=case.bau,
        report=case.report,
        scenario=case.scenario,
    )
    assert not result.passed
    assert any(check.code == "SERVICE" and not check.passed for check in result.checks)
    bad_budget = case.report.rows[0].model_copy(update={"budget_remaining": -1})
    report = case.report.model_copy(update={"rows": [bad_budget, *case.report.rows[1:]]})
    result = validate_strategic_plan(
        portfolio=case.portfolio,
        monitoring=case.monitoring,
        bau=case.bau,
        report=report,
        scenario=case.scenario,
    )
    assert any(check.code == "BUDGET" and not check.passed for check in result.checks)
    monitoring = case.monitoring.model_copy(update={"total_cost": 9999})
    result = validate_strategic_plan(
        portfolio=case.portfolio,
        monitoring=monitoring,
        bau=case.bau,
        report=case.report,
        scenario=case.scenario,
    )
    assert any(check.code == "MONITORING" and not check.passed for check in result.checks)
    no_bau = case.report.model_copy(update={"comparison": None})
    result = validate_strategic_plan(
        portfolio=case.portfolio,
        monitoring=case.monitoring,
        bau=case.bau,
        report=no_bau,
        scenario=case.scenario,
    )
    assert any(check.code == "BAU" and not check.passed for check in result.checks)
    wrong_total = case.report.model_copy(
        update={"optimized_total_cost": case.report.optimized_total_cost + 1}
    )
    result = validate_strategic_plan(
        portfolio=case.portfolio,
        monitoring=case.monitoring,
        bau=case.bau,
        report=wrong_total,
        scenario=case.scenario,
    )
    assert any(check.code == "TOTALS" and not check.passed for check in result.checks)
    tampered = case.scenario.model_copy(update={"portfolio_digest": "0" * 64})
    result = validate_strategic_plan(
        portfolio=case.portfolio,
        monitoring=case.monitoring,
        bau=case.bau,
        report=case.report,
        scenario=tampered,
    )
    assert any(check.code == "REPLAY" and not check.passed for check in result.checks)
    short_report = case.report.model_copy(update={"rows": case.report.rows[:2]})
    result = validate_strategic_plan(
        portfolio=case.portfolio,
        monitoring=case.monitoring,
        bau=case.bau,
        report=short_report,
        scenario=case.scenario,
    )
    assert any(check.code == "COVERAGE" and not check.passed for check in result.checks)


def test_validation_writers_and_guards(tmp_path: Path) -> None:
    """Writers round-trip and model guards reject invalid results."""
    case = build_synthetic_case()
    path = tmp_path / "validation.json"
    assert write_validation(case.validation, path) == path
    assert load_validation(path) == case.validation
    with pytest.raises(ValidationError):
        ValidationCheck(code="", passed=True)
    with pytest.raises(ValidationError):
        StrategicValidationResult(
            instance_id="x",
            portfolio_id="x",
            bau_policy_id="x",
            report_id="x",
            scenario_id="x",
            checks=[ValidationCheck(code="X", passed=True)],
            passed=True,
            created_utc=datetime(2026, 11, 14),
        )
