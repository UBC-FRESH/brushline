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

## Limits

- Fixed first year.
- 20 episodes.
- No weather, outage, recurrence, safety, or asset-owner priority model.
- First-year risk ranking for deferral.
