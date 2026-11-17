# Chance-constrained capacity

## Question

Does relaxing capacity to a sampled chance constraint improve the out-of-sample result beyond the
budget-only chance plan?

## Method

- 20 training paths.
- At most two budget violations per year.
- At most two capacity violations per year.
- Shared static decisions.
- 100 independent test paths at 60,000 CAD/year and 6,000 hours/year.

## Results

| Plan | 5-year cost P10 | P50 | P90 | Mean risk | Budget violation | Capacity violation |
|---|---:|---:|---:|---:|---:|---:|
| Chance capacity | 199,709 | 215,511 | 248,168 | 0.0516 | 22.0% | 0.0% |
| Chance budget only | 198,743 | 214,443 | 247,028 | 0.0516 | 21.0% | 0.0% |
| Nominal balanced | 269,679 | 291,824 | 333,777 | 0.0294 | 93.0% | 0.0% |

Chance capacity nominal cost: **222,076 CAD**; actions: 170.

## Interpretation

Chance capacity is a negative result. Out-of-sample capacity violations are already zero, so relaxing
capacity does not help; budget remains the tighter constraint. The budget-only chance plan is slightly
better on budget violation and cost with the same risk.

A meaningful next step is operational recourse or a distributional chance constraint with more
training paths.

## Limits

- Sampled constraints, not distributional.
- 20 training paths; 100 test paths.
- Static shared decisions; no recourse.
- No risk, weather, outage, safety, asset-owner priority, or field calibration.
