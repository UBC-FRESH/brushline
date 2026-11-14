"""Terrain and slope support for corridor segments.

The adapter consumes a validated FEMIC DEM or DSM provenance and a north-up raster array. It
aggregates cells within a buffered segment support, records the statistic, buffer, valid-pixel rule,
slope, aspect, terrain class, and an explicit access proxy, and marks partial or missing coverage.
It does not reproject, resample, fill, or download a raster.
"""

from __future__ import annotations

import itertools
import math
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal

import numpy as np
from pydantic import BaseModel, ConfigDict, Field, model_validator

from brushline.integrations.lidar import LidarProductProvenance
from brushline.model.validation import ContractValidation, check_duplicates

TERRAIN_SUPPORT_SCHEMA_VERSION: Literal["brushline.terrain-support.v1"] = (
    "brushline.terrain-support.v1"
)
TERRAIN_STATISTICS: tuple[str, ...] = ("mean", "median", "min", "max", "p90")
TERRAIN_STATES: tuple[str, ...] = ("observed", "partial", "missing")
TERRAIN_CLASSES: tuple[str, ...] = ("flat", "gentle", "moderate", "steep", "very_steep")
ACCESS_CLASSES: tuple[str, ...] = ("high", "moderate", "low", "unknown")
TERRAIN_PRODUCT_KINDS: frozenset[str] = frozenset({"dem", "dsm"})


class TerrainSupportError(ValueError):
    """Raised when a terrain raster or segment support cannot be aggregated."""


class SegmentWindow(BaseModel):
    """A buffered corridor segment for terrain aggregation.

    Parameters
    ----------
    segment_id : str
        Segment id.
    coordinates : list of tuple of float
        Polyline vertices in the raster CRS.
    buffer_m : float, optional
        Buffer distance in metres. Defaults to ``10``.
    crs : str, optional
        Segment CRS. It must match the raster CRS.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    segment_id: str = Field(min_length=1)
    coordinates: list[tuple[float, float]] = Field(min_length=2)
    buffer_m: float = Field(default=10.0, ge=0)
    crs: str = "EPSG:3005"


class TerrainConfig(BaseModel):
    """Aggregation rules for one terrain support run.

    Parameters
    ----------
    statistic : str, optional
        ``mean``, ``median``, ``min``, ``max``, or ``p90``.
    min_valid_pixels : int, optional
        Minimum slope-valid cells for observed support. Defaults to ``4``.
    min_coverage_pct : float, optional
        Minimum valid-cell percentage for observed support. Defaults to ``50``.
    access_slope_deg : float, optional
        Slope at which the access proxy reaches zero. Defaults to ``30``.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    statistic: str = "mean"
    min_valid_pixels: int = Field(default=4, ge=1)
    min_coverage_pct: float = Field(default=50.0, ge=0, le=100)
    access_slope_deg: float = Field(default=30.0, gt=0)


