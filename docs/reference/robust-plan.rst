Scenario-robust static plan
===========================

This is a static plan with shared treatment decisions and budget/capacity constraints for 20 training
paths from the rolling episode set. It is robust to those sampled paths, not to the full distribution.

The robust MILP adds one annual budget and one annual capacity row per training path, 200 rows total,
while sharing the same segment-period-method choices. The plan is then tested on 100 independent
factor paths.

Results
-------

Training: 20 paths.

.. list-table::
   :header-rows: 1

   * - Plan
     - 5-year cost P10-P90
     - Mean risk
     - Budget violation
     - Capacity violation
   * - Scenario-robust
     - 199,567-248,028
     - 0.0516
     - 23.0%
     - 0.0%
   * - Nominal balanced
     - 269,679-333,777
     - 0.0294
     - 93.0%
     - 0.0%

The robust plan has a nominal treatment cost of 221,876 CAD and 170 actions. It cuts out-of-sample
budget violations from 93% to 23%, at the cost of higher residual risk than the nominal plan.

It does **not** meet a 5% out-of-sample budget-risk target. The constraints cover only the 20 training
paths; a distributional or chance-constrained guarantee would require more scenarios or a different
formulation.

Limits
------

- Shared static decisions; no scenario-specific recourse.
- Budget/capacity uncertainty only; treatment risk and access are not scenario-robust.
- 20 training paths, 100 test paths; independent factors.
- No weather, outage, safety, asset-owner priority, or field calibration.
