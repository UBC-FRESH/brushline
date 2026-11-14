"""Tests for the P7.3 access plan."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from brushline.tactical.access import (
    AccessError,
    AccessWindow,
    RoadLink,
    build_access_plan,
)
from pydantic import ValidationError

NOW = datetime(2026, 11, 14, tzinfo=UTC)


def _links() -> list[RoadLink]:
    return [
        RoadLink(
            link_id="l1", source="fresh-road", status="open", status_source="als", length_m=100
        ),
        RoadLink(
            link_id="l2", source="fresh-road", status="unknown", status_source="als", length_m=200
        ),
        RoadLink(
            link_id="l3", source="fresh-road", status="restricted", status_source="als", length_m=50
        ),
        RoadLink(
            link_id="l4", source="fresh-road", status="closed", status_source="als", length_m=10
        ),
    ]


def _window(link_id: str = "l1") -> AccessWindow:
    return AccessWindow(window_id="w1", unit_id="u1", link_id=link_id, year=2026, season="spring")


def test_open_is_allowed_and_unknown_is_not_open() -> None:
    """Source status is preserved; unknown and restricted are not silently open."""
    plan = build_access_plan(plan_id="a", instance_id="tiny", windows=[_window()], links=_links())
    assert plan.feasible
    assert plan.results[0].allowed
    assert plan.results[0].source == "als"
    assert plan.total_route_m == 100
    for link in ("l2", "l3", "l4"):
        plan = build_access_plan(
            plan_id="a", instance_id="tiny", windows=[_window(link)], links=_links()
        )
        assert not plan.feasible
        assert not plan.results[0].allowed
        assert plan.results[0].caveats or plan.results[0].status == "closed"


def test_missing_link_and_duplicate_links() -> None:
    """Unknown links and duplicate sources fail explicitly."""
    with pytest.raises(AccessError):
        build_access_plan(
            plan_id="a", instance_id="tiny", windows=[_window("missing")], links=_links()
        )
    with pytest.raises(AccessError):
        build_access_plan(
            plan_id="a", instance_id="tiny", windows=[], links=[_links()[0], _links()[0]]
        )
    with pytest.raises(ValidationError):
        RoadLink(link_id="x", source="s", status="maybe", status_source="s", length_m=1)
    with pytest.raises(ValidationError):
        AccessWindow.model_validate(
            {"window_id": "w", "unit_id": "u", "link_id": "l", "year": 2026, "season": "monsoon"}
        )
