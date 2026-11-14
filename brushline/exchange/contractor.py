"""Contractor bid view of the shared plan."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from brushline.exchange.plan import PlanExchange


class ContractorBid(BaseModel):
    """Contractor-facing bid built from the same plan actions."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    plan_id: str
    version: int
    contractor_id: str
    currency: str
    quantities: dict[str, float]
    access_cost: float = Field(ge=0)
    schedule_days: int = Field(ge=1)
    productivity: float = Field(gt=0)
    cost_lines: dict[str, float]
    assumptions: list[str]
    total_cost: float = Field(ge=0)


def build_contractor_bid(
    exchange: PlanExchange,
    *,
    contractor_id: str,
    access_cost: float = 0,
    schedule_days: int = 1,
    productivity: float = 1.0,
    rate_adjustments: dict[str, float] | None = None,
    assumptions: list[str] | None = None,
) -> ContractorBid:
    """Build a contractor bid with named rate adjustments."""
    adjustments = rate_adjustments or {}
    lines: dict[str, float] = {}
    quantities: dict[str, float] = {}
    for action in exchange.plan.actions:
        quantities[action.action_id] = action.quantity_ha + action.quantity_km
        for line in action.cost_lines:
            factor = 1.0 + adjustments.get(line.category, 0.0)
            lines[line.category] = lines.get(line.category, 0.0) + line.amount * factor
    total = sum(lines.values()) + access_cost
    return ContractorBid(
        plan_id=exchange.plan.header.plan_id,
        version=exchange.plan.header.version,
        contractor_id=contractor_id,
        currency=exchange.plan.header.currency,
        quantities=quantities,
        access_cost=access_cost,
        schedule_days=schedule_days,
        productivity=productivity,
        cost_lines={key: round(value, 2) for key, value in sorted(lines.items())},
        assumptions=assumptions or ["Bid uses the shared plan quantities and rates."],
        total_cost=round(total, 2),
    )
