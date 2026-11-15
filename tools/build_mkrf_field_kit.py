# mypy: ignore-errors
# ruff: noqa: E501
"""Build a printable field-validation kit for the MKRF power-line corridor.

The kit is generated from the local private scene and remains under ignored runtime
storage. It contains planned plot locations, target LiDAR values, field cards, an
offline map, a CSV template, and photo-log guidance.
"""

from __future__ import annotations

import base64
import csv
import html
import json
import math
import zipfile
from datetime import UTC, datetime
from itertools import pairwise
from pathlib import Path
from typing import Any

import geopandas as gpd
import matplotlib
import numpy as np
from matplotlib.lines import Line2D
from pyproj import Transformer
from shapely.affinity import translate
from shapely.geometry import Point, box
from shapely.geometry.base import BaseGeometry
from shapely.ops import nearest_points

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from brushline.field.validation import FIELD_COLUMNS

ROOT = Path(__file__).resolve().parents[1]
SCENE_PATH = ROOT / "runtime/private/mkrf-powerline/scene.json"
BOUNDARY = ROOT.parent / "sources/mkrf-gis-2026-11-02/processed/boundary.gpkg"
ROADS = ROOT.parent / "sources/mkrf-gis-2026-11-02/processed/roads_current.gpkg"
OUT = ROOT / "runtime/private/mkrf-powerline/field-kit"
PLOT_FRACTIONS = (0.10, 0.22, 0.36, 0.50, 0.65, 0.80)
PLOT_OFFSETS = (0.0, 25.0, 0.0, -25.0, 0.0, 25.0)
PLOT_LABELS = ("C1", "E1", "C2", "E2", "C3", "E3")


def _point_at(points: list[list[float]], fraction: float) -> tuple[float, float, float, float]:
    """Return a point and tangent at a fraction of a polyline."""
    lengths = []
    for first, second in pairwise(points):
        lengths.append(math.dist(first, second))
    target = sum(lengths) * fraction
    walked = 0.0
    for (first, second), length in zip(pairwise(points), lengths, strict=False):
        if walked + length >= target:
            factor = (target - walked) / max(length, 1e-9)
            x = first[0] + (second[0] - first[0]) * factor
            y = first[1] + (second[1] - first[1]) * factor
            dx = (second[0] - first[0]) / max(length, 1e-9)
            dy = (second[1] - first[1]) / max(length, 1e-9)
            return x, y, dx, dy
        walked += length
    first, second = points[-2], points[-1]
    length = max(math.dist(first, second), 1e-9)
    return second[0], second[1], (second[0] - first[0]) / length, (second[1] - first[1]) / length


def _sample_canopy(scene: dict[str, Any], x: float, y: float) -> float:
    terrain = scene["terrain"]
    res = float(terrain["resolution_m"])
    col = max(0, min(int(terrain["width"]) - 1, round(x / res)))
    row = max(0, min(int(terrain["height"]) - 1, round(y / res)))
    return round(float(terrain["canopy_height"][row][col]), 1)


