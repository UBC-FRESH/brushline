"""Artifact-reading planning studio service.

The service owns no model state. It reads the synthetic run artifacts and exposes a small API for
the static studio shell, including 2D map data, Pareto members, timeline events, skins, and a
selected-block scene with pre/post treatment variants.
"""

from __future__ import annotations

import json
import re
from collections.abc import Awaitable, Callable, Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from fastapi import FastAPI, HTTPException, Query, Request, Response
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from brushline.strategic.planning_brief import PlanningBriefError, build_planning_brief

STUDIO_SCHEMA_VERSION: Literal["brushline.studio.v1"] = "brushline.studio.v1"
STATIC_ROOT = Path(__file__).resolve().with_name("static")
DEFAULT_ARTIFACT_ROOT = Path(__file__).resolve().parents[2] / "examples" / "synthetic-corridor"
REAL_SCENES: dict[str, tuple[str, str, str]] = {
    "ubc-public-block": ("ubc-real", "ubc-real-block.json", "UBC public-data block"),
    "ubc-public-block-2": ("ubc-real-2", "ubc-real-2.json", "UBC public-data block 2"),
    "ubc-public-block-3": ("ubc-real-3", "ubc-real-3.json", "UBC public-data block 3"),
}
RESOURCE_ROOT = Path(__file__).resolve().parents[1] / "resources"
MKRK_SCENE_PATH = Path(__file__).resolve().parents[2] / "runtime/private/mkrf-powerline/scene.json"
BC_NETWORK_DIR = Path(__file__).resolve().parents[2] / "runtime/private/bc-network/model"
BC_SCALING_DIR = BC_NETWORK_DIR.parent / "scaling"
BC_NETWORK_SCENE_PATH = BC_NETWORK_DIR / "scene.json"


def _current_commit() -> str:
    """Return the checked-out commit, or a working-tree marker."""
    git_dir = Path(__file__).resolve().parents[2] / ".git"
    try:
        head = (git_dir / "HEAD").read_text(encoding="utf-8").strip()
        if head.startswith("ref: "):
            ref = git_dir / head[5:]
            return ref.read_text(encoding="utf-8").strip()[:7]
        return head[:7]
    except OSError:
        return "working tree"


def _network_artifacts() -> dict[str, Any]:
    """Load the network artifact set used by the studio and brief."""

    def path_for(key: str) -> Path:
        if key == "rolling-recourse-590":
            return BC_SCALING_DIR / "rolling-recourse-590.json"
        return BC_NETWORK_DIR / f"{key}.json"

    return {
        key: json.loads(path_for(key).read_text(encoding="utf-8"))
        for key in (
            "network",
            "strategic",
            "tactical",
            "resources",
            "operations",
            "shifts",
            "workforce",
            "bid",
            "uncertainty",
            "scenario-optimization",
            "rolling-policy",
            "policy-execution",
            "policy-execution-scan",
            "static-robust",
            "operational-stress",
            "operational-stress-scan",
            "operational-remedies",
            "risk-ranked-scope",
            "risk-trajectory",
            "rolling-recovery",
            "out-of-sample-recovery",
            "deferral-frontier",
            "frontier-validation",
            "robust-plan",
            "chance-plan",
            "chance-capacity-plan",
            "chance-100-plan",
            "two-stage-policy",
            "two-stage-multi",
            "rolling-recourse",
            "rolling-recourse-590",
            "access",
        )
    }


INSTANCES: tuple[dict[str, object], ...] = (
    {
        "id": "synthetic-corridor",
        "title": "Synthetic planning corridor",
        "kind": "planning",
        "description": (
            "Five synthetic segments with a plan, Pareto archive, and treatment variants."
        ),
    },
    {
        "id": "ubc-public-block",
        "title": "UBC public-data block",
        "kind": "observed",
        "description": "538 UBC tree records and a 2 m DEM/CHM terrain grid; observed state only.",
    },
    {
        "id": "ubc-public-block-2",
        "title": "UBC public-data block 2",
        "kind": "observed",
        "description": "254 UBC tree records in a second 200 m block; observed state only.",
    },
    {
        "id": "ubc-public-block-3",
        "title": "UBC public-data block 3",
        "kind": "observed",
        "description": "231 UBC tree records in a third 200 m block; observed state only.",
    },
)
BC_NETWORK_INSTANCE: dict[str, object] = {
    "id": "bc-hydro-network",
    "title": "BC Hydro network prototype",
    "kind": "network",
    "description": (
        "8,737 ha public-data network with four mapped power-line features and 2027-2031 plans."
    ),
}


