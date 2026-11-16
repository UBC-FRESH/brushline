# Frontier out-of-sample validation

## Question

Do the deferral-frontier candidates retain recovery and cost behavior when future factors are
resampled rather than fixed?

## Method

- 20 rolling episodes.
- First-year risk-ranked deferral fixed at each candidate.
- 100 future paths for 0% and 20%; 40 paths for 5%, 10%, 15%, and 25%.
- 2028-2031 re-solved with the rolling persistence policy.
- Completion remains from the fixed-factor calendar scan.

## Results

| Target | Paths | Final gap P50 | Final gap P90 | Recovery P50 | Within 0.005 | Reopt cost P50 |
|---:|---:|---:|---:|---:|---:|---:|
| 0% | 100 | 0.0000 | 0.0000 | 0.0000 | 100.0% | 295,899 |
| 5% | 100 | -0.0010 | 0.0072 | 0.0112 | 87.0% | 295,043 |
| 10% | 100 | -0.0010 | 0.0072 | 0.0214 | 87.0% | 291,878 |
| 15% | 100 | -0.0010 | 0.0072 | 0.0312 | 87.0% | 289,012 |
| 20% | 100 | -0.0010 | 0.0072 | 0.0421 | 87.0% | 285,927 |
| 25% | 100 | -0.0010 | 0.0072 | 0.0516 | 87.0% | 283,018 |

All tested fractions remain budget-feasible and recover most or all of the fixed-future risk gap.
The 25% point has the highest recovery and lowest median reoptimized cost, but also the largest
fixed-future risk loss.

## Interpretation

The frontier’s recovery conclusion holds out of sample at every tested fraction with 100 paths per
target and a common future path set. The table does not select a risk
appetite.

## Limits

- Fixed first-year deferral.
- Independent future factors; no serial correlation.
- Rolling persistence heuristic, not a stochastic dynamic program.
- Only 40 paths for four of the six points.
- No recurrence, weather, outage, safety, or asset-owner priority model.
