"""Tests for LiDAR coverage, applicability, and observation-gap reporting."""

from __future__ import annotations

from datetime import UTC, date, datetime

import pytest
from brushline.integrations.lidar_coverage import (
    DEFAULT_OPTIONAL_KINDS,
    DEFAULT_REQUIRED_KINDS,
    Applicability,
    LidarCoverageConfig,
    LidarCoverageError,
    LidarCoverageReport,
    LidarCoverageRequest,
    LidarEvidence,
    assess_lidar_coverage,
    validate_lidar_coverage,
)
from pydantic import ValidationError

NOW = datetime(2026, 11, 14, tzinfo=UTC)
ACY = date(2026, 6, 1)


def _evidence(
    *,
    segment_id: str = "s1",
    kind: str = "dem",
    coverage: float = 100.0,
    valid: float | None = 100.0,
    acquired: date = ACY,
    applicability: Applicability | None = None,
    excluded: bool = False,
    reason: str = "",
    evidence: str = "bundle-1",
) -> LidarEvidence:
    return LidarEvidence(
        segment_id=segment_id,
        kind=kind,
        acquisition_date=acquired,
        coverage_pct=coverage,
        valid_pixel_pct=valid,
        applicability=applicability or Applicability(model_card_id="card-1"),
        evidence=evidence,
        excluded=excluded,
        reason=reason,
        source="femic",
        source_version="0.2.0a1",
    )


def _request(
    observations: list[LidarEvidence] | None = None,
    *,
    required: list[str] | None = None,
    optional: list[str] | None = None,
    segments: list[str] | None = None,
) -> LidarCoverageRequest:
    return LidarCoverageRequest(
        aoi="aoi.geojson",
        plan_id="plan-1",
        segment_ids=segments or ["s1"],
        observations=observations or [],
        required_kinds=required if required is not None else ["dem", "chm"],
        optional_kinds=optional if optional is not None else ["field_plot"],
    )


def test_all_evidence_observed() -> None:
    """Complete contemporary evidence yields observed entries and a continue decision."""
    report = assess_lidar_coverage(
        _request(
            [
                _evidence(kind="dem"),
                _evidence(kind="chm"),
                _evidence(kind="field_plot"),
            ],
            required=["dem", "chm"],
        ),
        created_utc=NOW,
    )
    assert report.gaps.decision == "continue"
    assert report.gaps.next_action == "none"
    assert len(report.entries) == 3
    assert all(entry.state == "observed" for entry in report.entries)
    assert report.coverage.entries
    assert validate_lidar_coverage(report).is_valid
    assert validate_lidar_coverage(report).counts["stop"] is False


def test_missing_required_evidence_stops() -> None:
    """A missing required point cloud or DEM stops and names the action."""
    report = assess_lidar_coverage(
        _request(
            [_evidence(kind="chm")],
            required=["point_cloud", "dem", "chm"],
            optional=[],
        ),
        created_utc=NOW,
    )
    missing = [entry for entry in report.entries if entry.state == "missing"]
    assert {entry.kind for entry in missing} == {"point_cloud", "dem"}
    assert report.gaps.decision == "stop"
    assert report.gaps.next_action
    assert any(entry.required for entry in missing)
    assert validate_lidar_coverage(report).is_valid


def test_missing_optional_plot_is_a_caveat() -> None:
    """Missing optional plot evidence continues with a caveat."""
    report = assess_lidar_coverage(
        _request([_evidence(kind="dem"), _evidence(kind="chm")], optional=["field_plot"]),
        created_utc=NOW,
    )
    plot = next(entry for entry in report.entries if entry.kind == "field_plot")
    assert plot.state == "missing"
    assert plot.required is False
    assert report.gaps.decision == "continue_with_caveat"
    assert report.gaps.next_action


def test_partial_and_valid_pixel_rule() -> None:
    """Low source coverage or valid-pixel coverage becomes partial with usable coverage."""
    report = assess_lidar_coverage(
        _request(
            [
                _evidence(kind="dem", coverage=100, valid=40),
                _evidence(kind="chm", coverage=20, valid=100),
            ],
            required=["dem", "chm"],
            optional=[],
        ),
        created_utc=NOW,
    )
    dem = next(entry for entry in report.entries if entry.kind == "dem")
    chm = next(entry for entry in report.entries if entry.kind == "chm")
    assert dem.state == "partial"
    assert dem.coverage_pct == 40
    assert dem.source_coverage_pct == 100
    assert chm.state == "partial"
    assert report.gaps.decision == "continue_with_caveat"
    assert validate_lidar_coverage(report).is_valid


