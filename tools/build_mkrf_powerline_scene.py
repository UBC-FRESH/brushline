# mypy: ignore-errors
"""Build the MKRF southwest 500 kV power-line scene from local MKRF data.

Run from the Brushline repository after the MKRF GIS delivery and OSM power-line
query are available. The derived scene is written under runtime/private and is
not committed.
"""

from __future__ import annotations

import json
import math
from itertools import pairwise
from pathlib import Path

import geopandas as gpd
import laspy
import numpy as np
import rasterio
from pyproj import Transformer
from rasterio.enums import Resampling
from rasterio.transform import from_origin
from rasterio.windows import from_bounds
from scipy.ndimage import distance_transform_edt, maximum_filter
from shapely import contains_xy
from shapely.geometry import LineString, Point, Polygon, box
from shapely.geometry.base import BaseGeometry

ROOT = Path(__file__).resolve().parents[1]
MKRF = ROOT.parent / "sources/mkrf-gis-2026-11-02"
OUT = ROOT / "runtime/private/mkrf-powerline/scene.json"
BOUNDARY = MKRF / "processed/boundary.gpkg"
DEM = MKRF / "extracted/DEMs/unpacked/DEM/DEM.asc"
CHM = MKRF / "extracted/CHM/unpacked/CHM__CHM_5m/mkrf_2016_chm_5_meter.tif"
OSM = ROOT / "runtime/private/mkrf-powerline/osm-power.json"
LAS_ROOT = MKRF / "extracted/LiDAR 2016/unpacked"


def _fill_nodata(values: np.ndarray, threshold: float = -1000.0) -> tuple[np.ndarray, int]:
    """Fill void cells with the nearest valid value."""
    valid = values > threshold
    missing = int((~valid).sum())
    if missing == 0:
        return values, 0
    if not valid.any():
        raise SystemExit("terrain window contains no valid elevation cells")
    indices = distance_transform_edt(~valid, return_distances=False, return_indices=True)
    return values[tuple(indices)], missing


def _las_tiles(bbox_utm: box) -> list[Path]:
    """Return LAS tiles whose headers intersect the scene bbox."""
    minx, miny, maxx, maxy = bbox_utm.bounds
    found = []
    for tile in sorted(LAS_ROOT.glob("*/*.las")):
        with laspy.open(tile) as reader:
            header = reader.header
        if header.maxs[0] < minx or header.mins[0] > maxx:
            continue
        if header.maxs[1] < miny or header.mins[1] > maxy:
            continue
        found.append(tile)
    return found


def _distance_to_lines(x: float, y: float, lines: list[dict]) -> float:
    best = float("inf")
    for line in lines:
        points = line.get("points", [])
        for (x1, y1), (x2, y2) in pairwise(points):
            dx, dy = x2 - x1, y2 - y1
            length2 = dx * dx + dy * dy
            factor = (
                0.0
                if length2 == 0
                else max(0.0, min(1.0, ((x - x1) * dx + (y - y1) * dy) / length2))
            )
            best = min(best, math.hypot(x - (x1 + factor * dx), y - (y1 + factor * dy)))
    return best


