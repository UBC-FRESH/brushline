"""Tests for terrain and slope support over validated DEM/DSM provenance."""

from __future__ import annotations

import math
from datetime import UTC, datetime

import numpy as np
import pytest
from brushline.integrations.lidar import LidarProductProvenance
from brushline.integrations.terrain import (
    SegmentWindow,
    TerrainConfig,
    TerrainRaster,
    TerrainSupport,
    TerrainSupportError,
    TerrainSupportReport,
    aggregate_terrain_support,
    validate_terrain_support,
)

NOW = datetime(2026, 11, 14, tzinfo=UTC)


def _provenance(
    *,
    product: str = "dem",
    crs: str = "EPSG:3005",
    resolution_m: float | None = 1.0,
    datum: str = "CGVD2013",
) -> LidarProductProvenance:
    return LidarProductProvenance(
        bundle_id="lidarbc-test",
        bundle_version="2026.1",
        femic_version="0.2.0a1",
        product_id=f"{product}-1",
        product=product,
        sha256="a" * 64,
        crs=crs,
        resolution_m=resolution_m,
        vertical_datum=datum,
        licence_id="OGL-BC",
        retrieved_utc="2026-11-14T00:00:00+00:00",
        source_tile_ids=["tile-1"],
        source_layer_ids=[1],
        derived=False,
        lineage=[],
    )


def _raster(
    values: np.ndarray | None = None,
    *,
    provenance: LidarProductProvenance | None = None,
    nodata: float | None = None,
) -> TerrainRaster:
    data = np.full((5, 5), 100.0) if values is None else values
    return TerrainRaster(
        values=data,
        min_x=0.0,
        min_y=0.0,
        max_x=5.0,
        max_y=5.0,
        crs="EPSG:3005",
        resolution_m=1.0,
        vertical_datum="CGVD2013",
        provenance=provenance or _provenance(),
        nodata=nodata,
    )


def _segment(
    segment_id: str = "s1",
    *,
    coordinates: list[tuple[float, float]] | None = None,
    buffer_m: float = 10.0,
    crs: str = "EPSG:3005",
) -> SegmentWindow:
    return SegmentWindow(
        segment_id=segment_id,
        coordinates=coordinates or [(0.0, 2.5), (5.0, 2.5)],
        buffer_m=buffer_m,
        crs=crs,
    )


def _plane(slope_deg: float) -> np.ndarray:
    x = np.arange(5, dtype=float)[None, :]
    gradient = math.tan(math.radians(slope_deg))
    return np.full((5, 5), 100.0) + gradient * x


def test_aggregate_observed_support() -> None:
    """A fully valid plane maps to observed support with a recorded aggregation."""
    report = aggregate_terrain_support(
        _raster(_plane(12)),
        [_segment()],
        TerrainConfig(min_valid_pixels=4, min_coverage_pct=50),
        created_utc=NOW,
    )
    assert validate_terrain_support(report).is_valid
    support = report.supports[0]
    assert support.state == "observed"
    assert support.coverage_pct == 100
    assert support.valid_pixels == support.candidate_pixels == 25
    assert support.elevation_m is not None
    assert support.slope_deg == pytest.approx(12, abs=0.01)
    assert support.aspect_deg is not None
    assert support.terrain_class == "moderate"
    assert support.access_proxy == pytest.approx(1 - 12 / 30, abs=0.001)
    assert support.access_class == "moderate"
    assert report.source.product == "dem"
    assert report.config.statistic == "mean"


@pytest.mark.parametrize("statistic", ["mean", "median", "min", "max", "p90"])
def test_each_statistic_is_supported(statistic: str) -> None:
    """Every documented statistic has a deterministic result."""
    report = aggregate_terrain_support(
        _raster(_plane(5)),
        [_segment()],
        TerrainConfig(statistic=statistic, min_valid_pixels=1),
        created_utc=NOW,
    )
    assert report.supports[0].elevation_m is not None
    assert report.supports[0].statistic == statistic


def test_nodata_and_partial_coverage() -> None:
    """A partly valid raster becomes partial, not a fabricated zero."""
    values = np.full((5, 5), np.nan)
    values[2:5, 2:5] = 100.0
    report = aggregate_terrain_support(
        _raster(values),
        [_segment()],
        TerrainConfig(min_valid_pixels=10, min_coverage_pct=90),
        created_utc=NOW,
    )
    support = report.supports[0]
    assert support.state == "partial"
    assert 0 < support.valid_pixels < support.candidate_pixels
    assert 0 < support.coverage_pct < 100
    assert support.elevation_m is not None
    assert support.reason
    assert validate_terrain_support(report).is_valid