def test_stale_evidence_is_not_contemporary() -> None:
    """An old acquisition is stale and names the refresh action."""
    report = assess_lidar_coverage(
        _request([_evidence(kind="dem", acquired=date(2010, 1, 1)), _evidence(kind="chm")]),
        created_utc=NOW,
    )
    dem = next(entry for entry in report.entries if entry.kind == "dem")
    assert dem.state == "stale"
    assert dem.vintage == "2010"
    assert "refresh" in dem.recommended_action
    assert report.gaps.decision == "continue_with_caveat"


def test_out_of_domain_stops_when_required() -> None:
    """An out-of-domain required model output stops and names the domain reason."""
    evidence = _evidence(
        kind="dem",
        applicability=Applicability(
            model_card_id="dem-card",
            in_domain=False,
            reason="outside predictor range",
        ),
    )
    report = assess_lidar_coverage(
        _request([evidence, _evidence(kind="chm")], optional=[]),
        created_utc=NOW,
    )
    dem = next(entry for entry in report.entries if entry.kind == "dem")
    assert dem.state == "out_of_domain"
    assert dem.reason == "outside predictor range"
    assert report.gaps.decision == "stop"
    assert validate_lidar_coverage(report).is_valid


def test_excluded_evidence_is_a_caveat() -> None:
    """A deliberate exclusion is explicit and continues with a caveat."""
    report = assess_lidar_coverage(
        _request(
            [
                _evidence(kind="dem", excluded=True, reason="non-forest mask"),
                _evidence(kind="chm"),
            ],
            optional=[],
        ),
        created_utc=NOW,
    )
    dem = next(entry for entry in report.entries if entry.kind == "dem")
    assert dem.state == "excluded"
    assert dem.reason == "non-forest mask"
    assert report.gaps.decision == "continue_with_caveat"
    assert validate_lidar_coverage(report).is_valid


def test_valid_pixel_absent_uses_source_coverage() -> None:
    """A missing valid-pixel record uses the source coverage without invention."""
    report = assess_lidar_coverage(
        _request([_evidence(kind="dem", valid=None), _evidence(kind="chm")], optional=[]),
        created_utc=NOW,
    )
    dem = next(entry for entry in report.entries if entry.kind == "dem")
    assert dem.valid_pixel_pct is None
    assert dem.state == "observed"
    assert dem.coverage_pct == 100


def test_zero_coverage_is_missing() -> None:
    """Zero usable coverage is missing, not a zero value."""
    report = assess_lidar_coverage(
        _request([_evidence(kind="dem", coverage=0, valid=0), _evidence(kind="chm")]),
        created_utc=NOW,
    )
    dem = next(entry for entry in report.entries if entry.kind == "dem")
    assert dem.state == "missing"
    assert dem.coverage_pct == 0
    assert dem.reason == "usable coverage is zero"


def test_request_and_evidence_validation_errors() -> None:
    """Duplicate segments, overlapping kinds, unknown kinds, and bad evidence fail."""
    with pytest.raises(ValidationError, match="unique"):
        LidarCoverageRequest(aoi="aoi", segment_ids=["s1", "s1"])
    with pytest.raises(ValidationError, match="must not overlap"):
        LidarCoverageRequest(
            aoi="aoi",
            segment_ids=["s1"],
            required_kinds=["dem"],
            optional_kinds=["dem"],
        )
    with pytest.raises(ValidationError, match="unknown evidence"):
        LidarCoverageRequest(
            aoi="aoi",
            segment_ids=["s1"],
            required_kinds=["unknown"],
        )
    with pytest.raises(ValidationError, match="at least one"):
        LidarCoverageRequest(
            aoi="aoi",
            segment_ids=["s1"],
            required_kinds=[],
            optional_kinds=[],
        )
    with pytest.raises(ValidationError, match="not requested"):
        _request([_evidence(segment_id="s2")])
    with pytest.raises(ValidationError, match="needs a reason"):
        _evidence(excluded=True)
    with pytest.raises(ValidationError, match="needs a reason"):
        Applicability(in_domain=False)