MKRK_INSTANCE: dict[str, object] = {
    "id": "mkrf-powerline",
    "title": "MKRF southwest 500 kV power line",
    "kind": "observed",
    "description": "Real MKRF power-line crossing, LiDAR terrain/canopy, and schematic towers.",
}


def available_instances() -> list[dict[str, object]]:
    """Return curated instances plus the local private MKRF scene when present."""
    values = list(INSTANCES)
    if MKRK_SCENE_PATH.exists():
        values.append(MKRK_INSTANCE)
    if BC_NETWORK_SCENE_PATH.exists():
        values.append(BC_NETWORK_INSTANCE)
    return values


def _mkrf_scene() -> dict[str, Any]:
    return dict(json.loads(MKRK_SCENE_PATH.read_text(encoding="utf-8")))


def _mkrf_block(scene: dict[str, Any]) -> dict[str, Any]:
    trees = scene.get("trees", [])
    heights = [float(tree.get("height_m") or 0) for tree in trees]
    canopy = [
        float(value) for row in scene.get("terrain", {}).get("canopy_height", []) for value in row
    ]
    cover = 100.0 * sum(value > 3.0 for value in canopy) / len(canopy) if canopy else None
    power = scene.get("powerline", {})
    lines = [line.get("points", []) for line in power.get("lines", [])]
    return {
        "block_id": "mkrf-sw-powerline",
        "block_kind": "powerline_block",
        "segment_ids": [],
        "height_m": round(max(heights), 1) if heights else None,
        "cover_pct": round(cover, 1) if cover is not None else None,
        "actions": [],
        "variant_available": False,
        "label": "MKRF southwest 500 kV power line",
        "tree_count": len(trees),
        "understory_patch_count": scene.get("understory", {}).get("patch_count", 0),
        "understory_corridor_count": scene.get("understory", {}).get("corridor_patch_count", 0),
        "understory_mean_cover_pct": scene.get("understory", {}).get("mean_cover_pct"),
        "treatment_schedule": scene.get("treatment_schedule"),
        "voltage_kv": power.get("voltage_kv"),
        "line_names": [line.get("name") for line in power.get("lines", [])],
        "geometry": {"lines": lines, "width_m": 70.0},
        "towers": power.get("towers", []),
    }


SKINS: tuple[dict[str, Any], ...] = (
    {"id": "model-builder", "workspaces": ["build", "data"], "read_only": False},
    {"id": "owner-strategic", "workspaces": ["map", "plan", "results", "data"], "read_only": False},
    {
        "id": "tactical-planner",
        "workspaces": ["map", "plan", "results", "data"],
        "read_only": False,
    },
    {"id": "operations-planner", "workspaces": ["map", "plan", "results"], "read_only": False},
    {"id": "contractor-bid", "workspaces": ["map", "plan", "results", "data"], "read_only": False},
    {"id": "monitoring", "workspaces": ["map", "plan", "results", "data"], "read_only": False},
    {"id": "reviewer", "workspaces": ["map", "plan", "results", "data"], "read_only": True},
)


class StudioError(ValueError):
    """Raised when a studio artifact is missing or invalid."""


def _read_json(root: Path, relative: str) -> Any:  # noqa: ANN401
    path = (root / relative).resolve()
    if not path.is_relative_to(root.resolve()):
        raise StudioError("artifact path escapes the root")
    if not path.exists():
        raise StudioError(f"missing artifact {relative}")
    return json.loads(path.read_text(encoding="utf-8"))


def _read_jsonl(root: Path, relative: str) -> list[dict[str, Any]]:
    path = root / relative
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def _plan_for(root: Path, plan_id: str) -> dict[str, Any]:
    run = _read_json(root, "run.json")
    artifact = next((item for item in run.get("artifacts", []) if item.get("name") == "plan"), None)
    if artifact is None:
        raise StudioError("run has no plan artifact")
    plan = _read_json(root, artifact["path"])
    if plan_id not in {plan.get("header", {}).get("plan_id"), "current"}:
        candidate = root / "plans" / f"{plan_id}.json"
        if not candidate.exists():
            raise StudioError(f"unknown plan {plan_id}")
        plan = json.loads(candidate.read_text(encoding="utf-8"))
    return dict(plan)


