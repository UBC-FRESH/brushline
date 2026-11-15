# BC network scenario optimization

## Question

Does re-planning after cost, productivity, and capacity uncertainty is revealed beat the fixed
balanced plan? This is a hindsight value-of-adaptivity comparison, not a deployable policy.

## Method

- Fixed plan: exact MILP balanced plan at 60,000 CAD/year.
- 30 seeded scenarios, seed 7.
- Lognormal multipliers with mean one: cost sigma 0.18; productive-hours sigma 0.15; capacity sigma
  0.15.
- Fixed plan: actions held fixed; action costs and hours scaled; risk unchanged.
- Adaptive plan: exact stateful MILP re-solved with scenario method costs/hours and period capacity;
  annual budget unchanged.
- Objective weights: risk 1.0; cost and hours weights 0.
- Fixed-plan feasibility penalty: normalized annual budget overrun plus capacity shortfall, added to
  the risk-equivalent objective.
- All 30 adaptive solves returned `optimal`.

## Results

| Policy | 5-year cost P10 | P50 | P90 | Mean risk | Budget violation |
|---|---:|---:|---:|---:|---:|
| Fixed balanced plan | 249,742 | 310,229 | 371,650 | 0.0294 | 56.7% |
| Scenario-optimized | 298,055 | 298,947 | 299,452 | 0.0317 | 0.0% |

- Fixed capacity violation probability: 0.0%.
- Mean risk-equivalent objective: fixed 0.1068; adaptive 0.0317.
- Mean regret: 0.0752; P90 regret: 0.2221.
- Adaptive improved the risk-equivalent objective in 100% of scenarios.

The fixed plan has slightly lower nominal risk reduction loss (0.0294 versus 0.0317), but it exceeds
the annual budget in 56.7% of scenarios. The adaptive plan keeps five-year cost tightly clustered near
the budget and remains feasible, at a small risk cost. The risk-equivalent objective includes the
declared feasibility penalty, so it is not a dollar value or a field-calibrated utility.

## Limits

- Hindsight adaptive: each scenario-specific plan sees the sampled factors before choosing treatments.
- Thirty scenarios are a demonstration sample, not a calibrated probability model.
- The exact MILP is exact only for the declared linear risk state, at 59 segments.
- The fixed plan's risk is unchanged by cost and hours draws; risk would change only if the treatment
  schedule adapts.
- No full stochastic dynamic program, forecast-update policy, outage constraint, or safety claim.
