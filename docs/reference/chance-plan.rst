Sampled budget chance constraint
================================

This is a static plan with a sampled budget chance constraint. The model allows at most two of 20
training paths to exceed the annual budget in each year, while keeping capacity hard across all
training paths.

This is not a distributional chance-constrained guarantee. It is a sampled constraint test.

Results
-------

Training: 20 paths; maximum budget violations 2 per year.

.. list-table::
   :header-rows: 1

   * - Plan
     - 5-year cost P10-P90
     - Mean risk
     - Budget violation
   * - Chance-constrained
     - 198,743-247,028
     - 0.0516
     - 21.0%
   * - Scenario-robust
     - 199,567-248,028
     - 0.0516
     - 23.0%
   * - Nominal balanced
     - 269,679-333,777
     - 0.0294
     - 93.0%

The chance plan costs 220,976 CAD nominally, has 170 actions, and is capacity-feasible under all
training paths. Its out-of-sample budget violation is 21%, only two points below the scenario-robust
plan.

Why the gain is small
---------------------

Capacity remains hard across all 20 training paths. That constraint binds first, so relaxing budget
chance alone barely changes the selected treatment schedule. A meaningful next step would be to
chance-constrain capacity or add recourse.

Limits
------

- Sampled chance constraint, not a distributional guarantee.
- Budget chance only; capacity is hard.
- 20 training paths; 100 test paths.
- No risk, weather, outage, safety, asset-owner priority, or field-calibration model.