def _build_plots(
    scene: dict[str, Any], perimeter: BaseGeometry, roads: gpd.GeoDataFrame
) -> list[dict[str, Any]]:
    origin_x, origin_y = (float(value) for value in scene["origin_m"])
    local_perimeter = translate(perimeter, xoff=-origin_x, yoff=-origin_y)
    to_wgs84 = Transformer.from_crs(3005, 4326, always_xy=True)
    patches = scene["understory"]["patches"]
    trees = scene["trees"]
    plots: list[dict[str, Any]] = []
    for unit in scene["treatment_schedule"]["units"]:
        for fraction, offset, label in zip(PLOT_FRACTIONS, PLOT_OFFSETS, PLOT_LABELS, strict=True):
            x, y, dx, dy = _point_at(unit["points"], fraction)
            if offset:
                nx, ny = -dy, dx
                candidate = (x + nx * offset, y + ny * offset)
                if not local_perimeter.contains(Point(candidate)):
                    candidate = (x - nx * offset, y - ny * offset)
                if local_perimeter.contains(Point(candidate)):
                    x, y = candidate
            unit_id = unit["unit_id"]
            plot_id = f"{unit_id.replace('-', '')}-{label}"
            nearby_patches = [
                patch for patch in patches if math.hypot(patch["x_m"] - x, patch["y_m"] - y) <= 15.0
            ]
            nearby_trees = [
                tree for tree in trees if math.hypot(tree["x_m"] - x, tree["y_m"] - y) <= 15.0
            ]
            cover = (
                sum(patch["cover_pct"] for patch in nearby_patches) / len(nearby_patches)
                if nearby_patches
                else 0.0
            )
            max_height = max(
                (patch["height_m"] for patch in nearby_patches),
                default=0.0,
            )
            easting = origin_x + x
            northing = origin_y + y
            lon, lat = to_wgs84.transform(easting, northing)
            plot_point = Point(easting, northing)
            nearest_road = roads.iloc[roads.distance(plot_point).argmin()]
            access_distance = float(nearest_road.geometry.distance(plot_point))
            access_point = nearest_points(nearest_road.geometry, plot_point)[0]
            access_road = str(nearest_road.get("NAME") or "unnamed road")
            access_status = str(nearest_road.get("STATUS") or "unknown")
            access_use = str(nearest_road.get("USE") or "unknown")
            plots.append(
                {
                    "plot_id": plot_id,
                    "unit_id": unit_id,
                    "unit_name": unit.get("name", unit_id),
                    "position": "center" if not offset else "edge",
                    "planned_year": unit["planned"]["year"],
                    "method": unit["planned"]["method"],
                    "x_m": round(x, 1),
                    "y_m": round(y, 1),
                    "easting_3005": round(easting, 2),
                    "northing_3005": round(northing, 2),
                    "latitude": round(lat, 6),
                    "longitude": round(lon, 6),
                    "access_road": access_road,
                    "access_status": access_status,
                    "access_use": access_use,
                    "access_distance_m": round(access_distance, 1),
                    "access_point_x_m": round(access_point.x - origin_x, 1),
                    "access_point_y_m": round(access_point.y - origin_y, 1),
                    "target_shrub_patches": len(nearby_patches),
                    "target_mean_cover_pct": round(cover, 1),
                    "target_max_shrub_height_m": round(max_height, 1),
                    "target_tree_clumps": len(nearby_trees),
                    "target_canopy_height_m": _sample_canopy(scene, x, y),
                }
            )
    return plots


def _geojson(scene: dict[str, Any], plots: list[dict[str, Any]]) -> dict[str, Any]:
    origin_x, origin_y = (float(value) for value in scene["origin_m"])
    to_wgs84 = Transformer.from_crs(3005, 4326, always_xy=True)

    def coordinates(point: list[float]) -> list[float]:
        lon, lat = to_wgs84.transform(point[0] + origin_x, point[1] + origin_y)
        return [round(lon, 7), round(lat, 7)]

    features = []
    for unit in scene["treatment_schedule"]["units"]:
        features.append(
            {
                "type": "Feature",
                "geometry": {
                    "type": "LineString",
                    "coordinates": [coordinates(point) for point in unit["points"]],
                },
                "properties": {
                    "feature_type": "unit",
                    "unit_id": unit["unit_id"],
                    "line_name": unit["line_name"],
                    "planned_year": unit["planned"]["year"],
                    "method": unit["planned"]["method"],
                },
            }
        )
    for tower in scene["powerline"]["towers"]:
        lon, lat = to_wgs84.transform(origin_x + tower["x_m"], origin_y + tower["y_m"])
        features.append(
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [round(lon, 7), round(lat, 7)]},
                "properties": {"feature_type": "tower", "tower_id": tower["tower_id"]},
            }
        )
    for plot in plots:
        features.append(
            {
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [plot["longitude"], plot["latitude"]],
                },
                "properties": {"feature_type": "plot", **plot},
            }
        )
    return {"type": "FeatureCollection", "features": features}


def _write_plots_csv(plots: list[dict[str, Any]], path: Path) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(plots[0]))
        writer.writeheader()
        writer.writerows(plots)


def _write_field_template(plots: list[dict[str, Any]], path: Path) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELD_COLUMNS)
        writer.writeheader()
        for plot in plots:
            writer.writerow(
                {
                    "plot_id": plot["plot_id"],
                    "unit_id": plot["unit_id"],
                    "position": plot["position"],
                    "latitude": plot["latitude"],
                    "longitude": plot["longitude"],
                }
            )


