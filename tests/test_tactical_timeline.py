"""Tests for the P7.6 operations timeline."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from brushline.tactical.access import AccessWindow, RoadLink, build_access_plan
from brushline.tactical.operations import OperationsConfig, OperationsPlan, build_operations_plan
from brushline.tactical.program import (
    TacticalAction,
    TacticalConfig,
    TreatmentUnit,
    build_tactical_program,
)
from brushline.tactical.timeline import (
    GeoPoint,
    OperationEvent,
    TimelineConfig,
    build_operations_timeline,
)
from pydantic import ValidationError

NOW = datetime(2026, 11, 14, tzinfo=UTC)


def _operations() -> OperationsPlan:
    units = [
        TreatmentUnit(
            unit_id="u1",
            span_id="sp",
            segment_ids=["s1"],
            area_ha=1,
            allowed_methods=["mowing"],
            allowed_seasons=["spring"],
        )
    ]
    actions = [
        TacticalAction(
            action_id="a1",
            unit_id="u1",
            year=2026,
            season="spring",
            method="mowing",
            contractor_id="c1",
            cost=100,
            capacity_units=1,
            access_window_id="w1",
        ),
        TacticalAction(
            action_id="a2",
            unit_id="u1",
            year=2026,
            season="spring",
            method="mowing",
            contractor_id="c1",
            cost=100,
            capacity_units=1,
            access_window_id="w2",
        ),
    ]
    program = build_tactical_program(
        program_id="p",
        instance_id="tiny",
        units=units,
        actions=actions,
        config=TacticalConfig(horizon_years=1, start_year=2026, budget_by_year={2026: 500}),
        created_utc=NOW,
    )
    links = [
        RoadLink(
            link_id="l1", source="fresh-road", status="open", status_source="als", length_m=10
        ),
        RoadLink(
            link_id="l2", source="fresh-road", status="open", status_source="als", length_m=20
        ),
    ]
    windows = [
        AccessWindow(window_id="w1", unit_id="u1", link_id="l1", year=2026, season="spring"),
        AccessWindow(window_id="w2", unit_id="u1", link_id="l2", year=2026, season="spring"),
    ]
    access = build_access_plan(plan_id="a", instance_id="tiny", windows=windows, links=links)
    return build_operations_plan(
        plan_id="ops",
        instance_id="tiny",
        program=program,
        access=access,
        config=OperationsConfig(max_orders_per_day=1),
        created_utc=NOW,
    )


def test_timeline_has_start_finish_and_explicit_positions() -> None:
    """Known positions are preserved; missing positions remain unknown."""
    plan = _operations()
    timeline = build_operations_timeline(
        timeline_id="t",
        instance_id="tiny",
        plan=plan,
        config=TimelineConfig(
            start_time=datetime(2026, 3, 1, tzinfo=UTC),
            positions={"wo-a1": GeoPoint(latitude=49.0, longitude=-123.0)},
        ),
        created_utc=NOW,
    )
    assert len(timeline.events) == 4
    assert timeline.total_cost == 200
    assert timeline.unknown_position_events == 2
    known = [event for event in timeline.events if event.position_status == "known"]
    assert len(known) == 2
    assert all(event.segment_ids == ["s1"] for event in timeline.events)
    assert timeline.events[0].event_type == "start"
    assert timeline.events[1].timestamp > timeline.events[0].timestamp
    assert timeline.created_utc == NOW


def test_timeline_model_guards() -> None:
    """Position consistency and timezone-aware start are required."""
    with pytest.raises(ValidationError):
        OperationEvent(
            event_id="e",
            event_type="start",
            timestamp=NOW,
            work_order_id="w",
            action_id="a",
            unit_id="u",
            segment_ids=[],
            crew_id="c",
            cost=1,
            position=None,
            position_status="known",
        )
    with pytest.raises(ValidationError):
        OperationEvent(
            event_id="e",
            event_type="unknown",
            timestamp=NOW,
            work_order_id="w",
            action_id="a",
            unit_id="u",
            segment_ids=[],
            crew_id="c",
            cost=1,
            position=None,
            position_status="unknown",
        )
    with pytest.raises(ValueError, match="timezone"):
        build_operations_timeline(
            timeline_id="t",
            instance_id="tiny",
            plan=_operations(),
            config=TimelineConfig(start_time=datetime(2026, 3, 1)),
        )
