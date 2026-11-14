"""Canopy, cover, and optional tree support for corridor segments.

The adapter maps a validated CHM to buffered segment support, records height and cover statistics,
keeps optional vertical structure and tree products separate, and records a VRI comparison without
silently reconciling it. It does not generate a CHM, segment trees, classify species, or decide the
low-vegetation state.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal

import numpy as np
from pydantic import BaseModel, ConfigDict, Field, model_validator

from brushline.integrations.lidar import LidarProductProvenance
from brushline.integrations.terrain import SegmentWindow, segment_buffer_mask
from brushline.model.validation import ContractValidation, check_duplicates

CANOPY_SUPPORT_SCHEMA_VERSION: Literal["brushline.canopy-support.v1"] = (
    "brushline.canopy-support.v1"
)
CANOPY_STATES: tuple[str, ...] = ("observed", "partial", "missing", "out_of_domain")
COVER_THRESHOLDS_M: tuple[float, ...] = (2.0, 5.0, 10.0, 20.0)
CANOPY_PRODUCT_KINDS: frozenset[str] = frozenset({"chm"})
TREE_PRODUCT_KINDS: frozenset[str] = frozenset({"individual_tree"})


class CanopySupportError(ValueError):
    """Raised when a CHM or canopy support input is invalid."""


class CanopyBand(BaseModel):
    """One vertical canopy band.

    Parameters
    ----------
    lower_m : float
        Lower height bound.
    upper_m : float
        Upper height bound.
    cover_pct : float
        Cover percentage in the band.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    lower_m: float = Field(ge=0)
    upper_m: float = Field(gt=0)
    cover_pct: float = Field(ge=0, le=100)

    @model_validator(mode="after")
    def _ordered(self) -> CanopyBand:
        if self.upper_m <= self.lower_m:
            raise ValueError("canopy band upper_m must exceed lower_m")
        return self


class TreeSupport(BaseModel):
    """Optional individual-tree summary for one segment.

    Parameters
    ----------
    segment_id : str
        Segment id.
    provenance : LidarProductProvenance
        Individual-tree product provenance.
    tree_count : int
        Tree count.
    mean_height_m : float or None
        Mean tree height.
    mean_crown_radius_m : float or None
        Mean crown radius.
    species : list of str
        Species labels.
    model_card_id : str or None
        Optional model card.
    note : str
        Optional note.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    segment_id: str = Field(min_length=1)
    provenance: LidarProductProvenance
    tree_count: int = Field(ge=0)
    mean_height_m: float | None = Field(default=None, ge=0)
    mean_crown_radius_m: float | None = Field(default=None, ge=0)
    species: list[str] = Field(default_factory=list)
    model_card_id: str | None = None
    note: str = ""

    @model_validator(mode="after")
    def _tree_product(self) -> TreeSupport:
        if self.provenance.product not in TREE_PRODUCT_KINDS:
            raise ValueError("tree support must use an individual_tree product")
        if self.tree_count > 0 and self.mean_height_m is None:
            raise ValueError("a non-empty tree product needs a mean height")
        return self


class VriObservation(BaseModel):
    """A VRI inventory observation for one segment.

    Parameters
    ----------
    segment_id : str
        Segment id.
    height_m : float
        VRI height.
    cover_pct : float
        VRI cover percentage.
    vintage : str
        Inventory vintage.
    source : str
        Inventory source.
    model_card_id : str or None
        Optional model card.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    segment_id: str = Field(min_length=1)
    height_m: float = Field(ge=0)
    cover_pct: float = Field(ge=0, le=100)
    vintage: str = Field(min_length=1)
    source: str = Field(min_length=1)
    model_card_id: str | None = None