class TerrainSupport(BaseModel):
    """One segment's terrain support.

    Parameters
    ----------
    segment_id : str
        Segment id.
    state : str
        ``observed``, ``partial``, or ``missing``.
    coverage_pct : float
        Valid-cell percentage.
    candidate_pixels : int
        Cells within the buffer.
    valid_pixels : int
        Cells with valid elevation and slope.
    elevation_m : float or None
        Aggregated elevation.
    slope_deg : float or None
        Aggregated slope.
    aspect_deg : float or None
        Circular mean aspect.
    terrain_class : str
        Slope class.
    access_proxy : float or None
        Slope-derived access proxy from 0 to 1. It is not an operability verdict.
    access_class : str
        ``high``, ``moderate``, ``low``, or ``unknown``.
    statistic : str
        Aggregation statistic.
    buffer_m : float
        Segment buffer.
    reason : str, optional
        Why support is partial or missing.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    segment_id: str = Field(min_length=1)
    state: str
    coverage_pct: float = Field(ge=0, le=100)
    candidate_pixels: int = Field(ge=0)
    valid_pixels: int = Field(ge=0)
    elevation_m: float | None = None
    slope_deg: float | None = Field(default=None, ge=0, le=90)
    aspect_deg: float | None = Field(default=None, ge=0, lt=360)
    terrain_class: str = "missing"
    access_proxy: float | None = Field(default=None, ge=0, le=1)
    access_class: str = "unknown"
    statistic: str = "mean"
    buffer_m: float = Field(ge=0)
    reason: str = ""

    @model_validator(mode="after")
    def _state_consistency(self) -> TerrainSupport:
        if self.state not in TERRAIN_STATES:
            raise ValueError(f"unknown terrain state {self.state!r}")
        if self.valid_pixels > self.candidate_pixels:
            raise ValueError("valid_pixels cannot exceed candidate_pixels")
        if self.state == "missing":
            if self.valid_pixels != 0:
                raise ValueError("a missing support must have zero valid pixels")
            if any(
                value is not None for value in (self.elevation_m, self.slope_deg, self.aspect_deg)
            ):
                raise ValueError("a missing support must have no terrain values")
        if self.state in ("observed", "partial") and self.elevation_m is None:
            raise ValueError("observed or partial support needs elevation")
        if self.terrain_class not in (*TERRAIN_CLASSES, "missing"):
            raise ValueError(f"unknown terrain class {self.terrain_class!r}")
        if self.access_class not in ACCESS_CLASSES:
            raise ValueError(f"unknown access class {self.access_class!r}")
        return self


class TerrainSupportReport(BaseModel):
    """The terrain support report for one raster.

    Parameters
    ----------
    schema_version : {"brushline.terrain-support.v1"}
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
        Validated DEM/DSM provenance.
    config : TerrainConfig
        Aggregation rules.
    supports : list of TerrainSupport
        Segment support records.
    """

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["brushline.terrain-support.v1"] = TERRAIN_SUPPORT_SCHEMA_VERSION
    created_utc: datetime
    crs: str = Field(min_length=1)
    resolution_m: float = Field(gt=0)
    vertical_datum: str = Field(min_length=1)
    raster_bounds: list[float] = Field(min_length=4, max_length=4)
    source: LidarProductProvenance
    config: TerrainConfig
    supports: list[TerrainSupport] = Field(default_factory=list)


@dataclass(frozen=True)
class TerrainRaster:
    """A north-up terrain raster with validated provenance.

    Parameters
    ----------
    values : numpy.ndarray
        Two-dimensional elevation array with row zero at the north edge.
    min_x : float
        Western raster edge.
    min_y : float
        Southern raster edge.
    max_x : float
        Eastern raster edge.
    max_y : float
        Northern raster edge.
    crs : str
        Raster CRS.
    resolution_m : float
        Cell size in metres.
    vertical_datum : str
        Vertical datum.
    provenance : LidarProductProvenance
        Validated DEM/DSM provenance.
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
        """Validate the raster shape, provenance, and bounds."""
        if self.values.ndim != 2 or self.values.size == 0:
            raise TerrainSupportError("terrain values must be a non-empty 2D array")
        if self.max_x <= self.min_x or self.max_y <= self.min_y:
            raise TerrainSupportError("terrain bounds must have positive area")
        if self.resolution_m <= 0:
            raise TerrainSupportError("terrain resolution must be positive")
        if not self.crs or not self.vertical_datum:
            raise TerrainSupportError("terrain CRS and vertical datum are required")
        if self.provenance.product not in TERRAIN_PRODUCT_KINDS:
            raise TerrainSupportError("terrain provenance must be a DEM or DSM")
        if self.provenance.crs != self.crs:
            raise TerrainSupportError("terrain provenance CRS does not match the raster")
        if self.provenance.resolution_m is not None and not math.isclose(
            self.provenance.resolution_m, self.resolution_m
        ):
            raise TerrainSupportError("terrain provenance resolution does not match the raster")
        if self.provenance.vertical_datum != self.vertical_datum:
            raise TerrainSupportError("terrain provenance vertical datum does not match the raster")

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


