"""Synthetic monitoring-policy validation."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from brushline.monitoring.recalibration import (
    PriorState,
    RecalibrationObservation,
    recalibrate,
)
from brushline.monitoring.replan import evaluate_replan
from brushline.monitoring.value import (
    MonitoringCandidate,
    fixed_calendar,
    select_monitoring,
)

VALIDATION_SCHEMA_VERSION: Literal["brushline.monitoring-validation.v1"] = (
    "brushline.monitoring-validation.v1"
)


class MonitoringValidation(BaseModel):
    """Adaptive, fixed, recalibration, and replan evidence."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["brushline.monitoring-validation.v1"] = VALIDATION_SCHEMA_VERSION
    instance_id: str
    adaptive_value: float
    fixed_value: float
    adaptive_regret_per_dollar: float
    fixed_regret_per_dollar: float
    beats_calendar: bool
    posterior_confidence: float
    replan_triggered: bool
    caveats: list[str] = Field(default_factory=list)
    created_utc: datetime


def build_validation(created_utc: datetime | None = None) -> MonitoringValidation:
    """Build the synthetic adaptive-versus-calendar comparison."""
    created = created_utc or datetime(2026, 11, 14, tzinfo=UTC)
    candidates = [
        MonitoringCandidate(
            candidate_id="a",
            span_id="s1",
            cost=15,
            coverage=0.9,
            uncertainty=0.8,
            expected_loss_reduction=20,
        ),
        MonitoringCandidate(
            candidate_id="b",
            span_id="s2",
            cost=10,
            coverage=0.9,
            uncertainty=0.8,
            expected_loss_reduction=50,
        ),
    ]
    adaptive = select_monitoring(candidates, report_id="adaptive", budget=20, created_utc=created)
    fixed = fixed_calendar(candidates, report_id="fixed", budget=20, created_utc=created)
    state = recalibrate(
        PriorState(
            segment_id="s1", probabilities={"shrub": 0.6, "grass_herb": 0.4}, confidence=0.4
        ),
        [RecalibrationObservation(observed_class="shrub", confidence=0.9)],
        created_utc=created,
    )
    replan = evaluate_replan(
        plan_id="plan-1", forecast_error=0.4, uncertainty=state.confidence, created_utc=created
    )
    return MonitoringValidation(
        instance_id="synthetic-monitoring",
        adaptive_value=adaptive.value_of_information,
        fixed_value=fixed.value_of_information,
        adaptive_regret_per_dollar=adaptive.regret_per_dollar,
        fixed_regret_per_dollar=fixed.regret_per_dollar,
        beats_calendar=adaptive.regret_per_dollar > fixed.regret_per_dollar,
        posterior_confidence=state.confidence,
        replan_triggered=replan.triggered,
        caveats=[
            "Synthetic expected-loss reduction; not field-calibrated.",
            "The fixed calendar is a deterministic baseline, not the owner's actual calendar.",
            "Value of information is an approximation.",
        ],
        created_utc=created,
    )


def write_validation(result: MonitoringValidation, path: str | Path) -> Path:
    """Write validation JSON."""
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(result.model_dump_json(indent=2) + "\n", encoding="utf-8")
    return destination
