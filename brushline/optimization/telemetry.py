"""Versioned progress-event and archive compatibility contract for the studio.

The telemetry stream is a report of search progress, not a second model state. Events reference the
archive, plan, and evidence artifacts. The studio compatibility check reads only the versioned event
stream and the archive.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from brushline.model.archive import ParetoArchive, validate_pareto_archive
from brushline.model.validation import (
    ContractValidation,
    check_duplicates,
    ensure_relative_path,
)
from brushline.optimization.adapter import SearchRun
from brushline.optimization.formulation import OBJECTIVE_NAMES

EVENT_SCHEMA_VERSION = "brushline.optimization-event.v1"
TELEMETRY_SCHEMA_VERSION = "brushline.optimization-telemetry.v1"
EVENT_TYPES: tuple[str, ...] = (
    "start",
    "iteration",
    "incumbent",
    "archive",
    "checkpoint",
    "finish",
)


class TelemetryError(ValueError):
    """Raised when an event stream or compatibility check is invalid."""


class TelemetryEvent(BaseModel):
    """One progress event.

    Parameters
    ----------
    schema_version : {"brushline.optimization-event.v1"}
        Schema version.
    event_id : str
        Stable event id.
    run_id : str
        Run id.
    sequence : int
        Zero-based sequence.
    event_type : str
        Event type.
    created_utc : datetime
        Timezone-aware creation time.
    instance_id : str
        Instance id.
    adapter : str
        Adapter name.
    fresh_solutions_version : str
        Fresh Solutions version.
    seed : int
        Search seed.
    budget : int
        Requested budget.
    payload : dict
        Event-specific data.
    objective_vector : dict of str to float or None
        Four objectives, when relevant.
    feasible : bool or None
        Feasibility, when relevant.
    plan_id : str or None
        Archive plan id, when relevant.
    evidence_path : str or None
        Archive-relative evidence path, when relevant.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = EVENT_SCHEMA_VERSION
    event_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    sequence: int = Field(ge=0)
    event_type: str
    created_utc: datetime
    instance_id: str = Field(min_length=1)
    adapter: str = Field(min_length=1)
    fresh_solutions_version: str = Field(min_length=1)
    seed: int
    budget: int = Field(ge=0)
    payload: dict[str, Any] = Field(default_factory=dict)
    objective_vector: dict[str, float] | None = None
    feasible: bool | None = None
    plan_id: str | None = None
    evidence_path: str | None = None

    @model_validator(mode="after")
    def _event(self) -> TelemetryEvent:
        if self.event_type not in EVENT_TYPES:
            raise ValueError("unknown event type")
        if self.created_utc.tzinfo is None:
            raise ValueError("created_utc must be timezone-aware")
        if self.objective_vector is not None and set(self.objective_vector) != set(OBJECTIVE_NAMES):
            raise ValueError("objective_vector must contain the four objectives")
        if self.evidence_path is not None:
            ensure_relative_path(self.evidence_path, "evidence path")
        return self


class EventStream(BaseModel):
    """A versioned progress-event stream.

    Parameters
    ----------
    schema_version : {"brushline.optimization-telemetry.v1"}
        Schema version.
    run_id : str
        Run id.
    instance_id : str
        Instance id.
    model_version : str
        Vegetation-model version.
    data_version : str
        Data version.
    archive_path : str or None
        Archive-relative path to ``pareto.json``.
    events : list of TelemetryEvent
        Ordered events.
    """

    model_config = ConfigDict(extra="forbid")

    schema_version: str = TELEMETRY_SCHEMA_VERSION
    run_id: str = Field(min_length=1)
    instance_id: str = Field(min_length=1)
    model_version: str = Field(min_length=1)
    data_version: str = Field(min_length=1)
    archive_path: str | None = None
    events: list[TelemetryEvent] = Field(min_length=1)

    @model_validator(mode="after")
    def _paths(self) -> EventStream:
        if self.archive_path is not None:
            ensure_relative_path(self.archive_path, "archive path")
        return self


