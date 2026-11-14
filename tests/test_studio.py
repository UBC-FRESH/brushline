"""Tests for the P10 artifact studio."""

from __future__ import annotations

from brushline.web.studio import create_app
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
    assert {item["id"] for item in instances} == {
        "synthetic-corridor",
        "ubc-public-block",
        "ubc-public-block-2",
        "ubc-public-block-3",
    }
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
    assert (
        "Walk this block"
        in (__import__("pathlib").Path("brushline/web/static/studio.html")).read_text()
    )
    assert "brushline3d" in js
    assert (
        "Pre / Post" in (__import__("pathlib").Path("brushline/web/static/studio.html")).read_text()
    )
