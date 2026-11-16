# Sampled budget chance-constrained plan

## Question

Can relaxing the budget robust constraint to a sampled chance constraint improve out-of-sample budget
performance without sacrificing too much risk reduction?

## Method

- 20 training paths from the rolling episode set.
- At most 2 budget violations per year across the 20 paths.
- Capacity remains hard across all training paths.
- Risk objective; shared static decisions.
- 100 independent test paths with a 60,000 CAD annual budget and 6,000-hour capacity.

## Results

| Plan | 5-year cost P10 | P50 | P90 | Mean risk | Budget violation |
|---|---:|---:|---:|---:|---:|
| Chance-constrained | 198,743 | 214,443 | 247,028 | 0.0516 | 21.0% |
| Scenario-robust | 199,567 | 215,351 | 248,028 | 0.0516 | 23.0% |
| Nominal balanced | 269,679 | 291,824 | 333,777 | 0.0294 | 93.0% |

Chance plan nominal cost: **220,976 CAD**; actions: 170.

## Interpretation

The budget chance constraint only reduces out-of-sample budget violations from 23% to 21%. Capacity is
hard across all training paths and binds first, so relaxing budget chance alone barely changes the
plan. The chance plan also does not improve risk over the scenario-robust plan.

A meaningful next step is a chance constraint on capacity or a policy with operational recourse.

## Limits

- Sampled chance constraint, not distributional.
- Budget only; capacity hard.
- 20 training paths; 100 test paths.
- No risk, weather, outage, safety, asset-owner priority, or field calibration.
