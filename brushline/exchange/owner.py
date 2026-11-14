"""Owner view of a shared plan."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from brushline.exchange.plan import PlanExchange


class OwnerView(BaseModel):
    """Owner-facing plan summary."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    plan_id: str
    version: int
    currency: str
    total_cost: float = Field(ge=0)
    budget: float = Field(ge=0)
    budget_remaining: float
    service_attainment: float = Field(ge=0, le=1)
    risk: float = Field(ge=0, le=1)
    portfolio: dict[str, float]
    bau: dict[str, float]
    assumptions: list[str]


def build_owner_view(
    exchange: PlanExchange,
    *,
    budget: float,
    service_attainment: float,
    risk: float,
    portfolio: dict[str, float] | None = None,
    bau: dict[str, float] | None = None,
) -> OwnerView:
    """Build the owner summary from the shared plan exchange."""
    total = exchange.cost_buildup.total_cost
    return OwnerView(
        plan_id=exchange.plan.header.plan_id,
        version=exchange.plan.header.version,
        currency=exchange.plan.header.currency,
        total_cost=total,
        budget=budget,
        budget_remaining=budget - total,
        service_attainment=service_attainment,
        risk=risk,
        portfolio=portfolio or {},
        bau=bau or {},
        assumptions=[item.statement for item in exchange.plan.assumptions],
    )
