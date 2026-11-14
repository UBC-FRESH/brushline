"""Source-preserving access and road-status checks."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from brushline.model.state import Season

ACCESS_SCHEMA_VERSION: Literal["brushline.tactical-access.v1"] = "brushline.tactical-access.v1"
ROAD_STATUSES: tuple[str, ...] = ("open", "restricted", "closed", "unknown")


class AccessError(ValueError):
    """Raised when access inputs are inconsistent."""


class RoadLink(BaseModel):
    """One source-preserving road link.

    Parameters
    ----------
    link_id : str
        Link id.
    source : str
        Source name.
    status : str
        Open, restricted, closed, or unknown.
    status_source : str
        Status source.
    length_m : float
        Route length.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    link_id: str = Field(min_length=1)
    source: str = Field(min_length=1)
    status: str
    status_source: str = Field(min_length=1)
    length_m: float = Field(ge=0)

    def model_post_init(self, __context: object) -> None:
        """Validate the source status label."""
        if self.status not in ROAD_STATUSES:
            raise ValueError("unknown road status")


class AccessWindow(BaseModel):
    """One access window.

    Parameters
    ----------
    window_id : str
        Window id.
    unit_id : str
        Treatment unit.
    link_id : str
        Road link.
    year : int
        Year.
    season : str
        Season.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    window_id: str = Field(min_length=1)
    unit_id: str = Field(min_length=1)
    link_id: str = Field(min_length=1)
    year: int = Field(ge=1900, le=2200)
    season: Season


class AccessResult(BaseModel):
    """One access decision.

    Parameters
    ----------
    window_id : str
        Window id.
    allowed : bool
        Whether the action is allowed.
    status : str
        Source status.
    source : str
        Status source.
    route_length_m : float
        Route length.
    reason : str
        Explanation.
    caveats : list of str
        Caveats.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    window_id: str
    allowed: bool
    status: str
    source: str
    route_length_m: float = Field(ge=0)
    reason: str
    caveats: list[str] = Field(default_factory=list)


class AccessPlan(BaseModel):
    """An access plan.

    Parameters
    ----------
    schema_version : {"brushline.tactical-access.v1"}
        Schema version.
    plan_id : str
        Plan id.
    instance_id : str
        Instance id.
    results : list of AccessResult
        Decisions.
    feasible : bool
        All requested windows allowed.
    total_route_m : float
        Total route length.
    created_utc : datetime
        Timezone-aware time.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["brushline.tactical-access.v1"] = ACCESS_SCHEMA_VERSION
    plan_id: str
    instance_id: str
    results: list[AccessResult]
    feasible: bool
    total_route_m: float = Field(ge=0)
    created_utc: datetime


def build_access_plan(
    *,
    plan_id: str,
    instance_id: str,
    windows: list[AccessWindow],
    links: list[RoadLink],
    created_utc: datetime | None = None,
) -> AccessPlan:
    """Check access windows against source road status.

    Parameters
    ----------
    plan_id : str
        Plan id.
    instance_id : str
        Instance id.
    windows : list of AccessWindow
        Windows.
    links : list of RoadLink
        Road links.
    created_utc : datetime, optional
        Creation time.

    Returns
    -------
    AccessPlan
        Source-preserving decisions.
    """
    link_map = {link.link_id: link for link in links}
    if len(link_map) != len(links):
        raise AccessError("road links must be unique")
    results: list[AccessResult] = []
    for window in windows:
        link = link_map.get(window.link_id)
        if link is None:
            raise AccessError(f"window {window.window_id} references an unknown link")
        allowed = link.status == "open"
        reason = {
            "open": "source status is open",
            "restricted": "source status is restricted; operational approval is required",
            "closed": "source status is closed",
            "unknown": "source status is unknown; access is not assumed open",
        }[link.status]
        caveats = []
        if link.status == "unknown":
            caveats.append("unknown is not a negative verdict; verify with the source")
        elif link.status == "restricted":
            caveats.append("restriction terms are not modelled here")
        results.append(
            AccessResult(
                window_id=window.window_id,
                allowed=allowed,
                status=link.status,
                source=link.status_source,
                route_length_m=link.length_m,
                reason=reason,
                caveats=caveats,
            )
        )
    return AccessPlan(
        plan_id=plan_id,
        instance_id=instance_id,
        results=results,
        feasible=all(result.allowed for result in results),
        total_route_m=sum(result.route_length_m for result in results),
        created_utc=created_utc or datetime.now(UTC),
    )


__all__ = [
    "ACCESS_SCHEMA_VERSION",
    "ROAD_STATUSES",
    "AccessError",
    "AccessPlan",
    "AccessResult",
    "AccessWindow",
    "RoadLink",
    "build_access_plan",
]
