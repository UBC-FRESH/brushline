"""Tests for the P10 artifact studio."""

from __future__ import annotations

from brushline.web.studio import BC_NETWORK_SCENE_PATH, MKRK_SCENE_PATH, create_app
from fastapi.testclient import TestClient


def test_studio_endpoints_and_pov_variants() -> None:
    client = TestClient(create_app())
    assert client.get("/").status_code in {200, 307}
    page = client.get("/studio")
    assert page.status_code == 200
    assert "Walk this block" in page.text
    summary = client.get("/api/studio/summary").json()
    assert summary["run_id"] == "run-2026"
    assert summary["plan_id"]
    blocks = client.get("/api/studio/blocks").json()["blocks"]
    assert blocks
    block_id = blocks[0]["block_id"]
    pre = client.get(f"/api/studio/scene/{block_id}?variant=pre")
    assert pre.status_code == 200
    assert pre.json()["block"]["variant"] == "pre"
    assert pre.json()["block"]["position_status"] == "unknown"
    post = client.get(f"/api/studio/scene/{block_id}?variant=post")
    assert post.status_code in {200, 404}
    assert client.get("/api/studio/pareto").json()["members"]
    assert client.get("/api/studio/timeline").json()["events"]
    assert len(client.get("/api/studio/skins").json()["skins"]) == 7
    reviewer = next(
        item for item in client.get("/api/studio/skins").json()["skins"] if item["id"] == "reviewer"
    )
    assert reviewer["read_only"]
    assert client.get(f"/api/studio/scene/{block_id}?variant=bad").status_code == 422
    assert client.get("/api/studio/scene/missing?variant=pre").status_code == 404
    real = client.get("/api/studio/scene/ubc-real?variant=pre")
    assert real.status_code == 200
    assert real.json()["schema_version"] == "brushline.real-scene.v1"
    assert real.json()["trees"]
    assert client.get("/api/studio/scene/ubc-real?variant=post").status_code == 404
    instances = client.get("/api/studio/instances").json()["instances"]
    assert {item["id"] for item in instances} >= {
        "synthetic-corridor",
        "ubc-public-block",
        "ubc-public-block-2",
        "ubc-public-block-3",
    }
    if MKRK_SCENE_PATH.exists():
        assert "mkrf-powerline" in {item["id"] for item in instances}
        mk = client.get("/api/studio/blocks?instance_id=mkrf-powerline").json()["blocks"]
        assert mk[0]["block_kind"] == "powerline_block"
        assert mk[0]["geometry"]["lines"]
        assert mk[0]["understory_patch_count"] > 0
        assert mk[0]["understory_corridor_count"] > 0
        schedule = mk[0]["treatment_schedule"]
        assert schedule["status"] == "modelled"
        assert len(schedule["units"]) > 0
        assert schedule["units"][0]["planned"]["year"] >= 2027
        scene_mk = client.get("/api/studio/scene/mkrf-sw-powerline?variant=pre")
        assert scene_mk.status_code == 200
        assert scene_mk.json()["powerline"]["voltage_kv"] == 500
        assert scene_mk.json()["understory"]["patch_count"] > 0
        assert scene_mk.json()["treatment_schedule"]["time_axis"][0] == 2026
    if BC_NETWORK_SCENE_PATH.exists():
        assert "bc-hydro-network" in {item["id"] for item in instances}
        network_summary = client.get("/api/studio/summary?instance_id=bc-hydro-network").json()
        assert network_summary["kind"] == "network"
        assert network_summary["aoi_ha"] > 5000
        network_blocks = client.get("/api/studio/blocks?instance_id=bc-hydro-network").json()[
            "blocks"
        ]
        assert network_blocks[0]["block_kind"] == "network_block"
        assert network_blocks[0]["geometry"]["lines"]
        network_plan = client.get("/api/studio/network?instance_id=bc-hydro-network").json()
        assert network_plan["strategic"]["portfolios"]
        assert network_plan["tactical"]["actions"]
        assert network_plan["operations"]["work_orders"]
        assert network_plan["shifts"]["assignments"]
        assert network_plan["workforce"]
        assert network_plan["bid"]["comparison"]["within_fair_range"]
        assert network_plan["uncertainty"]["cost_band"]["p50"] > 0
        assert network_plan["scenario-optimization"]["scenarios"] >= 1
        assert network_plan["rolling-policy"]["episodes"] >= 1
        assert network_plan["policy-execution"]["policy"]["shift_feasible"]
        assert network_plan["policy-execution-scan"]["execution_feasibility_rate"] == 1.0
        assert network_plan["static-robust"]["recommended"]
        assert network_plan["operational-stress"]["scenarios"] >= 1
        assert network_plan["operational-stress-scan"]["episodes"] >= 1
        assert network_plan["operational-remedies"]["cases"]
        assert network_plan["risk-ranked-scope"]["cases"]
        assert network_plan["risk-trajectory"]["years"]
        assert network_plan["rolling-recovery"]["final_recovery"] > 0
        assert network_plan["out-of-sample-recovery"]["paths_total"] >= 1
        assert network_plan["deferral-frontier"]["cases"]
        assert network_plan["frontier-validation"]["cases"]
        assert network_plan["robust-plan"]["test"]["plans"]
        assert network_plan["chance-plan"]["test"]["plans"]
        assert network_plan["chance-capacity-plan"]["test"]["plans"]
        assert network_plan["chance-100-plan"]["test"]["plans"]
        assert network_plan["two-stage-policy"]["recourse_budget_violation_probability"] == 0
        brief = client.get("/api/studio/network/brief?instance_id=bc-hydro-network")
        assert brief.status_code == 200
        assert brief.headers["content-type"].startswith("text/html")
        assert brief.headers["content-disposition"].startswith("inline; filename=")
        assert "BC Hydro public-data network planning brief" in brief.text
        brief_download = client.get(
            "/api/studio/network/brief?instance_id=bc-hydro-network&download=1"
        )
        assert brief_download.headers["content-disposition"].startswith("attachment; filename=")
        assert "<script" not in brief.text
        brief_md = client.get(
            "/api/studio/network/brief?instance_id=bc-hydro-network&format=markdown"
        )
        assert brief_md.status_code == 200
        assert brief_md.headers["content-type"].startswith("text/markdown")
        assert "# BC Hydro public-data network planning brief" in brief_md.text
        assert "## Rolling-horizon policy" in brief_md.text
        assert "## Rolling year-one execution" in brief_md.text
        assert "## Policy execution scan" in brief_md.text
        assert "## Static budget-headroom plans" in brief_md.text
        assert "## Weather and outage stress" in brief_md.text
        assert "## All-episode weather and outage scan" in brief_md.text
        assert "## Weather/outage remedies" in brief_md.text
        assert "## Risk-ranked scope deferral" in brief_md.text
        assert "## Multi-year risk trajectory" in brief_md.text
        assert "## Rolling recovery after deferral" in brief_md.text
        assert "## Out-of-sample recovery" in brief_md.text
        assert "## Deferral-fraction frontier" in brief_md.text
        assert "## Frontier out-of-sample validation" in brief_md.text
        assert "## Scenario-robust static plan" in brief_md.text
        assert "## Sampled budget chance constraint" in brief_md.text
        assert "## Chance-constrained capacity" in brief_md.text
        assert "## 100-path chance constraint" in brief_md.text
        assert "## Two-stage operational recourse" in brief_md.text
        assert (
            client.get("/api/studio/network/brief?instance_id=synthetic-corridor").status_code
            == 404
        )
        assert (
            client.get(
                "/api/studio/network/brief?instance_id=bc-hydro-network&format=pdf"
            ).status_code
            == 422
        )
        network_scene = client.get(
            "/api/studio/scene/bc-network?variant=pre&instance_id=bc-hydro-network"
        )
        assert network_scene.status_code == 200
        assert network_scene.json()["powerline"]["lines"]
        assert network_scene.json()["terrain"]["width"] > 0
    for instance_id, block_id in (
        ("ubc-public-block", "ubc-real"),
        ("ubc-public-block-2", "ubc-real-2"),
        ("ubc-public-block-3", "ubc-real-3"),
    ):
        blocks = client.get(f"/api/studio/blocks?instance_id={instance_id}").json()["blocks"]
        assert blocks[0]["block_id"] == block_id
        scene = client.get(f"/api/studio/scene/{block_id}?variant=pre&instance_id={instance_id}")
        assert scene.status_code == 200
    stream = client.get("/api/studio/search/stream")
    assert stream.status_code == 200
    assert "event: start" in stream.text
    assert "event: finish" in stream.text
    assert client.get("/static/studio.js").status_code == 200


def test_studio_static_contains_pre_post_and_skin_hooks() -> None:
    js = (__import__("pathlib").Path("brushline/web/static/studio.js")).read_text()
    assert "toggleVariant" in js
    assert "variant" in js
    assert "network/brief" in js
    assert "Rolling-horizon policy" in js
    assert "Rolling year-one execution" in js
    assert (
        "Walk this block"
        in (__import__("pathlib").Path("brushline/web/static/studio.html")).read_text()
    )
    assert "brushline3d" in js
    assert "Planning brief" in (
        __import__("pathlib").Path("brushline/web/static/studio.html").read_text()
    )
    assert (
        "Pre / Post" in (__import__("pathlib").Path("brushline/web/static/studio.html")).read_text()
    )
