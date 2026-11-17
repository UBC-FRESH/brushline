Two-stage operational recourse
==============================

The first-year nominal balanced plan is fixed. After annual cost, productivity, and capacity
factors are observed, the second stage defers whole actions by lowest first-year risk reduction per
hour until the annual budget and crew-hour capacity are satisfied.

This is an operational recourse evaluation for one year, not a multi-year stochastic dynamic program.

Results
-------

- First-stage plan: nominal balanced, 46 first-year actions.
- 100 factor scenarios, seed 23.
- Budget 60,000 CAD/year; capacity 6,000 hours/year.

.. list-table::
   :header-rows: 1

   * - Metric
     - Static execution
     - Two-stage recourse
   * - Budget violation
     - 44.0%
     - 0.0%
   * - Capacity violation
     - 0.0%
     - 0.0%
   * - Cost P50
     - 57,939
     - 57,939
   * - Cost P90
     - 71,471
     - 59,592
   * - Completion P50
     - 100.0%
     - 100.0%
   * - Mean completion
     - 100.0%
     - 93.98%
   * - Mean risk loss
     - 0.0000
     - 0.0121

The mean deferred workload is 2.75 actions and 60.2 crew-hours. The second stage guarantees budget
and capacity feasibility for the first year while retaining most of the planned work and risk
reduction.

Limits
------

- First-year only.
- First-stage plan is fixed; no strategic re-optimization.
- No weather, outage, future re-planning, or multi-year risk model.
- Deferral ranking is first-year risk reduction per hour only.
- No field calibration, safety, or asset-owner approval.

Multi-year annual recourse
--------------------------

The same deferral rule is applied independently to every year of the five-year nominal plan. The
first-stage plan remains fixed; there is no future strategic re-optimization.

- 100 annual-factor scenarios, seed 23.
- Static any-year budget violation: **93.0%**.
- Recourse any-year budget violation: **0.0%**.
- Static mean risk: **0.0294**; recourse mean risk: **0.0330**.
- Mean completion: **93.9%**; completion P50 **95.1%**.
- Mean deferred workload: **13.0 actions**, **306.0 hours**.

The annual recourse rule keeps the five-year plan budget- and capacity-feasible while retaining most
of the planned work. The risk increase is small but not eliminated. This remains a one-stage fixed
plan with annual operational recourse, not a stochastic dynamic program.
