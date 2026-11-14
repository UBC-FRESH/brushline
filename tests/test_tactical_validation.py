"""Tests for the P7.7 tactical/operational validation."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest
from brushline.tactical.validation import (
    TacticalValidationResult,
    ValidationCheck,
    build_synthetic_case,
    load_validation,
    write_validation,
)
from pydantic import ValidationError

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "notes" / "reference" / "p7-validation.v1.json"


def test_synthetic_case_passes_all_checks() -> None:
    """The 2026 case is capacity/access/season feasible and work-ready."""
    case = build_synthetic_case()
    assert case.validation.passed
    assert {check.code for check in case.validation.checks} == {
        "CAPACITY",
        "ACCESS",
        "SEASONALITY",
        "TRACEABILITY",
        "DRY_RUN",
        "TIMELINE",
    }
    assert case.program.feasible
    assert case.access.feasible
    assert case.resources.feasible
    assert case.operations.feasible
    assert len(case.operations.work_orders) == 2
    assert case.fhops.status == "dry_run"
    assert case.fhops.total_cost == 850
    assert len(case.timeline.events) == 4
    assert all(check.passed for check in case.validation.checks)
    second = build_synthetic_case()
    assert second.validation == case.validation


def test_committed_validation_fixture_loads() -> None:
    """The committed fixture is a passing tactical validation."""
    result = load_validation(FIXTURE)
    assert result.passed
    assert result.program_id == "p7-program"
    assert result.operations_id == "p7-operations"
    assert result.timeline_id == "p7-timeline"


def test_validation_round_trip_and_guards(tmp_path: Path) -> None:
    """Writers round-trip and invalid results are rejected."""
    result = build_synthetic_case().validation
    path = tmp_path / "validation.json"
    assert write_validation(result, path) == path
    assert load_validation(path) == result
    with pytest.raises(ValidationError):
        ValidationCheck(code="", passed=True)
    with pytest.raises(ValidationError):
        TacticalValidationResult(
            instance_id="x",
            program_id="p",
            operations_id="o",
            timeline_id="t",
            checks=[ValidationCheck(code="X", passed=True)],
            passed=True,
            created_utc=datetime(2026, 11, 14),
        )
