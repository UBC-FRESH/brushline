"""Synthetic owner-contractor exchange validation."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict

from brushline.exchange.audit import ApprovalRecord, approve_plan
from brushline.exchange.bids import BidComparison, compare_bid
from brushline.exchange.contractor import ContractorBid, build_contractor_bid
from brushline.exchange.owner import OwnerView, build_owner_view
from brushline.exchange.plan import PlanExchange, build_exchange
from brushline.model.plan import CostLine, Plan, PlanAction, PlanHeader

VALIDATION_SCHEMA_VERSION: Literal["brushline.exchange-validation.v1"] = (
    "brushline.exchange-validation.v1"
)


class ExchangeValidation(BaseModel):
    """Synthetic exchange checks."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["brushline.exchange-validation.v1"] = VALIDATION_SCHEMA_VERSION
    plan_id: str
    same_artifact: bool
    cost_reproduced: bool
    bid_attributable: bool
    within_fair_range: bool
    approval_reviewer: str
    checks_passed: bool
    created_utc: datetime


def build_synthetic_exchange(
    created_utc: datetime | None = None,
) -> tuple[
    PlanExchange, OwnerView, ContractorBid, BidComparison, ApprovalRecord, ExchangeValidation
]:
    """Build a shared plan, owner view, bid, comparison, approval, and validation."""
    created = created_utc or datetime(2026, 11, 14, tzinfo=UTC)
    header = PlanHeader(
        plan_id="p9-plan",
        version=1,
        status="proposed",
        scenario_id="p9-scenario",
        dataset_id="p9-dataset",
        data_version="v1",
        model_versions={"state": "v1", "growth": "v1"},
        currency="CAD",
        created_utc=created,
        created_by="brushline",
    )
    plan = Plan(
        header=header,
        actions=[
            PlanAction(
                action_id="a1",
                segment_id="s1",
                year=2026,
                season="spring",
                method="mowing",
                intensity=0.7,
                quantity_ha=1.0,
                cost_lines=[
                    CostLine(category="labour", amount=100, quantity=1, rate=100),
                    CostLine(category="travel", amount=20),
                ],
                assumptions=["One hectare; spring window."],
            )
        ],
    )
    exchange = build_exchange(plan)
    owner = build_owner_view(
        exchange,
        budget=200,
        service_attainment=0.8,
        risk=0.2,
        portfolio={"present_cost": 120},
        bau={"present_cost": 160},
    )
    bid = build_contractor_bid(
        exchange,
        contractor_id="c1",
        access_cost=10,
        schedule_days=1,
        productivity=0.2,
        rate_adjustments={"labour": 0.1},
        assumptions=["Bid includes a 10% labour adjustment."],
    )
    comparison = compare_bid(exchange, bid, fair_low=100, fair_high=160)
    approval = approve_plan(
        plan_id=plan.header.plan_id,
        version=plan.header.version,
        reviewer="reviewer-1",
        status="approved",
        plan=exchange,
        comment="Synthetic approval.",
        created_utc=created,
    )
    validation = ExchangeValidation(
        plan_id=plan.header.plan_id,
        same_artifact=owner.plan_id == bid.plan_id == exchange.plan.header.plan_id,
        cost_reproduced=abs(owner.total_cost - exchange.cost_buildup.total_cost) < 0.01,
        bid_attributable=comparison.attributable,
        within_fair_range=comparison.within_fair_range,
        approval_reviewer=approval.reviewer,
        checks_passed=all(
            [
                owner.plan_id == bid.plan_id,
                abs(owner.total_cost - exchange.cost_buildup.total_cost) < 0.01,
                comparison.attributable,
                comparison.within_fair_range,
                approval.status == "approved",
            ]
        ),
        created_utc=created,
    )
    return exchange, owner, bid, comparison, approval, validation


def write_validation(result: ExchangeValidation, path: str | Path) -> Path:
    """Write validation JSON."""
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(result.model_dump_json(indent=2) + "\n", encoding="utf-8")
    return destination
