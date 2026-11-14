"""Tests for the P5.8 studio telemetry and archive contract."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from brushline.model.archive import ParetoArchive
from brushline.optimization.adapter import ADAPTER_NAME, SearchRun
from brushline.optimization.telemetry import (
    EVENT_TYPES,
    EventStream,
    StudioCompatibility,
    TelemetryError,
    check_studio_compatibility,
    events_from_run,
    load_event_stream,
    make_event,
    to_sse,
    validate_event_stream,
    with_archive_event,
    write_event_stream,
    write_sse,
)
from pydantic import ValidationError

ROOT = Path(__file__).resolve().parents[1]
STREAM_FILE = ROOT / "notes" / "reference" / "p5-telemetry.v1.json"
ARCHIVE_FILE = ROOT / "notes" / "reference" / "p5-archive.v1.json"
NOW = datetime(2026, 11, 14, 12, 0, tzinfo=UTC)
ARCHIVE_PATH = "runs/tiny/pareto.json"


def _stream() -> EventStream:
    return load_event_stream(STREAM_FILE)


def _archive() -> ParetoArchive:
    return ParetoArchive.model_validate_json(ARCHIVE_FILE.read_text(encoding="utf-8"))


def _run() -> SearchRun:
    return SearchRun(
        mode="local",
        instance_id="tiny",
        adapter=ADAPTER_NAME,
        fresh_solutions_version="0.9.3",
        seed=7,
        budget=20,
        assignment={0: 1, 1: 1, 2: 0, 3: 0, 4: 0, 5: 0},
        objective=25.08,
        objective_vector={
            "present_cost": 100.0,
            "service_risk": 0.0003,
            "service_attainment": 1.0,
            "uncertainty": 0.3253,
        },
        feasible=True,
        evaluations=21,
        history=[25.08],
        stop_reason="budget",
        checkpoint_path="runs/tiny/checkpoint.json",
        evidence={"objective": 25.08},
        replay_ok=True,
    )


def test_committed_stream_and_archive_are_studio_compatible() -> None:
    """The committed stream and archive pass the compatibility check."""
    stream = _stream()
    archive = _archive()
    assert validate_event_stream(stream).is_valid
    report = check_studio_compatibility(stream, archive, archive_path=ARCHIVE_PATH)
    assert report.ok
    assert report.member_count == 1
    assert report.event_count == 4
    assert set(EVENT_TYPES) >= {event.event_type for event in stream.events}
    assert stream.model_version
    assert stream.data_version


def test_events_from_run_and_archive_insertion() -> None:
    """Run events add start, incumbent, checkpoint, finish, and one archive event."""
    stream = events_from_run(
        _run(),
        run_id="tiny-run-1",
        model_version="model-v1",
        data_version="data-v1",
        archive_path=ARCHIVE_PATH,
        created_utc=NOW,
    )
    assert [event.event_type for event in stream.events] == [
        "start",
        "incumbent",
        "checkpoint",
        "finish",
    ]
    archive_stream = with_archive_event(
        stream, _archive(), archive_path=ARCHIVE_PATH, created_utc=NOW
    )
    assert [event.event_type for event in archive_stream.events] == [
        "start",
        "incumbent",
        "checkpoint",
        "archive",
        "finish",
    ]
    assert archive_stream.archive_path == ARCHIVE_PATH
    assert check_studio_compatibility(archive_stream, _archive(), archive_path=ARCHIVE_PATH).ok
    with pytest.raises(TelemetryError, match="finish"):
        with_archive_event(
            stream.model_copy(update={"events": stream.events[:1]}),
            _archive(),
            archive_path=ARCHIVE_PATH,
        )
    bad_archive = _archive().model_copy(
        update={
            "members": [
                _archive().members[0].model_copy(update={"objective": {"present_cost": 1.0}})
            ]
        }
    )
    with pytest.raises(TelemetryError):
        with_archive_event(stream, bad_archive, archive_path=ARCHIVE_PATH)


def test_stream_validation_errors_are_named() -> None:
    """Sequence, order, run, instance, and duplicate problems are reported."""
    stream = _stream()
    events = list(stream.events)
    cases = [
        stream.model_copy(update={"events": [events[1], events[0], *events[2:]]}),
        stream.model_copy(update={"events": [*events[:2], events[3], events[2]]}),
        stream.model_copy(
            update={
                "events": [
                    events[0],
                    events[2],
                    events[1],
                    events[3],
                ]
            }
        ),
        stream.model_copy(
            update={
                "events": [
                    events[0].model_copy(update={"run_id": "other"}),
                    *events[1:],
                ]
            }
        ),
        stream.model_copy(
            update={
                "events": [
                    events[0].model_copy(update={"instance_id": "other"}),
                    *events[1:],
                ]
            }
        ),
        stream.model_copy(
            update={
                "events": [
                    events[0],
                    events[1],
                    events[2],
                    events[3].model_copy(update={"sequence": 2}),
                ]
            }
        ),
    ]
    for case in cases:
        assert not validate_event_stream(case).is_valid
    no_archive = stream.model_copy(update={"archive_path": None})
    assert any(
        warning.startswith("TELEMETRY-ARCHIVE")
        for warning in validate_event_stream(no_archive).warnings
    )


def test_compatibility_missing_and_mismatched_artifacts() -> None:
    """A missing archive, path, member, evidence, or objective is explicit."""
    stream = _stream()
    archive = _archive()
    missing = check_studio_compatibility(stream, None, archive_path=ARCHIVE_PATH)
    assert not missing.ok
    assert any("missing" in error for error in missing.errors)
    assert not check_studio_compatibility(stream, archive, archive_path="other").ok
    no_event = stream.model_copy(
        update={"events": [event for event in stream.events if event.event_type != "archive"]}
    )
    assert not check_studio_compatibility(no_event, archive, archive_path=ARCHIVE_PATH).ok
    archive_event = next(event for event in stream.events if event.event_type == "archive")
    members = archive_event.payload["members"]
    wrong_plan = [dict(members[0], plan_id="other")]
    bad_payload = archive_event.model_copy(
        update={"payload": {**archive_event.payload, "members": wrong_plan}}
    )
    bad_stream = stream.model_copy(
        update={
            "events": [
                event if event.event_type != "archive" else bad_payload for event in stream.events
            ]
        }
    )
    assert not check_studio_compatibility(bad_stream, archive, archive_path=ARCHIVE_PATH).ok
    wrong_objective = [dict(members[0], objective={"present_cost": 1.0})]
    bad_payload = archive_event.model_copy(
        update={"payload": {**archive_event.payload, "members": wrong_objective}}
    )
    bad_stream = stream.model_copy(
        update={
            "events": [
                event if event.event_type != "archive" else bad_payload for event in stream.events
            ]
        }
    )
    assert not check_studio_compatibility(bad_stream, archive, archive_path=ARCHIVE_PATH).ok


def test_event_and_stream_model_guards() -> None:
    """Unknown events, naive time, bad objectives, and paths fail."""
    with pytest.raises(ValidationError):
        make_event(
            event_id="e",
            run_id="r",
            sequence=0,
            event_type="unknown",
            created_utc=NOW,
            instance_id="i",
            adapter="a",
            fresh_solutions_version="0.9.3",
            seed=1,
            budget=1,
        )
    with pytest.raises(ValidationError):
        make_event(
            event_id="e",
            run_id="r",
            sequence=0,
            event_type="start",
            created_utc=datetime(2026, 11, 14),
            instance_id="i",
            adapter="a",
            fresh_solutions_version="0.9.3",
            seed=1,
            budget=1,
        )
    with pytest.raises(ValidationError):
        make_event(
            event_id="e",
            run_id="r",
            sequence=0,
            event_type="start",
            created_utc=NOW,
            instance_id="i",
            adapter="a",
            fresh_solutions_version="0.9.3",
            seed=1,
            budget=1,
            evidence_path="../escape.json",
        )
    with pytest.raises(ValidationError):
        EventStream(
            run_id="r",
            instance_id="i",
            model_version="m",
            data_version="d",
            events=[],
        )


def test_writers_and_sse(tmp_path: Path) -> None:
    """JSON and SSE writers round-trip and reject invalid streams."""
    stream = _stream()
    path = tmp_path / "events.json"
    assert write_event_stream(stream, path) == path
    assert load_event_stream(path) == stream
    sse = to_sse(stream)
    assert "event: start" in sse
    assert "event: finish" in sse
    sse_path = tmp_path / "events.sse"
    assert write_sse(stream, sse_path) == sse_path
    assert sse_path.read_text() == sse
    invalid = stream.model_copy(
        update={"events": [stream.events[1], stream.events[0], *stream.events[2:]]}
    )
    with pytest.raises(TelemetryError):
        write_event_stream(invalid, tmp_path / "bad.json")
    with pytest.raises(TelemetryError):
        to_sse(invalid)
    is_instance = StudioCompatibility(
        ok=True, errors=[], warnings=[], member_count=1, event_count=2
    )
    assert is_instance.ok


def test_telemetry_edge_paths_and_load_failure(tmp_path: Path) -> None:
    """Missing paths, no checkpoint, unsafe member payloads, and bad loads are explicit."""
    stream = _stream()
    assert not check_studio_compatibility(
        stream.model_copy(update={"archive_path": None}),
        _archive(),
    ).ok
    archive_event = next(event for event in stream.events if event.event_type == "archive")
    payload = {**archive_event.payload, "members": "not-a-list"}
    bad_payload = archive_event.model_copy(update={"payload": payload})
    bad_stream = stream.model_copy(
        update={
            "events": [
                event if event.event_type != "archive" else bad_payload for event in stream.events
            ]
        }
    )
    assert not check_studio_compatibility(bad_stream, _archive(), archive_path=ARCHIVE_PATH).ok
    members = archive_event.payload["members"]
    wrong_evidence = [dict(members[0], evidence_path="evidence/other.json")]
    bad_payload = archive_event.model_copy(
        update={"payload": {**archive_event.payload, "members": wrong_evidence}}
    )
    bad_stream = stream.model_copy(
        update={
            "events": [
                event if event.event_type != "archive" else bad_payload for event in stream.events
            ]
        }
    )
    assert not check_studio_compatibility(bad_stream, _archive(), archive_path=ARCHIVE_PATH).ok
    no_path = stream.model_copy(update={"archive_path": None})
    with pytest.raises(TelemetryError, match="archive path"):
        with_archive_event(no_path, _archive())
    no_checkpoint = _run().model_copy(update={"checkpoint_path": None})
    checkpointless = events_from_run(
        no_checkpoint,
        run_id="tiny-run-1",
        model_version="model-v1",
        data_version="data-v1",
        archive_path=ARCHIVE_PATH,
        created_utc=NOW,
    )
    assert [event.event_type for event in checkpointless.events] == [
        "start",
        "incumbent",
        "finish",
    ]
    with pytest.raises(ValidationError):
        make_event(
            event_id="e",
            run_id="r",
            sequence=0,
            event_type="start",
            created_utc=NOW,
            instance_id="i",
            adapter="a",
            fresh_solutions_version="0.9.3",
            seed=1,
            budget=1,
            objective_vector={"present_cost": 1.0},
        )
    EventStream(
        run_id="r",
        instance_id="i",
        model_version="m",
        data_version="d",
        archive_path=None,
        events=[stream.events[0]],
    )
    bad = stream.model_copy(
        update={"events": [stream.events[1], stream.events[0], *stream.events[2:]]}
    )
    path = tmp_path / "bad.json"
    path.write_text(bad.model_dump_json())
    with pytest.raises(TelemetryError):
        load_event_stream(path)