def test_nodata_value_is_masked() -> None:
    """A nodata value is removed before aggregation."""
    values = np.full((5, 5), 100.0)
    values[0, 0] = -9999
    report = aggregate_terrain_support(
        _raster(values, nodata=-9999),
        [_segment()],
        TerrainConfig(min_valid_pixels=1),
        created_utc=NOW,
    )
    assert report.supports[0].valid_pixels == 22


def test_missing_support_for_no_valid_cells() -> None:
    """A segment with no valid cells is missing with a reason."""
    values = np.full((5, 5), np.nan)
    report = aggregate_terrain_support(
        _raster(values),
        [_segment()],
        TerrainConfig(min_valid_pixels=1),
        created_utc=NOW,
    )
    support = report.supports[0]
    assert support.state == "missing"
    assert support.valid_pixels == 0
    assert support.coverage_pct == 0
    assert support.elevation_m is None
    assert support.slope_deg is None
    assert support.access_class == "unknown"
    assert support.reason
    assert validate_terrain_support(report).is_valid


def test_segment_outside_the_raster_is_missing() -> None:
    """A segment far from the raster has no candidate cells."""
    report = aggregate_terrain_support(
        _raster(_plane(5)),
        [_segment(coordinates=[(100.0, 100.0), (101.0, 100.0)], buffer_m=1)],
        TerrainConfig(min_valid_pixels=1),
        created_utc=NOW,
    )
    support = report.supports[0]
    assert support.state == "missing"
    assert support.candidate_pixels == 0
    assert support.valid_pixels == 0


@pytest.mark.parametrize(
    ("slope_deg", "terrain_class", "access_class"),
    [
        (0, "flat", "high"),
        (5, "gentle", "high"),
        (15, "moderate", "moderate"),
        (25, "steep", "low"),
        (40, "very_steep", "low"),
    ],
)
def test_slope_classes_and_access_proxy(
    slope_deg: float,
    terrain_class: str,
    access_class: str,
) -> None:
    """Slope classes and the access proxy follow the documented thresholds."""
    report = aggregate_terrain_support(
        _raster(_plane(slope_deg)),
        [_segment()],
        TerrainConfig(min_valid_pixels=1),
        created_utc=NOW,
    )
    support = report.supports[0]
    assert support.terrain_class == terrain_class
    assert support.access_class == access_class


def test_buffered_segment_selects_a_band() -> None:
    """The buffer limits support to cells near the segment polyline."""
    report = aggregate_terrain_support(
        _raster(_plane(5)),
        [_segment(coordinates=[(0.0, 2.5), (5.0, 2.5)], buffer_m=1.1)],
        TerrainConfig(min_valid_pixels=1),
        created_utc=NOW,
    )
    support = report.supports[0]
    assert 0 < support.candidate_pixels < 25


def test_crs_mismatch_fails_without_reprojection() -> None:
    """A segment CRS different from the raster fails."""
    with pytest.raises(TerrainSupportError, match="CRS"):
        aggregate_terrain_support(
            _raster(_plane(5)),
            [_segment(crs="EPSG:4326")],
        )


def test_unknown_statistic_fails() -> None:
    """An unknown statistic fails before aggregation."""
    with pytest.raises(TerrainSupportError, match="statistic"):
        aggregate_terrain_support(
            _raster(_plane(5)),
            [_segment()],
            TerrainConfig(statistic="sum"),
        )


def test_raster_provenance_and_shape_errors() -> None:
    """Wrong product, CRS, datum, resolution, shape, bounds, or resolution fail."""
    cases = [
        (_provenance(product="point_cloud"), "DEM or DSM"),
        (_provenance(crs="EPSG:4326"), "CRS"),
        (_provenance(datum="NAVD88"), "vertical datum"),
        (_provenance(resolution_m=2), "resolution"),
    ]
    for provenance, message in cases:
        with pytest.raises(TerrainSupportError, match=message):
            _raster(provenance=provenance)
    with pytest.raises(TerrainSupportError, match="2D"):
        TerrainRaster(
            values=np.array([1.0]),
            min_x=0,
            min_y=0,
            max_x=1,
            max_y=1,
            crs="EPSG:3005",
            resolution_m=1,
            vertical_datum="CGVD2013",
            provenance=_provenance(),
        )
    with pytest.raises(TerrainSupportError, match="area"):
        TerrainRaster(
            values=np.ones((2, 2)),
            min_x=0,
            min_y=0,
            max_x=0,
            max_y=1,
            crs="EPSG:3005",
            resolution_m=1,
            vertical_datum="CGVD2013",
            provenance=_provenance(),
        )
    with pytest.raises(TerrainSupportError, match="positive"):
        TerrainRaster(
            values=np.ones((2, 2)),
            min_x=0,
            min_y=0,
            max_x=1,
            max_y=1,
            crs="EPSG:3005",
            resolution_m=0,
            vertical_datum="CGVD2013",
            provenance=_provenance(),
        )