def test_duplicate_evidence_fails() -> None:
    """Two observations for the same segment/kind fail before a report is built."""
    with pytest.raises(LidarCoverageError, match="duplicate evidence"):
        assess_lidar_coverage(
            _request([_evidence(kind="dem"), _evidence(kind="dem")]),
        )


def test_defaults_and_config() -> None:
    """Default evidence kinds and configuration are explicit."""
    assert "point_cloud" in DEFAULT_REQUIRED_KINDS
    assert "field_plot" in DEFAULT_OPTIONAL_KINDS
    config = LidarCoverageConfig(max_age_years=5, min_coverage_pct=80)
    request = LidarCoverageRequest(aoi="aoi", segment_ids=["s1"], config=config)
    assert request.config.max_age_years == 5


def test_validation_names_bad_entries_and_refs() -> None:
    """Coverage validation catches entry and coverage-view inconsistencies."""
    report = assess_lidar_coverage(
        _request([_evidence(kind="dem"), _evidence(kind="chm")], optional=[]),
        created_utc=NOW,
    )
    entry = report.entries[0]
    cases = [
        (entry.model_copy(update={"state": "maybe"}), "LIDAR-COVERAGE-STATE"),
        (entry.model_copy(update={"valid_pixel_pct": 101}), "LIDAR-COVERAGE-VALID"),
        (
            entry.model_copy(update={"coverage_pct": 100, "source_coverage_pct": 20}),
            "LIDAR-COVERAGE-COVERAGE",
        ),
        (
            entry.model_copy(update={"state": "partial", "recommended_action": ""}),
            "LIDAR-COVERAGE-ACTION",
        ),
        (
            entry.model_copy(update={"state": "stale", "acquisition_date": None}),
            "LIDAR-COVERAGE-STALE",
        ),
        (
            entry.model_copy(
                update={
                    "state": "out_of_domain",
                    "applicability": Applicability(in_domain=True),
                }
            ),
            "LIDAR-COVERAGE-DOMAIN",
        ),
        (
            entry.model_copy(update={"state": "excluded", "reason": ""}),
            "LIDAR-COVERAGE-EXCLUDED",
        ),
    ]
    for bad_entry, prefix in cases:
        bad = report.model_copy(update={"entries": [bad_entry]})
        assert any(error.startswith(prefix) for error in validate_lidar_coverage(bad).errors), (
            prefix
        )
    bad_ref = report.model_copy(
        update={"entries": [entry.model_copy(update={"state": "missing", "coverage_pct": 0})]}
    )
    assert any(
        error.startswith("LIDAR-COVERAGE-REF") for error in validate_lidar_coverage(bad_ref).errors
    )
    duplicate = report.model_copy(update={"entries": [entry, entry]})
    assert any(
        error.startswith("LIDAR-COVERAGE-ID") for error in validate_lidar_coverage(duplicate).errors
    )
    naive = report.model_copy(update={"created_utc": datetime(2026, 11, 14)})
    assert any(
        error.startswith("LIDAR-COVERAGE-TIME") for error in validate_lidar_coverage(naive).errors
    )
    empty = LidarCoverageReport(
        created_utc=NOW,
        request=report.request,
        coverage=report.coverage.model_copy(update={"entries": []}),
        gaps=report.gaps,
    )
    result = validate_lidar_coverage(empty)
    assert any(warning.startswith("LIDAR-COVERAGE-EMPTY") for warning in result.warnings)


def test_validation_names_a_missing_coverage_reference() -> None:
    """An entry with no matching coverage-view key is named."""
    report = assess_lidar_coverage(
        _request([_evidence(kind="dem"), _evidence(kind="chm")], optional=[]),
        created_utc=NOW,
    )
    bad = report.model_copy(
        update={"entries": [report.entries[0].model_copy(update={"segment_id": "missing"})]}
    )
    assert any(
        error.startswith("LIDAR-COVERAGE-REF") for error in validate_lidar_coverage(bad).errors
    )
