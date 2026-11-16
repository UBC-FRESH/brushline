# mypy: ignore-errors
# ruff: noqa: E501
"""Build the public-data BC Hydro network prototype.

This is a proof-of-concept network, not an asset-owner plan. It uses OSM line geometry,
BC VRI forest-cover attributes, and Copernicus terrain. The demo stays under ignored
runtime storage until data-sharing and release review.
"""

from __future__ import annotations

import json
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import geopandas as gpd
import numpy as np
import rasterio
from brushline.exchange.bids import compare_bid
from brushline.exchange.contractor import build_contractor_bid
from brushline.exchange.plan import build_exchange
from brushline.model.plan import (
    CostLine,
    Plan,
    PlanAction,
    PlanAssumption,
    PlanHeader,
)
from brushline.strategic.bau import BauConfig, build_bau_plan, compare_bau
from brushline.strategic.heuristic import build_stateful_heuristic
from brushline.strategic.portfolio import (
    PortfolioConfig,
    PortfolioOption,
    PortfolioPeriod,
    PortfolioSegment,
    StrategicPortfolio,
    build_strategic_portfolio,
)
from brushline.strategic.rolling_policy import simulate_rolling_policy
from brushline.strategic.scenario_optimization import optimize_scenarios
from brushline.strategic.stateful import (
    StatefulConfig,
    StatefulMethod,
    StatefulPeriod,
    StatefulPlan,
    StatefulSegment,
    build_stateful_plan,
)
from brushline.strategic.uncertainty import UncertaintyConfig, evaluate_uncertainty
from brushline.tactical.access import AccessPlan, AccessWindow, RoadLink, build_access_plan
from brushline.tactical.operations import OperationsConfig, OperationsPlan, build_operations_plan
from brushline.tactical.program import (
    TacticalAction,
    TacticalConfig,
    TacticalProgram,
    TreatmentUnit,
    build_tactical_program,
)
from brushline.tactical.resources import (
    ContractorProfile,
    ResourcePlan,
    ResourceRequest,
    build_resource_plan,
)
from brushline.tactical.shifts import (
    ShiftConfig,
    ShiftCrew,
    ShiftMachine,
    ShiftPlan,
    ShiftWorkItem,
    build_shift_plan,
)
from pyproj import Transformer
from rasterio.enums import Resampling
from rasterio.warp import calculate_default_transform, reproject
from shapely.geometry import LineString, Point, box
from shapely.geometry.base import BaseGeometry
from shapely.ops import substring

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / "runtime/private/bc-network"
OUT = CACHE / "model"
OSM = CACHE / "osm-power.json"
VRI = CACHE / "vri.geojson"
DEM = CACHE / "copernicus-n49w123.tif"
AOI_WGS84 = (-122.62, 49.25, -122.50, 49.34)
START_YEAR = 2027
HORIZON = 5
SEGMENT_M = 500.0
SEGMENTS_PER_UNIT = 4
CREATED = datetime(2026, 11, 15, tzinfo=UTC)

METHODS: dict[str, dict[str, float]] = {
    "mowing": {"cost_ha": 420, "hours_ha": 7, "service_gain": 0.35, "risk_reduction": 0.30},
    "mechanical": {"cost_ha": 900, "hours_ha": 14, "service_gain": 0.50, "risk_reduction": 0.42},
    "manual": {"cost_ha": 1450, "hours_ha": 32, "service_gain": 0.65, "risk_reduction": 0.55},
}
CONTRACTORS = (
    ("first-nation-crew", ("manual", "mowing"), 1, 2600, 44.0),
    ("valley-crew", ("mowing", "mechanical"), 1, 4200, 39.0),
    ("ridge-crew", ("manual", "mechanical"), 1, 2400, 48.0),
)


def _aoi() -> tuple[Any, Transformer]:
    """Return the AOI polygon in EPSG:3005 and a WGS84 transformer."""
    to_3005 = Transformer.from_crs(4326, 3005, always_xy=True)
    corners = [
        to_3005.transform(AOI_WGS84[0], AOI_WGS84[1]),
        to_3005.transform(AOI_WGS84[2], AOI_WGS84[1]),
        to_3005.transform(AOI_WGS84[2], AOI_WGS84[3]),
        to_3005.transform(AOI_WGS84[0], AOI_WGS84[3]),
    ]
    xs, ys = zip(*corners, strict=True)
    return box(min(xs), min(ys), max(xs), max(ys)), to_3005


