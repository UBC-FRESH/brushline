"""Tests for the P8.2 mission simulation."""

from __future__ import annotations

from brushline.monitoring.mission import (
    MissionConfig,
    MissionEdge,
    MissionNode,
    MissionRequest,
    build_mission_plan,
)

NODES = [
    MissionNode(node_id="a", x_m=0, y_m=0),
    MissionNode(node_id="b", x_m=100, y_m=0),
    MissionNode(node_id="c", x_m=200, y_m=0),
]
EDGES = [
    MissionEdge(start_id="a", end_id="b", length_m=100),
    MissionEdge(start_id="b", end_id="c", length_m=100),
]
CONFIG = MissionConfig(
    start_node_id="a",
    endurance_minutes=5,
    speed_m_per_min=100,
    sensor_footprint_m=50,
    cost_per_minute=10,
    fixed_cost=20,
)


def test_mission_route_and_cost() -> None:
    plan = build_mission_plan(
        plan_id="m",
        nodes=NODES,
        edges=EDGES,
        request=MissionRequest(request_id="r", required_node_ids=["c"]),
        config=CONFIG,
    )
    assert plan.feasible
    assert plan.node_order == ["a", "c"]
    assert plan.route_length_m == 200
    assert plan.flight_minutes == 2
    assert plan.cost == 40
    assert plan.covered_node_ids == ["c"]


def test_mission_weather_endurance_and_errors() -> None:
    weather = build_mission_plan(
        plan_id="m",
        nodes=NODES,
        edges=EDGES,
        request=MissionRequest(request_id="r", required_node_ids=["c"], weather_open=False),
        config=CONFIG,
    )
    assert not weather.feasible
    assert "weather" in weather.reason
    short = build_mission_plan(
        plan_id="m",
        nodes=NODES,
        edges=EDGES,
        request=MissionRequest(request_id="r", required_node_ids=["c"]),
        config=MissionConfig(start_node_id="a", endurance_minutes=1, speed_m_per_min=100),
    )
    assert not short.feasible
    assert "endurance" in short.reason
    try:
        build_mission_plan(
            plan_id="m",
            nodes=NODES,
            edges=EDGES,
            request=MissionRequest(request_id="r", required_node_ids=["missing"]),
            config=CONFIG,
        )
    except ValueError:
        pass
    else:
        raise AssertionError("unknown node accepted")