def _write_photo_log(plots: list[dict[str, Any]], path: Path) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["plot_id", "filename", "visit_date", "bearing", "subject", "notes"])
        for plot in plots:
            writer.writerow([plot["plot_id"], "", "", "", "", ""])


def _map(
    scene: dict[str, Any], plots: list[dict[str, Any]], path: Path, roads: gpd.GeoDataFrame
) -> None:
    terrain = scene["terrain"]
    width = float(terrain["width"]) * float(terrain["resolution_m"])
    height = float(terrain["height"]) * float(terrain["resolution_m"])
    elevation = np.asarray(terrain["elevation"], dtype=float)
    origin_x, origin_y = (float(value) for value in scene["origin_m"])
    local_roads = roads.copy()
    local_roads["geometry"] = local_roads.geometry.translate(xoff=-origin_x, yoff=-origin_y)
    local_roads = gpd.clip(local_roads, box(0, 0, width, height))
    rows, cols = elevation.shape
    x = np.linspace(0, width, cols)
    y = np.linspace(0, height, rows)
    fig, ax = plt.subplots(figsize=(13, 8), constrained_layout=True)
    ax.imshow(
        elevation,
        extent=(0, width, 0, height),
        origin="lower",
        cmap="Greens",
        alpha=0.62,
        aspect="equal",
    )
    ax.contour(x, y, elevation, levels=10, colors="#526b54", linewidths=0.45, alpha=0.75)
    for _, road in local_roads.iterrows():
        geometry = road.geometry
        parts = [geometry] if geometry.geom_type == "LineString" else list(geometry.geoms)
        for part in parts:
            ax.plot(
                [point[0] for point in part.coords],
                [point[1] for point in part.coords],
                color="#8b9289",
                linewidth=1.2,
                zorder=2,
            )
    year_colors = {2027: "#d9691f", 2028: "#c49a31", 2029: "#3d6e51"}
    for unit in scene["treatment_schedule"]["units"]:
        points = unit["points"]
        year = unit["planned"]["year"]
        ax.plot(
            [point[0] for point in points],
            [point[1] for point in points],
            color=year_colors.get(year, "#555555"),
            linewidth=5,
            alpha=0.9,
            solid_capstyle="round",
        )
        mid = points[len(points) // 2]
        ax.annotate(
            f"{unit['unit_id']} · {year}",
            (mid[0], mid[1]),
            xytext=(8, 8),
            textcoords="offset points",
            fontsize=8,
            weight="bold",
            color="#1b2a20",
        )
    for tower in scene["powerline"]["towers"]:
        ax.scatter(
            tower["x_m"],
            tower["y_m"],
            marker="^",
            s=70,
            facecolor="#20332a",
            edgecolor="#f1d18a",
            linewidth=1,
            zorder=5,
        )
    for plot in plots:
        center = plot["position"] == "center"
        ax.scatter(
            plot["x_m"],
            plot["y_m"],
            marker="o" if center else "s",
            s=55 if center else 42,
            facecolor="#f8f5e8" if center else "#e9c16f",
            edgecolor="#1f3328",
            linewidth=1.2,
            zorder=7,
        )
        if plot["access_distance_m"] > 0.5:
            ax.plot(
                [plot["x_m"], plot["access_point_x_m"]],
                [plot["y_m"], plot["access_point_y_m"]],
                color="#8a6a45",
                linewidth=0.8,
                linestyle="--",
                zorder=3,
            )
        ax.annotate(
            plot["plot_id"],
            (plot["x_m"], plot["y_m"]),
            xytext=(5, -10),
            textcoords="offset points",
            fontsize=7.5,
            color="#17251b",
            zorder=8,
        )
    ax.plot([40, 140], [30, 30], color="#1f3328", linewidth=3)
    ax.text(40, 20, "100 m", fontsize=8, color="#1f3328")
    ax.annotate(
        "N",
        xy=(width - 70, height - 75),
        xytext=(width - 70, height - 20),
        arrowprops={"facecolor": "#1f3328", "width": 1.5, "headwidth": 7},
        ha="center",
        fontsize=9,
        weight="bold",
    )
    used_years = sorted({unit["planned"]["year"] for unit in scene["treatment_schedule"]["units"]})
    handles = [
        Line2D([0], [0], color=year_colors[year], lw=4, label=f"{year} treatment")
        for year in used_years
    ] + [
        Line2D(
            [0],
            [0],
            marker="o",
            color="w",
            markerfacecolor="#f8f5e8",
            markeredgecolor="#1f3328",
            markersize=9,
            label="center plot",
        ),
        Line2D(
            [0],
            [0],
            marker="s",
            color="w",
            markerfacecolor="#e9c16f",
            markeredgecolor="#1f3328",
            markersize=8,
            label="edge plot",
        ),
        Line2D([0], [0], color="#8b9289", linewidth=1.2, label="mapped road"),
        Line2D(
            [0],
            [0],
            marker="^",
            color="w",
            markerfacecolor="#20332a",
            markeredgecolor="#f1d18a",
            markersize=8,
            label="mapped tower",
        ),
    ]
    ax.legend(handles=handles, loc="lower right", fontsize=8, framealpha=0.92)
    ax.set_title("MKRF southwest 500 kV corridor — field validation plots", loc="left")
    ax.set_xlim(0, width)
    ax.set_ylim(0, height)
    ax.set_xlabel("local easting (m)")
    ax.set_ylabel("local northing (m)")
    ax.text(
        0.01,
        0.985,
        "Private field kit · positions: EPSG:3005 local / WGS84 in plots.csv · no work under energised conductors",
        transform=ax.transAxes,
        fontsize=8,
        color="#435b49",
        va="top",
    )
    fig.savefig(path.with_suffix(".png"), dpi=240, bbox_inches="tight")
    fig.savefig(path.with_suffix(".pdf"), bbox_inches="tight")
    plt.close(fig)


def _cards_html(plots: list[dict[str, Any]], scene: dict[str, Any]) -> str:
    map_path = OUT / "map.png"
    map_uri = base64.b64encode(map_path.read_bytes()).decode("ascii") if map_path.exists() else ""
    cards = []
    for plot in plots:
        rows = [
            ("GPS accuracy (m)", ""),
            ("Dominant shrub species", ""),
            ("Shrub height (cm)", ""),
            ("Shrub cover (%)", ""),
            ("Shrub stems (count)", ""),
            ("Recent cut? (Y/N)", ""),
            ("Cut/stubble height (cm)", ""),
            ("ROW width (m)", ""),
            ("Tree species", ""),
            ("Tree height (m)", ""),
            ("Tree distance to line (m)", ""),
            ("Conductor clearance (m)", ""),
            ("Photo IDs", ""),
            ("Notes / safety / access", ""),
        ]
        rows_html = "".join(f"<tr><th>{html.escape(label)}</th><td></td></tr>" for label, _ in rows)
        cards.append(
            f"""
            <article class="card">
              <header><strong>{html.escape(plot["plot_id"])}</strong>
                <span>{html.escape(plot["unit_id"])} · {html.escape(plot["position"])} plot · planned {plot["planned_year"]}</span>
              </header>
              <p class="loc">WGS84 {plot["latitude"]:.6f}, {plot["longitude"]:.6f} · EPSG:3005 {plot["easting_3005"]:.1f}, {plot["northing_3005"]:.1f}</p>
              <div class="targets">
                <span>Access: {html.escape(plot["access_road"])} ({html.escape(plot["access_status"])}) · {plot["access_distance_m"]} m walk from mapped road · verify permission/status</span><br>
                <span>LiDAR target: {plot["target_shrub_patches"]} shrub patches · {plot["target_mean_cover_pct"]}% mean cover · {plot["target_max_shrub_height_m"]} m max height · {plot["target_tree_clumps"]} tree clumps</span>
              </div>
              <table>{rows_html}</table>
              <p class="note">15 m radius plot · record all measurements · photograph centre and four cardinal directions · do not enter active work areas.</p>
            </article>
            """
        )
    legend = (
        f'<img class="map" src="data:image/png;base64,{map_uri}" alt="Corridor plot map" />'
        if map_uri
        else ""
    )
    return f"""<!doctype html>
<html><head><meta charset="utf-8"><title>MKRF field plot cards</title>
<style>
@page {{ size: A4; margin: 10mm; }}
body {{ font: 11px/1.35 system-ui, sans-serif; color:#17251b; margin:0; }}
h1 {{ font-size:20px; margin:0 0 4px; }}
p {{ margin:3px 0; }}
.map {{ width:100%; max-height:95mm; object-fit:contain; margin:6px 0 10px; border:1px solid #bfcbbd; }}
.cards {{ display:grid; grid-template-columns:1fr 1fr; gap:8px; }}
.card {{ border:1px solid #9caf9d; border-radius:5px; padding:7px; break-inside:avoid; page-break-inside:avoid; }}
.card header {{ display:flex; justify-content:space-between; gap:6px; border-bottom:1px solid #d8e0d5; padding-bottom:3px; margin-bottom:4px; }}
.card header span {{ font-size:9px; color:#4e6252; text-align:right; }}
.loc {{ font:9px/1.35 ui-monospace,monospace; color:#405548; }}
.targets {{ background:#edf4e9; padding:4px; margin:5px 0; font-size:9px; }}
table {{ width:100%; border-collapse:collapse; }}
th {{ text-align:left; font-weight:500; width:48%; padding:3px 0; border-bottom:1px dotted #c8d3c5; }}
td {{ border-bottom:1px solid #6f806f; }}
.note {{ font-size:8.5px; color:#58695b; margin-top:5px; }}
@media print {{ .cards {{ gap:6px; }} .card {{ min-height:128mm; }} }}
</style></head><body>
<h1>MKRF southwest 500 kV corridor — field plot cards</h1>
<p>Use with <strong>map.png / map.pdf</strong>, <strong>plots.csv</strong>, and <strong>field-observations-template.csv</strong>. Targets are 2016 LiDAR-derived baselines, not measurements.</p>
{legend}
<div class="cards">{"".join(cards)}</div>
</body></html>"""


def _print_cards(html_text: str, path: Path) -> None:
    from playwright.sync_api import sync_playwright

    html_path = OUT / "plot-cards.html"
    html_path.write_text(html_text, encoding="utf-8")
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page()
        page.set_content(html_text, wait_until="load")
        page.pdf(path=str(path), format="A4", print_background=True)
        browser.close()


def _readme(scene: dict[str, Any], plots: list[dict[str, Any]]) -> str:
    schedule = scene["treatment_schedule"]
    years = ", ".join(str(year) for year in schedule["time_axis"])
    lines = [
        "# MKRF southwest 500 kV corridor — field validation kit",
        "",
        "Private field kit generated from the local MKRF scene and schedule. Do not publish.",
        "",
        "## Contents",
        "",
        "- `map.png` / `map.pdf` — offline corridor map with scheduled units and plots.",
        "- `plots.csv` — planned plot locations, mapped-road access, and 2016 LiDAR target metrics.",
        "- `corridor-plots.geojson` — units, towers, and plot points for GIS import.",
        "- `plot-cards.html` / `plot-cards.pdf` — printable plot cards.",
        "- `field-observations-template.csv` — import template for field measurements.",
        "- `photo-log.csv` — photo naming and subject log.",
        "- `validate.md` — import and validation instructions.",
        "",
        "## Plot design",
        "",
        f"- {len(plots)} plots: six per scheduled unit, alternating corridor centre and edge.",
        "- Plot radius: 15 m. Record the dominant shrub layer and the nearest relevant tree.",
        "- Target values are derived from 2016 LiDAR (0.3-3 m understory returns and canopy maxima).",
        "- The removed SW-03 fragment lies outside the modelled terrain block and is not in this kit.",
        "",
        "## Schedule context",
        "",
        f"- Time axis: {years}",
        f"- Schedule status: {schedule['status']} (not an approved work plan)",
    ]
    for unit in schedule["units"]:
        planned = unit["planned"]
        lines.append(
            f"- {unit['unit_id']} · {planned['year']} · {planned['method']} · "
            f"{unit['area_ha']} ha · {unit['shrub_patch_count']} shrub patches"
        )
    lines.extend(
        [
            "",
            "## Access",
            "",
            "Each plot records the nearest mapped road, its mapped status/use, and the straight-line",
            "walk distance. A mapped road is not permission: verify gates, road status, and safe parking",
            "with MKRF before the visit. Do not walk along or under energised conductors.",
            "",
            "## Measurement definitions",
            "",
            "- Shrub height: tallest live woody shrub below 3 m, in cm.",
            "- Shrub cover: projected foliar cover of the shrub layer in the 15 m plot, in percent.",
            "- Shrub stems: count of rooted woody stems below 3 m in the plot.",
            "- Recent cut: visible cut stumps or mowing within the plot; record stubble height.",
            "- ROW width: measured maintained low-vegetation width at the plot.",
            "- Tree distance and clearance: distance to the nearest conductor centreline and a",
            "  ground-based clearance estimate; never climb or approach energised conductors.",
            "",
            "## Field visits",
            "",
            "Follow MKRF access rules and utility electrical-safety rules. Do not work under",
            "energised conductors. Record the visit date, observer, GPS accuracy, and photo IDs.",
            "",
            "## Photo naming",
            "",
            "Use `<plot_id>_<YYYYMMDD>_<sequence>.jpg`, for example "
            "`SW01-C1_20261120_01.jpg`. Record each file in `photo-log.csv` with bearing",
            "and subject. Take a centre photo and four cardinal-direction photos.",
            "",
            "## Import",
            "",
            "Fill `field-observations-template.csv`, then validate it with:",
            "",
            "```bash",
            "brushline field validate \\",
            "  --csv field-observations.csv \\",
            "  --plots corridor-plots.geojson \\",
            "  --out field-observations-validated.json",
            "```",
            "",
            "The validator checks required fields, plot IDs, unit/position matches, GPS",
            "distance, duplicates, and basic ranges. The normalized JSON is the input for",
            "future calibration; it is not itself a treatment decision.",
            "",
            "Then compare with the LiDAR targets:",
            "",
            "```bash",
            "brushline field compare \\",
            "  --observations field-observations-validated.json \\",
            "  --plots corridor-plots.geojson \\",
            "  --out field-comparison.json",
            "```",
            "",
            "The comparison reports residuals, unit bias/MAE/RMSE, review multipliers, and",
            "sample-size gates. It does not apply corrections automatically.",
            "",
            "## Limits",
            "",
            "- Target metrics are 2016 LiDAR-derived, not ground truth.",
            "- The schedule and shrub response are modelled; this kit exists to test them.",
            "- No cost, crew, access, environmental-window, or electrical clearances are assumed.",
            "- Confirm data-sharing and release approval before moving any derived content public.",
            "",
            f"Generated: {datetime.now(UTC).isoformat(timespec='seconds')}",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> None:
    """Generate the complete field kit."""
    scene = json.loads(SCENE_PATH.read_text(encoding="utf-8"))
    boundary = gpd.read_file(BOUNDARY).to_crs(3005)
    perimeter = boundary.geometry.union_all()
    roads = gpd.read_file(ROADS).to_crs(3005)
    origin_x, origin_y = (float(value) for value in scene["origin_m"])
    bbox = box(origin_x, origin_y, origin_x + 1300.0, origin_y + 780.0)
    roads = roads[roads.intersects(bbox)]
    plots = _build_plots(scene, perimeter, roads)
    OUT.mkdir(parents=True, exist_ok=True)
    plots_path = OUT / "plots.csv"
    _write_plots_csv(plots, plots_path)
    (OUT / "corridor-plots.geojson").write_text(
        json.dumps(_geojson(scene, plots), indent=2) + "\n", encoding="utf-8"
    )
    _write_field_template(plots, OUT / "field-observations-template.csv")
    _write_photo_log(plots, OUT / "photo-log.csv")
    _map(scene, plots, OUT / "map.png", roads)
    html_text = _cards_html(plots, scene)
    _print_cards(html_text, OUT / "plot-cards.pdf")
    (OUT / "README.md").write_text(_readme(scene, plots), encoding="utf-8")
    (OUT / "validate.md").write_text(
        "# Import validation\n\n"
        "Run the parser before calibration. It checks the planned plot ids, unit/position "
        "matches, GPS distance, duplicates, ranges, and photo ids.\n\n"
        "```bash\nbrushline field validate --csv field-observations.csv "
        "--plots corridor-plots.geojson --out field-observations-validated.json\n"
        "brushline field compare --observations field-observations-validated.json "
        "--plots corridor-plots.geojson --out field-comparison.json\n```\n",
        encoding="utf-8",
    )
    archive = OUT.with_suffix(".zip")
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as handle:
        for path in sorted(OUT.iterdir()):
            if path.is_file() and path.name != archive.name:
                handle.write(path, arcname=path.name)
    print(
        f"{OUT} plots={len(plots)} files={len(list(OUT.iterdir()))} archive={archive} "
        f"size={archive.stat().st_size}"
    )


if __name__ == "__main__":
    main()
