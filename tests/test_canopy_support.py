"""Tests for canopy, cover, optional tree products, and VRI comparison support."""

from __future__ import annotations

from datetime import UTC, datetime

import numpy as np
import pytest
from brushline.integrations.canopy import (
    CanopyBand,
    CanopyConfig,
    CanopyRaster,
    CanopySupport,
    CanopySupportError,
    CanopySupportReport,
    TreeSupport,
    VriComparison,
    VriObservation,
    aggregate_canopy_support,
    validate_canopy_support,
)
from brushline.integrations.lidar import LidarProductProvenance
from brushline.integrations.terrain import SegmentWindow
from pydantic import ValidationError

NOW = datetime(2026, 11, 14, tzinfo=UTC)


def _provenance(
    *,
    product: str = "chm",
    crs: str = "EPSG:3005",
    resolution_m: float | None = 1.0,
    datum: str = "CGVD2013",
    product_id: str | None = None,
) -> LidarProductProvenance:
    return LidarProductProvenance(
        bundle_id="lidarbc-test",
        bundle_version="2026.1",
        femic_version="0.2.0a1",
        product_id=product_id or f"{product}-1",
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
) -> CanopyRaster:
    data = np.full((5, 5), 12.0) if values is None else values
    return CanopyRaster(
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
    buffer_m: float = 10.0,
    crs: str = "EPSG:3005",
) -> SegmentWindow:
    return SegmentWindow(
        segment_id=segment_id,
        coordinates=[(0.0, 2.5), (5.0, 2.5)],
        buffer_m=buffer_m,
        crs=crs,
    )


def _tree(segment_id: str = "s1") -> TreeSupport:
    return TreeSupport(
        segment_id=segment_id,
        provenance=_provenance(product="individual_tree", product_id="tree-1"),
        tree_count=3,
        mean_height_m=10.0,
        mean_crown_radius_m=2.0,
        species=["conifer"],
        model_card_id="tree-card",
    )


def test_observed_canopy_support_and_cover_thresholds() -> None:
    """A constant CHM produces observed height and cover support."""
    report = aggregate_canopy_support(
        _raster(),
        [_segment()],
        CanopyConfig(min_valid_pixels=4),
        created_utc=NOW,
    )
    assert validate_canopy_support(report).is_valid
    support = report.supports[0]
    assert support.state == "observed"
    assert support.coverage_pct == 100
    assert support.valid_pixels == 25
    assert support.height_mean_m == pytest.approx(12.0)
    assert support.height_median_m == pytest.approx(12.0)
    assert support.height_p90_m == pytest.approx(12.0)
    assert support.cover_2m_pct == 100
    assert support.cover_5m_pct == 100
    assert support.cover_10m_pct == 100
    assert support.cover_20m_pct == 0
    assert support.height_max_m == pytest.approx(12.0)


def test_height_statistics_and_structure() -> None:
    """Height statistics and optional vertical bands are recorded."""
    values = np.arange(25, dtype=float).reshape(5, 5)
    bands = [
        CanopyBand(lower_m=0, upper_m=5, cover_pct=25),
        CanopyBand(lower_m=5, upper_m=20, cover_pct=60),
    ]
    report = aggregate_canopy_support(
        _raster(values),
        [_segment()],
        CanopyConfig(min_valid_pixels=1),
        structures={"s1": bands},
        created_utc=NOW,
    )
    support = report.supports[0]
    assert support.height_max_m == 24
    assert support.height_p95_m is not None
    assert support.height_median_m is not None
    assert support.height_p95_m > support.height_median_m
    assert support.structure == bands


