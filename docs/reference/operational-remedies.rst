Weather/outage remedies
=======================

The remedy comparison tests whether additional crew/machine capacity, a smaller first-year scope, or
a longer window improves the assumed weather/outage calendar result. It uses the same 20 rolling
episodes and 50 calendars per episode as the all-episode stress scan.

Added capacity is costed at 1,200 CAD per crew-day and 900 CAD per machine-day against the 60,000 CAD
first-year budget. These are prototype rates, not contractor quotes.

Results
-------

.. list-table::
   :header-rows: 1

   * - Remedy
     - Scenario full completion
     - Added cost P50
     - Total cost P50
     - Budget feasible
   * - Baseline
     - 13.2%
     - 0
     - 59,875
     - 100%
   * - +1 shared crew
     - 13.2%
     - 10,800
     - 70,761
     - 0%
   * - +1 shared crew + machine
     - 92.9%
     - 80,850
     - 140,800
     - 0%
   * - +1 shared machine
     - 13.2%
     - 8,100
     - 68,061
     - 0%
   * - 10% scope reduction
     - 23.4%
     - 0
     - 53,888
     - 100%
   * - 20% scope reduction
     - 44.9%
     - 0
     - 47,900
     - 100%
   * - 10% scope + 90-day
     - 54.9%
     - 0
     - 53,888
     - 100%
   * - 20% scope + 90-day
     - 66.4%
     - 0
     - 47,900
     - 100%
   * - 90-day window
     - 41.5%
     - 0
     - 59,875
     - 100%
   * - 105-day window
     - 61.9%
     - 0
     - 59,875
     - 100%
   * - **20% scope + 105-day**
     - **93.9%**
     - 0
     - **47,900**
     - **100%**

The **20% scope + 105-day** case is the best budget-feasible completion case. It is a proportional
scope reduction, so the risk effect of deferring 20% of work is not evaluated here.

A crew alone or machine alone does not improve completion because mowing and mechanical work require
both. The crew-plus-machine case is the strongest full-scope completion remedy, but its median total
first-year cost is about 140,800 CAD against the 60,000 CAD budget.

Limits
------

- Capacity and scope remedies are hypothetical scheduling tests, not contractor commitments.
- Crew-day and machine-day rates are prototype assumptions, not contractor quotes.
- Scope reduction applies proportionally to work-item hours; it is not a risk-ranked deferral policy,
  and the deferred risk is not evaluated.
- The calendar is assumed: independent weather loss and a fixed outage block.
- Only first-year shift scheduling is tested; access, later years, and safety are not certified.
