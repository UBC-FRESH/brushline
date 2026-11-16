# Risk-ranked scope deferral

## Question

The proportional 20% scope remedy defers hours mechanically. Can deferring whole actions by lowest
first-year risk reduction per hour protect more risk reduction for the same scheduling target?

## Method

- 20 rolling episodes, 50 assumed weather/outage calendars per episode.
- Target 20% of first-year action hours.
- Rank actions by first-year risk reduction per hour, lowest first.
- Defer whole segment actions until the target is met; actual mean deferred fraction 21.3%.
- Build tactical, access, resource, work-order, and shift packages for the remaining actions.
- Test 75-day and 105-day windows.
- Risk loss is the weighted first-year risk reduction lost relative to the full policy action set.

## Results

| Case | Scenario completion | Mean risk loss | Residual risk | Total cost P50 | Budget feasible |
|---|---:|---:|---:|---:|---:|
| Risk-ranked 20% + 75-day | 47.1% | 0.0413 | 0.1546 | 47,226 | 100% |
| Risk-ranked 20% + 105-day | 87.4% | 0.0413 | 0.1546 | 47,226 | 100% |

For context, the proportional 20% + 105-day case reaches 93.9% scenario completion. Under the same
action-benefit accounting, its estimated first-year risk loss is about 0.0448, versus 0.0413 for the
risk-ranked selection.

## Interpretation

Risk ranking protects slightly more first-year risk reduction per deferred hour, but the whole-action
selection loses scheduling completion relative to proportional scope. It is not a multi-year risk
recommendation.

## Limits

- First-year risk reduction per action hour only.
- Whole actions; actual deferred fraction can overshoot.
- No recurrence, multi-year risk, outage, safety, or asset-owner priority model.
- Weather/outage calendars are prototype assumptions.
