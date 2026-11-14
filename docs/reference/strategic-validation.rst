Synthetic strategic validation
==============================

P6.7 validates a complete 10-year synthetic strategic case: optimized portfolio, monitoring policy,
fixed-cycle BAU, yearly report, and scenario replay.

The committed result is ``notes/reference/p6-validation.v1.json``.

Case
----

``build_synthetic_case`` creates:

- three segments in one span with different lengths, service, risk, and uncertainty baselines;
- ten yearly periods from 2026 to 2035;
- one mowing option per segment and period;
- a service target of 0.7 and a risk target of 0.4;
- annual LiDAR monitoring with a value-of-information selection;
- a four-year BAU cycle;
- a 20-row optimized/BAU report;
- a scenario with canonical portfolio and report digests.

Checks
------

.. list-table::
   :header-rows: 1
   :widths: 20 80

   * - Code
     - Check
   * - ``COVERAGE``
     - Ten optimized and ten BAU yearly rows.
   * - ``BUDGET``
     - Optimized rows remain within the period budget.
   * - ``SERVICE``
     - Optimized service reaches the declared target.
   * - ``MONITORING``
     - Monitoring cost is within budget and at least one policy decision exists.
   * - ``BAU``
     - The comparison is like-for-like and the BAU plan is feasible.
   * - ``TOTALS``
     - The report total equals the sum of optimized yearly rows.
   * - ``REPLAY``
     - The scenario portfolio and report digests replay.

``validate_strategic_plan`` returns each check separately and a single pass/fail. A failed check is never
hidden behind the aggregate.

.. code-block:: python

   from brushline.strategic.validation import build_synthetic_case

   case = build_synthetic_case()
   assert case.validation.passed
   assert case.portfolio.service_attainment >= 0.7
   assert case.report.comparison.like_for_like

Results
-------

On the committed case:

- optimized service is about 0.707, present treatment cost is 920, and the plan is feasible;
- BAU service is about 0.413 with a four-year cycle;
- monitoring costs 200 and selects an annual LiDAR policy;
- all seven checks pass and the scenario replays exactly.

Limits
------

- The case is synthetic; it is not a field or realistic-corridor validation.
- The option outcomes and contingencies are assumptions, not calibrated forecasts.
- The validation proves contract and replay consistency, not global optimality.
- No MIP/CP bound or external solver is used.
