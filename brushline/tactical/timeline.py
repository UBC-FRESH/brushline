"""Operations timeline and 3D data contract."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from brushline.tactical.operations import OperationsPlan

TIMELINE_SCHEMA_VERSION: Literal["brushline.tactical-timeline.v1"] = (
    "brushline.tactical-timeline.v1"
)


class GeoPoint(BaseModel):
    """A known position.

    Parameters
    ----------
    latitude : float
        Latitude.
    longitude : float
        Longitude.
    height_m : float or None
        Optional height.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    height_m: float | None = None


class TimelineConfig(BaseModel):
    """Timeline settings.

    Parameters
    ----------
    start_time : datetime
        Start timestamp.
    shift_hours : float
        Event duration.
    positions : dict of str to GeoPoint
        Known positions by work-order id. Missing ids are unknown, not invented.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    start_time: datetime
    shift_hours: float = Field(default=8.0, gt=0, le=24)
    positions: dict[str, GeoPoint] = Field(default_factory=dict)


class OperationEvent(BaseModel):
    """One timestamped operation event.

    Parameters
    ----------
    event_id : str
        Event id.
    event_type : {"start", "finish"}
        Event type.
    timestamp : datetime
        Timestamp.
    work_order_id : str
        Source work order.
    action_id : str
        Source action.
    unit_id : str
        Unit.
    segment_ids : list of str
        Segments.
    crew_id : str
        Crew.
    machine_id : str or None
        Machine.
    cost : float
        Cost on the start event; zero on finish.
    position : GeoPoint or None
        Known position.
    position_status : {"known", "unknown"}
        Position state.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    event_id: str
    event_type: str
    timestamp: datetime
    work_order_id: str
    action_id: str
    unit_id: str
    segment_ids: list[str]
    crew_id: str
    machine_id: str | None = None
    cost: float = Field(ge=0)
    position: GeoPoint | None = None
    position_status: str

    def model_post_init(self, __context: object) -> None:
        """Validate event type and position consistency."""
        if self.event_type not in {"start", "finish"}:
            raise ValueError("unknown event type")
        if (self.position is None) != (self.position_status == "unknown"):
            raise ValueError("position and position_status disagree")


class OperationsTimeline(BaseModel):
    """A deterministic operations timeline.

    Parameters
    ----------
    schema_version : {"brushline.tactical-timeline.v1"}
        Schema version.
    timeline_id : str
        Timeline id.
    instance_id : str
        Instance id.
    source_plan_id : str
        Source operations plan.
    events : list of OperationEvent
        Events.
    total_cost : float
        Work-order cost.
    unknown_position_events : int
        Events without a known position.
    created_utc : datetime
        Timezone-aware time.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["brushline.tactical-timeline.v1"] = TIMELINE_SCHEMA_VERSION
    timeline_id: str
    instance_id: str
    source_plan_id: str
    events: list[OperationEvent]
    total_cost: float = Field(ge=0)
    unknown_position_events: int = Field(ge=0)
    created_utc: datetime


def build_operations_timeline(
    *,
    timeline_id: str,
    instance_id: str,
    plan: OperationsPlan,
    config: TimelineConfig,
    created_utc: datetime | None = None,
) -> OperationsTimeline:
    """Build start/finish events without inventing positions.

    Parameters
    ----------
    timeline_id : str
        Timeline id.
    instance_id : str
        Instance id.
    plan : OperationsPlan
        Operations plan.
    config : TimelineConfig
        Settings.
    created_utc : datetime, optional
        Creation time.

    Returns
    -------
    OperationsTimeline
        Timeline.
    """
    if config.start_time.tzinfo is None:
        raise ValueError("start_time must be timezone-aware")
    events: list[OperationEvent] = []
    for order in sorted(
        plan.work_orders, key=lambda item: (item.year, item.day, item.work_order_id)
    ):
        position = config.positions.get(order.work_order_id)
        start = config.start_time + timedelta(days=order.day - 1)
        for event_type, timestamp, cost in (
            ("start", start, order.cost),
            ("finish", start + timedelta(hours=config.shift_hours), 0.0),
        ):
            events.append(
                OperationEvent(
                    event_id=f"{order.work_order_id}-{event_type}",
                    event_type=event_type,
                    timestamp=timestamp,
                    work_order_id=order.work_order_id,
                    action_id=order.action_id,
                    unit_id=order.unit_id,
                    segment_ids=list(order.segment_ids),
                    crew_id=order.crew_id,
                    machine_id=order.machine_id,
                    cost=cost,
                    position=position,
                    position_status="known" if position is not None else "unknown",
                )
            )
    return OperationsTimeline(
        timeline_id=timeline_id,
        instance_id=instance_id,
        source_plan_id=plan.plan_id,
        events=events,
        total_cost=sum(order.cost for order in plan.work_orders),
        unknown_position_events=sum(1 for event in events if event.position_status == "unknown"),
        created_utc=created_utc or datetime.now(UTC),
    )


__all__ = [
    "TIMELINE_SCHEMA_VERSION",
    "GeoPoint",
    "OperationEvent",
    "OperationsTimeline",
    "TimelineConfig",
    "build_operations_timeline",
]
