from __future__ import annotations

from pathlib import Path

from brushline.exchange.bids import compare_bid
from brushline.exchange.owner import build_owner_view
from brushline.exchange.validation import build_synthetic_exchange, write_validation


def test_exchange_views_and_validation() -> None:
    exchange, owner, bid, comparison, approval, validation = build_synthetic_exchange()
    assert owner.plan_id == bid.plan_id == exchange.plan.header.plan_id
    assert owner.total_cost == exchange.cost_buildup.total_cost == 120
    assert bid.total_cost > 120
    assert comparison.attributable
    assert comparison.rate_differences
    assert approval.status == "approved"
    assert validation.checks_passed
    path = Path(__file__).resolve().parents[1] / "notes/reference/p9-validation.v1.json"
    write_validation(validation, path)
    assert "cost_reproduced" in path.read_text()


def test_bid_views_and_approval() -> None:
    exchange, _, bid, _comparison, _, _ = build_synthetic_exchange()
    assert (
        build_owner_view(exchange, budget=100, service_attainment=0.5, risk=0.5).budget_remaining
        == -20
    )
    assert compare_bid(exchange, bid, fair_low=1, fair_high=999).within_fair_range
    try:
        compare_bid(
            exchange, bid.model_copy(update={"plan_id": "other"}), fair_low=1, fair_high=999
        )
    except ValueError:
        pass
    else:
        raise AssertionError("different plan accepted")
