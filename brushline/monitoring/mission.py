"""Corridor-graph UAV/LiDAR mission simulation."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

MISSION_SCHEMA_VERSION: Literal["brushline.monitoring-mission.v1"] = (
    "brushline.monitoring-mission.v1"
)


class MissionError(ValueError):
    """Raised when a mission input is inconsistent."""


class MissionNode(BaseModel):
    """One corridor-graph node.

    Parameters
    ----------
    node_id : str
        Node id.
    x_m : float
        X coordinate.
    y_m : float
        Y coordinate.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    node_id: str = Field(min_length=1)
    x_m: float
    y_m: float


class MissionEdge(BaseModel):
    """One undirected corridor-graph edge.

    Parameters
    ----------
    start_id : str
        Start node.
    end_id : str
        End node.
    length_m : float
        Length.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    start_id: str = Field(min_length=1)
    end_id: str = Field(min_length=1)
    length_m: float = Field(gt=0)


class MissionRequest(BaseModel):
    """A monitor mission request.

    Parameters
    ----------
    request_id : str
        Request id.
    required_node_ids : list of str
        Nodes that must be covered.
    weather_open : bool
        Whether the weather window is open.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    request_id: str = Field(min_length=1)
    required_node_ids: list[str] = Field(min_length=1)
    weather_open: bool = True


class MissionConfig(BaseModel):
    """Mission settings.

    Parameters
    ----------
    start_node_id : str
        Start node.
    endurance_minutes : float
        Flight endurance.
    speed_m_per_min : float
        Travel speed.
    sensor_footprint_m : float
        Sensor footprint radius.
    cost_per_minute : float
        Flight cost.
    fixed_cost : float
        Fixed mission cost.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    start_node_id: str = Field(min_length=1)
    endurance_minutes: float = Field(default=45, gt=0)
    speed_m_per_min: float = Field(default=300, gt=0)
    sensor_footprint_m: float = Field(default=50, gt=0)
    cost_per_minute: float = Field(default=5, ge=0)
    fixed_cost: float = Field(default=100, ge=0)


class MissionPlan(BaseModel):
    """A feasible or blocked mission.

    Parameters
    ----------
    schema_version : {"brushline.monitoring-mission.v1"}
        Schema version.
    plan_id : str
        Plan id.
    request_id : str
        Request id.
    node_order : list of str
        Visited node order.
    covered_node_ids : list of str
        Covered nodes.
    route_length_m : float
        Route length.
    flight_minutes : float
        Flight time.
    cost : float
        Cost.
    feasible : bool
        Endurance/weather/route feasibility.
    reason : str
        Explanation.
    created_utc : datetime
        Timezone-aware time.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["brushline.monitoring-mission.v1"] = MISSION_SCHEMA_VERSION
    plan_id: str
    request_id: str
    node_order: list[str]
    covered_node_ids: list[str]
    route_length_m: float = Field(ge=0)
    flight_minutes: float = Field(ge=0)
    cost: float = Field(ge=0)
    feasible: bool
    reason: str
    created_utc: datetime


def build_mission_plan(
    *,
    plan_id: str,
    nodes: list[MissionNode],
    edges: list[MissionEdge],
    request: MissionRequest,
    config: MissionConfig,
    created_utc: datetime | None = None,
) -> MissionPlan:
    """Build a deterministic nearest-neighbour mission and check feasibility.

    Parameters
    ----------
    plan_id : str
        Plan id.
    nodes : list of MissionNode
        Nodes.
    edges : list of MissionEdge
        Edges.
    request : MissionRequest
        Request.
    config : MissionConfig
        Settings.
    created_utc : datetime, optional
        Creation time.

    Returns
    -------
    MissionPlan
        Mission plan.
    """
    node_map = {node.node_id: node for node in nodes}
    if len(node_map) != len(nodes):
        raise MissionError("mission nodes must be unique")
    if config.start_node_id not in node_map:
        raise MissionError("start node is unknown")
    for node_id in request.required_node_ids:
        if node_id not in node_map:
            raise MissionError(f"required node {node_id!r} is unknown")
    adjacency: dict[str, list[tuple[str, float]]] = {}
    for edge in edges:
        if edge.start_id not in node_map or edge.end_id not in node_map:
            raise MissionError("edge references an unknown node")
        adjacency.setdefault(edge.start_id, []).append((edge.end_id, edge.length_m))
        adjacency.setdefault(edge.end_id, []).append((edge.start_id, edge.length_m))
    remaining = set(request.required_node_ids)
    order = [config.start_node_id]
    route = 0.0
    current = config.start_node_id
    while remaining:
        options = sorted(
            (distance, target)
            for target in remaining
            if target in _reachable(current, adjacency)
            for distance in [_shortest(adjacency, current, target)]
            if distance is not None
        )
        if not options:
            break
        distance, target = options[0]
        route += distance
        order.append(target)
        remaining.remove(target)
        current = target
    flight = route / config.speed_m_per_min
    feasible = request.weather_open and not remaining and flight <= config.endurance_minutes
    reason = "feasible"
    if not request.weather_open:
        reason = "weather window is closed"
    elif remaining:
        reason = "required nodes are unreachable"
    elif flight > config.endurance_minutes:
        reason = "endurance exceeded"
    return MissionPlan(
        plan_id=plan_id,
        request_id=request.request_id,
        node_order=order,
        covered_node_ids=order[1:] if feasible else [],
        route_length_m=route,
        flight_minutes=flight,
        cost=config.fixed_cost + flight * config.cost_per_minute,
        feasible=feasible,
        reason=reason,
        created_utc=created_utc or datetime.now(UTC),
    )


def _distance(left: MissionNode, right: MissionNode) -> float:
    return float(((left.x_m - right.x_m) ** 2 + (left.y_m - right.y_m) ** 2) ** 0.5)


def _reachable(node_id: str, adjacency: dict[str, list[tuple[str, float]]]) -> set[str]:
    seen = {node_id}
    stack = [node_id]
    while stack:
        current = stack.pop()
        for neighbour, _ in adjacency.get(current, []):
            if neighbour not in seen:
                seen.add(neighbour)
                stack.append(neighbour)
    return seen


def _shortest(
    adjacency: dict[str, list[tuple[str, float]]], start: str, target: str
) -> float | None:
    distances: dict[str, float] = {start: 0.0}
    unvisited = {start}
    while unvisited:
        current = min(unvisited, key=lambda item: distances[item])
        unvisited.remove(current)
        if current == target:
            return distances[current]
        for neighbour, weight in adjacency.get(current, []):
            candidate = distances[current] + weight
            if candidate < distances.get(neighbour, float("inf")):
                distances[neighbour] = candidate
                unvisited.add(neighbour)
    return None


__all__ = [
    "MISSION_SCHEMA_VERSION",
    "MissionConfig",
    "MissionEdge",
    "MissionError",
    "MissionNode",
    "MissionPlan",
    "MissionRequest",
    "build_mission_plan",
]