def test_validation_names_bad_report_fields() -> None:
    """Terrain validation catches source, state, coverage, and value errors."""
    report = aggregate_terrain_support(
        _raster(_plane(5)),
        [_segment()],
        TerrainConfig(min_valid_pixels=4),
        created_utc=NOW,
    )
    bad_source = report.model_copy(update={"source": _provenance(product="point_cloud")})
    assert any(
        error.startswith("TERRAIN-SOURCE") for error in validate_terrain_support(bad_source).errors
    )
    bad_state = report.model_copy(
        update={"supports": [report.supports[0].model_copy(update={"state": "maybe"})]}
    )
    assert any(
        error.startswith("TERRAIN-STATE") for error in validate_terrain_support(bad_state).errors
    )
    bad_pixels = report.model_copy(
        update={
            "supports": [
                report.supports[0].model_copy(update={"valid_pixels": 99, "candidate_pixels": 2})
            ]
        }
    )
    assert any(
        error.startswith("TERRAIN-PIXELS") for error in validate_terrain_support(bad_pixels).errors
    )
    observed_low = report.model_copy(
        update={
            "config": report.config.model_copy(update={"min_valid_pixels": 100}),
            "supports": [report.supports[0].model_copy(update={"state": "observed"})],
        }
    )
    assert any(
        error.startswith("TERRAIN-COVERAGE")
        for error in validate_terrain_support(observed_low).errors
    )
    missing_values = report.model_copy(
        update={
            "supports": [
                report.supports[0].model_copy(
                    update={
                        "state": "missing",
                        "valid_pixels": 0,
                        "candidate_pixels": 1,
                        "elevation_m": None,
                        "slope_deg": None,
                        "aspect_deg": None,
                        "access_proxy": None,
                        "reason": "",
                    }
                )
            ]
        }
    )
    assert any(
        error.startswith("TERRAIN-REASON")
        for error in validate_terrain_support(missing_values).errors
    )
    missing_pixels = report.model_copy(
        update={
            "supports": [
                report.supports[0].model_copy(update={"state": "missing", "valid_pixels": 1})
            ]
        }
    )
    assert any(
        error.startswith("TERRAIN-MISSING")
        for error in validate_terrain_support(missing_pixels).errors
    )
    duplicate = report.model_copy(update={"supports": [report.supports[0], report.supports[0]]})
    assert any(
        error.startswith("TERRAIN-ID") for error in validate_terrain_support(duplicate).errors
    )
    naive = report.model_copy(update={"created_utc": datetime(2026, 11, 14)})
    assert any(error.startswith("TERRAIN-TIME") for error in validate_terrain_support(naive).errors)
    empty = TerrainSupportReport(
        created_utc=NOW,
        crs=report.crs,
        resolution_m=report.resolution_m,
        vertical_datum=report.vertical_datum,
        raster_bounds=report.raster_bounds,
        source=report.source,
        config=report.config,
    )
    assert any(
        warning.startswith("TERRAIN-EMPTY") for warning in validate_terrain_support(empty).warnings
    )
    assert not validate_terrain_support(empty).errors


def test_support_model_rejects_inconsistent_states() -> None:
    """The TerrainSupport model rejects impossible state/value combinations."""
    from pydantic import ValidationError

    base = {
        "segment_id": "s1",
        "state": "observed",
        "coverage_pct": 100.0,
        "candidate_pixels": 10,
        "valid_pixels": 10,
        "elevation_m": 100.0,
        "slope_deg": 5.0,
        "aspect_deg": 180.0,
        "terrain_class": "gentle",
        "access_proxy": 0.8,
        "access_class": "high",
        "statistic": "mean",
        "buffer_m": 10.0,
    }
    cases: list[tuple[dict[str, object], str]] = [
        ({"state": "maybe"}, "unknown terrain state"),
        ({"valid_pixels": 11}, "valid_pixels cannot exceed"),
        ({"state": "missing", "valid_pixels": 1}, "zero valid pixels"),
        ({"state": "missing", "valid_pixels": 0, "elevation_m": 1.0}, "no terrain values"),
        ({"state": "observed", "elevation_m": None}, "needs elevation"),
        ({"terrain_class": "other"}, "unknown terrain class"),
        ({"access_class": "other"}, "unknown access class"),
    ]
    for updates, message in cases:
        payload: dict[str, object] = dict(base)
        payload.update(updates)
        with pytest.raises(ValidationError, match=message):
            TerrainSupport.model_validate(payload)


