# Rolling policy with recourse

## Question

Does combining rolling future re-optimization with annual operational deferral retain budget
feasibility and restore the scope deferred by fixed-future recourse?

## Method

- 20 common annual-factor episodes, seed 7.
- First year from the fixed nominal plan.
- Later years re-solved with the rolling persistence forecast and two-year lookahead.
- Recourse cases defer lowest-first-year-risk-reduction-per-hour actions until budget and capacity fit.
- Four cases: static fixed, fixed-future recourse, rolling-only, rolling recourse.

## Results

| Policy | Budget violation | Completion P50 | Mean completion | Mean risk | Cost P50 |
|---|---:|---:|---:|---:|---:|
| Static fixed | 95.0% | 100.0% | 100.0% | 0.0294 | 300,711 |
| Fixed-future recourse | 0.0% | 93.1% | 93.3% | 0.0335 | 279,595 |
| Rolling-only | 55.0% | 100.0% | 100.0% | 0.0293 | 300,236 |
| Rolling recourse | 0.0% | 99.4% | 98.8% | 0.0349 | 297,451 |

Rolling recourse restores almost all first-year scope while remaining budget- and capacity-feasible.
It costs about 17,856 CAD more than fixed-future recourse and does not lower mean risk in this run.

## Interpretation

Future re-optimization recovers the completion lost by fixed-future deferral, but not at a lower mean
risk. The risk metric combines the fixed first-year deferral with re-optimized future years and is not
a like-for-like multi-year risk improvement. The policy remains a heuristic, not a stochastic dynamic
program.


## 590-segment scale test

A replicated 590-segment instance uses an exact fixed plan and Fresh Solutions annual rolling
re-solves.

| Policy | Budget violation | Completion P50 | Mean risk | Cost P50 |
|---|---:|---:|---:|---:|
| Static fixed | 95.0% | 100.0% | 0.0291 | 3,008,496 |
| Fixed-future recourse | 0.0% | 93.9% | 0.0329 | 2,811,913 |
| Rolling-only | 55.0% | 100.0% | 0.0290 | 2,969,701 |
| Rolling recourse | 0.0% | 99.6% | 0.0340 | 2,942,470 |

Fixed exact plan: 47.1 s. Twenty rolling episodes: 87.2 s with heuristic annual re-solves. The
scale result preserves zero budget violation and near-complete scope. The instance is replicated,
not a real 590-segment network, and the heuristic is not globally optimal.

## Limits

- Fixed first year.
- 20 episodes.
- No weather, outage, recurrence, safety, or asset-owner priority model.
- First-year risk ranking for deferral.