def aggregate_terrain_support(
    raster: TerrainRaster,
    segments: list[SegmentWindow],
    config: TerrainConfig | None = None,
    *,
    created_utc: datetime | None = None,
) -> TerrainSupportReport:
    """Aggregate a validated terrain raster to buffered segment support.

    Parameters
    ----------
    raster : TerrainRaster
        North-up DEM or DSM with validated provenance.
    segments : list of SegmentWindow
        Buffered segment polylines.
    config : TerrainConfig, optional
        Aggregation rules.
    created_utc : datetime, optional
        Report time. Defaults to the current UTC time.

    Returns
    -------
    TerrainSupportReport
        Segment support with coverage and provenance.

    Raises
    ------
    TerrainSupportError
        When a segment CRS differs from the raster CRS or the configuration is invalid.
    """
    rules = config or TerrainConfig()
    if rules.statistic not in TERRAIN_STATISTICS:
        raise TerrainSupportError(f"unknown terrain statistic {rules.statistic!r}")
    x_grid, y_grid = raster.cell_centers()
    elevations = raster.values.astype(float)
    if raster.nodata is not None:
        elevations = np.where(elevations == raster.nodata, np.nan, elevations)
    slope, aspect = _slope_aspect(elevations, raster.resolution_m)
    valid = np.isfinite(elevations) & np.isfinite(slope)
    supports: list[TerrainSupport] = []
    for segment in segments:
        if segment.crs != raster.crs:
            raise TerrainSupportError(
                f"segment {segment.segment_id} CRS {segment.crs!r} does not match "
                f"raster CRS {raster.crs!r}; explicit transformation is required"
            )
        if segment.buffer_m < 0:
            raise TerrainSupportError("segment buffer must be non-negative")
        support_mask = _buffer_mask(
            x_grid,
            y_grid,
            np.asarray(segment.coordinates, dtype=float),
            segment.buffer_m,
        )
        candidate = int(np.count_nonzero(support_mask))
        chosen = support_mask & valid
        valid_pixels = int(np.count_nonzero(chosen))
        coverage = 100.0 * valid_pixels / candidate if candidate else 0.0
        if valid_pixels == 0:
            supports.append(
                TerrainSupport(
                    segment_id=segment.segment_id,
                    state="missing",
                    coverage_pct=0.0,
                    candidate_pixels=candidate,
                    valid_pixels=0,
                    terrain_class="missing",
                    access_class="unknown",
                    statistic=rules.statistic,
                    buffer_m=segment.buffer_m,
                    reason="no valid terrain cells within the segment buffer",
                )
            )
            continue
        state = (
            "observed"
            if valid_pixels >= rules.min_valid_pixels and coverage >= rules.min_coverage_pct
            else "partial"
        )
        elevation = _statistic(elevations[chosen], rules.statistic)
        slope_deg = _statistic(slope[chosen], rules.statistic)
        aspect_deg = _circular_mean(aspect[chosen])
        terrain_class = _terrain_class(slope_deg)
        access_proxy = max(0.0, min(1.0, 1.0 - slope_deg / rules.access_slope_deg))
        support = TerrainSupport(
            segment_id=segment.segment_id,
            state=state,
            coverage_pct=coverage,
            candidate_pixels=candidate,
            valid_pixels=valid_pixels,
            elevation_m=elevation,
            slope_deg=slope_deg,
            aspect_deg=aspect_deg,
            terrain_class=terrain_class,
            access_proxy=access_proxy,
            access_class=_access_class(access_proxy),
            statistic=rules.statistic,
            buffer_m=segment.buffer_m,
            reason="" if state == "observed" else "valid coverage is below the threshold",
        )
        supports.append(support)
    return TerrainSupportReport(
        created_utc=created_utc or datetime.now(UTC),
        crs=raster.crs,
        resolution_m=raster.resolution_m,
        vertical_datum=raster.vertical_datum,
        raster_bounds=[raster.min_x, raster.min_y, raster.max_x, raster.max_y],
        source=raster.provenance,
        config=rules,
        supports=supports,
    )


def validate_terrain_support(report: TerrainSupportReport) -> ContractValidation:
    """Validate terrain support states, ranges, and provenance.

    Parameters
    ----------
    report : TerrainSupportReport
        Report to validate.

    Returns
    -------
    ContractValidation
        Errors, warnings, and counts.
    """
    errors: list[str] = []
    warnings: list[str] = []
    check_duplicates(
        "TERRAIN",
        "segment",
        [support.segment_id for support in report.supports],
        errors,
    )
    if report.created_utc.tzinfo is None:
        errors.append("TERRAIN-TIME: created_utc is not timezone-aware")
    if report.config.statistic not in TERRAIN_STATISTICS:
        errors.append(f"TERRAIN-CONFIG: unknown statistic {report.config.statistic!r}")
    if report.source.product not in TERRAIN_PRODUCT_KINDS:
        errors.append("TERRAIN-SOURCE: provenance is not a DEM or DSM")
    if report.source.crs != report.crs:
        errors.append("TERRAIN-CRS: source CRS does not match the report")
    if report.source.vertical_datum != report.vertical_datum:
        errors.append("TERRAIN-DATUM: source vertical datum does not match the report")
    if report.source.resolution_m is not None and not math.isclose(
        report.source.resolution_m, report.resolution_m
    ):
        errors.append("TERRAIN-RESOLUTION: source resolution does not match the report")
    for support in report.supports:
        if support.state not in TERRAIN_STATES:
            errors.append(
                f"TERRAIN-STATE: {support.segment_id} has unknown state {support.state!r}"
            )
        if support.valid_pixels > support.candidate_pixels:
            errors.append(
                f"TERRAIN-PIXELS: {support.segment_id} valid pixels exceed candidate pixels"
            )
        if support.state == "missing" and support.valid_pixels != 0:
            errors.append(f"TERRAIN-MISSING: {support.segment_id} has valid pixels but is missing")
        if support.state == "missing" and not support.reason.strip():
            errors.append(f"TERRAIN-REASON: {support.segment_id} has no missing reason")
        if support.state == "observed":
            if support.valid_pixels < report.config.min_valid_pixels:
                errors.append(
                    f"TERRAIN-COVERAGE: {support.segment_id} is observed below the pixel threshold"
                )
            if support.coverage_pct < report.config.min_coverage_pct:
                errors.append(
                    f"TERRAIN-COVERAGE: {support.segment_id} is observed below the "
                    "coverage threshold"
                )
            if support.elevation_m is None or support.slope_deg is None:
                errors.append(
                    f"TERRAIN-VALUE: {support.segment_id} is observed without terrain values"
                )
        if support.state in ("observed", "partial") and support.valid_pixels == 0:
            errors.append(
                f"TERRAIN-COVERAGE: {support.segment_id} has no valid pixels for a "
                "non-missing state"
            )
        if support.access_proxy is None and support.state != "missing":
            warnings.append(f"TERRAIN-ACCESS: {support.segment_id} has no access proxy")
    if not report.supports:
        warnings.append("TERRAIN-EMPTY: the report has no segment supports")
    counts: dict[str, int | float] = {
        "segments": len(report.supports),
        "observed": sum(1 for support in report.supports if support.state == "observed"),
        "partial": sum(1 for support in report.supports if support.state == "partial"),
        "missing": sum(1 for support in report.supports if support.state == "missing"),
    }
    return ContractValidation(tuple(errors), tuple(warnings), counts)