def _lines(
    aoi: BaseGeometry, to_3005: Transformer
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Load and clip mapped transmission and distribution lines."""
    data = json.loads(OSM.read_text())
    lines: list[dict[str, Any]] = []
    towers: list[dict[str, Any]] = []
    for element in data["elements"]:
        tags = element.get("tags", {})
        if element["type"] == "way" and tags.get("power") in {"line", "minor_line", "cable"}:
            if tags.get("power") == "minor_line" and not tags.get("voltage"):
                continue
            geometry = LineString(
                [(point["lon"], point["lat"]) for point in element.get("geometry", [])]
            )
            projected = gpd.GeoSeries([geometry], crs=4326).to_crs(3005).iloc[0]
            clipped = projected.intersection(aoi)
            if clipped.is_empty:
                continue
            parts = list(clipped.geoms) if clipped.geom_type == "MultiLineString" else [clipped]
            for part in parts:
                if part.length < 100:
                    continue
                voltage = str(tags.get("voltage") or "")
                width = 70.0 if voltage == "500000" else (20.0 if voltage == "25000" else 15.0)
                lines.append(
                    {
                        "line_id": f"L{len(lines) + 1:02d}",
                        "osm_way_id": element["id"],
                        "name": tags.get("name") or f"mapped {tags.get('power', 'power')} line",
                        "power": tags.get("power"),
                        "voltage": voltage,
                        "operator": tags.get("operator") or "operator not tagged",
                        "geometry": part,
                        "width_m": width,
                        "length_m": part.length,
                    }
                )
        elif element["type"] == "node" and tags.get("power") == "tower":
            point = (
                gpd.GeoSeries([Point(element["lon"], element["lat"])], crs=4326)
                .to_crs(3005)
                .iloc[0]
            )
            if aoi.contains(point):
                towers.append({"osm_node_id": element["id"], "geometry": point})
    return lines, towers


def _vri(aoi: BaseGeometry) -> gpd.GeoDataFrame:
    """Load and clip BC VRI polygons."""
    data = gpd.read_file(VRI).to_crs(3005)
    data = data[data.intersects(aoi)].copy()
    data["shrub_height"] = data["SHRUB_HEIGHT"].fillna(0.6).clip(0, 5)
    data["shrub_cover"] = data["SHRUB_CROWN_CLOSURE"].fillna(20).clip(0, 100)
    data["tree_height"] = data["PROJ_HEIGHT_1"].fillna(0).clip(0, 100)
    data["crown_closure"] = data["CROWN_CLOSURE"].fillna(0).clip(0, 100)
    return data


def _segment_line(line: dict[str, Any]) -> list[dict[str, Any]]:
    """Split a line into fixed-length segments and assign management units."""
    parts = []
    start = 0.0
    while start < line["geometry"].length:
        end = min(start + SEGMENT_M, line["geometry"].length)
        geometry = substring(line["geometry"], start, end)
        if geometry.length >= 50:
            parts.append(
                {
                    "segment_id": f"{line['line_id']}-S{len(parts) + 1:03d}",
                    "line_id": line["line_id"],
                    "line_name": line["name"],
                    "voltage": line["voltage"],
                    "operator": line["operator"],
                    "width_m": line["width_m"],
                    "length_m": round(geometry.length, 1),
                    "geometry": geometry,
                }
            )
        start = end
    return parts


def _assign_units(segments: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Group consecutive segments into tactical units."""
    units = []
    for line_id in sorted({segment["line_id"] for segment in segments}):
        line_segments = sorted(
            [segment for segment in segments if segment["line_id"] == line_id],
            key=lambda segment: segment["segment_id"],
        )
        for index in range(0, len(line_segments), SEGMENTS_PER_UNIT):
            group = line_segments[index : index + SEGMENTS_PER_UNIT]
            unit_id = f"U{len(units) + 1:03d}"
            for segment in group:
                segment["unit_id"] = unit_id
            unit = {
                "unit_id": unit_id,
                "line_id": line_id,
                "line_name": group[0]["line_name"],
                "voltage": group[0]["voltage"],
                "segment_ids": [segment["segment_id"] for segment in group],
                "area_ha": round(
                    sum(segment["length_m"] * segment["width_m"] / 10000 for segment in group), 2
                ),
                "length_m": round(sum(segment["length_m"] for segment in group), 1),
            }
            units.append(unit)
    return units


def _attach_vri(segments: list[dict[str, Any]], vri: gpd.GeoDataFrame) -> None:
    """Attach a representative VRI stand to each segment midpoint."""
    valid = vri.dropna(subset=["geometry"]).copy()
    for segment in segments:
        midpoint = segment["geometry"].interpolate(0.5, normalized=True)
        distance = valid.geometry.distance(midpoint)
        row = valid.iloc[int(distance.argmin())]
        segment["vri_polygon_id"] = int(row.get("POLYGON_ID") or 0)
        segment["shrub_height_m"] = round(float(row["shrub_height"]), 2)
        segment["shrub_cover_pct"] = round(float(row["shrub_cover"]), 1)
        segment["tree_height_m"] = round(float(row["tree_height"]), 1)
        segment["crown_closure_pct"] = round(float(row["crown_closure"]), 1)
        segment["species"] = str(row.get("SPECIES_CD_1") or "unknown")
        segment["stand_source"] = "BC VRI 2020"
        shrub_pressure = min(
            1.0,
            (segment["shrub_height_m"] / 2.5) * (segment["shrub_cover_pct"] / 100) * 1.2,
        )
        tree_pressure = min(
            1.0,
            (segment["tree_height_m"] / 45.0) * max(segment["crown_closure_pct"] / 100, 0.15),
        )
        segment["base_risk"] = round(min(0.95, 0.55 * shrub_pressure + 0.45 * tree_pressure), 3)
        segment["base_service"] = round(1.0 - segment["base_risk"], 3)
        segment["base_uncertainty"] = 0.2


def _terrain(aoi: BaseGeometry) -> dict[str, Any]:
    """Reproject the Copernicus tile into a compact local terrain grid."""
    with rasterio.open(DEM) as source:
        transform, width, height = calculate_default_transform(
            source.crs,
            "EPSG:3005",
            source.width,
            source.height,
            *source.bounds,
            dst_width=1000,
            dst_height=1000,
        )
        destination = np.full((height, width), np.nan, dtype=np.float32)
        reproject(
            rasterio.band(source, 1),
            destination,
            src_transform=source.transform,
            src_crs=source.crs,
            dst_transform=transform,
            dst_crs="EPSG:3005",
            resampling=Resampling.bilinear,
        )
    with rasterio.open(
        CACHE / "dem-3005.tif",
        "w",
        driver="GTiff",
        height=height,
        width=width,
        count=1,
        dtype="float32",
        crs="EPSG:3005",
        transform=transform,
        nodata=np.nan,
    ) as sink:
        sink.write(destination, 1)
    minx, miny, maxx, maxy = aoi.bounds
    window = rasterio.windows.from_bounds(minx, miny, maxx, maxy, transform)
    data = destination[
        max(0, int(window.row_off)) : int(window.row_off + window.height),
        max(0, int(window.col_off)) : int(window.col_off + window.width),
    ]
    data = np.where(np.isfinite(data), data, np.nanmedian(data)).astype(float)
    return {
        "width": int(data.shape[1]),
        "height": int(data.shape[0]),
        "resolution_m": round((maxx - minx) / data.shape[1], 2),
        "elevation": data.round(1).tolist(),
        "elevation_range_m": [round(float(np.nanmin(data)), 1), round(float(np.nanmax(data)), 1)],
        "source": "Copernicus DEM GLO-30 (public)",
        "crs": "EPSG:3005",
    }


def _options(
    segments: list[dict[str, Any]], periods: list[PortfolioPeriod]
) -> tuple[list[PortfolioSegment], list[PortfolioOption]]:
    """Create strategic segment options from VRI pressure and method assumptions."""
    base_segments = []
    options = []
    for segment in segments:
        base_segments.append(
            PortfolioSegment(
                segment_id=segment["segment_id"],
                span_id=segment["unit_id"],
                sequence=int(segment["segment_id"].split("S")[-1]),
                length_m=segment["length_m"],
                base_service=segment["base_service"],
                base_risk=segment["base_risk"],
                base_uncertainty=segment["base_uncertainty"],
            )
        )
        for offset, period in enumerate(periods):
            growth = 0.035 * offset
            base_service = max(0.0, segment["base_service"] - growth)
            base_risk = min(1.0, segment["base_risk"] + growth)
            options.append(
                PortfolioOption(
                    option_id=f"{segment['segment_id']}-{period.period_id}-none",
                    segment_id=segment["segment_id"],
                    period_id=period.period_id,
                    action_id="none",
                    method=None,
                    cost=0,
                    capacity_units=0,
                    service_attainment=round(base_service, 3),
                    risk=round(base_risk, 3),
                    uncertainty=0.25,
                )
            )
            area_ha = segment["length_m"] * segment["width_m"] / 10000
            for method, params in METHODS.items():
                options.append(
                    PortfolioOption(
                        option_id=f"{segment['segment_id']}-{period.period_id}-{method}",
                        segment_id=segment["segment_id"],
                        period_id=period.period_id,
                        action_id=method,
                        method=method,
                        cost=round(area_ha * params["cost_ha"], 2),
                        capacity_units=round(area_ha * params["hours_ha"], 1),
                        service_attainment=round(
                            min(1.0, base_service + params["service_gain"]), 3
                        ),
                        risk=round(max(0.0, base_risk - params["risk_reduction"]), 3),
                        uncertainty=0.12,
                    )
                )
    return base_segments, options


def _cycle_tradeoff(segments: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Simulate fixed treatment cycles for the cost-versus-risk message."""
    results = []
    for method, params in METHODS.items():
        for cycle in (2, 3, 4, 5):
            annual_hours = []
            annual_costs = []
            cumulative_risk = 0.0
            for year_index in range(HORIZON):
                treated = year_index % cycle == 0
                hours = 0.0
                cost = 0.0
                if treated:
                    hours = sum(
                        segment["length_m"] * segment["width_m"] / 10000 * params["hours_ha"]
                        for segment in segments
                    )
                    cost = sum(
                        segment["length_m"] * segment["width_m"] / 10000 * params["cost_ha"]
                        for segment in segments
                    )
                annual_hours.append(round(hours, 1))
                annual_costs.append(round(cost, 1))
                for segment in segments:
                    years_since = year_index % cycle
                    risk = max(
                        0.0,
                        min(
                            0.95,
                            segment["base_risk"]
                            + 0.025 * years_since
                            - (params["risk_reduction"] if treated else 0),
                        ),
                    )
                    cumulative_risk += risk
            results.append(
                {
                    "method": method,
                    "cycle_years": cycle,
                    "annual_hours": annual_hours,
                    "annual_cost": annual_costs,
                    "five_year_cost": round(sum(annual_costs), 1),
                    "mean_annual_hours": round(sum(annual_hours) / HORIZON, 1),
                    "mean_risk": round(cumulative_risk / (HORIZON * len(segments)), 3),
                    "assumption": "Fixed full-network cycle; no budget or capacity constraint.",
                }
            )
    return results


def _milp_plan(
    segments: list[dict[str, Any]],
    *,
    name: str,
    annual_budget: float,
    capacity_hours: float = 6000.0,
    risk_weight: float = 1.0,
) -> dict[str, Any]:
    """Solve one stateful MILP and attach the network unit ids."""
    stateful_segments = [
        StatefulSegment(
            segment_id=segment["segment_id"],
            span_id=segment["unit_id"],
            length_m=segment["length_m"],
            area_ha=segment["length_m"] * segment["width_m"] / 10000,
            initial_risk=segment["base_risk"],
        )
        for segment in segments
    ]
    methods = [
        StatefulMethod(
            method=method,
            cost_per_ha=params["cost_ha"],
            hours_per_ha=params["hours_ha"],
            risk_reduction=params["risk_reduction"],
        )
        for method, params in METHODS.items()
    ]
    periods = [
        StatefulPeriod(
            year=START_YEAR + offset,
            budget=annual_budget,
            capacity_hours=capacity_hours,
        )
        for offset in range(HORIZON)
    ]
    plan = build_stateful_plan(
        instance_id="bc-hydro-network-2026",
        segments=stateful_segments,
        methods=methods,
        periods=periods,
        config=StatefulConfig(
            risk_weight=risk_weight,
            cost_weight=0.0,
            growth_per_year=0.03,
            max_seconds=45,
        ),
        created_utc=CREATED,
    )
    segment_map = {segment["segment_id"]: segment for segment in segments}
    actions = [
        {
            **action.model_dump(mode="json"),
            "unit_id": segment_map[action.segment_id]["unit_id"],
        }
        for action in plan.actions
    ]
    rows = [row.model_dump(mode="json") for row in plan.years]
    return {
        "name": name,
        "annual_budget": annual_budget,
        "capacity_hours": capacity_hours,
        "solver": plan.solver,
        "solver_status": plan.status,
        "replay_ok": plan.replay_ok,
        "plan": plan.model_dump(mode="json"),
        "rows": rows,
        "actions": actions,
        "five_year_cost": plan.total_cost,
        "mean_service": plan.mean_service,
        "mean_risk": plan.mean_risk,
        "mean_annual_hours": round(plan.total_hours / HORIZON, 1),
    }


def _scalability(segments: list[dict[str, Any]], instance_id: str) -> list[dict[str, Any]]:
    """Benchmark the Fresh Solutions heuristic on replicated network scales."""
    methods = [
        StatefulMethod(
            method=method,
            cost_per_ha=params["cost_ha"],
            hours_per_ha=params["hours_ha"],
            risk_reduction=params["risk_reduction"],
        )
        for method, params in METHODS.items()
    ]
    results = []
    for factor in (1, 10, 50, 170):
        scaled_segments = []
        for copy in range(factor):
            for segment in segments:
                scaled_segments.append(
                    StatefulSegment(
                        segment_id=f"{segment['segment_id']}-{copy}",
                        span_id=f"{segment['unit_id']}-{copy}",
                        length_m=segment["length_m"],
                        area_ha=segment["length_m"] * segment["width_m"] / 10000,
                        initial_risk=segment["base_risk"],
                    )
                )
        periods = [
            StatefulPeriod(
                year=START_YEAR + offset,
                budget=60000 * factor,
                capacity_hours=6000 * factor,
            )
            for offset in range(HORIZON)
        ]
        started = time.perf_counter()
        plan = build_stateful_heuristic(
            instance_id=instance_id,
            segments=scaled_segments,
            methods=methods,
            periods=periods,
            config=StatefulConfig(risk_weight=1.0, cost_weight=0.0),
            iterations=20,
            seed=7,
            created_utc=CREATED,
        )
        results.append(
            {
                "segments": len(scaled_segments),
                "variables": len(scaled_segments) * HORIZON,
                "seconds": round(time.perf_counter() - started, 2),
                "status": plan.status,
                "mean_risk": plan.mean_risk,
                "mean_service": plan.mean_service,
                "total_cost": plan.total_cost,
                "evaluations": int(plan.search.get("evaluations", 0)),
            }
        )
    return results


def _grow_risk(risk: float) -> float:
    """Apply one year of unreported vegetation growth to a risk index."""
    return min(0.95, risk + 0.015 + 0.03 * (1.0 - risk))


def _stateful_scenario(
    segments: list[dict[str, Any]],
    *,
    name: str,
    annual_budget: float,
    risk_weight: float,
    capacity_hours: float = 6000.0,
    policy: str = "risk",
) -> dict[str, Any]:
    """Simulate a budget-constrained treatment policy with state carry-over.

    The policy is a deterministic risk-per-dollar heuristic, not an exact
    multi-period optimizer. The state does carry treatment benefits and growth
    forward, unlike the static portfolio screening model.
    """
    state = {segment["segment_id"]: float(segment["base_risk"]) for segment in segments}
    rows = []
    actions = []
    total_cost = 0.0
    total_hours = 0.0
    for offset in range(HORIZON):
        year = START_YEAR + offset
        for segment in segments:
            sid = segment["segment_id"]
            state[sid] = _grow_risk(state[sid])
        selected: list[tuple[dict[str, Any], str, float, float, float]] = []
        if policy == "bau-cycle":
            if offset == 0:
                for segment in segments:
                    params = METHODS["mowing"]
                    area = segment["length_m"] * segment["width_m"] / 10000
                    selected.append(
                        (
                            segment,
                            "mowing",
                            area * params["cost_ha"],
                            area * params["hours_ha"],
                            state[segment["segment_id"]],
                        )
                    )
        else:
            candidates = []
            for segment in segments:
                sid = segment["segment_id"]
                area = segment["length_m"] * segment["width_m"] / 10000
                for method, params in METHODS.items():
                    post = max(0.0, state[sid] - params["risk_reduction"])
                    benefit = (state[sid] - post) * risk_weight
                    score = benefit / max(area * params["cost_ha"], 1.0)
                    candidates.append(
                        (
                            score,
                            segment,
                            method,
                            area * params["cost_ha"],
                            area * params["hours_ha"],
                            post,
                        )
                    )
            candidates.sort(key=lambda item: (-item[0], item[1]["segment_id"], item[2]))
            used: set[str] = set()
            spent = 0.0
            hours = 0.0
            for _score, segment, method, cost, capacity, post in candidates:
                sid = segment["segment_id"]
                if sid in used or spent + cost > annual_budget or hours + capacity > capacity_hours:
                    continue
                used.add(sid)
                selected.append((segment, method, cost, capacity, post))
                spent += cost
                hours += capacity
        for segment, method, cost, capacity, post in selected:
            sid = segment["segment_id"]
            before = state[sid]
            state[sid] = max(0.0, post)
            actions.append(
                {
                    "year": year,
                    "segment_id": sid,
                    "unit_id": segment["unit_id"],
                    "method": method,
                    "cost": round(cost, 2),
                    "hours": round(capacity, 1),
                    "risk_before": round(before, 3),
                    "risk_after": round(state[sid], 3),
                }
            )
        total_cost += sum(item[2] for item in selected)
        total_hours += sum(item[3] for item in selected)
        weighted_total = sum(segment["length_m"] for segment in segments)
        weighted_risk = sum(
            state[segment["segment_id"]] * segment["length_m"] for segment in segments
        ) / max(weighted_total, 1.0)
        rows.append(
            {
                "year": year,
                "cost": round(sum(item[2] for item in selected), 1),
                "hours": round(sum(item[3] for item in selected), 1),
                "actions": len(selected),
                "service": round(1.0 - weighted_risk, 3),
                "risk": round(weighted_risk, 3),
            }
        )
    return {
        "name": name,
        "annual_budget": annual_budget,
        "policy": policy,
        "rows": rows,
        "actions": actions,
        "five_year_cost": round(total_cost, 1),
        "mean_service": round(sum(row["service"] for row in rows) / HORIZON, 3),
        "mean_risk": round(sum(row["risk"] for row in rows) / HORIZON, 3),
        "mean_annual_hours": round(total_hours / HORIZON, 1),
    }


def _stateful_frontier(scenarios: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Keep the non-dominated cost/risk points from a stateful budget sweep."""
    ordered = sorted(scenarios, key=lambda item: (item["five_year_cost"], item["mean_risk"]))
    frontier = []
    best_risk = 1.1
    for scenario in ordered:
        if scenario["mean_risk"] < best_risk - 1e-9:
            frontier.append(scenario)
            best_risk = scenario["mean_risk"]
    return frontier


def _stateful_cycles(segments: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Run stateful fixed-cycle simulations for the cost-versus-risk table."""
    results = []
    for method, params in METHODS.items():
        for cycle in (2, 3, 4, 5):
            state = {segment["segment_id"]: float(segment["base_risk"]) for segment in segments}
            rows = []
            total_cost = 0.0
            total_hours = 0.0
            for offset in range(HORIZON):
                for segment in segments:
                    state[segment["segment_id"]] = _grow_risk(state[segment["segment_id"]])
                treat = offset % cycle == 0
                cost = 0.0
                hours = 0.0
                if treat:
                    for segment in segments:
                        area = segment["length_m"] * segment["width_m"] / 10000
                        state[segment["segment_id"]] = max(
                            0.0, state[segment["segment_id"]] - params["risk_reduction"]
                        )
                        cost += area * params["cost_ha"]
                        hours += area * params["hours_ha"]
                total_cost += cost
                total_hours += hours
                weighted = sum(segment["length_m"] for segment in segments)
                risk = sum(
                    state[segment["segment_id"]] * segment["length_m"] for segment in segments
                ) / max(weighted, 1.0)
                rows.append(
                    {
                        "year": START_YEAR + offset,
                        "cost": round(cost, 1),
                        "hours": round(hours, 1),
                        "risk": round(risk, 3),
                    }
                )
            results.append(
                {
                    "method": method,
                    "cycle_years": cycle,
                    "annual_cost": [row["cost"] for row in rows],
                    "annual_hours": [row["hours"] for row in rows],
                    "five_year_cost": round(total_cost, 1),
                    "mean_annual_hours": round(total_hours / HORIZON, 1),
                    "mean_risk": round(sum(row["risk"] for row in rows) / HORIZON, 3),
                }
            )
    return results


def _portfolio(
    segments: list[dict[str, Any]],
    periods: list[PortfolioPeriod],
    options: list[PortfolioOption],
    budget: float,
    risk_weight: float,
) -> StrategicPortfolio:
    """Run one strategic budget scenario."""
    config = PortfolioConfig(
        service_target=0.0,
        risk_target=0.0,
        service_weight=1.0,
        risk_weight=risk_weight,
        uncertainty_weight=0.4,
        cost_weight=0.0,
        continuity_weight=0.0,
        max_steps=120,
        seed=7,
    )
    scenario_periods = [
        PortfolioPeriod(
            period_id=period.period_id,
            start_year=period.start_year,
            budget=budget,
            capacity_by_method={"mowing": 6000, "mechanical": 6000, "manual": 6000},
        )
        for period in periods
    ]
    return build_strategic_portfolio(
        portfolio_id=f"portfolio-{int(budget)}-{risk_weight}",
        instance_id="bc-hydro-network-2026",
        segments=segments,
        periods=scenario_periods,
        options=options,
        config=config,
        created_utc=CREATED,
    )


def _profiles(
    extra: tuple[tuple[str, tuple[str, ...], int, float, float], ...] = (),
) -> list[ContractorProfile]:
    """Build contractor profiles from the demo tuples."""
    values = [
        ContractorProfile(
            contractor_id=contractor_id,
            methods=list(methods),
            crews=crews,
            machines=1 if "mechanical" in methods else 0,
            rate_per_unit=rate,
            travel_cost_per_km=2.5,
            supervision_rate=0.08,
            overhead_fraction=0.10,
            risk_fraction=0.03,
            annual_capacity_units=capacity,
            currency="CAD",
        )
        for contractor_id, methods, crews, capacity, rate in (*CONTRACTORS, *extra)
    ]
    return values


def _tactical(
    source_actions: list[dict[str, Any]],
    segments: list[dict[str, Any]],
    units: list[dict[str, Any]],
    towers: list[dict[str, Any]],
) -> tuple[TacticalProgram, AccessPlan, ResourcePlan, OperationsPlan]:
    """Turn stateful strategic actions into tactical and operational plans."""
    unit_actions = [
        (
            action["unit_id"],
            int(action["year"]),
            str(action["method"]),
            float(action["cost"]),
            float(action["hours"]),
            str(action["segment_id"]),
        )
        for action in source_actions
    ]
    grouped: dict[tuple[str, int, str], dict[str, Any]] = {}
    for unit_id, year, method, cost, hours, segment_id in unit_actions:
        key = (unit_id, year, method)
        item = grouped.setdefault(key, {"cost": 0.0, "hours": 0.0, "segments": []})
        item["cost"] += cost
        item["hours"] += hours
        item["segments"].append(segment_id)
    actions = []
    contractor_load: dict[tuple[str, int], float] = {}
    for index, ((unit_id, year, method), item) in enumerate(sorted(grouped.items()), start=1):
        eligible = [profile for profile in CONTRACTORS if method in profile[1]]
        profile = min(
            eligible,
            key=lambda candidate: (
                contractor_load.get((candidate[0], year), 0.0) / candidate[3],
                candidate[0],
            ),
        )
        contractor_load[(profile[0], year)] = (
            contractor_load.get((profile[0], year), 0.0) + item["hours"]
        )
        actions.append(
            TacticalAction(
                action_id=f"A{index:03d}",
                unit_id=unit_id,
                year=year,
                season="fall",
                method=method,
                contractor_id=profile[0],
                cost=round(item["cost"], 2),
                capacity_units=round(item["hours"], 1),
                access_window_id=f"W-{unit_id}-{year}",
            )
        )
    tactical_units = [
        TreatmentUnit(
            unit_id=unit["unit_id"],
            span_id=unit["unit_id"],
            segment_ids=unit["segment_ids"],
            area_ha=unit["area_ha"],
            allowed_methods=["manual", "mowing", "mechanical"],
            allowed_seasons=["fall"],
        )
        for unit in units
    ]
    windows = [
        AccessWindow(
            window_id=f"W-{action.unit_id}-{action.year}",
            unit_id=action.unit_id,
            link_id=action.unit_id,
            year=action.year,
            season="fall",
        )
        for action in actions
    ]
    links = [
        RoadLink(
            link_id=unit["unit_id"],
            source="prototype access assumption (verify with MKRF/BC Hydro)",
            status="open",
            status_source="prototype assumption",
            length_m=round(unit["length_m"] * 0.6, 1),
        )
        for unit in units
    ]
    access = build_access_plan(
        plan_id="access-bc-network",
        instance_id="bc-hydro-network-2026",
        windows=windows,
        links=links,
        created_utc=CREATED,
    )
    program = build_tactical_program(
        program_id="tactical-bc-network",
        instance_id="bc-hydro-network-2026",
        units=tactical_units,
        actions=actions,
        config=TacticalConfig(
            horizon_years=HORIZON,
            start_year=START_YEAR,
            budget_by_year={2027 + i: 60000 for i in range(HORIZON)},
            currency="CAD",
        ),
        created_utc=CREATED,
    )
    profiles = [
        ContractorProfile(
            contractor_id=contractor_id,
            methods=list(methods),
            crews=crews,
            machines=1 if "mechanical" in methods else 0,
            rate_per_unit=rate,
            travel_cost_per_km=2.5,
            supervision_rate=0.08,
            overhead_fraction=0.10,
            risk_fraction=0.03,
            annual_capacity_units=capacity,
            currency="CAD",
        )
        for contractor_id, methods, crews, capacity, rate in CONTRACTORS
    ]
    requests = [
        ResourceRequest(
            request_id=f"R-{action.action_id}",
            contractor_id=action.contractor_id,
            method=action.method,
            year=action.year,
            capacity_units=action.capacity_units,
            travel_km=40,
        )
        for action in actions
    ]
    resources = build_resource_plan(
        plan_id="resources-bc-network",
        instance_id="bc-hydro-network-2026",
        requests=requests,
        profiles=profiles,
        created_utc=CREATED,
    )
    operations = build_operations_plan(
        plan_id="operations-bc-network",
        instance_id="bc-hydro-network-2026",
        program=program,
        access=access,
        config=OperationsConfig(
            start_year=START_YEAR,
            start_day=1,
            max_orders_per_day=2,
            crew_ids=["crew-a", "crew-b", "crew-c"],
        ),
        created_utc=CREATED,
    )
    return program, access, resources, operations


def _policy_execution(
    rolling_policy: dict[str, Any],
    fixed_actions: list[dict[str, Any]],
    segments: list[dict[str, Any]],
    units: list[dict[str, Any]],
    towers: list[dict[str, Any]],
    profiles: list[ContractorProfile],
) -> dict[str, Any]:
    """Turn the median rolling-policy episode into a first-year execution package."""
    episodes = sorted(
        rolling_policy["episodes_detail"],
        key=lambda episode: (float(episode["rolling_cost"]), int(episode["index"])),
    )
    episode = episodes[len(episodes) // 2]
    year_row = episode["years"][0]
    year = int(year_row["year"])
    policy_actions = [dict(action) for action in year_row.get("action_details") or []]
    if not policy_actions:
        raise ValueError("rolling-policy episode has no first-year action details")
    source_actions = [
        {
            "unit_id": action["unit_id"],
            "year": year,
            "method": action["method"],
            "cost": float(action["cost"]),
            "hours": float(action["hours"]),
            "segment_id": action["segment_id"],
        }
        for action in policy_actions
    ]
    program, access, resources, operations = _tactical(source_actions, segments, units, towers)
    shifts = _shifts(program.actions, "bc-hydro-network-2026", profiles)
    fixed_year = [action for action in fixed_actions if int(action["year"]) == year]
    fixed_cost = sum(float(action["cost"]) for action in fixed_year)
    fixed_hours = sum(float(action["hours"]) for action in fixed_year)
    policy_cost = float(year_row["cost"])
    policy_hours = float(year_row["hours"])
    factors = next(
        (factor for factor in episode["factors"] if int(factor["year"]) == year),
        {},
    )
    return {
        "schema_version": "brushline.policy-execution.v1",
        "instance_id": "bc-hydro-network-2026",
        "selection": {
            "rule": "median rolling five-year cost",
            "episode_index": episode["index"],
            "episode_cost": episode["rolling_cost"],
            "year": year,
            "factors": factors,
        },
        "policy": {
            "actions": len(policy_actions),
            "cost": round(policy_cost, 2),
            "hours": round(policy_hours, 2),
            "risk": year_row["risk"],
            "tactical_actions": len(program.actions),
            "work_orders": len(operations.work_orders),
            "shift_assignments": len(shifts.assignments),
            "resource_feasible": resources.feasible,
            "shift_feasible": shifts.feasible,
        },
        "fixed": {
            "actions": len(fixed_year),
            "cost": round(fixed_cost, 2),
            "hours": round(fixed_hours, 2),
        },
        "comparison": {
            "cost_delta": round(policy_cost - fixed_cost, 2),
            "hours_delta": round(policy_hours - fixed_hours, 2),
            "cost_ratio": round(policy_cost / fixed_cost, 4) if fixed_cost else None,
            "hours_ratio": round(policy_hours / fixed_hours, 4) if fixed_hours else None,
        },
        "policy_actions": policy_actions,
        "tactical": program.model_dump(mode="json"),
        "access": access.model_dump(mode="json"),
        "resources": resources.model_dump(mode="json"),
        "operations": operations.model_dump(mode="json"),
        "shifts": shifts.model_dump(mode="json"),
        "caveats": [
            "Selected from the median rolling five-year cost, not the best or worst episode.",
            "First-year execution package only; future years are re-planned by the policy.",
            "Tactical and shift assumptions are prototype values, not field rates or commitments.",
            "No outage, weather, safety, or asset-owner clearance standard is claimed.",
        ],
    }


def _scene(
    network: dict[str, Any],
    segments: list[dict[str, Any]],
    vri: gpd.GeoDataFrame,
    lines: list[dict[str, Any]],
    towers: list[dict[str, Any]],
    aoi: BaseGeometry,
) -> dict[str, Any]:
    """Build a Studio-compatible 3D context scene from the network prototype."""
    origin_x, origin_y = aoi.bounds[0], aoi.bounds[1]
    terrain = network["terrain"]
    trees = []
    understory = []
    for index, (_, row) in enumerate(vri.iterrows()):
        point = row.geometry.representative_point()
        local_x = point.x - origin_x
        local_y = point.y - origin_y
        if not (0 <= local_x <= terrain["width"] * terrain["resolution_m"]):
            continue
        if not (0 <= local_y <= terrain["height"] * terrain["resolution_m"]):
            continue
        height = float(row.get("tree_height") or 0)
        if height > 2:
            minx, miny, maxx, maxy = row.geometry.bounds
            offsets = (
                (0.0, 0.0),
                ((maxx - minx) * 0.22, 0.0),
                (-(maxx - minx) * 0.22, 0.0),
                (0.0, (maxy - miny) * 0.22),
                (0.0, -(maxy - miny) * 0.22),
            )
            for tree_index, (dx, dy) in enumerate(offsets):
                candidate = Point(point.x + dx, point.y + dy)
                if not row.geometry.contains(candidate):
                    continue
                trees.append(
                    {
                        "tree_id": f"vri-{index}-{tree_index}",
                        "x_m": round(candidate.x - origin_x, 2),
                        "y_m": round(candidate.y - origin_y, 2),
                        "height_m": round(height, 2),
                        "crown_width_m": round(min(12.0, max(1.5, height * 0.22)), 2),
                        "species": str(row.get("SPECIES_CD_1") or "VRI stand"),
                        "source": "BC VRI 2020 stand sample",
                    }
                )
        shrub_cover = float(row.get("shrub_cover") or 0)
        shrub_height = float(row.get("shrub_height") or 0)
        if shrub_cover > 5 and shrub_height > 0.2:
            understory.append(
                {
                    "patch_id": f"vri-shrub-{index}",
                    "x_m": round(local_x, 2),
                    "y_m": round(local_y, 2),
                    "height_m": round(shrub_height, 2),
                    "width_m": round(min(4.0, 1.0 + shrub_cover / 40), 2),
                    "cover_pct": round(shrub_cover, 1),
                    "in_corridor": False,
                    "source": "BC VRI 2020 shrub attributes",
                }
            )
    line_payload = []
    for line in lines:
        line_payload.append(
            {
                "name": line["name"],
                "points": [
                    [round(x - origin_x, 2), round(y - origin_y, 2)]
                    for x, y in line["geometry"].coords
                ],
            }
        )
    tower_payload = []
    for tower in towers:
        tower_payload.append(
            {
                "tower_id": f"T{len(tower_payload) + 1:03d}",
                "x_m": round(tower["geometry"].x - origin_x, 2),
                "y_m": round(tower["geometry"].y - origin_y, 2),
                "height_m": 45.0,
            }
        )
    width = round(terrain["width"] * terrain["resolution_m"], 1)
    height_m = round(terrain["height"] * terrain["resolution_m"], 1)
    return {
        "schema_version": "brushline.real-scene.v1",
        "instance_id": "bc-hydro-network-2026",
        "block": {
            "block_id": "bc-network",
            "block_kind": "network_block",
            "segment_ids": [],
            "bounds_m": [0, 0, width, height_m],
            "position_status": "derived",
        },
        "crs": "EPSG:3005",
        "origin_m": [origin_x, origin_y],
        "terrain": terrain,
        "trees": trees,
        "understory": {
            "source": "BC VRI 2020 shrub attributes",
            "patches": understory,
            "patch_count": len(understory),
            "corridor_patch_count": 0,
        },
        "powerline": {
            "name": "BC Hydro public-data network prototype",
            "voltage_kv": 500,
            "lines": line_payload,
            "towers": tower_payload,
            "conductor_height_m": 32.0,
            "corridor_width_m": 70.0,
            "source": "OpenStreetMap power lines",
        },
        "sources": [
            {"name": "OpenStreetMap power lines", "licence": "ODbL-1.0"},
            {"name": "BC VRI 2020", "licence": "BC Open Government Licence"},
            {"name": "Copernicus DEM GLO-30", "licence": "Copernicus DEM licence"},
        ],
        "caveats": [
            "Proof-of-concept network and VRI stand context; not a survey or asset-owner plan.",
            "Tower geometry is schematic and conductor height is approximate.",
            "Tree and shrub instances are VRI stand centroids, not measured stems.",
            "No clearance, outage, access, or safety certification is claimed.",
        ],
        "treatment": None,
    }


def _shifts(
    actions: list[TacticalAction], instance_id: str, profiles: list[ContractorProfile]
) -> ShiftPlan:
    """Build a deterministic crew and machine shift schedule for tactical actions."""
    work_items = [
        ShiftWorkItem(
            work_order_id=f"wo-{action.action_id}",
            unit_id=action.unit_id,
            method=action.method,
            year=action.year,
            hours=action.capacity_units,
            travel_hours=0.5,
            contractor_id=action.contractor_id,
            priority=1,
        )
        for action in actions
    ]
    crews = [
        ShiftCrew(
            crew_id=profile.contractor_id,
            methods=list(profile.methods),
            shift_hours=8.0,
            contractor_id=profile.contractor_id,
        )
        for profile in profiles
    ]
    machines = [
        ShiftMachine(
            machine_id=f"{profile.contractor_id}-machine",
            methods=[method for method in profile.methods if method in {"mowing", "mechanical"}],
            shift_hours=8.0,
            contractor_id=profile.contractor_id,
        )
        for profile in profiles
    ]
    machines = [machine for machine in machines if machine.methods]
    return build_shift_plan(
        plan_id="shifts-bc-network",
        instance_id=instance_id,
        work_items=work_items,
        crews=crews,
        machines=machines,
        config=ShiftConfig(max_days_per_year=260, include_travel=True),
        created_utc=CREATED,
    )


def _workforce_scenarios(actions: list[TacticalAction], instance_id: str) -> list[dict[str, Any]]:
    """Compare current, expanded, and community-enterprise workforce scenarios."""
    total_hours = sum(action.capacity_units for action in actions)
    scenarios = [
        ("current-mix", None, 0.0, 1.0, ()),
        (
            "expanded",
            "expansion-crew",
            0.25,
            1.0,
            (("expansion-crew", ("manual", "mowing", "mechanical"), 2, 4000.0, 40.0),),
        ),
        (
            "community-enterprise",
            "community-crew",
            0.20,
            1.4,
            (("community-crew", ("manual", "mowing"), 1, 2000.0, 44.0),),
        ),
    ]
    results = []
    for name, target_contractor, target_share, productivity, extra in scenarios:
        profiles = _profiles(extra)
        scenario_actions = []
        reassigned = 0.0
        for action in actions:
            target = None
            if target_contractor is not None and reassigned < total_hours * target_share:
                target_profile = next(
                    profile for profile in profiles if profile.contractor_id == target_contractor
                )
                if action.method in target_profile.methods:
                    target = target_contractor
            if target is None:
                scenario_actions.append(action)
                continue
            hours = action.capacity_units * productivity
            scenario_actions.append(
                action.model_copy(update={"contractor_id": target, "capacity_units": hours})
            )
            reassigned += action.capacity_units
        requests = [
            ResourceRequest(
                request_id=f"R-{action.action_id}",
                contractor_id=action.contractor_id,
                method=action.method,
                year=action.year,
                capacity_units=action.capacity_units,
                travel_km=40,
            )
            for action in scenario_actions
        ]
        resource_plan = build_resource_plan(
            plan_id=f"workforce-{name}",
            instance_id=instance_id,
            requests=requests,
            profiles=profiles,
            created_utc=CREATED,
        )
        shift_plan = _shifts(scenario_actions, instance_id, profiles)
        results.append(
            {
                "name": name,
                "target_share": target_share,
                "productivity_factor": productivity,
                "total_action_hours": round(total_hours, 1),
                "reassigned_hours": round(reassigned, 1),
                "resource_cost": resource_plan.total_cost,
                "resource_feasible": resource_plan.feasible,
                "shift_feasible": shift_plan.feasible,
                "shift_assignments": len(shift_plan.assignments),
                "crew_hours": shift_plan.crew_utilization,
                "contractor_cost": resource_plan.by_contractor,
            }
        )
    return results


def _bid(
    actions: list[TacticalAction], units: list[dict[str, Any]], instance_id: str
) -> dict[str, Any]:
    """Build the owner plan, contractor bid, and fair-price check."""
    unit_map = {unit["unit_id"]: unit for unit in units}
    plan_actions = []
    for action in actions:
        labour = round(action.cost * 0.70, 2)
        equipment = round(action.cost * 0.20, 2)
        travel = round(action.cost - labour - equipment, 2)
        area = float(unit_map[action.unit_id]["area_ha"])
        plan_actions.append(
            PlanAction(
                action_id=action.action_id,
                segment_id=action.unit_id,
                year=action.year,
                season=action.season,
                method=action.method,
                intensity=0.5,
                efficacy=0.5,
                cost_lines=[
                    CostLine(category="labour", amount=labour, source="prototype method mix"),
                    CostLine(category="equipment", amount=equipment, source="prototype method mix"),
                    CostLine(category="travel", amount=travel, source="prototype method mix"),
                ],
                treatment_unit_id=action.unit_id,
                quantity_ha=area,
                assumptions=["Prototype cost allocation; not a contractor rate sheet."],
                risk_notes="Planning estimate only.",
            )
        )
    plan = Plan(
        header=PlanHeader(
            plan_id="bc-network-balanced-2027",
            version=1,
            status="proposed",
            scenario_id="bc-hydro-network-2026",
            dataset_id="bc-hydro-network-2026",
            data_version="public-data-2026-11-15",
            model_versions={
                "data_version": "public-data-2026-11-15",
                "model": "brushline.stateful-milp.v1",
            },
            configuration={"budget_per_year": 60000, "objective": "risk-first linear MILP"},
            currency="CAD",
            created_utc=CREATED,
            created_by="Brushline prototype",
        ),
        actions=plan_actions,
        assumptions=[
            PlanAssumption(
                assumption_id="A1",
                statement="Cost allocation is a prototype 70/20/10 labour/equipment/travel split.",
                source="Brushline demo",
                impact="Commercial comparison only.",
            )
        ],
    )
    exchange = build_exchange(plan)
    bid = build_contractor_bid(
        exchange,
        contractor_id="valley-crew",
        access_cost=5000.0,
        schedule_days=60,
        productivity=0.9,
        rate_adjustments={"labour": 0.06, "equipment": 0.02, "travel": 0.10},
        assumptions=[
            "Mock contractor rate adjustments and access cost.",
            "Productivity 0.9 for bid comparison.",
        ],
    )
    comparison = compare_bid(
        exchange,
        bid,
        fair_low=round(exchange.cost_buildup.total_cost * 0.95, 2),
        fair_high=round(exchange.cost_buildup.total_cost * 1.15, 2),
    )
    return {
        "plan_id": plan.header.plan_id,
        "owner_total": exchange.cost_buildup.total_cost,
        "bid": bid.model_dump(mode="json"),
        "comparison": comparison.model_dump(mode="json"),
    }


def _summary(
    network: dict[str, Any],
    strategic: dict[str, Any],
    tactical: dict[str, Any],
    resources: dict[str, Any],
    operations: dict[str, Any],
    shifts: dict[str, Any],
    workforce: list[dict[str, Any]],
    scalability: list[dict[str, Any]],
    bid: dict[str, Any],
    uncertainty: dict[str, Any],
    scenario_optimization: dict[str, Any],
    rolling_policy: dict[str, Any],
    policy_execution: dict[str, Any],
) -> str:
    """Write a compact human-readable report."""
    lines = [
        "# BC Hydro network prototype",
        "",
        f"AOI: {network['aoi_ha']:.1f} ha, {network['line_km']:.1f} km of mapped power-line features.",
        f"Feature count: {len(network['lines'])}; management units: {len(network['units'])}; segments: {len(network['segments'])}.",
        "",
        "## Strategic scenarios",
        "",
        "| Scenario | Budget/yr | Five-year cost | Mean service | Mean risk | Hours/yr |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for scenario in strategic["milp_scenarios"]:
        lines.append(
            f"| {scenario['name']} | {scenario['annual_budget']:.0f} | "
            f"{scenario['five_year_cost']:.0f} | {scenario['mean_service']:.3f} | "
            f"{scenario['mean_risk']:.3f} | {scenario['mean_annual_hours']:.0f} |"
        )
    bau = strategic["bau"]
    bau_cost = sum(row["cost"] for row in bau["period_summary"])
    bau_hours = sum(row["capacity_used"].get("mowing", 0) for row in bau["period_summary"])
    lines.append(
        f"| BAU 5-year mowing | 0 | {bau_cost:.0f} | "
        f"{bau['service_attainment']:.3f} | {bau['risk']:.3f} | "
        f"{bau_hours / HORIZON:.0f} |"
    )
    lines.extend(
        [
            "",
            "## Treatment-cycle tradeoff",
            "",
            "| Method | Cycle | Five-year cost | Hours/yr | Mean risk |",
            "|---|---:|---:|---:|---:|",
        ]
    )
    for item in strategic["stateful_cycles"]:
        lines.append(
            f"| {item['method']} | {item['cycle_years']} | {item['five_year_cost']:.0f} | "
            f"{item['mean_annual_hours']:.0f} | {item['mean_risk']:.3f} |"
        )
    demand_by_year: dict[int, float] = {}
    for request in resources["requests"]:
        demand_by_year[request["year"]] = (
            demand_by_year.get(request["year"], 0.0) + request["capacity_units"]
        )
    lines.extend(
        [
            "",
            "## Tactical and operational plan",
            "",
            f"MILP scenarios: {len(strategic['milp_scenarios'])}; all optimal/replayed: "
            f"{all(item['solver_status'] == 'optimal' and item['replay_ok'] for item in strategic['milp_scenarios'])}.",
            f"Selected actions: {len(tactical['actions'])}; total cost: {tactical['total_cost']:.0f}; "
            f"resource cost: {resources['total_cost']:.0f}; contractor capacity feasible: "
            f"{resources['feasible']}; work orders: {len(operations['work_orders'])}; "
            f"shift assignments: {len(shifts.get('assignments', []))}.",
            "",
            "## Annual tactical demand",
            "",
            "| Year | Tactical cost | Crew-hours requested |",
            "|---:|---:|---:|",
        ]
    )
    for year in sorted(demand_by_year):
        lines.append(
            f"| {year} | {tactical['cost_by_year'].get(str(year), 0):.0f} | "
            f"{demand_by_year[year]:.0f} |"
        )
    lines.extend(
        [
            "",
            "## Workforce scenarios",
            "",
            "| Scenario | Reassigned h | Resource cost | Resource feasible | Shift feasible |",
            "|---|---:|---:|---|---|",
        ]
    )
    for scenario in workforce:
        lines.append(
            f"| {scenario['name']} | {scenario['reassigned_hours']:.0f} | "
            f"{scenario['resource_cost']:.0f} | {scenario['resource_feasible']} | "
            f"{scenario['shift_feasible']} |"
        )
    lines.extend(
        [
            "",
            "## Heuristic scalability",
            "",
            "| Segments | Variables | Seconds | Mean risk | Status | Evaluations |",
            "|---:|---:|---:|---:|---|---:|",
        ]
    )
    for item in scalability:
        lines.append(
            f"| {item['segments']} | {item['variables']} | {item['seconds']:.2f} | "
            f"{item['mean_risk']:.3f} | {item['status']} | {item['evaluations']} |"
        )
    lines.extend(
        [
            "",
            "## Commercial check",
            "",
            f"Owner plan: {bid['owner_total']:.0f} CAD; contractor bid: "
            f"{bid['bid']['total_cost']:.0f} CAD; delta: "
            f"{bid['comparison']['delta']:.0f} CAD; within fair range: "
            f"{bid['comparison']['within_fair_range']}.",
            "",
            "## Execution uncertainty",
            "",
            "| Metric | P10 | P50 | P90 | Probability of shortfall |",
            "|---|---:|---:|---:|---:|",
            f"| 5-year total cost | {uncertainty['cost_band']['p10']:.0f} | {uncertainty['cost_band']['p50']:.0f} | {uncertainty['cost_band']['p90']:.0f} | {uncertainty['probability_budget_exceeded']:.1%} budget |",
            f"| 5-year crew-hours | {uncertainty['hours_band']['p10']:.0f} | {uncertainty['hours_band']['p50']:.0f} | {uncertainty['hours_band']['p90']:.0f} | {uncertainty['probability_capacity_shortfall']:.1%} capacity |",
            "",
            "## Hindsight adaptive planning",
            "",
            f"{scenario_optimization['scenarios']} exact scenario re-solves. The fixed plan is the "
            "balanced MILP plan; the adaptive policy re-solves with each scenario's costs, hours, "
            "and capacity. This is a hindsight upper bound, not a deployable adaptive policy.",
            "",
            "| Policy | 5-year cost P10-P90 | Mean risk | Budget violation | Capacity violation |",
            "|---|---:|---:|---:|---:|",
            f"| Fixed balanced plan | {scenario_optimization['fixed_cost_band']['p10']:.0f}-"
            f"{scenario_optimization['fixed_cost_band']['p90']:.0f} | "
            f"{scenario_optimization['fixed_risk_band']['mean']:.4f} | "
            f"{scenario_optimization['fixed_budget_violation_probability']:.1%} | "
            f"{scenario_optimization['fixed_capacity_violation_probability']:.1%} |",
            f"| Scenario-optimized | {scenario_optimization['adaptive_cost_band']['p10']:.0f}-"
            f"{scenario_optimization['adaptive_cost_band']['p90']:.0f} | "
            f"{scenario_optimization['adaptive_risk_band']['mean']:.4f} | 0.0% | 0.0% |",
            "",
            f"Risk-equivalent objective: fixed {scenario_optimization['mean_fixed_objective']:.4f}, "
            f"adaptive {scenario_optimization['mean_adaptive_objective']:.4f}, mean regret "
            f"{scenario_optimization['mean_regret']:.4f}. Adaptive improved "
            f"{scenario_optimization['probability_adaptation_improves']:.1%} of scenarios under this "
            "scoring rule, which includes a normalized budget/capacity penalty for the fixed plan.",
            "",
            "## Rolling-horizon policy",
            "",
            f"{rolling_policy['episodes']} annual-factor episodes; {rolling_policy['lookahead_years']}-year "
            "lookahead. The policy observes current conditions, assumes persistence, re-solves, and "
            "commits only the current year. It is executable but not a global optimal policy.",
            "",
            "| Policy | 5-year cost P10-P90 | Mean risk | Budget violation | Capacity violation |",
            "|---|---:|---:|---:|---:|",
            f"| Fixed nominal | {rolling_policy['fixed_cost_band']['p10']:.0f}-"
            f"{rolling_policy['fixed_cost_band']['p90']:.0f} | "
            f"{rolling_policy['fixed_risk_band']['mean']:.4f} | "
            f"{rolling_policy['fixed_budget_violation_probability']:.1%} | "
            f"{rolling_policy['fixed_capacity_violation_probability']:.1%} |",
            f"| Rolling policy | {rolling_policy['rolling_cost_band']['p10']:.0f}-"
            f"{rolling_policy['rolling_cost_band']['p90']:.0f} | "
            f"{rolling_policy['rolling_risk_band']['mean']:.4f} | "
            f"{rolling_policy['rolling_budget_violation_probability']:.1%} | "
            f"{rolling_policy['rolling_capacity_violation_probability']:.1%} |",
            "",
            f"Risk-equivalent objective: fixed {rolling_policy['mean_fixed_objective']:.4f}, rolling "
            f"{rolling_policy['mean_rolling_objective']:.4f}, mean regret "
            f"{rolling_policy['mean_regret']:.4f}. Rolling improved "
            f"{rolling_policy['probability_rolling_improves']:.1%} of episodes.",
            "",
            "## Rolling year-one execution",
            "",
            f"Selected episode {policy_execution['selection']['episode_index']} by median rolling "
            f"five-year cost. First-year policy actions are converted to tactical/access/resource "
            f"and shift plans. This is an execution test, not a new optimization.",
            "",
            "| Metric | Policy year 1 | Fixed year 1 |",
            "|---|---:|---:|",
            f"| Segment treatments | {policy_execution['policy']['actions']} | "
            f"{policy_execution['fixed']['actions']} |",
            f"| Cost | {policy_execution['policy']['cost']:.0f} | "
            f"{policy_execution['fixed']['cost']:.0f} |",
            f"| Crew-hours | {policy_execution['policy']['hours']:.0f} | "
            f"{policy_execution['fixed']['hours']:.0f} |",
            f"| Tactical actions | {policy_execution['policy']['tactical_actions']} | n/a |",
            f"| Work orders | {policy_execution['policy']['work_orders']} | n/a |",
            f"| Shift assignments | {policy_execution['policy']['shift_assignments']} | n/a |",
            f"| Resource feasible | {policy_execution['policy']['resource_feasible']} | n/a |",
            f"| Shift feasible | {policy_execution['policy']['shift_feasible']} | n/a |",
            "",
            "## Caveats",
            "",
            "- OSM geometry and BC VRI cover are real public inputs; stand values are a prototype state, not a survey.",
            "- Costs, hours, productivity, access, and contractor capacities are explicit demo assumptions.",
            "- The MILP is exact for the declared linear risk state, not for a full nonlinear vegetation model.",
            "- The BAU row is a fixed five-year mowing cycle, not a like-for-like comparison of every strategy.",
            "- Scenario-optimized planning is a hindsight upper bound: it re-solves after seeing each sampled scenario and is not an executable forecast-update policy.",
            "- The rolling policy observes current conditions only and assumes they persist over its lookahead; it is a heuristic policy, not a stochastic dynamic program.",
            "- The year-one execution package selects the median-cost episode and uses prototype tactical, access, resource, and shift assumptions; it is not a commitment.",
            "- No asset-owner clearance standard, outage constraint, weather, or safety certification is claimed.",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> None:
    """Build the network, planning examples, and prototype report."""
    aoi, to_3005 = _aoi()
    lines, towers = _lines(aoi, to_3005)
    vri = _vri(aoi)
    segments = []
    for line in lines:
        segments.extend(_segment_line(line))
    _attach_vri(segments, vri)
    units = _assign_units(segments)
    periods = [
        PortfolioPeriod(
            period_id=f"Y{START_YEAR + i}",
            start_year=START_YEAR + i,
            budget=150000,
            capacity_by_method={"mowing": 6000, "mechanical": 6000, "manual": 6000},
        )
        for i in range(HORIZON)
    ]
    portfolio_segments, options = _options(segments, periods)
    scenarios = []
    for name, budget, risk_weight in (
        ("constrained", 30000, 1.0),
        ("balanced", 60000, 1.5),
        ("risk-first", 100000, 3.0),
    ):
        portfolio = _portfolio(portfolio_segments, periods, options, budget, risk_weight)
        scenarios.append(
            {
                "name": name,
                "annual_budget": budget,
                "portfolio": portfolio.model_dump(mode="json"),
                "five_year_cost": round(sum(row.cost for row in portfolio.period_summary), 1),
                "mean_service": round(
                    sum(row.service_attainment for row in portfolio.period_summary) / HORIZON, 3
                ),
                "mean_risk": round(sum(row.risk for row in portfolio.period_summary) / HORIZON, 3),
                "mean_annual_hours": round(
                    sum(sum(row.capacity_used.values()) for row in portfolio.period_summary)
                    / HORIZON,
                    1,
                ),
            }
        )
    stateful_scenarios = [
        _stateful_scenario(
            segments,
            name=name,
            annual_budget=budget,
            risk_weight=risk_weight,
        )
        for name, budget, risk_weight in (
            ("stateful-constrained", 30000, 1.0),
            ("stateful-balanced", 60000, 1.5),
            ("stateful-risk-first", 100000, 3.0),
        )
    ]
    budget_sweep = [
        _stateful_scenario(
            segments,
            name=f"budget-{budget}",
            annual_budget=budget,
            risk_weight=1.5,
        )
        for budget in (20000, 30000, 45000, 60000, 80000, 100000, 125000)
    ]
    pareto_frontier = _stateful_frontier(budget_sweep)
    capacity_sensitivity = [
        _stateful_scenario(
            segments,
            name=f"capacity-{capacity}",
            annual_budget=100000,
            risk_weight=1.5,
            capacity_hours=capacity,
        )
        for capacity in (300, 600, 1000, 1500, 2500)
    ]
    milp_scenarios = [
        _milp_plan(
            segments,
            name=f"milp-budget-{budget}",
            annual_budget=budget,
            capacity_hours=6000,
        )
        for budget in (20000, 30000, 45000, 60000, 80000, 100000)
    ]
    milp_balanced = next(item for item in milp_scenarios if item["name"] == "milp-budget-60000")
    milp_frontier = _stateful_frontier(milp_scenarios)
    milp_capacity = [
        _milp_plan(
            segments,
            name=f"milp-capacity-{capacity}",
            annual_budget=100000,
            capacity_hours=capacity,
        )
        for capacity in (300, 600, 1000, 1500, 2500)
    ]
    stateful_bau = _stateful_scenario(
        segments,
        name="stateful-bau-5-year-mowing",
        annual_budget=0,
        risk_weight=1.0,
        policy="bau-cycle",
    )
    stateful_cycles = _stateful_cycles(segments)
    bau = build_bau_plan(
        policy_id="bau-mowing-5",
        instance_id="bc-hydro-network-2026",
        segments=portfolio_segments,
        periods=periods,
        options=options,
        config=BauConfig(cycle_years=5, start_year=START_YEAR, action_id="mowing"),
        created_utc=CREATED,
    )
    portfolio_model = _portfolio(portfolio_segments, periods, options, 60000, 1.5)
    bau_comparison = compare_bau(portfolio_model, bau, created_utc=CREATED)
    tactical, access, resources, operations = _tactical(
        milp_balanced["actions"], segments, units, towers
    )
    profiles = _profiles()
    shifts = _shifts(tactical.actions, "bc-hydro-network-2026", profiles)
    workforce = _workforce_scenarios(tactical.actions, "bc-hydro-network-2026")
    scalability = _scalability(segments, "bc-hydro-network-2026")
    tactical_periods = [
        StatefulPeriod(
            year=START_YEAR + offset,
            budget=60000.0,
            capacity_hours=6000.0,
        )
        for offset in range(HORIZON)
    ]
    uncertainty = evaluate_uncertainty(
        instance_id="bc-hydro-network-2026",
        actions=tactical.actions,
        periods=tactical_periods,
        profiles=profiles,
        config=UncertaintyConfig(samples=500, seed=7),
        created_utc=CREATED,
    )
    scenario_methods = [
        StatefulMethod(
            method=method,
            cost_per_ha=params["cost_ha"],
            hours_per_ha=params["hours_ha"],
            risk_reduction=params["risk_reduction"],
        )
        for method, params in METHODS.items()
    ]
    fixed_plan = StatefulPlan.model_validate(milp_balanced["plan"])
    stateful_segments = [
        StatefulSegment(
            segment_id=segment["segment_id"],
            span_id=segment["unit_id"],
            length_m=segment["length_m"],
            area_ha=segment["length_m"] * segment["width_m"] / 10000,
            initial_risk=segment["base_risk"],
        )
        for segment in segments
    ]
    scenario_optimization = optimize_scenarios(
        instance_id="bc-hydro-network-2026",
        segments=stateful_segments,
        methods=scenario_methods,
        periods=tactical_periods,
        fixed=fixed_plan,
        config=StatefulConfig(risk_weight=1.0, max_seconds=30),
        scenarios=30,
        seed=7,
        created_utc=CREATED,
    )
    rolling_policy = simulate_rolling_policy(
        instance_id="bc-hydro-network-2026",
        segments=stateful_segments,
        methods=scenario_methods,
        periods=tactical_periods,
        fixed=fixed_plan,
        config=StatefulConfig(risk_weight=1.0, max_seconds=30),
        episodes=20,
        lookahead_years=2,
        seed=7,
        created_utc=CREATED,
    )
    policy_execution = _policy_execution(
        rolling_policy.model_dump(mode="json"),
        milp_balanced["actions"],
        segments,
        units,
        towers,
        profiles,
    )
    bid = _bid(tactical.actions, units, "bc-hydro-network-2026")
    network = {
        "schema_version": "brushline.network-demo.v1",
        "instance_id": "bc-hydro-network-2026",
        "aoi_wgs84": AOI_WGS84,
        "aoi_ha": 8737.0,
        "origin_m": [aoi.bounds[0], aoi.bounds[1]],
        "line_km": round(sum(line["length_m"] for line in lines) / 1000, 1),
        "lines": [
            {
                "line_id": line["line_id"],
                "osm_way_id": line["osm_way_id"],
                "name": line["name"],
                "voltage": line["voltage"],
                "operator": line["operator"],
                "length_m": round(line["length_m"], 1),
                "width_m": line["width_m"],
                "coordinates_3005": [
                    [round(x, 2), round(y, 2)] for x, y in line["geometry"].coords
                ],
            }
            for line in lines
        ],
        "segments": [
            {
                "segment_id": segment["segment_id"],
                "unit_id": segment["unit_id"],
                "line_id": segment["line_id"],
                "length_m": segment["length_m"],
                "width_m": segment["width_m"],
                "area_ha": round(segment["length_m"] * segment["width_m"] / 10000, 2),
                "shrub_height_m": segment["shrub_height_m"],
                "shrub_cover_pct": segment["shrub_cover_pct"],
                "tree_height_m": segment["tree_height_m"],
                "crown_closure_pct": segment["crown_closure_pct"],
                "species": segment["species"],
                "base_risk": segment["base_risk"],
                "base_service": segment["base_service"],
                "vri_polygon_id": segment["vri_polygon_id"],
                "coordinates_3005": [
                    [round(x, 2), round(y, 2)] for x, y in segment["geometry"].coords
                ],
            }
            for segment in segments
        ],
        "units": units,
        "towers": [
            {
                "tower_id": f"T{index:03d}",
                "x_3005": round(tower["geometry"].x, 2),
                "y_3005": round(tower["geometry"].y, 2),
            }
            for index, tower in enumerate(towers, start=1)
        ],
        "terrain": _terrain(aoi),
        "assumptions": {
            "method_costs": METHODS,
            "contractor_capacity": [profile[3] for profile in CONTRACTORS],
            "segment_m": SEGMENT_M,
            "segments_per_unit": SEGMENTS_PER_UNIT,
            "start_year": START_YEAR,
            "horizon": HORIZON,
            "caveat": "Prototype assumptions; not BC Hydro costs, standards, or capacity.",
        },
        "sources": [
            {"name": "OpenStreetMap power lines", "licence": "ODbL-1.0"},
            {"name": "BC Vegetation Resources Inventory", "licence": "BC Open Government Licence"},
            {"name": "Copernicus DEM GLO-30", "licence": "Copernicus DEM licence"},
        ],
    }
    strategic = {
        "schema_version": "brushline.network-strategic.v1",
        "instance_id": "bc-hydro-network-2026",
        "periods": [period.model_dump(mode="json") for period in periods],
        "portfolios": scenarios,
        "stateful_scenarios": stateful_scenarios,
        "milp_scenarios": milp_scenarios,
        "milp_frontier": milp_frontier,
        "milp_capacity": milp_capacity,
        "scalability": scalability,
        "stateful_bau": stateful_bau,
        "stateful_cycles": stateful_cycles,
        "pareto_frontier": pareto_frontier,
        "capacity_sensitivity": capacity_sensitivity,
        "bau": bau.model_dump(mode="json"),
        "bau_comparison": bau_comparison.model_dump(mode="json"),
        "cycle_tradeoffs": _cycle_tradeoff(segments),
        "caveats": [
            "Strategic options are period-static; growth carry-over is not yet a state transition.",
            "Budget, hours, and contractor capacity are demo assumptions.",
        ],
    }
    scene_payload = _scene(network, segments, vri, lines, towers, aoi)
    tactical_payload = tactical.model_dump(mode="json")
    operations_payload = operations.model_dump(mode="json")
    resources_payload = resources.model_dump(mode="json")
    access_payload = access.model_dump(mode="json")
    OUT.mkdir(parents=True, exist_ok=True)
    for name, payload in (
        ("network.json", network),
        ("strategic.json", strategic),
        ("scene.json", scene_payload),
        ("tactical.json", tactical_payload),
        ("resources.json", resources_payload),
        ("operations.json", operations_payload),
        ("shifts.json", shifts.model_dump(mode="json")),
        ("workforce.json", workforce),
        ("bid.json", bid),
        ("uncertainty.json", uncertainty.model_dump(mode="json")),
        ("scenario-optimization.json", scenario_optimization.model_dump(mode="json")),
        ("rolling-policy.json", rolling_policy.model_dump(mode="json")),
        ("policy-execution.json", policy_execution),
        ("access.json", access_payload),
    ):
        (OUT / name).write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    (OUT / "summary.md").write_text(
        _summary(
            network,
            strategic,
            tactical_payload,
            resources_payload,
            operations_payload,
            shifts.model_dump(mode="json"),
            workforce,
            scalability,
            bid,
            uncertainty.model_dump(mode="json"),
            scenario_optimization.model_dump(mode="json"),
            rolling_policy.model_dump(mode="json"),
            policy_execution,
        ),
        encoding="utf-8",
    )
    print(
        f"AOI={network['aoi_ha']} ha lines={network['line_km']} km features={len(lines)} "
        f"segments={len(segments)} units={len(units)} tactical_actions={len(tactical.actions)} "
        f"work_orders={len(operations.work_orders)} output={OUT}"
    )


if __name__ == "__main__":
    main()