def _understory(
    perimeter: BaseGeometry,
    bbox: Polygon,
    origin: tuple[float, float],
    resolution: float,
    elevation: np.ndarray,
    lines: list[dict],
) -> dict:
    """Extract low-vegetation patches from 2016 LiDAR returns."""
    bbox_utm = gpd.GeoSeries([bbox], crs=3005).to_crs(26910).iloc[0]
    tiles = _las_tiles(bbox_utm)
    if not tiles:
        return {"patches": [], "patch_count": 0, "source": "MKRF 2016 LiDAR returns"}
    cell_m = 10.0
    width = bbox.bounds[2] - bbox.bounds[0]
    height = bbox.bounds[3] - bbox.bounds[1]
    cols = math.ceil(width / cell_m)
    rows = math.ceil(height / cell_m)
    count = rows * cols
    shrub_count = np.zeros(count, dtype=np.int64)
    first_count = np.zeros(count, dtype=np.int64)
    shrub_sum = np.zeros(count, dtype=np.float64)
    shrub_max = np.zeros(count, dtype=np.float32)
    to_scene = Transformer.from_crs(26910, 3005, always_xy=True)
    points_in_block = 0
    minx, miny, maxx, maxy = bbox_utm.bounds
    for tile in tiles:
        with laspy.open(tile) as reader:
            for points in reader.chunk_iterator(1_000_000):
                x = np.asarray(points.x, dtype=np.float64)
                y = np.asarray(points.y, dtype=np.float64)
                z = np.asarray(points.z, dtype=np.float64)
                inside_bbox = (x >= minx) & (x < maxx) & (y >= miny) & (y < maxy)
                if not inside_bbox.any():
                    continue
                x, y, z = x[inside_bbox], y[inside_bbox], z[inside_bbox]
                classes = np.asarray(points.classification)[inside_bbox]
                return_numbers = np.asarray(points.return_number)[inside_bbox]
                x, y = to_scene.transform(x, y)
                inside_boundary = contains_xy(perimeter, x, y)
                if not inside_boundary.any():
                    continue
                x, y, z, classes, return_numbers = (
                    x[inside_boundary],
                    y[inside_boundary],
                    z[inside_boundary],
                    classes[inside_boundary],
                    return_numbers[inside_boundary],
                )
                col = ((x - origin[0]) / cell_m).astype(np.int32)
                row = ((y - origin[1]) / cell_m).astype(np.int32)
                valid = (col >= 0) & (col < cols) & (row >= 0) & (row < rows)
                if not valid.any():
                    continue
                x, y, z, classes, return_numbers = (
                    x[valid],
                    y[valid],
                    z[valid],
                    classes[valid],
                    return_numbers[valid],
                )
                col, row = col[valid], row[valid]
                elev_col = np.rint((x - origin[0]) / resolution).astype(np.int32)
                elev_row = np.rint((y - origin[1]) / resolution).astype(np.int32)
                valid = (
                    (elev_col >= 0)
                    & (elev_col < elevation.shape[1])
                    & (elev_row >= 0)
                    & (elev_row < elevation.shape[0])
                )
                if not valid.any():
                    continue
                x, z, classes, return_numbers = (
                    x[valid],
                    z[valid],
                    classes[valid],
                    return_numbers[valid],
                )
                col, row = col[valid], row[valid]
                ground = elevation[elev_row[valid], elev_col[valid]]
                above_ground = z - ground
                index = row * cols + col
                first = return_numbers == 1
                first_count += np.bincount(index[first], minlength=count)
                vegetation = (above_ground >= 0.3) & (above_ground <= 3.0) & (classes != 2)
                if vegetation.any():
                    veg_index = index[vegetation]
                    veg_height = above_ground[vegetation]
                    shrub_count += np.bincount(veg_index, minlength=count)
                    shrub_sum += np.bincount(veg_index, weights=veg_height, minlength=count)
                    np.maximum.at(shrub_max, veg_index, veg_height)
                points_in_block += len(z)
    cover = np.minimum(100.0, 100.0 * shrub_count / np.maximum(first_count, 1))
    mean_height = np.divide(shrub_sum, np.maximum(shrub_count, 1))
    patches = []
    for row in range(rows):
        for col in range(cols):
            index = row * cols + col
            if shrub_count[index] < 3 or cover[index] < 3.0 or mean_height[index] < 0.4:
                continue
            x = minx + (col + 0.5) * cell_m
            y = miny + (row + 0.5) * cell_m
            x, y = to_scene.transform(x, y)
            local_x = x - origin[0]
            local_y = y - origin[1]
            corridor_distance = _distance_to_lines(local_x, local_y, lines)
            patches.append(
                {
                    "x_m": round(float(local_x), 2),
                    "y_m": round(float(local_y), 2),
                    "height_m": round(float(min(2.8, max(0.5, mean_height[index] * 1.2 + 0.2))), 2),
                    "width_m": round(float(min(4.0, 0.8 + 2.0 * math.sqrt(cover[index] / 100))), 2),
                    "cover_pct": round(float(cover[index]), 1),
                    "hits": int(shrub_count[index]),
                    "corridor_distance_m": round(float(corridor_distance), 1),
                    "in_corridor": corridor_distance <= 35.0,
                }
            )
    corridor = [patch for patch in patches if patch["in_corridor"]]
    return {
        "source": "MKRF 2016 LiDAR returns",
        "method": "Density of non-ground returns 0.3-3.0 m above the LiDAR DEM",
        "cell_m": cell_m,
        "band_m": [0.3, 3.0],
        "las_tiles": [tile.name for tile in tiles],
        "points_in_block": points_in_block,
        "patch_count": len(patches),
        "patches": patches,
        "mean_cover_pct": round(float(cover[shrub_count > 0].mean()), 1)
        if (shrub_count > 0).any()
        else 0.0,
        "max_height_m": round(float(shrub_max.max()), 2),
        "corridor_patch_count": len(corridor),
        "corridor_mean_cover_pct": round(
            float(np.mean([patch["cover_pct"] for patch in corridor])), 1
        )
        if corridor
        else 0.0,
    }


