# Phase close-out report: P8 Monitoring and adaptive replanning

Parent issue: #78
Pull request: pending
Evidence head: `129d1c0`
Status: queued for approval. Not merged.

## Delivered

- P8.1 observation model: coverage, detection, confusion, error, confidence, latency.
- P8.2 mission simulation: corridor graph, route, endurance, footprint, weather, cost.
- P8.3 value of information: expected loss reduction, cost, regret per dollar, fixed calendar.
- P8.4 recalibration: posterior state, uncertainty, parameter, model-card version.
- P8.5 replan trigger: forecast error and uncertainty thresholds, new plan id.
- P8.6 synthetic validation: adaptive regret/dollar 5.0 vs fixed 1.33; posterior confidence increased; replan triggered.

## Limits

Synthetic-only; no live sensor, UAV control, field data, or production safety/optimality claim. Value of information is an approximation. The fixed calendar is a deterministic baseline, not the owner's actual calendar.

## Verification

Local dashboard `OVERALL: GREEN`; pytest 763 passed with 98% coverage; validator 0 errors. No merge, branch deletion, parent close, tag, release, or settings change has been performed.

## Recommendation

Squash-merge, delete `feature/p8-monitoring`, close #78, and launch P9 (Plan and bid exchange).
