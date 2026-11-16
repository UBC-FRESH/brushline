Risk-ranked scope deferral
==========================

The proportional scope remedy defers hours mechanically. This comparison instead defers whole
first-year actions ranked by **lowest first-year risk reduction per hour**, until about 20% of action
hours are deferred.

This is first-year risk ranking, not a multi-year risk model. The actual deferred fraction can
overshoot because whole actions are selected.

## Network result

- 20 rolling episodes, 50 calendars per episode.
- Target 20% of first-year action hours.
- Mean actual deferred fraction: **21.3%**.
- Mean first-year risk loss: **0.0413**.
- Mean residual risk: **0.1546** (from a lower full-plan risk).
- Median total cost: **47,226 CAD**, budget-feasible in 100% of scenarios.

.. list-table::
   :header-rows: 1

   * - Case
     - Scenario completion
     - Mean risk loss
     - Residual risk
     - Budget feasible
   * - Risk-ranked 20% + 75-day
     - 47.1%
     - 0.0413
     - 0.1546
     - 100%
   * - Risk-ranked 20% + 105-day
     - 87.4%
     - 0.0413
     - 0.1546
     - 100%

For context, a proportional 20% reduction has an estimated mean first-year risk loss of about
0.0448 under the same action-benefit accounting. The risk-ranked choice loses less first-year risk
reduction, but its whole-action selection also has lower scheduling completion than the proportional
20% + 105-day case.

## Interpretation

The risk-ranked 105-day case completes less of the assumed calendar than the proportional case, but
it protects more first-year risk reduction per deferred hour. Neither result is a multi-year risk
recommendation. A real deferral decision would need year-specific risk accounting, recurring
treatment effects, and asset-owner priorities.

## Limits

- Ranking uses first-year risk reduction per action hour only.
- Whole segment actions are deferred; actual deferred fraction can overshoot the target.
- No multi-year risk, treatment recurrence, outage, or safety model.
- Weather and outage assumptions are prototype values.
- The MILP is exact only for the declared linear risk state at 59 segments.