def test_optional_tree_and_vri_comparison() -> None:
    """Tree products are optional and VRI differences are recorded, not reconciled."""
    report = aggregate_canopy_support(
        _raster(),
        [_segment()],
        tree_supports=[_tree()],
        vri_observations=[
            VriObservation(
                segment_id="s1",
                height_m=10.0,
                cover_pct=40.0,
                vintage="2024",
                source="VRI",
                model_card_id="vri-card",
            )
        ],
        created_utc=NOW,
    )
    support = report.supports[0]
    assert support.tree is not None
    assert support.tree.tree_count == 3
    assert support.tree.species == ["conifer"]
    assert support.vri is not None
    assert support.vri.lidar_height_m == pytest.approx(12.0)
    assert support.vri.height_difference_m == pytest.approx(2.0)
    assert support.vri.lidar_cover_pct == 100
    assert support.vri.cover_difference_pct == pytest.approx(60.0)
    assert support.vri.note


def test_optional_products_absent() -> None:
    """Missing optional tree and VRI inputs do not block the build."""
    report = aggregate_canopy_support(_raster(), [_segment()], created_utc=NOW)
    support = report.supports[0]
    assert support.tree is None
    assert support.vri is None
    assert support.structure == []
    assert report.supports[0].state == "observed"


def test_partial_missing_and_out_of_domain_states() -> None:
    """Partial, missing, and out-of-domain states are explicit."""
    partial = aggregate_canopy_support(
        _raster(),
        [_segment()],
        CanopyConfig(min_valid_pixels=100),
        created_utc=NOW,
    ).supports[0]
    assert partial.state == "partial"
    assert partial.reason

    missing = aggregate_canopy_support(
        _raster(np.full((5, 5), np.nan)),
        [_segment()],
        created_utc=NOW,
    ).supports[0]
    assert missing.state == "missing"
    assert missing.valid_pixels == 0
    assert missing.height_mean_m is None
    assert missing.cover_2m_pct is None
    assert missing.reason

    out = aggregate_canopy_support(
        _raster(),
        [_segment()],
        CanopyConfig(domain_min_m=0, domain_max_m=10, max_out_of_domain_fraction=0.5),
        created_utc=NOW,
    ).supports[0]
    assert out.state == "out_of_domain"
    assert out.out_of_domain_fraction == 1.0
    assert out.reason


def test_nodata_and_negative_heights_are_invalid() -> None:
    """A nodata value and negative CHM values are excluded."""
    values = np.full((5, 5), 12.0)
    values[0, 0] = -9999
    report = aggregate_canopy_support(
        _raster(values, nodata=-9999),
        [_segment()],
        created_utc=NOW,
    )
    assert report.supports[0].valid_pixels == 24
    values[1, 1] = -2
    report = aggregate_canopy_support(
        _raster(values),
        [_segment()],
        created_utc=NOW,
    )
    assert report.supports[0].valid_pixels == 23


def test_missing_segment_with_vri_records_no_lidar_values() -> None:
    """A missing segment still records the VRI observation with empty LiDAR fields."""
    report = aggregate_canopy_support(
        _raster(np.full((5, 5), np.nan)),
        [_segment()],
        vri_observations=[
            VriObservation(
                segment_id="s1",
                height_m=8,
                cover_pct=30,
                vintage="2024",
                source="VRI",
            )
        ],
        created_utc=NOW,
    )
    support = report.supports[0]
    assert support.state == "missing"
    assert support.vri is not None
    assert support.vri.lidar_height_m is None
    assert support.vri.height_difference_m is None


def test_crs_mismatch_fails() -> None:
    """A segment CRS different from the CHM fails."""
    with pytest.raises(CanopySupportError, match="CRS"):
        aggregate_canopy_support(
            _raster(),
            [_segment(crs="EPSG:4326")],
        )


