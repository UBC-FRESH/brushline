# BC network rolling-horizon policy

## Question

Can an executable annual policy retain the cost and budget stability of the hindsight-adaptive
comparison without knowing future factors? The policy observes current-year conditions, assumes they
persist over a two-year lookahead, re-solves the stateful MILP, and commits only the current year.

## Method

- Network: 8,737 ha, 59 segments, 2027-2031.
- 20 annual-factor episodes, seed 7.
- Lognormal annual factors with mean one: cost sigma 0.18, productive-hours sigma 0.15, capacity
  sigma 0.15.
- Factors are independent across years.
- Policy sees the current year's factors and assumes persistence over a two-year lookahead.
- All 100 annual MILP re-solves returned optimal.
- The fixed nominal plan is evaluated under the same annual factors; its risk remains the nominal
  plan's risk.

## Results

| Policy | 5-year cost P10 | P50 | P90 | Mean risk | Budget violation |
|---|---:|---:|---:|---:|---:|
| Fixed nominal | 265,469 | 300,711 | 333,437 | 0.0294 | 95.0% |
| Rolling policy | 298,123 | 298,894 | 299,398 | 0.0296 | 0.0% |

- Capacity violation probability: 0.0% for both policies.
- Mean risk-equivalent objective: fixed 0.1031; rolling 0.0296.
- Mean regret: 0.0735; P90 regret: 0.1218.
- Rolling improved the objective in 100% of episodes.

The fixed plan's budget-violation rate is high because annual cost factors are independent and the
fixed plan commits the nominal five-year schedule. The rolling policy re-solves each year and commits
only the current year, so its annual actions fit the observed condition. The risk-equivalent objective
includes a normalized budget/capacity penalty and is not a dollar value.

## Interpretation

The rolling policy gives up a small amount of nominal risk reduction and substantially narrows the
five-year cost range. The result is an executable policy result, not a claim that the policy is
globally optimal.

## Limits

- Persistence forecast over a two-year lookahead; no serial correlation or calibrated forecast model.
- Annual factors are independent; 20 episodes are a demonstration sample.
- Only current-year actions are committed; the remaining plan is a forecast.
- Exact MILP only for the declared linear risk state at 59 segments.
- No field calibration, outage constraint, safety certification, or asset-owner approval.
