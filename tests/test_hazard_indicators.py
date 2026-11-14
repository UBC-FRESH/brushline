"""Tests for P4.5 hazard and service indicators."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from brushline.model.corridor import ServiceStandard
from brushline.vegetation.hazards import (
    AccessEvidence,
    FuelNeighbor,
    HazardConfig,
    HazardReport,
    HazardRequest,
    assess_hazards,
    validate_hazard_report,
)
from pydantic import ValidationError

NOW = datetime(2026, 11, 14, tzinfo=UTC)


def _request(**updates: object) -> HazardRequest:
    values: dict[str, object] = {
        "segment_id": "s1",
        "height_m": 2.0,
        "cover_pct": 40.0,
        "service_standard": ServiceStandard(
            service_standard_id="clearance",
            max_height_m=4.0,
            min_clearance_m=1.0,
        ),
        "asset_height_m": 5.0,
        "edge_height_m": 12.0,
        "edge_distance_m": 8.0,
        "neighbors": [
            FuelNeighbor(segment_id="s2", cover_pct=60.0, distance_m=10.0),
            FuelNeighbor(segment_id="s0", cover_pct=20.0, distance_m=100.0),
        ],
        "access": AccessEvidence(
            slope_deg=10.0,
            road_status="class_1",
            road_status_source="ALSroads",
            road_score=0.9,
            distance_m=20.0,
        ),
    }
    values.update(updates)
    return HazardRequest.model_validate(values)


def test_clearance_clear_at_risk_and_exceeded() -> None:
    """Clearance reflects the service margin and the asset gap."""
    clear = assess_hazards(_request(), created_utc=NOW)
    assert clear.clearance.status == "clear"
    assert clear.clearance.height_margin_m == 2.0
    assert clear.clearance.clearance_gap_m == 2.0

    at_risk = assess_hazards(_request(height_m=3.2), created_utc=NOW)
    assert at_risk.clearance.status == "at_risk"
    assert at_risk.clearance.height_margin_m == pytest.approx(0.8)

    exceeded = assess_hazards(_request(height_m=4.5), created_utc=NOW)
    assert exceeded.clearance.status == "exceeded"
    assert exceeded.clearance.height_margin_m < 0

    asset_gap = assess_hazards(_request(height_m=2.0, asset_height_m=2.5), created_utc=NOW)
    assert asset_gap.clearance.status == "exceeded"
    assert asset_gap.clearance.clearance_gap_m is not None
    assert asset_gap.clearance.clearance_gap_m < 0


def test_fall_in_risk_states_and_unknown() -> None:
    """Fall-in reach and risk produce low, moderate, high, or unknown."""
    low = assess_hazards(_request(edge_distance_m=30), created_utc=NOW)
    assert low.fall_in.status == "low"
    moderate = assess_hazards(_request(edge_distance_m=10), created_utc=NOW)
    assert moderate.fall_in.status == "moderate"
    high = assess_hazards(_request(edge_distance_m=2), created_utc=NOW)
    assert high.fall_in.status == "high"
    unknown = assess_hazards(
        _request(edge_height_m=None, edge_distance_m=None),
        created_utc=NOW,
    )
    assert unknown.fall_in.status == "unknown"
    assert unknown.fall_in.risk is None


def test_fuel_connectivity_and_unknown() -> None:
    """Neighbour cover produces a distance-weighted connectivity."""
    report = assess_hazards(_request(), created_utc=NOW)
    assert report.fuel.status in ("low", "moderate", "high")
    assert report.fuel.connectivity is not None
    assert report.fuel.neighbor_count == 2
    low = assess_hazards(
        _request(neighbors=[FuelNeighbor(segment_id="s2", cover_pct=2, distance_m=10)]),
        created_utc=NOW,
    )
    assert low.fuel.status == "low"
    unknown = assess_hazards(_request(neighbors=[]), created_utc=NOW)
    assert unknown.fuel.status == "unknown"
    assert unknown.fuel.connectivity is None


def test_access_proxy_and_status() -> None:
    """Slope and the source-preserving road score produce an access proxy."""
    report = assess_hazards(_request(), created_utc=NOW)
    assert report.access.status in ("moderate", "low", "high")
    assert report.access.road_status == "class_1"
    assert report.access.road_status_source == "ALSroads"
    assert report.access.proxy is not None
    unknown = assess_hazards(_request(access=None), created_utc=NOW)
    assert unknown.access.status == "unknown"
    assert unknown.access.proxy is None
    flat = assess_hazards(
        _request(
            access=AccessEvidence(
                slope_deg=0,
                road_status="class_1",
                road_status_source="ALSroads",
                road_score=1.0,
                distance_m=1,
            )
        ),
        created_utc=NOW,
    )
    assert flat.access.status == "high"
    steep = assess_hazards(
        _request(
            access=AccessEvidence(
                slope_deg=45,
                road_status="class_4",
                road_status_source="ALSroads",
                road_score=0.2,
                distance_m=1,
            )
        ),
        created_utc=NOW,
    )
    assert steep.access.status == "low"


def test_reliability_weighted_and_missing_components() -> None:
    """Reliability uses available weighted components and omits missing ones."""
    report = assess_hazards(_request(), created_utc=NOW)
    assert report.reliability.score is not None
    assert 0 <= report.reliability.score <= 1
    assert set(report.reliability.components) == {
        "clearance",
        "fall_in",
        "fuel",
        "access",
    }
    missing = assess_hazards(
        _request(access=None, edge_height_m=None, edge_distance_m=None, neighbors=[]),
        created_utc=NOW,
    )
    assert "access" not in missing.reliability.components
    assert "fall_in" not in missing.reliability.components
    assert missing.reliability.score is not None
    assert any("omitted" in caveat for caveat in missing.caveats)


def test_unknown_reliability_when_no_components() -> None:
    """A report with no available component has an unknown reliability."""
    report = assess_hazards(
        _request(
            access=None,
            edge_height_m=None,
            edge_distance_m=None,
            neighbors=[],
            service_standard=ServiceStandard(
                service_standard_id="clearance",
                max_height_m=4,
                min_clearance_m=1,
            ),
        ),
        created_utc=NOW,
    )
    # Clearance is always available, so reliability is not empty here.
    assert report.reliability.score is not None
    blocked = report.model_copy(
        update={
            "reliability": report.reliability.model_copy(
                update={"components": {}, "score": None, "status": "unknown"}
            )
        }
    )
    assert not validate_hazard_report(blocked).errors


def test_config_validation() -> None:
    """Weights and thresholds are validated."""
    with pytest.raises(ValidationError, match="every reliability"):
        HazardConfig(weights={"clearance": 1.0})
    with pytest.raises(ValidationError, match="sum to 1"):
        HazardConfig(weights={"clearance": 1, "fall_in": 1, "fuel": 1, "access": 1})
    with pytest.raises(ValidationError, match="non-negative"):
        HazardConfig(weights={"clearance": -0.1, "fall_in": 0.4, "fuel": 0.3, "access": 0.4})
    with pytest.raises(ValidationError):
        HazardConfig(wind_factor=0)
    with pytest.raises(ValidationError):
        HazardConfig(fuel_distance_scale_m=0)


def test_request_validation() -> None:
    """Observation ranges, edge pairs, and service standards are validated."""
    with pytest.raises(ValidationError, match="edge height and distance"):
        _request(edge_height_m=10, edge_distance_m=None)
    with pytest.raises(ValidationError):
        _request(height_m=-1)
    with pytest.raises(ValidationError):
        AccessEvidence(
            slope_deg=100,
            road_status="class_1",
            road_status_source="ALSroads",
            road_score=0.5,
            distance_m=1,
        )
    with pytest.raises(ValidationError):
        FuelNeighbor(segment_id="s2", cover_pct=101, distance_m=1)


def test_validator_names_bad_reports() -> None:
    """The validator catches statuses, weights, evidence, and caveats."""
    report = assess_hazards(_request(), created_utc=NOW)
    cases = [
        (
            report.model_copy(
                update={"clearance": report.clearance.model_copy(update={"status": "maybe"})}
            ),
            "HAZARD-CLEARANCE",
        ),
        (
            report.model_copy(
                update={"fall_in": report.fall_in.model_copy(update={"status": "maybe"})}
            ),
            "HAZARD-FALLIN",
        ),
        (
            report.model_copy(update={"fuel": report.fuel.model_copy(update={"status": "maybe"})}),
            "HAZARD-FUEL",
        ),
        (
            report.model_copy(
                update={"access": report.access.model_copy(update={"status": "maybe"})}
            ),
            "HAZARD-ACCESS",
        ),
        (
            report.model_copy(
                update={"reliability": report.reliability.model_copy(update={"status": "maybe"})}
            ),
            "HAZARD-RELIABILITY",
        ),
        (
            report.model_copy(
                update={
                    "reliability": report.reliability.model_copy(
                        update={"weights": {"clearance": 1.0}}
                    )
                }
            ),
            "HAZARD-RELIABILITY",
        ),
        (
            report.model_copy(
                update={
                    "reliability": report.reliability.model_copy(
                        update={"components": {}, "score": 0.5}
                    )
                }
            ),
            "HAZARD-RELIABILITY",
        ),
        (
            report.model_copy(
                update={
                    "clearance": report.clearance.model_copy(
                        update={"status": "exceeded", "height_margin_m": 1.0}
                    )
                }
            ),
            "HAZARD-CLEARANCE",
        ),
        (
            report.model_copy(
                update={
                    "fall_in": report.fall_in.model_copy(update={"status": "high", "risk": None})
                }
            ),
            "HAZARD-FALLIN",
        ),
        (
            report.model_copy(
                update={
                    "fuel": report.fuel.model_copy(
                        update={"status": "unknown", "neighbor_count": 1}
                    )
                }
            ),
            "HAZARD-FUEL",
        ),
        (
            report.model_copy(
                update={
                    "access": report.access.model_copy(update={"status": "high", "proxy": None})
                }
            ),
            "HAZARD-ACCESS",
        ),
    ]
    for bad, prefix in cases:
        assert any(error.startswith(prefix) for error in validate_hazard_report(bad).errors), prefix
    naive = report.model_copy(update={"created_utc": datetime(2026, 11, 14)})
    assert any(error.startswith("HAZARD-TIME") for error in validate_hazard_report(naive).errors)
    no_caveats = report.model_copy(update={"caveats": []})
    assert any(
        warning.startswith("HAZARD-CAVEAT")
        for warning in validate_hazard_report(no_caveats).warnings
    )


def test_report_model_round_trip_and_schema() -> None:
    """The report carries the schema and caveats."""
    report = assess_hazards(_request(), created_utc=NOW)
    assert report.schema_version == "brushline.hazards.v1"
    assert report.caveats
    assert isinstance(report, HazardReport)
    assert report.clearance.formula
    assert report.reliability.formula


def test_weights_must_sum_and_name_all_components() -> None:
    """A weight map that omits a component or sums incorrectly is rejected."""
    report = assess_hazards(_request(), created_utc=NOW)
    missing = report.model_copy(
        update={
            "reliability": report.reliability.model_copy(update={"weights": {"clearance": 1.0}})
        }
    )
    assert any(
        error.startswith("HAZARD-RELIABILITY") for error in validate_hazard_report(missing).errors
    )
    wrong_sum = report.model_copy(
        update={
            "reliability": report.reliability.model_copy(
                update={
                    "weights": {
                        "clearance": 1.0,
                        "fall_in": 1.0,
                        "fuel": 1.0,
                        "access": 1.0,
                    }
                }
            )
        }
    )
    assert any(
        error.startswith("HAZARD-RELIABILITY") for error in validate_hazard_report(wrong_sum).errors
    )


def test_reliability_unknown_and_low_private_paths() -> None:
    """The private reliability helper handles no components and a low score."""
    from brushline.vegetation.hazards import (
        AccessIndicator,
        ClearanceIndicator,
        FallInIndicator,
        FuelIndicator,
        _reliability,
    )

    clearance = ClearanceIndicator(
        status="unknown",
        height_m=0,
        max_height_m=4,
        min_clearance_m=1,
        asset_height_m=None,
        height_margin_m=4,
        clearance_gap_m=None,
    )
    fall = FallInIndicator(
        status="unknown",
        edge_height_m=None,
        edge_distance_m=None,
        wind_factor=1.5,
        reach_m=None,
        risk=None,
    )
    fuel = FuelIndicator(status="unknown", connectivity=None, neighbor_count=0)
    access = AccessIndicator(status="unknown")
    unknown = _reliability(clearance, fall, fuel, access, HazardConfig())
    assert unknown.status == "unknown"
    assert unknown.score is None
    low = _reliability(
        clearance.model_copy(update={"status": "exceeded"}),
        fall,
        fuel,
        access,
        HazardConfig(),
    )
    assert low.status == "low"
    assert low.score == 0.0


def test_fuel_high_connectivity() -> None:
    """Dense adjacent cover produces high fuel connectivity."""
    report = assess_hazards(
        _request(neighbors=[FuelNeighbor(segment_id="s2", cover_pct=95, distance_m=1)]),
        created_utc=NOW,
    )
    assert report.fuel.status == "high"
