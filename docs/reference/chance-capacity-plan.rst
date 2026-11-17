Chance-constrained capacity
===========================

This extends the sampled budget chance constraint to capacity: at most two of 20 training paths may
exceed budget and at most two may exceed capacity in each year. Both constraints are sampled; this is
not a distributional guarantee.

Results
-------

.. list-table::
   :header-rows: 1

   * - Plan
     - 5-year cost P10-P90
     - Mean risk
     - Budget violation
     - Capacity violation
   * - Chance capacity
     - 199,709-248,168
     - 0.0516
     - 22.0%
     - 0.0%
   * - Chance budget only
     - 198,743-247,028
     - 0.0516
     - 21.0%
     - 0.0%
   * - Nominal balanced
     - 269,679-333,777
     - 0.0294
     - 93.0%
     - 0.0%

Chance capacity nominal cost: **222,076 CAD**; 170 actions.

Chance capacity does not improve the out-of-sample result. Budget violation is 22% versus 21% for
budget-only chance, risk is unchanged, and out-of-sample capacity violation is already 0% in the test
set. The budget-only plan is better in this test.

Interpretation
--------------

The sampled capacity relaxation does not help because the test paths do not show capacity violations
and the budget constraint remains tighter. The experiment is a negative result for this parameter set.

A better next step would be an operational recourse model or a distributional chance constraint with
more training paths.

Limits
------

- Sampled constraints, not distributional.
- 20 training paths; 100 test paths.
- Shared static decisions; no recourse.
- No risk, weather, outage, safety, asset-owner priority, or field calibration.