class VriComparison(BaseModel):
    """The recorded difference between LiDAR support and VRI.

    Parameters
    ----------
    segment_id : str
        Segment id.
    inventory_vintage : str
        VRI vintage.
    vri_height_m : float
        VRI height.
    lidar_height_m : float or None
        LiDAR height, when available.
    height_difference_m : float or None
        LiDAR height minus VRI height.
    vri_cover_pct : float
        VRI cover.
    lidar_cover_pct : float or None
        LiDAR cover at 10 m, when available.
    cover_difference_pct : float or None
        LiDAR cover minus VRI cover.
    source : str
        VRI source.
    model_card_id : str or None
        Optional VRI model card.
    note : str
        Comparison note.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    segment_id: str = Field(min_length=1)
    inventory_vintage: str = Field(min_length=1)
    vri_height_m: float = Field(ge=0)
    lidar_height_m: float | None = Field(default=None, ge=0)
    height_difference_m: float | None = None
    vri_cover_pct: float = Field(ge=0, le=100)
    lidar_cover_pct: float | None = Field(default=None, ge=0, le=100)
    cover_difference_pct: float | None = None
    source: str = Field(min_length=1)
    model_card_id: str | None = None
    note: str = ""


class CanopyConfig(BaseModel):
    """Aggregation and applicability rules for canopy support.

    Parameters
    ----------
    min_valid_pixels : int, optional
        Minimum valid CHM cells for observed support. Defaults to ``4``.
    min_coverage_pct : float, optional
        Minimum valid-cell percentage for observed support. Defaults to ``50``.
    domain_min_m : float or None, optional
        Lower height of the applicability domain.
    domain_max_m : float or None, optional
        Upper height of the applicability domain.
    max_out_of_domain_fraction : float, optional
        Maximum fraction of valid cells outside the domain. Defaults to ``0.5``.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    min_valid_pixels: int = Field(default=4, ge=1)
    min_coverage_pct: float = Field(default=50.0, ge=0, le=100)
    domain_min_m: float | None = Field(default=None, ge=0)
    domain_max_m: float | None = Field(default=None, gt=0)
    max_out_of_domain_fraction: float = Field(default=0.5, ge=0, le=1)

    @model_validator(mode="after")
    def _ordered_domain(self) -> CanopyConfig:
        if (
            self.domain_min_m is not None
            and self.domain_max_m is not None
            and self.domain_max_m <= self.domain_min_m
        ):
            raise ValueError("domain_max_m must exceed domain_min_m")
        return self