def test_chm_raster_provenance_and_shape_errors() -> None:
    """Wrong product, CRS, datum, resolution, shape, bounds, or resolution fail."""
    cases = [
        (_provenance(product="dem"), "CHM"),
        (_provenance(crs="EPSG:4326"), "CRS"),
        (_provenance(datum="NAVD88"), "vertical datum"),
        (_provenance(resolution_m=2), "resolution"),
    ]
    for provenance, message in cases:
        with pytest.raises(CanopySupportError, match=message):
            _raster(provenance=provenance)
    with pytest.raises(CanopySupportError, match="2D"):
        CanopyRaster(
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
    with pytest.raises(CanopySupportError, match="area"):
        CanopyRaster(
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
    with pytest.raises(CanopySupportError, match="positive"):
        CanopyRaster(
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
    with pytest.raises(CanopySupportError, match="required"):
        CanopyRaster(
            values=np.ones((2, 2)),
            min_x=0,
            min_y=0,
            max_x=1,
            max_y=1,
            crs="",
            resolution_m=1,
            vertical_datum="CGVD2013",
            provenance=_provenance(),
        )


def test_canopy_models_reject_invalid_inputs() -> None:
    """Band, tree, config, and support models reject impossible combinations."""
    with pytest.raises(ValidationError, match="upper_m"):
        CanopyBand(lower_m=5, upper_m=1, cover_pct=10)
    with pytest.raises(ValidationError, match="individual_tree"):
        TreeSupport(
            segment_id="s1",
            provenance=_provenance(product="chm"),
            tree_count=1,
            mean_height_m=1.0,
        )
    with pytest.raises(ValidationError, match="mean height"):
        TreeSupport(
            segment_id="s1",
            provenance=_provenance(product="individual_tree"),
            tree_count=1,
        )
    with pytest.raises(ValidationError, match="domain_max"):
        CanopyConfig(domain_min_m=20, domain_max_m=10)


def test_canopy_support_model_rejects_inconsistent_states() -> None:
    """The support model checks state, pixel counts, values, and references."""
    base = {
        "segment_id": "s1",
        "state": "observed",
        "coverage_pct": 100.0,
        "candidate_pixels": 10,
        "valid_pixels": 10,
        "height_mean_m": 12.0,
        "height_median_m": 12.0,
        "height_p90_m": 12.0,
        "height_p95_m": 12.0,
        "height_p99_m": 12.0,
        "height_max_m": 12.0,
        "cover_2m_pct": 100.0,
        "cover_5m_pct": 100.0,
        "cover_10m_pct": 100.0,
        "cover_20m_pct": 0.0,
        "buffer_m": 10.0,
    }
    cases: list[tuple[dict[str, object], str]] = [
        ({"state": "maybe"}, "unknown canopy state"),
        ({"valid_pixels": 11}, "valid_pixels cannot exceed"),
        ({"state": "missing"}, "zero valid pixels"),
        ({"state": "observed", "height_mean_m": None}, "needs a height"),
        ({"state": "partial"}, "needs a reason"),
        (
            {
                "tree": TreeSupport(
                    segment_id="other",
                    provenance=_provenance(product="individual_tree"),
                    tree_count=0,
                )
            },
            "tree support segment_id",
        ),
    ]
    for updates, message in cases:
        payload: dict[str, object] = dict(base)
        payload.update(updates)
        with pytest.raises(ValidationError, match=message):
            CanopySupport.model_validate(payload)


def test_canopy_validator_names_report_errors() -> None:
    """The report validator catches source, state, coverage, tree, VRI, and band errors."""
    report = aggregate_canopy_support(
        _raster(),
        [_segment()],
        tree_supports=[_tree()],
        vri_observations=[
            VriObservation(
                segment_id="s1",
                height_m=10,
                cover_pct=40,
                vintage="2024",
                source="VRI",
            )
        ],
        structures={"s1": [CanopyBand(lower_m=0, upper_m=5, cover_pct=30)]},
        created_utc=NOW,
    )
    source = report.model_copy(update={"source": _provenance(product="dem")})
    assert any(
        error.startswith("CANOPY-SOURCE") for error in validate_canopy_support(source).errors
    )
    bad_state = report.model_copy(
        update={"supports": [report.supports[0].model_copy(update={"state": "maybe"})]}
    )
    assert any(
        error.startswith("CANOPY-STATE") for error in validate_canopy_support(bad_state).errors
    )
    bad_pixels = report.model_copy(
        update={
            "supports": [
                report.supports[0].model_copy(update={"valid_pixels": 99, "candidate_pixels": 2})
            ]
        }
    )
    assert any(
        error.startswith("CANOPY-PIXELS") for error in validate_canopy_support(bad_pixels).errors
    )
    bad_tree = report.model_copy(
        update={
            "supports": [
                report.supports[0].model_copy(
                    update={
                        "tree": _tree("other"),
                    }
                )
            ]
        }
    )
    assert any(
        error.startswith("CANOPY-TREE") for error in validate_canopy_support(bad_tree).errors
    )
    vri = report.supports[0].vri
    assert vri is not None
    bad_vri = report.model_copy(
        update={
            "supports": [
                report.supports[0].model_copy(
                    update={"vri": vri.model_copy(update={"segment_id": "other"})}
                )
            ]
        }
    )
    assert any(error.startswith("CANOPY-VRI") for error in validate_canopy_support(bad_vri).errors)
    bad_band = report.model_copy(
        update={
            "supports": [
                report.supports[0].model_copy(
                    update={
                        "structure": [
                            CanopyBand(
                                lower_m=0,
                                upper_m=5,
                                cover_pct=30,
                            ).model_copy(update={"upper_m": 0})
                        ]
                    }
                )
            ]
        }
    )
    assert any(
        error.startswith("CANOPY-STRUCTURE") for error in validate_canopy_support(bad_band).errors
    )
    duplicate = report.model_copy(update={"supports": [report.supports[0], report.supports[0]]})
    assert any(error.startswith("CANOPY-ID") for error in validate_canopy_support(duplicate).errors)
    naive = report.model_copy(update={"created_utc": datetime(2026, 11, 14)})
    assert any(error.startswith("CANOPY-TIME") for error in validate_canopy_support(naive).errors)
    empty = CanopySupportReport(
        created_utc=NOW,
        crs=report.crs,
        resolution_m=report.resolution_m,
        vertical_datum=report.vertical_datum,
        raster_bounds=report.raster_bounds,
        source=report.source,
        config=report.config,
    )
    assert any(
        warning.startswith("CANOPY-EMPTY") for warning in validate_canopy_support(empty).warnings
    )
    assert not validate_canopy_support(empty).errors


def test_one_sided_domains_and_no_domain() -> None:
    """A one-sided domain and no domain are handled without inventing a rule."""
    lower_only = aggregate_canopy_support(
        _raster(),
        [_segment()],
        CanopyConfig(domain_min_m=10),
        created_utc=NOW,
    ).supports[0]
    assert lower_only.out_of_domain_fraction == 0
    assert lower_only.state == "observed"
    upper_only = aggregate_canopy_support(
        _raster(),
        [_segment()],
        CanopyConfig(domain_max_m=10),
        created_utc=NOW,
    ).supports[0]
    assert upper_only.out_of_domain_fraction == 1
    assert upper_only.state == "out_of_domain"
    no_domain = aggregate_canopy_support(_raster(), [_segment()], created_utc=NOW)
    assert no_domain.supports[0].out_of_domain_fraction == 0


def test_canopy_support_vri_segment_mismatch_model() -> None:
    """The support model rejects a VRI comparison for another segment."""
    base = {
        "segment_id": "s1",
        "state": "observed",
        "coverage_pct": 100.0,
        "candidate_pixels": 10,
        "valid_pixels": 10,
        "height_mean_m": 12.0,
        "height_median_m": 12.0,
        "height_p90_m": 12.0,
        "height_p95_m": 12.0,
        "height_p99_m": 12.0,
        "height_max_m": 12.0,
        "cover_2m_pct": 100.0,
        "cover_5m_pct": 100.0,
        "cover_10m_pct": 100.0,
        "cover_20m_pct": 0.0,
        "vri": VriComparison(
            segment_id="other",
            inventory_vintage="2024",
            vri_height_m=10,
            vri_cover_pct=40,
            source="VRI",
        ),
        "buffer_m": 10.0,
    }
    with pytest.raises(ValidationError, match="VRI comparison"):
        CanopySupport.model_validate(base)


def test_missing_support_with_values_is_rejected() -> None:
    """A missing support cannot carry canopy values."""
    base = {
        "segment_id": "s1",
        "state": "missing",
        "coverage_pct": 0.0,
        "candidate_pixels": 10,
        "valid_pixels": 0,
        "height_mean_m": 12.0,
        "buffer_m": 10.0,
    }
    with pytest.raises(ValidationError, match="no canopy values"):
        CanopySupport.model_validate(base)


def test_report_source_metadata_errors() -> None:
    """Source CRS, datum, and resolution mismatches are named."""
    report = aggregate_canopy_support(_raster(), [_segment()], created_utc=NOW)
    for source, prefix in (
        (_provenance(crs="EPSG:4326"), "CANOPY-CRS"),
        (_provenance(datum="NAVD88"), "CANOPY-DATUM"),
        (_provenance(resolution_m=2), "CANOPY-RESOLUTION"),
    ):
        bad = report.model_copy(update={"source": source})
        assert any(error.startswith(prefix) for error in validate_canopy_support(bad).errors)


def test_missing_and_state_reason_errors() -> None:
    """Missing pixels, missing reasons, and partial/out-of-domain reasons are checked."""
    report = aggregate_canopy_support(_raster(), [_segment()], created_utc=NOW)
    support = report.supports[0]
    missing_pixels = report.model_copy(
        update={
            "supports": [
                support.model_copy(
                    update={
                        "state": "missing",
                        "valid_pixels": 1,
                        "reason": "x",
                    }
                )
            ]
        }
    )
    assert any(
        error.startswith("CANOPY-MISSING")
        for error in validate_canopy_support(missing_pixels).errors
    )
    missing_reason = report.model_copy(
        update={
            "supports": [
                support.model_copy(
                    update={
                        "state": "missing",
                        "valid_pixels": 0,
                        "height_mean_m": None,
                        "height_median_m": None,
                        "height_p90_m": None,
                        "height_p95_m": None,
                        "height_p99_m": None,
                        "height_max_m": None,
                        "cover_2m_pct": None,
                        "cover_5m_pct": None,
                        "cover_10m_pct": None,
                        "cover_20m_pct": None,
                        "reason": "",
                    }
                )
            ]
        }
    )
    assert any(
        error.startswith("CANOPY-REASON")
        for error in validate_canopy_support(missing_reason).errors
    )
    out_reason = report.model_copy(
        update={"supports": [support.model_copy(update={"state": "out_of_domain", "reason": ""})]}
    )
    assert any(
        error.startswith("CANOPY-REASON") for error in validate_canopy_support(out_reason).errors
    )


def test_non_missing_without_height_and_observed_threshold_errors() -> None:
    """A non-missing support needs height; observed thresholds are enforced."""
    report = aggregate_canopy_support(_raster(), [_segment()], created_utc=NOW)
    support = report.supports[0]
    no_height = report.model_copy(
        update={"supports": [support.model_copy(update={"height_mean_m": None})]}
    )
    assert any(
        error.startswith("CANOPY-VALUE") for error in validate_canopy_support(no_height).errors
    )
    low_pixels = report.model_copy(
        update={
            "config": report.config.model_copy(update={"min_valid_pixels": 100}),
            "supports": [support.model_copy(update={"state": "observed"})],
        }
    )
    assert any(
        error.startswith("CANOPY-COVERAGE") for error in validate_canopy_support(low_pixels).errors
    )
    low_coverage = report.model_copy(
        update={
            "config": report.config.model_copy(update={"min_coverage_pct": 100}),
            "supports": [support.model_copy(update={"state": "observed", "coverage_pct": 50})],
        }
    )
    assert any(
        error.startswith("CANOPY-COVERAGE")
        for error in validate_canopy_support(low_coverage).errors
    )
