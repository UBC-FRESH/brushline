# Rolling recovery after first-year deferral

## Question

Does re-optimizing future years close the persistent risk gap created by first-year risk-ranked scope
deferral?

## Method

- 20 rolling episodes.
- First-year risk-ranked deferral: 20% target, 21.3% actual mean deferral.
- After the first year, re-solve 2028-2031 with the rolling persistence forecast and a two-year
  lookahead.
- Use the same annual factors as the original rolling episode.
- Compare full policy, deferred without reoptimization, and deferred with rolling recovery.

## Results

| Case | 2027 | 2028 | 2029 | 2030 | 2031 | Mean loss | Final loss |
|---|---:|---:|---:|---:|---:|---:|---:|
| Full policy | 0.1133 | 0.0147 | 0.0060 | 0.0067 | 0.0073 | 0.0 | 0.0 |
| Deferred, no reoptimization | 0.1546 | 0.0560 | 0.0473 | 0.0480 | 0.0486 | 0.0413 | 0.0413 |
| Deferred, rolling reoptimization | 0.1546 | 0.0318 | 0.0063 | 0.0067 | 0.0073 | 0.0117 | 0.000003 |

- Mean recovery: **0.0295**
- Final recovery: **0.0413**
- Five-year cost: full 298,797 CAD; no reoptimization 285,970 CAD; reoptimization 285,825 CAD.

The rolling policy closes most of the gap by 2028 and reaches essentially the full-policy risk path
by 2029. The reoptimized path retains most of the first-year cost saving under the fixed-factor
assumptions.

## Interpretation

The persistent-gap result from the fixed-future trajectory is largely a **no-replanning** result.
Allowing future re-optimization recovers almost all of the deferred risk while retaining most of the
cost saving.

This is not a multi-year stochastic guarantee: the annual factors are fixed from the original
episode, the first-year deferral is fixed, and the rolling policy is a persistence-forecast heuristic.

## Limits

- Annual factors are fixed; no new uncertainty is sampled.
- First-year deferral cannot be reversed later.
- First-year risk ranking only.
- No recurrence, weather, outage, safety, or asset-owner priority model.
