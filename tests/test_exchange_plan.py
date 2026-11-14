from __future__ import annotations

from datetime import UTC, datetime

from brushline.exchange.plan import build_exchange, cost_buildup
from brushline.model.plan import CostLine, Plan, PlanAction, PlanHeader

NOW = datetime(2026, 11, 14, tzinfo=UTC)
HEADER = PlanHeader(
    plan_id="p",
    version=1,
    status="draft",
    scenario_id="s",
    dataset_id="d",
    data_version="v",
    model_versions={"m": "1"},
    currency="CAD",
    created_utc=NOW,
    created_by="test",
)


def plan() -> Plan:
    return Plan(
        header=HEADER,
        actions=[
            PlanAction(
                action_id="a",
                segment_id="s1",
                year=2026,
                season="spring",
                method="mowing",
                intensity=0.5,
                cost_lines=[
                    CostLine(category="labour", amount=100, quantity=1, rate=100),
                    CostLine(category="travel", amount=20),
                ],
                assumptions=["rate"],
            )
        ],
    )


def test_cost_buildup_and_exchange() -> None:
    p = plan()
    b = cost_buildup(p)
    assert b.total_cost == 120
    assert b.action_count == 1
    assert {c.category for c in b.categories} == {"labour", "travel"}
    ex = build_exchange(p)
    assert ex.cost_buildup.total_cost == p.total_cost
    assert ex.cost_buildup.currency == "CAD"