def _blocks(root: Path, plan: dict[str, Any]) -> list[dict[str, Any]]:
    state = _read_json(root, "state.json")
    states = {item["segment_id"]: item for item in state.get("states", [])}
    actions: dict[str, list[dict[str, Any]]] = {}
    for action in plan.get("actions", []):
        actions.setdefault(action["segment_id"], []).append(action)
    blocks = []
    for segment_id in sorted(states):
        item = states[segment_id]
        blocks.append(
            {
                "block_id": segment_id,
                "block_kind": "segment",
                "segment_ids": [segment_id],
                "height_m": item.get("height_m"),
                "cover_pct": item.get("cover_pct"),
                "actions": actions.get(segment_id, []),
                "variant_available": bool(actions.get(segment_id)),
            }
        )
    return blocks


def _segment_geometry(root: Path, block_id: str) -> dict[str, Any]:
    corridor = _read_json(root, "corridor.json")
    segment = next(
        (item for item in corridor.get("segments", []) if item.get("segment_id") == block_id),
        None,
    )
    if segment is None:
        return {"points": [], "width_m": 10.0}
    points = [
        [float(x), float(y)]
        for x, y in re.findall(
            r"(-?\d+(?:\.\d+)?)\s+(-?\d+(?:\.\d+)?)", segment.get("geometry_wkt", "")
        )
    ]
    return {"points": points, "width_m": 10.0}


def _scene(root: Path, block_id: str, variant: str) -> dict[str, Any]:
    if block_id == "bc-network":
        if variant != "pre":
            raise StudioError("the network prototype has no post-treatment scene")
        return dict(json.loads(BC_NETWORK_SCENE_PATH.read_text(encoding="utf-8")))
    if block_id == "mkrf-sw-powerline":
        if variant != "pre":
            raise StudioError("the observed MKRF block has no modelled post-treatment state")
        if not MKRK_SCENE_PATH.exists():
            raise StudioError("MKRF power-line scene is missing")
        return _mkrf_scene()
    real_entry = next(
        (
            (instance, filename)
            for instance, (block, filename, _title) in REAL_SCENES.items()
            if block == block_id
        ),
        None,
    )
    if real_entry is not None:
        if variant != "pre":
            raise StudioError("the observed UBC block has no modelled post-treatment state")
        path = RESOURCE_ROOT / real_entry[1]
        if not path.exists():
            raise StudioError("real block scene is missing")
        return dict(json.loads(path.read_text(encoding="utf-8")))
    plan = _plan_for(root, "current")
    blocks = _blocks(root, plan)
    block = next((item for item in blocks if item["block_id"] == block_id), None)
    if block is None:
        raise StudioError(f"unknown block {block_id}")
    state = _read_json(root, "state.json")
    current = next(item for item in state["states"] if item["segment_id"] == block_id)
    action = block["actions"][0] if block["actions"] else None
    if variant == "post" and action is None:
        raise StudioError("post-treatment state is not available")
    factor = 0.5 if variant == "post" and action else 1.0
    return {
        "schema_version": "brushline.scene.v1",
        "instance_id": plan.get("header", {}).get("scenario_id", "synthetic"),
        "block": {
            "block_id": block_id,
            "block_kind": "segment",
            "segment_ids": [block_id],
            "variant": variant,
            "position_status": "unknown",
        },
        "plan": {
            "plan_id": plan.get("header", {}).get("plan_id"),
            "action_id": action.get("action_id") if action else None,
            "method": action.get("method") if action else None,
            "year": action.get("year") if action else None,
        },
        "vegetation": {
            "height_m": round(float(current.get("height_m") or 0) * factor, 3),
            "cover_pct": round(
                float(current.get("cover_pct") or 0) * (0.6 if factor < 1 else 1), 2
            ),
            "functional_group": current.get("functional_group"),
            "position_status": "unknown",
        },
        "geometry": _segment_geometry(root, block_id),
        "caveats": [
            "Context view only; positions are not invented.",
            "Model state, not a stem map.",
        ],
    }


