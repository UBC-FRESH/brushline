"""Explicit observation model for monitoring."""

from __future__ import annotations

import random
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

OBSERVATION_SCHEMA_VERSION: Literal["brushline.observation.v1"] = "brushline.observation.v1"


class ObservationConfig(BaseModel):
    """Observation quality settings.

    Parameters
    ----------
    coverage : float
        Spatial coverage.
    detection_probability : float
        Detection probability.
    measurement_sd : float
        Measurement error standard deviation.
    confusion : dict of str to dict of str to float
        Class confusion probabilities.
    latency_days : int
        Observation latency.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    coverage: float = Field(default=0.8, ge=0, le=1)
    detection_probability: float = Field(default=0.9, ge=0, le=1)
    measurement_sd: float = Field(default=0.1, ge=0)
    confusion: dict[str, dict[str, float]] = Field(default_factory=dict)
    latency_days: int = Field(default=0, ge=0)

    @model_validator(mode="after")
    def _confusion(self) -> ObservationConfig:
        for row in self.confusion.values():
            if any(value < 0 for value in row.values()):
                raise ValueError("confusion probabilities must be non-negative")
        return self


class ObservationRequest(BaseModel):
    """One observation request.

    Parameters
    ----------
    segment_id : str
        Segment id.
    true_class : str
        True class.
    true_value : float
        True continuous value.
    seed : int
        Seed.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    segment_id: str = Field(min_length=1)
    true_class: str
    true_value: float = Field(ge=0)
    seed: int = 0


class Observation(BaseModel):
    """One observation result.

    Parameters
    ----------
    schema_version : {"brushline.observation.v1"}
        Schema version.
    segment_id : str
        Segment.
    detected : bool
        Detection.
    observed_class : str or None
        Observed class.
    measured_value : float or None
        Noisy measurement.
    error : float or None
        Measurement error.
    confidence : float
        Confidence.
    latency_days : int
        Latency.
    covered : bool
        Coverage.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["brushline.observation.v1"] = OBSERVATION_SCHEMA_VERSION
    segment_id: str
    detected: bool
    observed_class: str | None
    measured_value: float | None
    error: float | None
    confidence: float = Field(ge=0, le=1)
    latency_days: int = Field(ge=0)
    covered: bool


def simulate_observation(
    request: ObservationRequest, config: ObservationConfig | None = None
) -> Observation:
    """Simulate coverage, detection, confusion, measurement error, and latency.

    Parameters
    ----------
    request : ObservationRequest
        Request.
    config : ObservationConfig, optional
        Settings.

    Returns
    -------
    Observation
        Observation evidence.
    """
    rules = config or ObservationConfig()
    rng = random.Random(request.seed)
    covered = rng.random() <= rules.coverage
    detected = covered and rng.random() <= rules.detection_probability
    observed_class = None
    measured = None
    error = None
    if detected:
        row = rules.confusion.get(request.true_class, {})
        if row:
            pick = rng.random()
            cumulative = 0.0
            observed_class = next(iter(row))
            for name, probability in sorted(row.items()):
                cumulative += probability
                if pick <= cumulative:
                    observed_class = name
                    break
        else:
            observed_class = request.true_class
        error = rng.gauss(0.0, rules.measurement_sd)
        measured = max(0.0, request.true_value + error)
    confidence = rules.coverage * rules.detection_probability if detected else 0.0
    return Observation(
        segment_id=request.segment_id,
        detected=detected,
        observed_class=observed_class,
        measured_value=measured,
        error=error,
        confidence=confidence,
        latency_days=rules.latency_days,
        covered=covered,
    )


__all__ = [
    "OBSERVATION_SCHEMA_VERSION",
    "Observation",
    "ObservationConfig",
    "ObservationRequest",
    "simulate_observation",
]
