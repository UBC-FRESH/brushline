"""Artifact-reading planning studio service.

The service owns no model state. It reads the synthetic run artifacts and exposes a small API for
the static studio shell, including 2D map data, Pareto members, timeline events, skins, and a
selected-block scene with pre/post treatment variants.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any, Literal

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

STUDIO_SCHEMA_VERSION: Literal["brushline.studio.v1"] = "brushline.studio.v1"
STATIC_ROOT = Path(__file__).resolve().with_name("static")
DEFAULT_ARTIFACT_ROOT = Path(__file__).resolve().parents[2] / "examples" / "synthetic-corridor"
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


def _scene(root: Path, block_id: str, variant: str) -> dict[str, Any]:
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
    app = FastAPI(title="Brushline studio", version="0.1.0")

    def safe_json(relative: str) -> Any:  # noqa: ANN401
        try:
            return _read_json(root, relative)
        except (StudioError, json.JSONDecodeError) as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get("/")
    def home() -> RedirectResponse:
        return RedirectResponse("/studio")

    @app.get("/studio")
    def studio() -> FileResponse:
        return FileResponse(STATIC_ROOT / "studio.html")

    @app.get("/api/studio/summary")
    def summary() -> dict[str, Any]:
        run = safe_json("run.json")
        plan = safe_json("plan.json")
        return {
            "schema_version": STUDIO_SCHEMA_VERSION,
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
    def plan(plan_id: str) -> dict[str, Any]:
        try:
            return _plan_for(root, plan_id)
        except StudioError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get("/api/studio/pareto")
    def pareto() -> dict[str, Any]:
        return dict(safe_json("pareto.json"))

    @app.get("/api/studio/timeline")
    def timeline() -> dict[str, Any]:
        return {"events": _read_jsonl(root, "operations_timeline.jsonl")}

    @app.get("/api/studio/blocks")
    def blocks() -> dict[str, Any]:
        plan = safe_json("plan.json")
        return {"blocks": _blocks(root, plan)}

    @app.get("/api/studio/scene/{block_id}")
    def scene(
        block_id: str,
        variant: str = Query(default="pre", pattern="^(pre|post)$"),
    ) -> dict[str, Any]:
        try:
            return _scene(root, block_id, variant)
        except StudioError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get("/api/studio/search/stream")
    def search_stream() -> StreamingResponse:
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
