"""Tests for the P7.4 operational work plan."""

from __future__ import annotations

from datetime import UTC, datetime

from brushline.tactical.access import AccessPlan, AccessWindow, RoadLink, build_access_plan
from brushline.tactical.operations import OperationsConfig, build_operations_plan
from brushline.tactical.program import (
    TacticalAction,
    TacticalConfig,
    TacticalProgram,
    TreatmentUnit,
    build_tactical_program,
)

NOW = datetime(2026, 11, 14, tzinfo=UTC)


def _program(access: str | None = "w1") -> TacticalProgram:
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
            access_window_id=access,
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
    return build_tactical_program(
        program_id="p",
        instance_id="tiny",
        units=units,
        actions=actions,
        config=TacticalConfig(horizon_years=1, start_year=2026, budget_by_year={2026: 500}),
        created_utc=NOW,
    )


def _access(status: str = "open") -> AccessPlan:
    links = [
        RoadLink(
            link_id="l1", source="fresh-road", status=status, status_source="als", length_m=10
        ),
        RoadLink(
            link_id="l2", source="fresh-road", status="open", status_source="als", length_m=20
        ),
    ]
    windows = [
        AccessWindow(window_id="w1", unit_id="u1", link_id="l1", year=2026, season="spring"),
        AccessWindow(window_id="w2", unit_id="u1", link_id="l2", year=2026, season="spring"),
    ]
    return build_access_plan(plan_id="a", instance_id="tiny", windows=windows, links=links)


def test_work_orders_trace_to_actions_and_respect_access() -> None:
    """Every work order traces to one tactical action and an open access window."""
    plan = build_operations_plan(
        plan_id="ops",
        instance_id="tiny",
        program=_program(),
        access=_access(),
        config=OperationsConfig(max_orders_per_day=1, crew_ids=["c1", "c2"]),
        created_utc=NOW,
    )
    assert plan.feasible
    assert len(plan.work_orders) == 2
    assert plan.total_cost == 200
    assert [order.action_id for order in plan.work_orders] == ["a1", "a2"]
    assert {order.crew_id for order in plan.work_orders} == {"c1", "c2"}
    assert plan.work_orders[0].day == 1
    assert plan.work_orders[1].day == 2
    assert plan.created_utc == NOW


def test_blocked_missing_access_and_missing_window() -> None:
    """Blocked or absent access prevents scheduling and is explicit."""
    blocked = build_operations_plan(
        plan_id="ops", instance_id="tiny", program=_program(), access=_access("unknown")
    )
    assert not blocked.feasible
    assert any(v.code == "OPERATIONS-ACCESS-BLOCKED" for v in blocked.violations)
    missing = build_operations_plan(
        plan_id="ops", instance_id="tiny", program=_program(None), access=_access()
    )
    assert not missing.feasible
    assert any(v.code == "OPERATIONS-ACCESS-MISSING" for v in missing.violations)
    no_result = build_operations_plan(
        plan_id="ops",
        instance_id="tiny",
        program=_program("missing"),
        access=_access(),
    )
    assert not no_result.feasible
    assert any(v.code == "OPERATIONS-ACCESS-MISSING" for v in no_result.violations)
