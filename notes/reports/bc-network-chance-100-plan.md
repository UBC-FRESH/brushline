# 100-path chance constraint

## Question

Does training the sampled budget chance constraint on 100 paths improve out-of-sample budget
performance enough to justify the risk cost?

## Method

- 100 training paths sampled from the lognormal assumptions.
- At most 10 budget violations per year.
- Capacity hard across all training paths.
- 100 independent test paths.
- Risk objective; shared static decisions.

## Results

| Plan | 5-year cost P10 | P50 | P90 | Mean risk | Budget violation |
|---|---:|---:|---:|---:|---:|
| Chance, 100 paths | 176,580 | 191,739 | 220,447 | 0.0671 | 8.0% |
| Chance, 20 paths | 198,743 | 214,443 | 247,028 | 0.0516 | 21.0% |
| Nominal balanced | 269,679 | 291,824 | 333,777 | 0.0294 | 93.0% |

100-path plan nominal cost: **197,659 CAD**; 155 actions.

## Interpretation

More training paths reduce out-of-sample budget violations from 21% to 8%. The cost is a substantial
loss of risk reduction: mean risk rises from 0.0516 to 0.0671. The plan remains below a 5% budget-risk
target and is still a sampled constraint, not a distributional guarantee.

The sampled static chance approach is nearing its useful limit; operational recourse or a different
policy class is the next lever.

## Limits

- Sampled budget chance; capacity hard.
- 100 training paths; 100 independent test paths.
- Shared static decisions; no recourse.
- No risk, weather, outage, safety, asset-owner priority, or field calibration.
