"""Observation-driven state recalibration."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

RECALIBRATION_SCHEMA_VERSION: Literal["brushline.recalibration.v1"] = "brushline.recalibration.v1"


class PriorState(BaseModel):
    """Prior class distribution."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    segment_id: str
    probabilities: dict[str, float]
    confidence: float = Field(ge=0, le=1)
    parameter: float = Field(default=1.0, gt=0)


class RecalibrationObservation(BaseModel):
    """One observation for recalibration."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    observed_class: str
    confidence: float = Field(ge=0, le=1)
    latency_days: int = Field(default=0, ge=0)


class RecalibrationConfig(BaseModel):
    """Recalibration settings."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    observation_weight: float = Field(default=0.5, ge=0, le=1)
    parameter_weight: float = Field(default=0.25, ge=0, le=1)
    model_version: str = "brushline.low-vegetation.prototype.v0"


class RecalibratedState(BaseModel):
    """Calibrated state and model update record."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["brushline.recalibration.v1"] = RECALIBRATION_SCHEMA_VERSION
    segment_id: str
    posterior: dict[str, float]
    confidence: float = Field(ge=0, le=1)
    parameter: float = Field(gt=0)
    observation_count: int = Field(ge=0)
    model_version: str
    created_utc: datetime


def recalibrate(
    prior: PriorState,
    observations: list[RecalibrationObservation],
    config: RecalibrationConfig | None = None,
    created_utc: datetime | None = None,
) -> RecalibratedState:
    """Update class probabilities, uncertainty, and a model parameter.

    Parameters
    ----------
    prior : PriorState
        Prior.
    observations : list of RecalibrationObservation
        Observations.
    config : RecalibrationConfig, optional
        Settings.
    created_utc : datetime, optional
        Creation time.

    Returns
    -------
    RecalibratedState
        Posterior and model update.
    """
    rules = config or RecalibrationConfig()
    posterior = {key: max(0.0, value) for key, value in prior.probabilities.items()}
    total = sum(posterior.values()) or 1.0
    posterior = {key: value / total for key, value in posterior.items()}
    for observation in observations:
        posterior[observation.observed_class] = (
            posterior.get(observation.observed_class, 0.0)
            + rules.observation_weight * observation.confidence
        )
    total = sum(posterior.values()) or 1.0
    posterior = {key: value / total for key, value in posterior.items()}
    confidence = min(
        1.0,
        prior.confidence + sum(item.confidence for item in observations) * rules.observation_weight,
    )
    parameter = prior.parameter * (1.0 + rules.parameter_weight * (confidence - prior.confidence))
    return RecalibratedState(
        segment_id=prior.segment_id,
        posterior=posterior,
        confidence=confidence,
        parameter=parameter,
        observation_count=len(observations),
        model_version=rules.model_version,
        created_utc=created_utc or datetime.now(UTC),
    )