def main() -> None:
    """Build the derived MKRF power-line scene."""
    boundary = gpd.read_file(BOUNDARY).to_crs(3005)
    perimeter = boundary.geometry.union_all()
    osm = json.loads(OSM.read_text())
    osm_timestamp = osm.get("osm3s", {}).get("timestamp_osm_base")
    lines = []
    towers = []
    for element in osm["elements"]:
        if element["type"] == "way" and element.get("tags", {}).get("power") in {
            "line",
            "minor_line",
            "cable",
        }:
            geom = LineString([(p["lon"], p["lat"]) for p in element["geometry"]])
            geom = gpd.GeoSeries([geom], crs=4326).to_crs(3005).iloc[0]
            clipped = geom.intersection(perimeter)
            if clipped.is_empty:
                continue
            parts = list(clipped.geoms) if clipped.geom_type == "MultiLineString" else [clipped]
            for part in parts:
                if part.length > 100:
                    lines.append(
                        {
                            "name": element.get("tags", {}).get("name", "power line"),
                            "geometry": part,
                        }
                    )
        if element["type"] == "node" and element.get("tags", {}).get("power") == "tower":
            point = (
                gpd.GeoSeries([Point(element["lon"], element["lat"])], crs=4326)
                .to_crs(3005)
                .iloc[0]
            )
            towers.append(point)
    # Southwest entry: the first long clipped parts near the western boundary.
    bbox = box(1247400, 478650, 1248700, 479430)
    selected = [line for line in lines if line["geometry"].intersects(bbox)]
    if not selected:
        raise SystemExit("no power-line geometry in the southwest bbox")
    selected_towers = [point for point in towers if bbox.contains(point)]
    bounds = bbox
    origin = (bounds.bounds[0], bounds.bounds[1])
    to_wgs84 = Transformer.from_crs(3005, 4326, always_xy=True)
    west, south = to_wgs84.transform(origin[0], origin[1])
    east, north = to_wgs84.transform(bounds.bounds[2], bounds.bounds[3])
    width_m = bounds.bounds[2] - bounds.bounds[0]
    height_m = bounds.bounds[3] - bounds.bounds[1]
    resolution = 2.0
    cols = int(width_m / resolution) + 1
    rows = int(height_m / resolution) + 1

    src = gpd.GeoSeries([bounds], crs=3005).to_crs(26910).iloc[0]
    minx, miny, maxx, maxy = src.bounds
    with rasterio.open(DEM) as dem:
        transform = from_origin(528700, 5454800 + 13200, 1, 1)
        window = from_bounds(minx, miny, maxx, maxy, transform)
        elevation = dem.read(
            1, window=window, out_shape=(rows, cols), resampling=Resampling.average
        )
    with rasterio.open(CHM) as chm:
        chm_window = from_bounds(minx, miny, maxx, maxy, chm.transform)
        canopy = chm.read(
            1, window=chm_window, out_shape=(rows, cols), resampling=Resampling.average
        )
    elevation, elevation_voids = _fill_nodata(elevation.astype(float))
    elevation = elevation.round(2)
    canopy_voids = int((canopy <= -1000.0).sum())
    canopy = np.where(canopy > -1000.0, canopy, 0).astype(float).round(2)
    # Local maxima are LiDAR-derived canopy clumps, not measured stems.
    maxima = (canopy == maximum_filter(canopy, size=5)) & (canopy > 3.0)
    rr, cc = np.where(maxima)
    trees = []
    for index, (row, col) in enumerate(zip(rr, cc, strict=True)):
        if index % 2:
            continue
        h = float(canopy[row, col])
        trees.append(
            {
                "tree_id": f"chm-{index}",
                "x_m": round(col * resolution, 2),
                "y_m": round(row * resolution, 2),
                "height_m": round(h, 2),
                "crown_width_m": round(max(1.5, min(12.0, h * 0.22)), 2),
                "species": "LiDAR canopy clump",
                "source": "mkrf_2016_chm_5m",
            }
        )
    line_payload = []
    for line in selected:
        coords = [
            [round(x - origin[0], 2), round(y - origin[1], 2)] for x, y in line["geometry"].coords
        ]
        line_payload.append({"name": line["name"], "points": coords})
    tower_payload = [
        {
            "tower_id": f"osm-{index}",
            "x_m": round(p.x - origin[0], 2),
            "y_m": round(p.y - origin[1], 2),
            "height_m": 45.0,
        }
        for index, p in enumerate(selected_towers)
    ]
    understory = _understory(perimeter, bbox, origin, resolution, elevation, line_payload)
    scene = {
        "schema_version": "brushline.real-scene.v1",
        "instance_id": "mkrf-powerline-2016",
        "block": {
            "block_id": "mkrf-sw-powerline",
            "block_kind": "powerline_block",
            "segment_ids": [],
            "bounds_m": [0, 0, width_m, height_m],
            "position_status": "derived",
        },
        "crs": "EPSG:3005",
        "origin_m": [origin[0], origin[1]],
        "terrain": {
            "width": cols,
            "height": rows,
            "resolution_m": resolution,
            "elevation": elevation.tolist(),
            "canopy_height": canopy.tolist(),
            "elevation_range_m": [float(elevation.min()), float(elevation.max())],
            "nodata_filled_cells": elevation_voids,
            "canopy_void_cells": canopy_voids,
        },
        "trees": trees,
        "understory": understory,
        "location": {
            "bbox_3005": list(bounds.bounds),
            "bbox_wgs84": [west, south, east, north],
        },
        "powerline": {
            "name": "Meridian-Nicola / Meridian-Ruby Creek 500 kV",
            "voltage_kv": 500,
            "lines": line_payload,
            "towers": tower_payload,
            "conductor_height_m": 32.0,
            "source": "OpenStreetMap via Overpass API",
            "source_timestamp": osm_timestamp,
            "corridor_length_m": round(sum(line["geometry"].length for line in selected), 1),
            "corridor_width_m": 70.0,
            "tree_clearance_m": 36.0,
        },
        "sources": [
            {
                "name": "OpenStreetMap power lines and towers",
                "licence": "ODbL-1.0",
                "url": "https://www.openstreetmap.org/",
            },
            {
                "name": "MKRF 2016 LiDAR DEM and CHM",
                "licence": "MKRF/UBC educational use only; private delivery, release not reviewed",
                "url": "",
            },
            {
                "name": "MKRF 2016 LiDAR understory returns",
                "licence": "MKRF/UBC educational use only; private delivery, release not reviewed",
                "url": "",
            },
            {
                "name": "MKRF GIS boundary",
                "licence": "MKRF private delivery (not redistributed)",
                "url": "",
            },
        ],
        "caveats": [
            "Real MKRF power-line location and LiDAR terrain/canopy; derived private scene.",
            "Tower geometry is schematic, not engineered; conductor height is approximate.",
            "Tree instances are LiDAR canopy maxima, not measured stems.",
            "Understory patches are LiDAR return density in the 0.3-3 m band, not a species "
            "inventory; no maintenance treatment is inferred.",
            "Tall tree instances within 36 m of the line are suppressed for the 70 m corridor "
            "view; this is a visualization choice, not an observed treatment.",
            "DEM/CHM void cells outside valid coverage are filled with the nearest valid sample.",
            "Context view only; not survey-grade or a safety certification.",
        ],
        "treatment": None,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(scene, separators=(",", ":")) + "\n", encoding="utf-8")
    print(
        OUT,
        "trees",
        len(trees),
        "understory",
        understory.get("patch_count"),
        "towers",
        len(tower_payload),
        "lines",
        len(line_payload),
        "size",
        OUT.stat().st_size,
    )


if __name__ == "__main__":
    main()