def _slope_aspect(
    elevations: np.ndarray,
    resolution_m: float,
) -> tuple[np.ndarray, np.ndarray]:
    dz_dy, dz_dx = np.gradient(elevations, resolution_m, resolution_m)
    slope = np.degrees(np.arctan(np.hypot(dz_dx, dz_dy)))
    aspect = np.degrees(np.arctan2(-dz_dx, dz_dy)) % 360.0
    return slope, aspect


def _buffer_mask(
    x_grid: np.ndarray,
    y_grid: np.ndarray,
    coordinates: np.ndarray,
    buffer_m: float,
) -> np.ndarray:
    distance = np.full(x_grid.shape, np.inf, dtype=float)
    for start, end in itertools.pairwise(coordinates):
        distance = np.minimum(
            distance,
            _point_to_segment_distance(
                x_grid,
                y_grid,
                start[0],
                start[1],
                end[0],
                end[1],
            ),
        )
    return distance <= buffer_m


def _point_to_segment_distance(
    x: np.ndarray,
    y: np.ndarray,
    x1: float,
    y1: float,
    x2: float,
    y2: float,
) -> np.ndarray:
    dx = x2 - x1
    dy = y2 - y1
    length_squared = dx * dx + dy * dy
    if length_squared == 0:
        return np.hypot(x - x1, y - y1)
    t = ((x - x1) * dx + (y - y1) * dy) / length_squared
    t = np.clip(t, 0.0, 1.0)
    return np.hypot(x - (x1 + t * dx), y - (y1 + t * dy))


def _statistic(values: np.ndarray, name: str) -> float:
    if name == "mean":
        return float(np.mean(values))
    if name == "median":
        return float(np.median(values))
    if name == "min":
        return float(np.min(values))
    if name == "max":
        return float(np.max(values))
    if name == "p90":
        return float(np.percentile(values, 90))
    raise TerrainSupportError(f"unknown terrain statistic {name!r}")


def _circular_mean(angles: np.ndarray) -> float:
    radians = np.radians(angles)
    return float(np.degrees(np.arctan2(np.mean(np.sin(radians)), np.mean(np.cos(radians)))) % 360.0)


def _terrain_class(slope_deg: float) -> str:
    if slope_deg < 2:
        return "flat"
    if slope_deg < 10:
        return "gentle"
    if slope_deg < 20:
        return "moderate"
    if slope_deg < 30:
        return "steep"
    return "very_steep"


def _access_class(proxy: float) -> str:
    if proxy >= 0.8:
        return "high"
    if proxy >= 0.5:
        return "moderate"
    return "low"


__all__ = [
    "ACCESS_CLASSES",
    "TERRAIN_CLASSES",
    "TERRAIN_PRODUCT_KINDS",
    "TERRAIN_STATES",
    "TERRAIN_STATISTICS",
    "TERRAIN_SUPPORT_SCHEMA_VERSION",
    "SegmentWindow",
    "TerrainConfig",
    "TerrainRaster",
    "TerrainSupport",
    "TerrainSupportError",
    "TerrainSupportReport",
    "aggregate_terrain_support",
    "validate_terrain_support",
]
