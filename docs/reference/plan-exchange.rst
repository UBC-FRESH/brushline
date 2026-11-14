Plan and bid exchange
=====================

P9 makes the existing `brushline.plan.v1` artifact the shared owner-contractor surface.

- `cost_buildup` groups line items by category and reproduces the plan total to the cent.
- `OwnerView` reports budget, remaining budget, service, risk, portfolio, BAU, and assumptions.
- `ContractorBid` derives quantities and cost lines from the same plan; rate adjustments and access cost are named.
- `compare_bid` reports owner/bid totals, delta, fair-price range, named assumptions, rate differences, scope differences, and attributability.
- `ApprovalRecord` records plan version, reviewer, status, comment, plan digest, and time.

The synthetic validation confirms one artifact, reproduced cost, attributable differences, a fair-range bid, and an approval record.