def create_app(artifact_root: str | Path | None = None) -> FastAPI:
    """Create the studio FastAPI app.

    Parameters
    ----------
    artifact_root : str or Path, optional
        Run artifact directory. Defaults to the synthetic corridor.

    Returns
    -------
    FastAPI
        Artifact-only studio service.
    """
    root = Path(artifact_root or DEFAULT_ARTIFACT_ROOT).resolve()
    app = FastAPI(title="Brushline studio", version="0.1.4")

    @app.middleware("http")
    async def no_cache(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        response = await call_next(request)
        if request.url.path == "/" or request.url.path.startswith("/static/"):
            response.headers["Cache-Control"] = "no-store"
        return response

    def root_for(instance_id: str) -> Path:
        if instance_id == "synthetic-corridor":
            return root
        if instance_id in REAL_SCENES or instance_id in {"mkrf-powerline", "bc-hydro-network"}:
            return root
        raise HTTPException(status_code=404, detail=f"unknown instance {instance_id}")

    def safe_json(path_root: Path, relative: str) -> Any:  # noqa: ANN401
        try:
            return _read_json(path_root, relative)
        except (StudioError, json.JSONDecodeError) as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get("/")
    def home() -> FileResponse:
        return FileResponse(STATIC_ROOT / "studio.html")

    @app.get("/studio")
    def studio() -> FileResponse:
        return FileResponse(STATIC_ROOT / "studio.html")

    @app.get("/api/studio/instances")
    def instances() -> dict[str, Any]:
        return {"instances": available_instances()}

    @app.get("/api/studio/network")
    def network(instance_id: str = Query(default="bc-hydro-network")) -> dict[str, Any]:
        if instance_id != "bc-hydro-network":
            raise HTTPException(status_code=404, detail="not a network instance")
        return _network_artifacts()

    @app.get("/api/studio/network/brief")
    def network_brief(
        instance_id: str = Query(default="bc-hydro-network"),
        output_format: Literal["html", "markdown"] = Query(default="html", alias="format"),
        download: bool = Query(default=False),
    ) -> Response:
        if instance_id != "bc-hydro-network":
            raise HTTPException(status_code=404, detail="not a network instance")
        artifacts = _network_artifacts()
        try:
            brief = build_planning_brief(
                network=artifacts["network"],
                strategic=artifacts["strategic"],
                tactical=artifacts["tactical"],
                resources=artifacts["resources"],
                operations=artifacts["operations"],
                shifts=artifacts["shifts"],
                workforce=artifacts["workforce"],
                bid=artifacts["bid"],
                uncertainty=artifacts["uncertainty"],
                scenario_optimization=artifacts["scenario-optimization"],
                access=artifacts["access"],
                rolling_policy=artifacts["rolling-policy"],
                policy_execution=artifacts["policy-execution"],
                policy_execution_scan=artifacts["policy-execution-scan"],
                static_plan=artifacts["static-robust"],
                operational_stress=artifacts["operational-stress"],
                operational_stress_scan=artifacts["operational-stress-scan"],
                operational_remedies=artifacts["operational-remedies"],
                risk_ranked_scope=artifacts["risk-ranked-scope"],
                risk_trajectory=artifacts["risk-trajectory"],
                rolling_recovery=artifacts["rolling-recovery"],
                out_of_sample_recovery=artifacts["out-of-sample-recovery"],
                deferral_frontier=artifacts["deferral-frontier"],
                frontier_validation=artifacts["frontier-validation"],
                robust_plan=artifacts["robust-plan"],
                chance_plan=artifacts["chance-plan"],
                chance_capacity_plan=artifacts["chance-capacity-plan"],
                chance_100_plan=artifacts["chance-100-plan"],
                two_stage_policy=artifacts["two-stage-policy"],
                two_stage_multi=artifacts["two-stage-multi"],
                rolling_recourse=artifacts["rolling-recourse"],
                rolling_recourse_590=artifacts["rolling-recourse-590"],
                generated_utc=datetime.now(UTC),
                command="python tools/build_bc_network_demo.py",
                commit=_current_commit(),
            )
        except PlanningBriefError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc
        content = brief.markdown if output_format == "markdown" else brief.html
        filename = brief.filename_markdown if output_format == "markdown" else brief.filename_html
        media_type = (
            "text/markdown; charset=utf-8"
            if output_format == "markdown"
            else "text/html; charset=utf-8"
        )
        disposition = "attachment" if download or output_format == "markdown" else "inline"
        return Response(
            content=content,
            media_type=media_type,
            headers={
                "Content-Disposition": f'{disposition}; filename="{filename}"',
                "Cache-Control": "no-store",
            },
        )

    @app.get("/api/studio/summary")
    def summary(instance_id: str = Query(default="synthetic-corridor")) -> dict[str, Any]:
        root_for(instance_id)
        if instance_id == "bc-hydro-network":
            network = json.loads((BC_NETWORK_DIR / "network.json").read_text(encoding="utf-8"))
            strategic = json.loads((BC_NETWORK_DIR / "strategic.json").read_text(encoding="utf-8"))
            return {
                "schema_version": STUDIO_SCHEMA_VERSION,
                "instance_id": instance_id,
                "title": "BC Hydro network prototype",
                "kind": "network",
                "tree_count": 0,
                "blocks": 1,
                "status": "prototype",
                "aoi_ha": network.get("aoi_ha"),
                "line_km": network.get("line_km"),
                "feature_count": len(network.get("lines", [])),
                "unit_count": len(network.get("units", [])),
                "segment_count": len(network.get("segments", [])),
                "scenario_count": len(
                    strategic.get("milp_scenarios") or strategic.get("portfolios", [])
                ),
                "sources": network.get("sources", []),
                "caveats": [
                    "Public-data network prototype; not an asset-owner plan.",
                    "Costs, hours, access, and contractor capacity are demo assumptions.",
                ],
            }
        if instance_id == "mkrf-powerline":
            real = _mkrf_scene()
            power = real.get("powerline", {})
            return {
                "schema_version": STUDIO_SCHEMA_VERSION,
                "instance_id": instance_id,
                "title": "MKRF southwest 500 kV power line",
                "kind": "observed",
                "tree_count": len(real.get("trees", [])),
                "understory_patch_count": real.get("understory", {}).get("patch_count", 0),
                "understory_corridor_count": real.get("understory", {}).get(
                    "corridor_patch_count", 0
                ),
                "blocks": 1,
                "status": "observed",
                "crs": real.get("crs"),
                "origin_m": real.get("origin_m"),
                "powerline_name": power.get("name"),
                "voltage_kv": power.get("voltage_kv"),
                "line_count": len(power.get("lines", [])),
                "tower_count": len(power.get("towers", [])),
                "sources": real.get("sources", []),
                "caveats": real.get("caveats", []),
            }
        if instance_id in REAL_SCENES:
            _block, filename, title = REAL_SCENES[instance_id]
            real = json.loads((RESOURCE_ROOT / filename).read_text(encoding="utf-8"))
            return {
                "schema_version": STUDIO_SCHEMA_VERSION,
                "instance_id": instance_id,
                "title": title,
                "kind": "observed",
                "tree_count": len(real.get("trees", [])),
                "blocks": 1,
                "status": "observed",
            }
        run = safe_json(root, "run.json")
        plan = safe_json(root, "plan.json")
        return {
            "schema_version": STUDIO_SCHEMA_VERSION,
            "instance_id": instance_id,
            "title": "Synthetic planning corridor",
            "kind": "planning",
            "run_id": run["run_id"],
            "plan_id": plan["header"]["plan_id"],
            "currency": plan["header"]["currency"],
            "actions": len(plan["actions"]),
            "total_cost": round(
                sum(sum(line["amount"] for line in a["cost_lines"]) for a in plan["actions"]), 2
            ),
            "status": run.get("status"),
            "skins": list(SKINS),
        }

    @app.get("/api/studio/plan/{plan_id}")
    def plan(
        plan_id: str, instance_id: str = Query(default="synthetic-corridor")
    ) -> dict[str, Any]:
        root_for(instance_id)
        if instance_id in REAL_SCENES or instance_id in {"mkrf-powerline", "bc-hydro-network"}:
            raise HTTPException(status_code=404, detail="observed block has no plan")
        try:
            return _plan_for(root, plan_id)
        except StudioError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get("/api/studio/pareto")
    def pareto(instance_id: str = Query(default="synthetic-corridor")) -> dict[str, Any]:
        root_for(instance_id)
        if instance_id in REAL_SCENES or instance_id in {"mkrf-powerline", "bc-hydro-network"}:
            return {"members": []}
        return dict(safe_json(root, "pareto.json"))

    @app.get("/api/studio/timeline")
    def timeline(instance_id: str = Query(default="synthetic-corridor")) -> dict[str, Any]:
        root_for(instance_id)
        if instance_id in REAL_SCENES or instance_id in {"mkrf-powerline", "bc-hydro-network"}:
            return {"events": []}
        return {"events": _read_jsonl(root, "operations_timeline.jsonl")}

    @app.get("/api/studio/blocks")
    def blocks(instance_id: str = Query(default="synthetic-corridor")) -> dict[str, Any]:
        root_for(instance_id)
        if instance_id == "bc-hydro-network":
            network = json.loads((BC_NETWORK_DIR / "network.json").read_text(encoding="utf-8"))
            scene = json.loads(BC_NETWORK_SCENE_PATH.read_text(encoding="utf-8"))
            origin_x, origin_y = network.get("origin_m", [0, 0])
            towers = [
                {
                    "x_m": round(tower["x_3005"] - origin_x, 1),
                    "y_m": round(tower["y_3005"] - origin_y, 1),
                }
                for tower in network.get("towers", [])
            ]
            return {
                "blocks": [
                    {
                        "block_id": "bc-network",
                        "block_kind": "network_block",
                        "segment_ids": [],
                        "height_m": None,
                        "cover_pct": None,
                        "actions": [],
                        "variant_available": False,
                        "label": "BC Hydro public-data network prototype",
                        "tree_count": len(scene.get("trees", [])),
                        "line_names": [line["name"] for line in network.get("lines", [])],
                        "voltage_kv": None,
                        "geometry": {
                            "lines": [
                                line["coordinates_3005"] for line in network.get("lines", [])
                            ],
                            "width_m": 70.0,
                        },
                        "towers": towers,
                        "treatment_schedule": None,
                    }
                ]
            }
        if instance_id == "mkrf-powerline":
            return {"blocks": [_mkrf_block(_mkrf_scene())]}
        if instance_id in REAL_SCENES:
            block_id, filename, title = REAL_SCENES[instance_id]
            real = json.loads((RESOURCE_ROOT / filename).read_text(encoding="utf-8"))
            return {
                "blocks": [
                    {
                        "block_id": block_id,
                        "block_kind": "real_block",
                        "segment_ids": [],
                        "height_m": None,
                        "cover_pct": None,
                        "actions": [],
                        "variant_available": False,
                        "label": title,
                        "tree_count": len(real.get("trees", [])),
                    }
                ]
            }
        plan = safe_json(root, "plan.json")
        return {"blocks": _blocks(root, plan)}

    @app.get("/api/studio/scene/{block_id}")
    def scene(
        block_id: str,
        variant: str = Query(default="pre", pattern="^(pre|post)$"),
        instance_id: str = Query(default="synthetic-corridor"),
    ) -> dict[str, Any]:
        root_for(instance_id)
        try:
            return _scene(root, block_id, variant)
        except StudioError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get("/api/studio/search/stream")
    def search_stream(instance_id: str = Query(default="synthetic-corridor")) -> StreamingResponse:
        root_for(instance_id)

        def events() -> Iterator[str]:
            for sequence, event_type in enumerate(("start", "incumbent", "finish")):
                data = json.dumps(
                    {"sequence": sequence, "event_type": event_type, "run_id": "run-2026"}
                )
                yield f"id: {sequence}\nevent: {event_type}\ndata: {data}\n\n"

        return StreamingResponse(events(), media_type="text/event-stream")

    @app.get("/api/studio/skins")
    def skins() -> dict[str, Any]:
        return {"skins": list(SKINS)}

    app.mount("/static", StaticFiles(directory=STATIC_ROOT), name="static")
    return app


app = create_app()