def test_raster_requires_crs_and_datum() -> None:
    """An empty raster CRS or vertical datum fails."""
    with pytest.raises(TerrainSupportError, match="required"):
        _raster(provenance=_provenance()).__class__(
            values=np.ones((2, 2)),
            min_x=0,
            min_y=0,
            max_x=2,
            max_y=2,
            crs="",
            resolution_m=1,
            vertical_datum="CGVD2013",
            provenance=_provenance(),
        )


def test_negative_buffer_and_zero_length_segment() -> None:
    """A negative buffer fails; a zero-length segment still has support."""
    raster = _raster(_plane(5))
    segment = _segment(coordinates=[(2.5, 2.5), (2.5, 2.5)], buffer_m=1.0)
    report = aggregate_terrain_support(
        raster,
        [segment],
        TerrainConfig(min_valid_pixels=1),
        created_utc=NOW,
    )
    assert report.supports[0].state == "observed"
    with pytest.raises(TerrainSupportError, match="buffer"):
        aggregate_terrain_support(
            raster,
            [segment.model_copy(update={"buffer_m": -1.0})],
        )


def test_report_source_and_config_mismatches_are_named() -> None:
    """Source CRS, datum, resolution, and config rules are checked in the report."""
    report = aggregate_terrain_support(
        _raster(_plane(5)),
        [_segment()],
        TerrainConfig(min_valid_pixels=1),
        created_utc=NOW,
    )
    for source, prefix in (
        (_provenance(crs="EPSG:4326"), "TERRAIN-CRS"),
        (_provenance(datum="NAVD88"), "TERRAIN-DATUM"),
        (_provenance(resolution_m=2), "TERRAIN-RESOLUTION"),
    ):
        bad = report.model_copy(update={"source": source})
        assert any(error.startswith(prefix) for error in validate_terrain_support(bad).errors)
    bad_config = report.model_copy(
        update={"config": report.config.model_copy(update={"statistic": "sum"})}
    )
    assert any(
        error.startswith("TERRAIN-CONFIG") for error in validate_terrain_support(bad_config).errors
    )


def test_report_observed_below_coverage_and_without_values() -> None:
    """Observed support below the coverage rule or without values fails."""
    report = aggregate_terrain_support(
        _raster(_plane(5)),
        [_segment()],
        TerrainConfig(min_valid_pixels=1),
        created_utc=NOW,
    )
    low = report.model_copy(
        update={
            "config": report.config.model_copy(update={"min_coverage_pct": 100}),
            "supports": [
                report.supports[0].model_copy(update={"state": "observed", "coverage_pct": 50})
            ],
        }
    )
    assert any(
        error.startswith("TERRAIN-COVERAGE") for error in validate_terrain_support(low).errors
    )
    no_values = report.model_copy(
        update={
            "supports": [
                report.supports[0].model_copy(
                    update={
                        "state": "observed",
                        "elevation_m": None,
                        "slope_deg": None,
                    }
                )
            ]
        }
    )
    assert any(
        error.startswith("TERRAIN-VALUE") for error in validate_terrain_support(no_values).errors
    )
    no_access = report.model_copy(
        update={
            "supports": [
                report.supports[0].model_copy(update={"state": "observed", "access_proxy": None})
            ]
        }
    )
    assert any(
        warning.startswith("TERRAIN-ACCESS")
        for warning in validate_terrain_support(no_access).warnings
    )


def test_support_with_no_valid_pixels_in_a_non_missing_state_fails() -> None:
    """A non-missing support with zero valid pixels fails."""
    report = aggregate_terrain_support(
        _raster(_plane(5)),
        [_segment()],
        TerrainConfig(min_valid_pixels=1),
        created_utc=NOW,
    )
    bad = report.model_copy(
        update={
            "supports": [
                report.supports[0].model_copy(update={"state": "partial", "valid_pixels": 0})
            ]
        }
    )
    assert any(
        error.startswith("TERRAIN-COVERAGE") for error in validate_terrain_support(bad).errors
    )


def test_private_statistic_rejects_unknown_name() -> None:
    """The internal statistic helper rejects an unknown name."""
    from brushline.integrations.terrain import _statistic

    with pytest.raises(TerrainSupportError, match="statistic"):
        _statistic(np.array([1.0, 2.0]), "sum")
