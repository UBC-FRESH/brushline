"""Contract and browser-surface tests for the model-builder prototype."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import cast

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")

from brushline.integrations.catalogue import DataCatalogue
from brushline.web import model_builder
from brushline.web.model_builder import (
    DEFAULT_SOURCE_IDS,
    ModelBuilderStore,
    create_app,
)
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "examples" / "synthetic-corridor"
CATALOGUE_PATH = ROOT / "notes" / "reference" / "data-catalogue.v1.json"


def _client(tmp_path: Path) -> tuple[TestClient, ModelBuilderStore]:
    catalogue = DataCatalogue.model_validate_json(CATALOGUE_PATH.read_text(encoding="utf-8"))
    store = ModelBuilderStore(
        catalogue=catalogue,
        fixture_root=FIXTURE,
        runtime_root=tmp_path / "runtime",
    )
    return TestClient(create_app(store)), store


def _create(client: TestClient, **updates: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "aoi_id": "synthetic-corridor",
        "source_ids": list(DEFAULT_SOURCE_IDS),
        "dry_run": True,
    }
    payload.update(updates)
    response = client.post("/api/model-builder/sessions", json=payload)
    assert response.status_code == 200, response.text
    return cast("dict[str, object]", response.json())


def _dict(value: object) -> dict[str, object]:
    assert isinstance(value, dict)
    return cast("dict[str, object]", value)


def _list(value: object) -> list[object]:
    assert isinstance(value, list)
    return cast("list[object]", value)


def _session_id(session: dict[str, object]) -> str:
    return str(session["session_id"])


def test_static_shell_and_aoi_options(tmp_path: Path) -> None:
    """The browser shell, static assets, and the synthetic AOI are served."""
    client, _store = _client(tmp_path)
    index = client.get("/")
    assert index.status_code == 200
    assert "Brushline model builder" in index.text
    assert "model-builder.js" in index.text
    assert client.get("/static/model-builder.js").status_code == 200
    assert client.get("/static/model-builder.css").status_code == 200
    options = client.get("/api/model-builder/aois")
    assert options.status_code == 200
    payload = options.json()
    assert payload["aois"][0]["id"] == "synthetic-corridor"
    assert len(payload["aois"][0]["bbox"]) == 4
    assert "transmission" in payload["asset_types"]
    assert "clearance" in payload["standards"]


def test_catalogue_view_hides_authentication_references(tmp_path: Path) -> None:
    """The browser sees source and safe connector metadata only."""
    client, _store = _client(tmp_path)
    response = client.get("/api/model-builder/catalogue")
    assert response.status_code == 200
    text = response.text
    assert "lidarbc" in text
    assert "asset-registry" in text
    assert "authentication_reference" not in text
    assert "BRUSHLINE_ASSET_REGISTRY_TOKEN" not in text


def test_create_session_shows_plan_and_coverage(tmp_path: Path) -> None:
    """A session has an availability list, a path-free plan, and a gap report."""
    client, _store = _client(tmp_path)
    session = _create(
        client,
        source_ids=["lidarbc", "vri"],
        connector_ids=["asset-registry"],
    )
    assert session["status"] == "planned"
    plan = _dict(session["plan"])
    assert plan["mode"] == "plan_only"
    assert len(_list(plan["items"])) == 3
    availability = _list(session["availability"])
    assert len(availability) == 13
    by_id = {str(_dict(row)["source_id"]): _dict(row) for row in availability}
    assert by_id["lidarbc"]["coverage_state"] == "observed"
    assert by_id["lidarbc"]["selected"] is True
    assert by_id["vdyp"]["coverage_state"] == "missing"
    assert by_id["vdyp"]["selected"] is False
    gap = _dict(session["gap"])
    assert gap["decision"] == "continue_with_caveat"
    assert gap["next_action"]
    assert "authentication_reference" not in json.dumps(session)
    runtime = tmp_path / "runtime" / _session_id(session)
    assert (runtime / "fetch_plan.json").is_file()
    assert not (runtime / "dataset").exists()


def test_bulk_and_private_approval_builds_a_valid_plan(tmp_path: Path) -> None:
    """Public and bulk approvals plus connector approval produce an approved plan."""
    client, _store = _client(tmp_path)
    session = _create(
        client,
        source_ids=["vri"],
        connector_ids=["asset-registry"],
        bulk_fetch=True,
    )
    approved = client.post(
        f"/api/model-builder/sessions/{_session_id(session)}/approve",
        json={
            "public_sources": True,
            "bulk_fetch": True,
            "connector_ids": ["asset-registry"],
        },
    )
    assert approved.status_code == 200, approved.text
    payload = approved.json()
    assert payload["status"] == "approved"
    assert payload["public_approved"] is True
    assert payload["bulk_approved"] is True
    assert payload["approved_connectors"] == ["asset-registry"]
    for item in payload["plan"]["items"]:
        assert item["approval"]["scope"] == "bulk"
        assert item["bulk"] is True
    assert payload["plan"]["items"][-1]["access_status"] == "available"


def test_private_connector_without_approval_blocks_the_build(tmp_path: Path) -> None:
    """An unapproved private connector fails the fetch-plan stage."""
    client, _store = _client(tmp_path)
    session = _create(client, connector_ids=["asset-registry"])
    built = client.post(
        f"/api/model-builder/sessions/{_session_id(session)}/build",
        json={"dry_run": True},
    )
    assert built.status_code == 200
    payload = built.json()
    assert payload["status"] == "blocked"
    stage = next(item for item in payload["stages"] if item["name"] == "fetch_plan")
    assert stage["status"] == "failed"
    assert "FETCH-CONNECTOR" in stage["detail"]
    review = client.get(f"/api/model-builder/sessions/{_session_id(session)}/review")
    assert review.status_code == 409
    handoff = client.post(f"/api/model-builder/sessions/{_session_id(session)}/handoff")
    assert handoff.status_code == 409


def test_bulk_without_bulk_approval_blocks_the_build(tmp_path: Path) -> None:
    """A bulk plan without a bulk-scope approval stops at the plan validator."""
    client, _store = _client(tmp_path)
    session = _create(client, source_ids=["vri"], bulk_fetch=True)
    approved = client.post(
        f"/api/model-builder/sessions/{_session_id(session)}/approve",
        json={"public_sources": True, "bulk_fetch": False, "connector_ids": []},
    )
    assert approved.status_code == 200
    built = client.post(
        f"/api/model-builder/sessions/{_session_id(session)}/build",
        json={"dry_run": True},
    )
    assert built.status_code == 200
    payload = built.json()
    assert payload["status"] == "blocked"
    stage = next(item for item in payload["stages"] if item["name"] == "fetch_plan")
    assert "FETCH-APPROVAL" in stage["detail"]


def test_dry_run_writes_plan_and_review_but_no_payload(tmp_path: Path) -> None:
    """A dry run writes the plan and review, skips payload stages, and links a handoff."""
    client, _store = _client(tmp_path)
    session = _create(client)
    sid = _session_id(session)
    approved = client.post(
        f"/api/model-builder/sessions/{sid}/approve",
        json={"public_sources": True, "bulk_fetch": False, "connector_ids": []},
    )
    assert approved.status_code == 200
    built = client.post(f"/api/model-builder/sessions/{sid}/build", json={"dry_run": True})
    assert built.status_code == 200
    payload = built.json()
    assert payload["status"] == "complete"
    stages = {item["name"]: item for item in payload["stages"]}
    assert stages["fetch_plan"]["validator"] == "validate_fetch_plan"
    assert stages["fetch"]["status"] == "skipped"
    assert stages["compile_dataset"]["status"] == "skipped"
    assert stages["seed_vegetation_state"]["status"] == "skipped"
    assert stages["review"]["status"] == "passed"
    runtime = tmp_path / "runtime" / sid
    assert (runtime / "fetch_plan.json").is_file()
    assert (runtime / "review.json").is_file()
    assert not (runtime / "dataset").exists()
    assert not (runtime / "state.json").exists()
    assert not (runtime / "demo.json").exists()
    review = client.get(f"/api/model-builder/sessions/{sid}/review")
    assert review.status_code == 200
    review_payload = review.json()
    assert review_payload["segment_count"] == 5
    assert sum(review_payload["state_distribution"].values()) == 5
    assert review_payload["coverage_counts"]["observed"] == 6
    assert review_payload["gaps"]
    assert review_payload["open_questions"]
    assert isinstance(review_payload["model_cards"], list)
    assert review_payload["source"] == "synthetic-fixture"
    progress = client.get(f"/api/model-builder/sessions/{sid}/progress")
    assert progress.status_code == 200
    assert progress.headers["content-type"].startswith("text/event-stream")
    assert "event: stage" in progress.text
    assert "validate_fetch_plan" in progress.text
    handoff = client.post(f"/api/model-builder/sessions/{sid}/handoff")
    assert handoff.status_code == 200
    handoff_payload = handoff.json()
    assert handoff_payload["status"] == "linked"
    assert handoff_payload["dry_run"] is True
    assert (runtime / "handoff.json").is_file()
    assert Path(handoff_payload["instance_root"]).is_dir()


def test_non_dry_synthetic_build_writes_the_fixture_payloads(tmp_path: Path) -> None:
    """The synthetic local build compiles the fixture and copies the demo."""
    client, _store = _client(tmp_path)
    session = _create(client)
    sid = _session_id(session)
    client.post(
        f"/api/model-builder/sessions/{sid}/approve",
        json={"public_sources": True, "connector_ids": []},
    )
    built = client.post(f"/api/model-builder/sessions/{sid}/build", json={"dry_run": False})
    assert built.status_code == 200
    payload = built.json()
    assert payload["status"] == "complete"
    runtime = tmp_path / "runtime" / sid
    assert (runtime / "dataset" / "manifest.json").is_file()
    assert (runtime / "state.json").is_file()
    assert (runtime / "demo.json").is_file()
    assert (runtime / "scenario" / "scenario_validation.json").is_file()
    assert payload["review"]["segment_count"] == 5


def test_custom_aoi_is_missing_and_blocks_at_segmentation(tmp_path: Path) -> None:
    """A drawn AOI is honest about missing coverage and cannot use the fixture segmenter."""
    client, _store = _client(tmp_path)
    geometry = {
        "type": "Polygon",
        "coordinates": [[[10, 10], [80, 10], [80, 70], [10, 70], [10, 10]]],
    }
    session = _create(client, geometry=geometry, source_ids=["lidarbc"])
    assert _dict(session["aoi"])["id"] == "custom"
    assert all(_dict(row)["coverage_state"] == "missing" for row in _list(session["availability"]))
    assert _dict(session["gap"])["decision"] == "stop"
    built = client.post(
        f"/api/model-builder/sessions/{_session_id(session)}/build",
        json={"dry_run": True},
    )
    assert built.status_code == 200
    payload = built.json()
    assert payload["status"] == "blocked"
    stages = {item["name"]: item for item in payload["stages"]}
    assert stages["validate_aoi"]["status"] == "passed"
    assert stages["segment_corridor"]["status"] == "failed"


def test_custom_aoi_non_dry_stops_at_materialization(tmp_path: Path) -> None:
    """A custom AOI has no local materialization path."""
    client, _store = _client(tmp_path)
    geometry = {
        "type": "Polygon",
        "coordinates": [[[0, 0], [50, 0], [50, 50], [0, 50], [0, 0]]],
    }
    session = _create(client, geometry=geometry)
    built = client.post(
        f"/api/model-builder/sessions/{_session_id(session)}/build",
        json={"dry_run": False},
    )
    assert built.status_code == 200
    payload = built.json()
    stage = next(item for item in payload["stages"] if item["name"] == "fetch")
    assert stage["status"] == "failed"


def test_invalid_requests_and_missing_sessions(tmp_path: Path) -> None:
    """Invalid AOIs, sources, connectors, and sessions have stable HTTP errors."""
    client, _store = _client(tmp_path)
    assert (
        client.post(
            "/api/model-builder/sessions",
            json={"aoi_id": "missing"},
        ).status_code
        == 400
    )
    assert (
        client.post(
            "/api/model-builder/sessions",
            json={"source_ids": ["missing-source"]},
        ).status_code
        == 400
    )
    assert (
        client.post(
            "/api/model-builder/sessions",
            json={
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[[0, 0], [0, 0], [0, 0], [0, 0]]],
                }
            },
        ).status_code
        == 400
    )
    session = _create(client, connector_ids=["asset-registry"])
    sid = _session_id(session)
    assert (
        client.post(
            f"/api/model-builder/sessions/{sid}/approve",
            json={"connector_ids": ["treatment-history"]},
        ).status_code
        == 400
    )
    assert client.get("/api/model-builder/sessions/missing").status_code == 404
    assert client.get("/api/model-builder/sessions/missing/progress").status_code == 404
    assert client.get(f"/api/model-builder/sessions/{sid}/review").status_code == 409
    assert client.post(f"/api/model-builder/sessions/{sid}/handoff").status_code == 409


def test_invalid_connector_and_missing_route_errors(tmp_path: Path) -> None:
    """An unknown connector and every missing-session route fail cleanly."""
    client, _store = _client(tmp_path)
    assert (
        client.post(
            "/api/model-builder/sessions",
            json={"connector_ids": ["missing-connector"]},
        ).status_code
        == 400
    )
    missing = "/api/model-builder/sessions/missing"
    assert client.post(f"{missing}/approve", json={}).status_code == 404
    assert client.post(f"{missing}/build", json={}).status_code == 404
    assert client.get(f"{missing}/review").status_code == 404
    assert client.post(f"{missing}/handoff").status_code == 404
    assert client.get(f"{missing}/progress").status_code == 404


def test_invalid_aoi_is_recorded_at_the_validation_stage(tmp_path: Path) -> None:
    """A tampered session AOI fails the first build stage."""
    client, store = _client(tmp_path)
    session = _create(client)
    sid = _session_id(session)
    stored = store.sessions[sid]
    bad_aoi = stored.aoi.model_copy(update={"geometry": {"type": "Point", "coordinates": [0, 0]}})
    store.sessions[sid] = stored.model_copy(update={"aoi": bad_aoi})
    built = client.post(f"/api/model-builder/sessions/{sid}/build", json={"dry_run": True})
    assert built.status_code == 200
    payload = built.json()
    assert payload["status"] == "blocked"
    stage = next(item for item in payload["stages"] if item["name"] == "validate_aoi")
    assert stage["status"] == "failed"


def test_missing_or_invalid_corridor_stops_the_segment_stage(tmp_path: Path) -> None:
    """A missing or invalid fixture corridor fails the segmentation stage."""
    client, store = _client(tmp_path)
    session = _create(client)
    sid = _session_id(session)
    bad = tmp_path / "bad-fixture"
    bad.mkdir()
    shutil.copy2(FIXTURE / "state.json", bad / "state.json")
    shutil.copy2(FIXTURE / "demo.json", bad / "demo.json")
    shutil.copytree(FIXTURE / "dataset", bad / "dataset")
    store.fixture_root = bad
    (bad / "corridor.json").write_text("{}", encoding="utf-8")
    missing = client.post(
        f"/api/model-builder/sessions/{sid}/build",
        json={"dry_run": True},
    )
    assert missing.status_code == 200
    stage = next(item for item in missing.json()["stages"] if item["name"] == "segment_corridor")
    assert stage["status"] == "failed"


def test_invalid_corridor_contract_stops_the_segment_stage(tmp_path: Path) -> None:
    """A corridor that parses but fails the graph validator stops segmentation."""
    client, store = _client(tmp_path)
    session = _create(client)
    sid = _session_id(session)
    bad = tmp_path / "bad-contract"
    bad.mkdir()
    shutil.copy2(FIXTURE / "state.json", bad / "state.json")
    shutil.copy2(FIXTURE / "demo.json", bad / "demo.json")
    shutil.copytree(FIXTURE / "dataset", bad / "dataset")
    corridor = json.loads((FIXTURE / "corridor.json").read_text(encoding="utf-8"))
    corridor["corridors"][0]["length_m"] = 1.0
    (bad / "corridor.json").write_text(json.dumps(corridor), encoding="utf-8")
    store.fixture_root = bad
    built = client.post(f"/api/model-builder/sessions/{sid}/build", json={"dry_run": True})
    assert built.status_code == 200
    stage = next(item for item in built.json()["stages"] if item["name"] == "segment_corridor")
    assert stage["status"] == "failed"


def test_non_dry_invalid_state_and_scenario_failures(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The non-dry path records a compile failure and a scenario failure."""
    client, store = _client(tmp_path)
    session = _create(client)
    sid = _session_id(session)
    client.post(
        f"/api/model-builder/sessions/{sid}/approve",
        json={"public_sources": True, "connector_ids": []},
    )
    bad = tmp_path / "bad-state"
    shutil.copytree(FIXTURE, bad)
    (bad / "state.json").write_text("{}", encoding="utf-8")
    store.fixture_root = bad
    built = client.post(f"/api/model-builder/sessions/{sid}/build", json={"dry_run": False})
    assert built.status_code == 200
    assert built.json()["status"] == "blocked"
    assert any(
        item["name"] == "compile_dataset" and item["status"] == "failed"
        for item in built.json()["stages"]
    )

    client, store = _client(tmp_path / "second")
    session = _create(client)
    sid = _session_id(session)
    client.post(
        f"/api/model-builder/sessions/{sid}/approve",
        json={"public_sources": True, "connector_ids": []},
    )
    monkeypatch.setattr(model_builder, "TEMPLATE_ROOT", tmp_path / "missing-template")
    built = client.post(f"/api/model-builder/sessions/{sid}/build", json={"dry_run": False})
    assert built.status_code == 200
    assert built.json()["status"] == "blocked"
    assert any(
        item["name"] == "validate_scenario" and item["status"] == "failed"
        for item in built.json()["stages"]
    )


