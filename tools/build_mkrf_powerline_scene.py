# mypy: ignore-errors
"""Build the MKRF southwest 500 kV power-line scene from local MKRF data.

Run from the Brushline repository after the MKRF GIS delivery and OSM power-line
query are available. The derived scene is written under runtime/private and is
not committed.
"""

from __future__ import annotations

import json
from pathlib import Path

import geopandas as gpd
import numpy as np
import rasterio
from pyproj import Transformer
from rasterio.enums import Resampling
from rasterio.transform import from_origin
from rasterio.windows import from_bounds
from scipy.ndimage import maximum_filter
from shapely.geometry import LineString, Point, box

ROOT = Path(__file__).resolve().parents[1]
MKRF = ROOT.parent / "sources/mkrf-gis-2026-11-02"
OUT = ROOT / "runtime/private/mkrf-powerline/scene.json"
BOUNDARY = MKRF / "processed/boundary.gpkg"
DEM = MKRF / "extracted/DEMs/unpacked/DEM/DEM.asc"
CHM = MKRF / "extracted/CHM/unpacked/CHM__CHM_5m/mkrf_2016_chm_5_meter.tif"
OSM = ROOT / "runtime/private/mkrf-powerline/osm-power.json"


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
    elevation = (
        np.where(np.isfinite(elevation), elevation, np.nanmedian(elevation)).astype(float).round(2)
    )
    canopy = np.where(np.isfinite(canopy), canopy, 0).astype(float).round(2)
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
                "crown_width_m": round(max(1.5, h * 0.3), 2),
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
        },
        "trees": trees,
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
                "name": "MKRF GIS boundary",
                "licence": "MKRF private delivery (not redistributed)",
                "url": "",
            },
        ],
        "caveats": [
            "Real MKRF power-line location and LiDAR terrain/canopy; derived private scene.",
            "Tower geometry is schematic, not engineered; conductor height is approximate.",
            "Tree instances are LiDAR canopy maxima, not measured stems.",
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
        "towers",
        len(tower_payload),
        "lines",
        len(line_payload),
        "size",
        OUT.stat().st_size,
    )


if __name__ == "__main__":
    main()
