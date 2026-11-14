"""Tests for P8.4-P8.6 recalibration, replan, and validation."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from brushline.monitoring.recalibration import (
    PriorState,
    RecalibrationObservation,
    recalibrate,
)
from brushline.monitoring.replan import evaluate_replan
from brushline.monitoring.validation import build_validation, write_validation

NOW = datetime(2026, 11, 14, tzinfo=UTC)


def test_recalibration_and_replan() -> None:
    prior = PriorState(
        segment_id="s", probabilities={"shrub": 0.6, "grass_herb": 0.4}, confidence=0.4
    )
    state = recalibrate(
        prior, [RecalibrationObservation(observed_class="shrub", confidence=0.9)], created_utc=NOW
    )
    assert state.posterior["shrub"] > 0.6
    assert state.confidence > 0.4
    assert state.parameter > 1
    assert state.observation_count == 1
    decision = evaluate_replan(plan_id="p", forecast_error=0.4, uncertainty=0.2, created_utc=NOW)
    assert decision.triggered
    assert decision.new_plan_id
    quiet = evaluate_replan(plan_id="p", forecast_error=0.1, uncertainty=0.2, created_utc=NOW)
    assert not quiet.triggered
    assert quiet.new_plan_id is None


def test_synthetic_validation() -> None:
    result = build_validation()
    assert result.beats_calendar
    assert result.adaptive_regret_per_dollar > result.fixed_regret_per_dollar
    assert result.posterior_confidence > 0.4
    assert result.replan_triggered
    assert len(result.caveats) == 3
    path = Path(__file__).resolve().parents[1] / "notes" / "reference" / "p8-validation.v1.json"
    write_validation(result, path)
    loaded = type(result).model_validate_json(path.read_text())
    assert loaded.beats_calendar
