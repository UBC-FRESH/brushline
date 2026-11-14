"""Adaptive replanning trigger."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

REPLAN_SCHEMA_VERSION: Literal["brushline.replan.v1"] = "brushline.replan.v1"


class ReplanTrigger(BaseModel):
    """Replan thresholds."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    forecast_error_threshold: float = Field(default=0.2, ge=0)
    uncertainty_threshold: float = Field(default=0.5, ge=0, le=1)


class ReplanDecision(BaseModel):
    """Replan decision and new plan version."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["brushline.replan.v1"] = REPLAN_SCHEMA_VERSION
    triggered: bool
    reasons: list[str]
    new_plan_id: str | None = None
    source_plan_id: str
    created_utc: datetime


def evaluate_replan(
    *,
    plan_id: str,
    forecast_error: float,
    uncertainty: float,
    trigger: ReplanTrigger | None = None,
    created_utc: datetime | None = None,
) -> ReplanDecision:
    """Trigger a new plan version when error or uncertainty crosses a threshold."""
    rules = trigger or ReplanTrigger()
    reasons = []
    if forecast_error > rules.forecast_error_threshold:
        reasons.append("forecast error above threshold")
    if uncertainty > rules.uncertainty_threshold:
        reasons.append("uncertainty above threshold")
    return ReplanDecision(
        triggered=bool(reasons),
        reasons=reasons,
        new_plan_id=f"{plan_id}-r{int((created_utc or datetime.now(UTC)).timestamp())}"
        if reasons
        else None,
        source_plan_id=plan_id,
        created_utc=created_utc or datetime.now(UTC),
    )
