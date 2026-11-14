"""Bid normalization and fair-price comparison."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from brushline.exchange.contractor import ContractorBid
from brushline.exchange.plan import PlanExchange


class BidComparison(BaseModel):
    """Owner-plan versus contractor-bid comparison."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    plan_id: str
    owner_total: float = Field(ge=0)
    bid_total: float = Field(ge=0)
    delta: float
    fair_low: float = Field(ge=0)
    fair_high: float = Field(ge=0)
    within_fair_range: bool
    named_assumptions: list[str]
    rate_differences: dict[str, float]
    scope_differences: list[str]
    attributable: bool


def compare_bid(
    exchange: PlanExchange,
    bid: ContractorBid,
    *,
    fair_low: float,
    fair_high: float,
) -> BidComparison:
    """Compare a bid to the shared plan and record every difference source."""
    if bid.plan_id != exchange.plan.header.plan_id:
        raise ValueError("bid references a different plan")
    owner_total = exchange.cost_buildup.total_cost
    rate_differences: dict[str, float] = {}
    for action in exchange.plan.actions:
        for line in action.cost_lines:
            rate_differences[line.category] = rate_differences.get(line.category, 0.0) + line.amount
    for category, amount in bid.cost_lines.items():
        rate_differences[category] = round(amount - rate_differences.get(category, 0.0), 2)
    assumptions = list(bid.assumptions)
    if bid.access_cost:
        assumptions.append("Bid includes access cost.")
    scope = (
        []
        if set(bid.quantities) == {a.action_id for a in exchange.plan.actions}
        else ["quantity scope differs"]
    )
    attributable = bool(rate_differences or assumptions or scope or bid.access_cost)
    return BidComparison(
        plan_id=bid.plan_id,
        owner_total=owner_total,
        bid_total=bid.total_cost,
        delta=round(bid.total_cost - owner_total, 2),
        fair_low=fair_low,
        fair_high=fair_high,
        within_fair_range=fair_low <= bid.total_cost <= fair_high,
        named_assumptions=assumptions,
        rate_differences={k: v for k, v in rate_differences.items() if abs(v) > 0.001},
        scope_differences=scope,
        attributable=attributable,
    )
