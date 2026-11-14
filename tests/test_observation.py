"""Tests for the P8.1 observation model."""

from __future__ import annotations

import pytest
from brushline.monitoring.observation import (
    ObservationConfig,
    ObservationRequest,
    simulate_observation,
)
from pydantic import ValidationError


def test_observation_deterministic_and_confused() -> None:
    cfg = ObservationConfig(
        coverage=1,
        detection_probability=1,
        measurement_sd=0,
        confusion={"shrub": {"grass_herb": 1.0}},
        latency_days=2,
    )
    req = ObservationRequest(segment_id="s", true_class="shrub", true_value=2, seed=1)
    a = simulate_observation(req, cfg)
    b = simulate_observation(req, cfg)
    assert a == b
    assert a.detected
    assert a.covered
    assert a.observed_class == "grass_herb"
    assert a.measured_value == 2
    assert a.latency_days == 2
    assert a.confidence == 1
    assert a.error == 0


def test_no_detection_and_validation() -> None:
    cfg = ObservationConfig(coverage=0, detection_probability=1)
    result = simulate_observation(
        ObservationRequest(segment_id="s", true_class="shrub", true_value=1, seed=1), cfg
    )
    assert not result.covered
    assert not result.detected
    assert result.observed_class is None
    with pytest.raises(ValidationError):
        ObservationConfig(confusion={"x": {"y": -1}})
