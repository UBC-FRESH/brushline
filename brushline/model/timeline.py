"""Operations timeline contract for the 2D map and 3D scene.

The timeline is a sequence of timestamped events: a crew or machine travels, starts, treats,
pauses, or finishes a segment. It drives the animation. The timeline is a simulation artifact, not a
live telemetry feed, and it never invents a position that is not in the file.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from brushline.model.validation import ContractValidation, check_duplicates

TIMELINE_SCHEMA_VERSION: Literal["brushline.timeline.v1"] = "brushline.timeline.v1"
RESOURCE_TYPES: tuple[str, ...] = ("crew", "machine", "vehicle", "other")
EVENT_TYPES: tuple[str, ...] = ("travel", "start", "treatment", "pause", "finish", "other")

ResourceType = Literal["crew", "machine", "vehicle", "other"]
EventType = Literal["travel", "start", "treatment", "pause", "finish", "other"]


class TimelineEvent(BaseModel):
    """One timestamped operations event.

    Parameters
    ----------
    event_id : str
        Stable event identifier.
    resource_id : str
        Crew, machine, or vehicle identifier.
    resource_type : {"crew", "machine", "vehicle", "other"}
        Resource class.
    segment_id : str
        Segment identifier.
    event_type : {"travel", "start", "treatment", "pause", "finish", "other"}
        Event class.
    start_utc : datetime
        Timezone-aware start time.
    state : str
        Resource state, such as ``idle`` or ``working``.
    action_id : str or None, optional
        Plan action identifier.
    end_utc : datetime or None, optional
        Timezone-aware end time. Must not be before ``start_utc``.
    cost : float, optional
        Event cost. Defaults to ``0``.
    currency : str, optional
        Currency code. Defaults to ``CAD``.
    notes : str, optional
        Free notes.
    """

    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)

    event_id: str = Field(min_length=1)
    resource_id: str = Field(min_length=1)
    resource_type: ResourceType
    segment_id: str = Field(min_length=1)
    event_type: EventType
    start_utc: datetime
    state: str = Field(min_length=1)
    action_id: str | None = None
    end_utc: datetime | None = None
    cost: float = Field(default=0.0, ge=0)
    currency: str = Field(default="CAD", min_length=1)
    notes: str = ""

    @field_validator("start_utc", "end_utc")
    @classmethod
    def _timezone_aware(cls, value: datetime | None) -> datetime | None:
        if value is not None and (value.tzinfo is None or value.utcoffset() is None):
            raise ValueError("timeline timestamps must be timezone-aware")
        return value

    @model_validator(mode="after")
    def _end_is_after_start(self) -> TimelineEvent:
        if self.end_utc is not None and self.end_utc < self.start_utc:
            raise ValueError("end_utc must not be before start_utc")
        return self


class OperationsTimeline(BaseModel):
    """The operations timeline for one run.

    Parameters
    ----------
    run_id : str
        Run identifier.
    events : list of TimelineEvent
        Timeline events. At least one is required.
    created_utc : datetime
        Timezone-aware creation time.
    created_by : str
        Person, process, or agent that created the timeline.
    """

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["brushline.timeline.v1"] = TIMELINE_SCHEMA_VERSION
    run_id: str = Field(min_length=1)
    events: list[TimelineEvent] = Field(min_length=1)
    created_utc: datetime
    created_by: str = Field(min_length=1)

    @field_validator("created_utc")
    @classmethod
    def _timezone_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("created_utc must be timezone-aware")
        return value


def validate_timeline(
    timeline: OperationsTimeline,
    *,
    known_segment_ids: set[str] | None = None,
) -> ContractValidation:
    """Validate event ids, ordering, and segment references.

    Parameters
    ----------
    timeline : OperationsTimeline
        Timeline to validate.
    known_segment_ids : set of str or None, optional
        Segment ids that the timeline may reference.

    Returns
    -------
    ContractValidation
        Errors, warnings, and counts.
    """
    errors: list[str] = []
    warnings: list[str] = []
    check_duplicates("TIMELINE", "event", [item.event_id for item in timeline.events], errors)
    previous = timeline.events[0].start_utc
    for event in timeline.events:
        if event.start_utc < previous:
            errors.append(
                f"TIMELINE-ORDER: event {event.event_id} starts before the previous event"
            )
        previous = event.start_utc
        if known_segment_ids is not None and event.segment_id not in known_segment_ids:
            errors.append(
                f"TIMELINE-REF: event {event.event_id} references unknown segment "
                f"{event.segment_id}"
            )
        if event.end_utc is None:
            warnings.append(f"TIMELINE-OPEN: event {event.event_id} has no end time")
    counts: dict[str, int | float] = {
        "events": len(timeline.events),
        "resources": len({item.resource_id for item in timeline.events}),
        "segments": len({item.segment_id for item in timeline.events}),
    }
    return ContractValidation(tuple(errors), tuple(warnings), counts)


__all__ = [
    "EVENT_TYPES",
    "RESOURCE_TYPES",
    "TIMELINE_SCHEMA_VERSION",
    "OperationsTimeline",
    "TimelineEvent",
    "validate_timeline",
]