def test_synthetic_aoi_and_bbox_error_paths(tmp_path: Path) -> None:
    """Malformed AOI files and geometries fail with named errors."""
    cases = [
        ({"type": "FeatureCollection", "features": []}, "no features"),
        ({"type": "Point"}, "Feature or FeatureCollection"),
        ({"type": "FeatureCollection", "features": [1]}, "not an object"),
        ({"type": "Feature", "geometry": None}, "no geometry"),
    ]
    for index, (payload, message) in enumerate(cases):
        folder = tmp_path / f"fixture-{index}"
        folder.mkdir()
        (folder / "aoi.geojson").write_text(json.dumps(payload), encoding="utf-8")
        with pytest.raises(ValueError, match=message):
            model_builder._synthetic_aoi(folder)
    with pytest.raises(ValueError, match="object"):
        model_builder._bbox_from_geometry(None)
    with pytest.raises(ValueError, match="Polygon"):
        model_builder._bbox_from_geometry({"type": "Point", "coordinates": [0, 0]})
    with pytest.raises(ValueError, match="three"):
        model_builder._bbox_from_geometry({"type": "Polygon", "coordinates": []})
    with pytest.raises(ValueError, match="positive area"):
        model_builder._bbox_from_geometry(
            {"type": "Polygon", "coordinates": [[[0, 0], [0, 0], [0, 0], [0, 0]]]}
        )


def test_catalogue_fallback_uses_an_empty_catalogue(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A missing reference catalogue falls back to an empty catalogue."""
    monkeypatch.setattr(model_builder, "DEFAULT_CATALOGUE_PATH", tmp_path / "missing.json")
    catalogue = model_builder._load_catalogue()
    assert catalogue.sources == []
    assert catalogue.connectors == []