class StudioCompatibility(BaseModel):
    """The result of a studio compatibility check.

    Parameters
    ----------
    ok : bool
        Whether the stream and archive are compatible.
    errors : list of str
        Compatibility errors.
    warnings : list of str
        Compatibility warnings.
    archive_path : str or None
        Archive path.
    member_count : int
        Archive member count.
    event_count : int
        Event count.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    ok: bool
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    archive_path: str | None = None
    member_count: int = 0
    event_count: int = 0


def make_event(
    *,
    event_id: str,
    run_id: str,
    sequence: int,
    event_type: str,
    created_utc: datetime,
    instance_id: str,
    adapter: str,
    fresh_solutions_version: str,
    seed: int,
    budget: int,
    payload: dict[str, Any] | None = None,
    objective_vector: dict[str, float] | None = None,
    feasible: bool | None = None,
    plan_id: str | None = None,
    evidence_path: str | None = None,
) -> TelemetryEvent:
    """Construct one validated event.

    Parameters
    ----------
    event_id : str
        Event id.
    run_id : str
        Run id.
    sequence : int
        Sequence.
    event_type : str
        Type.
    created_utc : datetime
        Creation time.
    instance_id : str
        Instance id.
    adapter : str
        Adapter name.
    fresh_solutions_version : str
        Fresh Solutions version.
    seed : int
        Seed.
    budget : int
        Budget.
    payload : dict, optional
        Event data.
    objective_vector : dict, optional
        Objectives.
    feasible : bool, optional
        Feasibility.
    plan_id : str, optional
        Plan id.
    evidence_path : str, optional
        Evidence path.

    Returns
    -------
    TelemetryEvent
        Event.
    """
    return TelemetryEvent(
        event_id=event_id,
        run_id=run_id,
        sequence=sequence,
        event_type=event_type,
        created_utc=created_utc,
        instance_id=instance_id,
        adapter=adapter,
        fresh_solutions_version=fresh_solutions_version,
        seed=seed,
        budget=budget,
        payload=payload or {},
        objective_vector=objective_vector,
        feasible=feasible,
        plan_id=plan_id,
        evidence_path=evidence_path,
    )


def events_from_run(
    run: SearchRun,
    *,
    run_id: str,
    model_version: str,
    data_version: str,
    archive_path: str | None = None,
    created_utc: datetime | None = None,
) -> EventStream:
    """Create start, incumbent, checkpoint, and finish events for a run.

    Parameters
    ----------
    run : SearchRun
        Replayable search result.
    run_id : str
        Run id.
    model_version : str
        Vegetation-model version.
    data_version : str
        Data version.
    archive_path : str or None, optional
        Archive path.
    created_utc : datetime, optional
        Creation time.

    Returns
    -------
    EventStream
        Progress stream. An archive event is not fabricated.
    """
    created = created_utc or datetime.now(UTC)
    events = [
        make_event(
            event_id=f"{run_id}:0",
            run_id=run_id,
            sequence=0,
            event_type="start",
            created_utc=created,
            instance_id=run.instance_id,
            adapter=run.adapter,
            fresh_solutions_version=run.fresh_solutions_version,
            seed=run.seed,
            budget=run.budget,
            payload={"mode": run.mode, "stop_reason": run.stop_reason},
        ),
        make_event(
            event_id=f"{run_id}:1",
            run_id=run_id,
            sequence=1,
            event_type="incumbent",
            created_utc=created,
            instance_id=run.instance_id,
            adapter=run.adapter,
            fresh_solutions_version=run.fresh_solutions_version,
            seed=run.seed,
            budget=run.budget,
            payload={
                "assignment": {str(key): value for key, value in sorted(run.assignment.items())},
                "evaluations": run.evaluations,
                "stop_reason": run.stop_reason,
                "history": run.history,
            },
            objective_vector=run.objective_vector,
            feasible=run.feasible,
        ),
    ]
    sequence = 2
    if run.checkpoint_path is not None:
        events.append(
            make_event(
                event_id=f"{run_id}:{sequence}",
                run_id=run_id,
                sequence=sequence,
                event_type="checkpoint",
                created_utc=created,
                instance_id=run.instance_id,
                adapter=run.adapter,
                fresh_solutions_version=run.fresh_solutions_version,
                seed=run.seed,
                budget=run.budget,
                payload={"path": run.checkpoint_path},
            )
        )
        sequence += 1
    events.append(
        make_event(
            event_id=f"{run_id}:{sequence}",
            run_id=run_id,
            sequence=sequence,
            event_type="finish",
            created_utc=created,
            instance_id=run.instance_id,
            adapter=run.adapter,
            fresh_solutions_version=run.fresh_solutions_version,
            seed=run.seed,
            budget=run.budget,
            payload={"stop_reason": run.stop_reason, "evaluations": run.evaluations},
        )
    )
    return EventStream(
        run_id=run_id,
        instance_id=run.instance_id,
        model_version=model_version,
        data_version=data_version,
        archive_path=archive_path,
        events=events,
    )


def with_archive_event(
    stream: EventStream,
    archive: ParetoArchive,
    *,
    archive_path: str | None = None,
    created_utc: datetime | None = None,
) -> EventStream:
    """Insert a validated archive event before the finish event.

    Parameters
    ----------
    stream : EventStream
        Existing stream.
    archive : ParetoArchive
        Archive.
    archive_path : str or None, optional
        Archive path. Defaults to the stream path.
    created_utc : datetime, optional
        Event time.

    Returns
    -------
    EventStream
        Stream with an archive event before finish.

    Raises
    ------
    TelemetryError
        When the archive is invalid or no finish event exists.
    """
    validation = validate_pareto_archive(archive)
    if not validation.is_valid:
        raise TelemetryError("; ".join(validation.errors))
    path = archive_path or stream.archive_path
    if path is None:
        raise TelemetryError("an archive path is required")
    ensure_relative_path(path, "archive path")
    payload = {
        "archive_path": path,
        "members": [member.model_dump(mode="json") for member in archive.members],
    }
    created = created_utc or max(event.created_utc for event in stream.events)
    archive_event = make_event(
        event_id=f"{stream.run_id}:archive",
        run_id=stream.run_id,
        sequence=0,
        event_type="archive",
        created_utc=created,
        instance_id=archive.instance_id,
        adapter=stream.events[0].adapter,
        fresh_solutions_version=stream.events[0].fresh_solutions_version,
        seed=stream.events[0].seed,
        budget=stream.events[0].budget,
        payload=payload,
    )
    events = [event for event in stream.events if event.event_type != "finish"]
    finish = next((event for event in stream.events if event.event_type == "finish"), None)
    if finish is None:
        raise TelemetryError("the stream needs a finish event before an archive event")
    events.append(archive_event)
    events.append(finish)
    renumbered = [
        event.model_copy(update={"sequence": index, "event_id": f"{stream.run_id}:{index}"})
        for index, event in enumerate(events)
    ]
    return stream.model_copy(
        update={
            "events": renumbered,
            "archive_path": path,
        }
    )


def validate_event_stream(stream: EventStream) -> ContractValidation:
    """Validate sequence, run identity, event order, and artifact references.

    Parameters
    ----------
    stream : EventStream
        Stream to validate.

    Returns
    -------
    ContractValidation
        Errors and warnings.
    """
    errors: list[str] = []
    warnings: list[str] = []
    check_duplicates("TELEMETRY", "event", [event.event_id for event in stream.events], errors)
    sequences = [event.sequence for event in stream.events]
    if sequences != list(range(len(sequences))):
        errors.append("TELEMETRY-SEQUENCE: sequences must be consecutive from zero")
    if stream.events[0].event_type != "start":
        errors.append("TELEMETRY-ORDER: the first event must be start")
    if stream.events[-1].event_type != "finish":
        errors.append("TELEMETRY-ORDER: the last event must be finish")
    finished = False
    for event in stream.events:
        if event.run_id != stream.run_id:
            errors.append(f"TELEMETRY-RUN: {event.event_id} has a different run id")
        if event.instance_id != stream.instance_id:
            errors.append(f"TELEMETRY-INSTANCE: {event.event_id} has a different instance")
        if event.event_type == "finish":
            finished = True
        elif finished:
            errors.append(f"TELEMETRY-ORDER: {event.event_id} appears after finish")
    if stream.archive_path is None:
        warnings.append("TELEMETRY-ARCHIVE: no archive path is declared")
    return ContractValidation(
        tuple(errors),
        tuple(warnings),
        {"events": len(stream.events)},
    )


def check_studio_compatibility(
    stream: EventStream,
    archive: ParetoArchive | None,
    *,
    archive_path: str | None = None,
) -> StudioCompatibility:
    """Check that the studio can read the stream and archive without private state.

    Parameters
    ----------
    stream : EventStream
        Progress stream.
    archive : ParetoArchive or None
        Archive. None is an explicit missing artifact.
    archive_path : str or None, optional
        Expected archive path.

    Returns
    -------
    StudioCompatibility
        Compatibility result.
    """
    errors: list[str] = []
    warnings: list[str] = []
    validation = validate_event_stream(stream)
    errors.extend(validation.errors)
    warnings.extend(validation.warnings)
    if archive is None:
        errors.append("STUDIO-ARCHIVE: the archive artifact is missing")
        return StudioCompatibility(
            ok=False,
            errors=errors,
            warnings=warnings,
            archive_path=stream.archive_path,
            event_count=len(stream.events),
        )
    archive_validation = validate_pareto_archive(archive)
    errors.extend(archive_validation.errors)
    expected_path = archive_path or stream.archive_path
    if expected_path is None:
        errors.append("STUDIO-ARCHIVE: the archive path is missing")
    elif stream.archive_path != expected_path:
        errors.append("STUDIO-ARCHIVE: stream and archive paths differ")
    archive_events = [event for event in stream.events if event.event_type == "archive"]
    if len(archive_events) != 1:
        errors.append("STUDIO-ARCHIVE: exactly one archive event is required")
    else:
        payload = archive_events[0].payload
        members = payload.get("members")
        if not isinstance(members, list):
            errors.append("STUDIO-ARCHIVE: the archive event has no member list")
        else:
            event_plans = {
                str(item.get("plan_id")): item for item in members if isinstance(item, dict)
            }
            archive_plans = {member.plan_id: member for member in archive.members}
            if set(event_plans) != set(archive_plans):
                errors.append("STUDIO-ARCHIVE: event and archive plan ids differ")
            for plan_id, member in archive_plans.items():
                event_member = event_plans.get(plan_id)
                if event_member is None:
                    continue
                if event_member.get("evidence_path") != member.evidence_path:
                    errors.append(f"STUDIO-EVIDENCE: {plan_id} evidence paths differ")
                if event_member.get("objective") != member.objective:
                    errors.append(f"STUDIO-OBJECTIVE: {plan_id} objective vectors differ")
    return StudioCompatibility(
        ok=not errors,
        errors=errors,
        warnings=warnings,
        archive_path=expected_path,
        member_count=len(archive.members),
        event_count=len(stream.events),
    )


def write_event_stream(stream: EventStream, path: str | Path) -> Path:
    """Validate and write an event stream as JSON.

    Parameters
    ----------
    stream : EventStream
        Stream.
    path : str or Path
        Destination.

    Returns
    -------
    Path
        Written path.

    Raises
    ------
    TelemetryError
        When the stream is invalid.
    """
    validation = validate_event_stream(stream)
    if not validation.is_valid:
        raise TelemetryError("; ".join(validation.errors))
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(stream.model_dump_json(indent=2) + "\n", encoding="utf-8")
    return destination


def load_event_stream(path: str | Path) -> EventStream:
    """Load and validate an event stream.

    Parameters
    ----------
    path : str or Path
        Source.

    Returns
    -------
    EventStream
        Stream.

    Raises
    ------
    TelemetryError
        When the stream is invalid.
    """
    stream = EventStream.model_validate_json(Path(path).read_text(encoding="utf-8"))
    validation = validate_event_stream(stream)
    if not validation.is_valid:
        raise TelemetryError("; ".join(validation.errors))
    return stream


def to_sse(stream: EventStream) -> str:
    """Render an event stream as server-sent events.

    Parameters
    ----------
    stream : EventStream
        Stream.

    Returns
    -------
    str
        SSE body.
    """
    validation = validate_event_stream(stream)
    if not validation.is_valid:
        raise TelemetryError("; ".join(validation.errors))
    blocks: list[str] = []
    for event in stream.events:
        data = json.dumps(event.model_dump(mode="json"), sort_keys=True)
        blocks.append(f"id: {event.sequence}\nevent: {event.event_type}\ndata: {data}\n\n")
    return "".join(blocks)


def write_sse(stream: EventStream, path: str | Path) -> Path:
    """Write a validated SSE event stream.

    Parameters
    ----------
    stream : EventStream
        Stream.
    path : str or Path
        Destination.

    Returns
    -------
    Path
        Written path.
    """
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(to_sse(stream), encoding="utf-8")
    return destination


__all__ = [
    "EVENT_SCHEMA_VERSION",
    "EVENT_TYPES",
    "TELEMETRY_SCHEMA_VERSION",
    "EventStream",
    "StudioCompatibility",
    "TelemetryError",
    "TelemetryEvent",
    "check_studio_compatibility",
    "events_from_run",
    "load_event_stream",
    "make_event",
    "to_sse",
    "validate_event_stream",
    "with_archive_event",
    "write_event_stream",
    "write_sse",
]
