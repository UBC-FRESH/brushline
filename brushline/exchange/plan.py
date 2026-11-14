"""Shared plan cost build-up for owner and contractor exchange."""

from __future__ import annotations

from collections import defaultdict
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from brushline.model.plan import Plan, validate_plan

EXCHANGE_SCHEMA_VERSION: Literal["brushline.plan-exchange.v1"] = "brushline.plan-exchange.v1"


class CostCategoryTotal(BaseModel):
    """Cost total for one category."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    category: str
    amount: float = Field(ge=0)
    line_count: int = Field(ge=0)


class CostBuildUp(BaseModel):
    """A reproducible plan cost build-up."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["brushline.plan-exchange.v1"] = EXCHANGE_SCHEMA_VERSION
    plan_id: str
    currency: str
    categories: list[CostCategoryTotal]
    total_cost: float = Field(ge=0)
    action_count: int = Field(ge=1)


class PlanExchange(BaseModel):
    """The single shared plan artifact plus its cost build-up."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["brushline.plan-exchange.v1"] = EXCHANGE_SCHEMA_VERSION
    plan: Plan
    cost_buildup: CostBuildUp


def cost_buildup(plan: Plan) -> CostBuildUp:
    """Build category totals from line items and reject cent-level drift.

    Parameters
    ----------
    plan : Plan
        Plan artifact.

    Returns
    -------
    CostBuildUp
        Category totals and exact plan total.

    Raises
    ------
    ValueError
        When the plan is invalid or totals disagree by more than a cent.
    """
    validation = validate_plan(plan)
    if not validation.is_valid:
        raise ValueError("; ".join(validation.errors))
    totals: dict[str, float] = defaultdict(float)
    counts: dict[str, int] = defaultdict(int)
    for action in plan.actions:
        for line in action.cost_lines:
            totals[line.category] += line.amount
            counts[line.category] += 1
    total = round(sum(totals.values()), 2)
    if abs(total - round(plan.total_cost, 2)) > 0.01:
        raise ValueError("cost build-up does not reproduce the plan total")
    return CostBuildUp(
        plan_id=plan.header.plan_id,
        currency=plan.header.currency,
        categories=[
            CostCategoryTotal(category=key, amount=round(value, 2), line_count=counts[key])
            for key, value in sorted(totals.items())
        ],
        total_cost=total,
        action_count=len(plan.actions),
    )


def build_exchange(plan: Plan) -> PlanExchange:
    """Validate a plan and attach its cost build-up."""
    return PlanExchange(plan=plan, cost_buildup=cost_buildup(plan))


__all__ = [
    "EXCHANGE_SCHEMA_VERSION",
    "CostBuildUp",
    "CostCategoryTotal",
    "PlanExchange",
    "build_exchange",
    "cost_buildup",
]