class CanopySupport(BaseModel):
    """One segment's canopy support.

    Parameters
    ----------
    segment_id : str
        Segment id.
    state : str
        ``observed``, ``partial``, ``missing``, or ``out_of_domain``.
    coverage_pct : float
        Valid-cell percentage.
    candidate_pixels : int
        Cells within the buffer.
    valid_pixels : int
        Cells with finite, non-negative CHM values.
    height_mean_m, height_median_m, height_p90_m, height_p95_m, height_p99_m, height_max_m :
        float or None
        Height statistics.
    cover_2m_pct, cover_5m_pct, cover_10m_pct, cover_20m_pct : float or None
        Cover at the four thresholds.
    structure : list of CanopyBand
        Optional vertical structure.
    tree : TreeSupport or None
        Optional tree product.
    vri : VriComparison or None
        Optional VRI comparison.
    domain_min_m, domain_max_m : float or None
        Applicability domain used.
    out_of_domain_fraction : float
        Fraction of valid cells outside the domain.
    buffer_m : float
        Segment buffer.
    reason : str
        Why support is partial, missing, or out of domain.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    segment_id: str = Field(min_length=1)
    state: str
    coverage_pct: float = Field(ge=0, le=100)
    candidate_pixels: int = Field(ge=0)
    valid_pixels: int = Field(ge=0)
    height_mean_m: float | None = Field(default=None, ge=0)
    height_median_m: float | None = Field(default=None, ge=0)
    height_p90_m: float | None = Field(default=None, ge=0)
    height_p95_m: float | None = Field(default=None, ge=0)
    height_p99_m: float | None = Field(default=None, ge=0)
    height_max_m: float | None = Field(default=None, ge=0)
    cover_2m_pct: float | None = Field(default=None, ge=0, le=100)
    cover_5m_pct: float | None = Field(default=None, ge=0, le=100)
    cover_10m_pct: float | None = Field(default=None, ge=0, le=100)
    cover_20m_pct: float | None = Field(default=None, ge=0, le=100)
    structure: list[CanopyBand] = Field(default_factory=list)
    tree: TreeSupport | None = None
    vri: VriComparison | None = None
    domain_min_m: float | None = None
    domain_max_m: float | None = None
    out_of_domain_fraction: float = Field(default=0.0, ge=0, le=1)
    buffer_m: float = Field(ge=0)
    reason: str = ""

    @model_validator(mode="after")
    def _state_consistency(self) -> CanopySupport:
        if self.state not in CANOPY_STATES:
            raise ValueError(f"unknown canopy state {self.state!r}")
        if self.valid_pixels > self.candidate_pixels:
            raise ValueError("valid_pixels cannot exceed candidate_pixels")
        if self.tree is not None and self.tree.segment_id != self.segment_id:
            raise ValueError("tree support segment_id must match the canopy support")
        if self.vri is not None and self.vri.segment_id != self.segment_id:
            raise ValueError("VRI comparison segment_id must match the canopy support")
        if self.state == "missing":
            if self.valid_pixels != 0:
                raise ValueError("a missing support must have zero valid pixels")
            if any(
                value is not None
                for value in (
                    self.height_mean_m,
                    self.height_median_m,
                    self.height_p90_m,
                    self.height_p95_m,
                    self.height_p99_m,
                    self.height_max_m,
                    self.cover_2m_pct,
                    self.cover_5m_pct,
                    self.cover_10m_pct,
                    self.cover_20m_pct,
                )
            ):
                raise ValueError("a missing support must have no canopy values")
        elif self.height_mean_m is None:
            raise ValueError("non-missing support needs a height statistic")
        if self.state in ("partial", "out_of_domain") and not self.reason.strip():
            raise ValueError("partial or out-of-domain support needs a reason")
        return self


class CanopySupportReport(BaseModel):
    """The canopy support report for one CHM.

    Parameters
    ----------
    schema_version : {"brushline.canopy-support.v1"}
        Report schema version.
    created_utc : datetime
        Timezone-aware creation time.
    crs : str
        Raster CRS.
    resolution_m : float
        Raster resolution.
    vertical_datum : str
        Raster vertical datum.
    raster_bounds : list of float
        ``min_x, min_y, max_x, max_y``.
    source : LidarProductProvenance
        CHM provenance.
    config : CanopyConfig
        Aggregation and applicability rules.
    supports : list of CanopySupport
        Segment support.
    """

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["brushline.canopy-support.v1"] = CANOPY_SUPPORT_SCHEMA_VERSION
    created_utc: datetime
    crs: str = Field(min_length=1)
    resolution_m: float = Field(gt=0)
    vertical_datum: str = Field(min_length=1)
    raster_bounds: list[float] = Field(min_length=4, max_length=4)
    source: LidarProductProvenance
    config: CanopyConfig
    supports: list[CanopySupport] = Field(default_factory=list)


@dataclass(frozen=True)
class CanopyRaster:
    """A north-up CHM raster with validated provenance.

    Parameters
    ----------
    values : numpy.ndarray
        Two-dimensional CHM array with row zero at the north edge.
    min_x : float
        Western edge.
    min_y : float
        Southern edge.
    max_x : float
        Eastern edge.
    max_y : float
        Northern edge.
    crs : str
        Raster CRS.
    resolution_m : float
        Cell size in metres.
    vertical_datum : str
        Vertical datum.
    provenance : LidarProductProvenance
        Validated CHM provenance.
    nodata : float or None, optional
        Nodata value.
    """

    values: np.ndarray
    min_x: float
    min_y: float
    max_x: float
    max_y: float
    crs: str
    resolution_m: float
    vertical_datum: str
    provenance: LidarProductProvenance
    nodata: float | None = None

    def __post_init__(self) -> None:
        """Validate the CHM shape, provenance, and bounds."""
        if self.values.ndim != 2 or self.values.size == 0:
            raise CanopySupportError("CHM values must be a non-empty 2D array")
        if self.max_x <= self.min_x or self.max_y <= self.min_y:
            raise CanopySupportError("CHM bounds must have positive area")
        if self.resolution_m <= 0:
            raise CanopySupportError("CHM resolution must be positive")
        if not self.crs or not self.vertical_datum:
            raise CanopySupportError("CHM CRS and vertical datum are required")
        if self.provenance.product not in CANOPY_PRODUCT_KINDS:
            raise CanopySupportError("canopy provenance must be a CHM product")
        if self.provenance.crs != self.crs:
            raise CanopySupportError("CHM provenance CRS does not match the raster")
        if self.provenance.resolution_m is not None and not math.isclose(
            self.provenance.resolution_m, self.resolution_m
        ):
            raise CanopySupportError("CHM provenance resolution does not match the raster")
        if self.provenance.vertical_datum != self.vertical_datum:
            raise CanopySupportError("CHM provenance vertical datum does not match the raster")

    def cell_centers(self) -> tuple[np.ndarray, np.ndarray]:
        """Return cell-center x and y arrays.

        Returns
        -------
        tuple of numpy.ndarray
            Two arrays with the raster shape.
        """
        rows, cols = self.values.shape
        xs = self.min_x + (np.arange(cols) + 0.5) * self.resolution_m
        ys = self.max_y - (np.arange(rows) + 0.5) * self.resolution_m
        x_grid, y_grid = np.meshgrid(xs, ys)
        return x_grid, y_grid


def aggregate_canopy_support(
    raster: CanopyRaster,
    segments: list[SegmentWindow],
    config: CanopyConfig | None = None,
    *,
    structures: Mapping[str, Sequence[CanopyBand]] | None = None,
    tree_supports: Sequence[TreeSupport] | None = None,
    vri_observations: Sequence[VriObservation] | None = None,
    created_utc: datetime | None = None,
) -> CanopySupportReport:
    """Aggregate a validated CHM to buffered segment support.

    Parameters
    ----------
    raster : CanopyRaster
        North-up CHM with validated provenance.
    segments : list of SegmentWindow
        Buffered segment polylines.
    config : CanopyConfig, optional
        Aggregation and applicability rules.
    structures : mapping of str to sequence of CanopyBand, optional
        Vertical structure by segment.
    tree_supports : sequence of TreeSupport, optional
        Optional individual-tree summaries.
    vri_observations : sequence of VriObservation, optional
        VRI inventory observations.
    created_utc : datetime, optional
        Report time. Defaults to the current UTC time.

    Returns
    -------
    CanopySupportReport
        Segment canopy support with provenance and comparison evidence.

    Raises
    ------
    CanopySupportError
        When a segment CRS differs from the CHM CRS.
    """
    rules = config or CanopyConfig()
    x_grid, y_grid = raster.cell_centers()
    heights = raster.values.astype(float)
    if raster.nodata is not None:
        heights = np.where(heights == raster.nodata, np.nan, heights)
    valid = np.isfinite(heights) & (heights >= 0)
    trees = {item.segment_id: item for item in tree_supports or []}
    vri = {item.segment_id: item for item in vri_observations or []}
    bands = structures or {}
    supports: list[CanopySupport] = []
    for segment in segments:
        if segment.crs != raster.crs:
            raise CanopySupportError(
                f"segment {segment.segment_id} CRS {segment.crs!r} does not match "
                f"CHM CRS {raster.crs!r}; explicit transformation is required"
            )
        support_mask = segment_buffer_mask(
            x_grid,
            y_grid,
            np.asarray(segment.coordinates, dtype=float),
            segment.buffer_m,
        )
        candidate = int(np.count_nonzero(support_mask))
        chosen = support_mask & valid
        valid_pixels = int(np.count_nonzero(chosen))
        coverage = 100.0 * valid_pixels / candidate if candidate else 0.0
        support_structure = list(bands.get(segment.segment_id, ()))
        tree = trees.get(segment.segment_id)
        comparison = _vri_comparison(
            segment.segment_id, vri.get(segment.segment_id), chosen, heights
        )
        if valid_pixels == 0:
            supports.append(
                CanopySupport(
                    segment_id=segment.segment_id,
                    state="missing",
                    coverage_pct=0.0,
                    candidate_pixels=candidate,
                    valid_pixels=0,
                    structure=support_structure,
                    tree=tree,
                    vri=comparison,
                    domain_min_m=rules.domain_min_m,
                    domain_max_m=rules.domain_max_m,
                    buffer_m=segment.buffer_m,
                    reason="no valid CHM cells within the segment buffer",
                )
            )
            continue
        values = heights[chosen]
        domain_fraction = _out_of_domain_fraction(values, rules)
        if valid_pixels < rules.min_valid_pixels or coverage < rules.min_coverage_pct:
            state = "partial"
            reason = "valid coverage is below the threshold"
        elif domain_fraction > rules.max_out_of_domain_fraction:
            state = "out_of_domain"
            reason = "the CHM values are outside the configured applicability domain"
        else:
            state = "observed"
            reason = ""
        supports.append(
            CanopySupport(
                segment_id=segment.segment_id,
                state=state,
                coverage_pct=coverage,
                candidate_pixels=candidate,
                valid_pixels=valid_pixels,
                height_mean_m=float(np.mean(values)),
                height_median_m=float(np.median(values)),
                height_p90_m=float(np.percentile(values, 90)),
                height_p95_m=float(np.percentile(values, 95)),
                height_p99_m=float(np.percentile(values, 99)),
                height_max_m=float(np.max(values)),
                cover_2m_pct=_cover_pct(values, 2.0),
                cover_5m_pct=_cover_pct(values, 5.0),
                cover_10m_pct=_cover_pct(values, 10.0),
                cover_20m_pct=_cover_pct(values, 20.0),
                structure=support_structure,
                tree=tree,
                vri=comparison,
                domain_min_m=rules.domain_min_m,
                domain_max_m=rules.domain_max_m,
                out_of_domain_fraction=domain_fraction,
                buffer_m=segment.buffer_m,
                reason=reason,
            )
        )
    return CanopySupportReport(
        created_utc=created_utc or datetime.now(UTC),
        crs=raster.crs,
        resolution_m=raster.resolution_m,
        vertical_datum=raster.vertical_datum,
        raster_bounds=[raster.min_x, raster.min_y, raster.max_x, raster.max_y],
        source=raster.provenance,
        config=rules,
        supports=supports,
    )


def validate_canopy_support(report: CanopySupportReport) -> ContractValidation:
    """Validate canopy states, statistics, structure, trees, and VRI evidence.

    Parameters
    ----------
    report : CanopySupportReport
        Report to validate.

    Returns
    -------
    ContractValidation
        Errors, warnings, and counts.
    """
    errors: list[str] = []
    warnings: list[str] = []
    check_duplicates(
        "CANOPY",
        "segment",
        [support.segment_id for support in report.supports],
        errors,
    )
    if report.created_utc.tzinfo is None:
        errors.append("CANOPY-TIME: created_utc is not timezone-aware")
    if report.source.product not in CANOPY_PRODUCT_KINDS:
        errors.append("CANOPY-SOURCE: provenance is not a CHM")
    if report.source.crs != report.crs:
        errors.append("CANOPY-CRS: source CRS does not match the report")
    if report.source.vertical_datum != report.vertical_datum:
        errors.append("CANOPY-DATUM: source vertical datum does not match the report")
    if report.source.resolution_m is not None and not math.isclose(
        report.source.resolution_m, report.resolution_m
    ):
        errors.append("CANOPY-RESOLUTION: source resolution does not match the report")
    for support in report.supports:
        if support.state not in CANOPY_STATES:
            errors.append(f"CANOPY-STATE: {support.segment_id} has unknown state {support.state!r}")
        if support.valid_pixels > support.candidate_pixels:
            errors.append(
                f"CANOPY-PIXELS: {support.segment_id} valid pixels exceed candidate pixels"
            )
        if support.state == "missing" and support.valid_pixels != 0:
            errors.append(f"CANOPY-MISSING: {support.segment_id} has valid pixels but is missing")
        if support.state == "missing" and not support.reason.strip():
            errors.append(f"CANOPY-REASON: {support.segment_id} has no missing reason")
        if support.state in ("partial", "out_of_domain") and not support.reason.strip():
            errors.append(f"CANOPY-REASON: {support.segment_id} has no state reason")
        if support.state != "missing" and support.height_mean_m is None:
            errors.append(f"CANOPY-VALUE: {support.segment_id} has no height statistic")
        if support.state == "observed" and support.valid_pixels < report.config.min_valid_pixels:
            errors.append(
                f"CANOPY-COVERAGE: {support.segment_id} is observed below the pixel threshold"
            )
        if support.state == "observed" and support.coverage_pct < report.config.min_coverage_pct:
            errors.append(
                f"CANOPY-COVERAGE: {support.segment_id} is observed below the coverage threshold"
            )
        if support.tree is not None and support.tree.segment_id != support.segment_id:
            errors.append(f"CANOPY-TREE: {support.segment_id} tree segment mismatch")
        if support.vri is not None and support.vri.segment_id != support.segment_id:
            errors.append(f"CANOPY-VRI: {support.segment_id} VRI segment mismatch")
        for band in support.structure:
            if band.upper_m <= band.lower_m:
                errors.append(f"CANOPY-STRUCTURE: {support.segment_id} band is unordered")
    if not report.supports:
        warnings.append("CANOPY-EMPTY: the report has no segment supports")
    counts: dict[str, int | float] = {
        "segments": len(report.supports),
        "observed": sum(1 for support in report.supports if support.state == "observed"),
        "partial": sum(1 for support in report.supports if support.state == "partial"),
        "missing": sum(1 for support in report.supports if support.state == "missing"),
        "out_of_domain": sum(1 for support in report.supports if support.state == "out_of_domain"),
    }
    return ContractValidation(tuple(errors), tuple(warnings), counts)


def _cover_pct(heights: np.ndarray, threshold: float) -> float:
    return float(100.0 * np.count_nonzero(heights >= threshold) / len(heights))


def _out_of_domain_fraction(heights: np.ndarray, config: CanopyConfig) -> float:
    if config.domain_min_m is None and config.domain_max_m is None:
        return 0.0
    outside = np.zeros(heights.shape, dtype=bool)
    if config.domain_min_m is not None:
        outside |= heights < config.domain_min_m
    if config.domain_max_m is not None:
        outside |= heights > config.domain_max_m
    return float(np.count_nonzero(outside) / len(heights))


def _vri_comparison(
    segment_id: str,
    observation: VriObservation | None,
    chosen: np.ndarray,
    heights: np.ndarray,
) -> VriComparison | None:
    if observation is None:
        return None
    lidar_height = float(np.mean(heights[chosen])) if np.any(chosen) else None
    lidar_cover = _cover_pct(heights[chosen], 10.0) if np.any(chosen) else None
    return VriComparison(
        segment_id=segment_id,
        inventory_vintage=observation.vintage,
        vri_height_m=observation.height_m,
        lidar_height_m=lidar_height,
        height_difference_m=(
            lidar_height - observation.height_m if lidar_height is not None else None
        ),
        vri_cover_pct=observation.cover_pct,
        lidar_cover_pct=lidar_cover,
        cover_difference_pct=(
            lidar_cover - observation.cover_pct if lidar_cover is not None else None
        ),
        source=observation.source,
        model_card_id=observation.model_card_id,
        note="recorded difference; no reconciliation applied",
    )


__all__ = [
    "CANOPY_PRODUCT_KINDS",
    "CANOPY_STATES",
    "CANOPY_SUPPORT_SCHEMA_VERSION",
    "COVER_THRESHOLDS_M",
    "TREE_PRODUCT_KINDS",
    "CanopyBand",
    "CanopyConfig",
    "CanopyRaster",
    "CanopySupport",
    "CanopySupportError",
    "CanopySupportReport",
    "TreeSupport",
    "VriComparison",
    "VriObservation",
    "aggregate_canopy_support",
    "validate_canopy_support",
]
