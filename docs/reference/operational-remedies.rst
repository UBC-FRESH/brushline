Weather/outage remedies
=======================

The remedy comparison tests whether additional crew/machine capacity or a smaller first-year scope
improves the assumed weather/outage calendar result. It uses the same 20 rolling episodes and 50
calendars per episode as the all-episode stress scan.

## Results

Added capacity is costed at 1,200 CAD per crew-day and 900 CAD per machine-day against the
60,000 CAD first-year budget. These are prototype rates, not contractor quotes.

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
   * - 10% scope reduction
     - 23.4%
     - 0
     - 53,888
     - 100%
   * - 90-day window
     - 41.5%
     - 0
     - 59,875
     - 100%

A crew without a machine does not help because mowing and mechanical work require machine capacity.
The shared crew plus machine is the strongest completion remedy, but its median total cost of about
140,800 CAD is more than twice the 60,000 CAD first-year budget. Under the fixed budget, the 90-day
window is the best budget-feasible completion case at 41.5%; the 10% scope reduction reaches 23.4%.
Capacity is therefore a budget-expansion decision, not a free scheduling fix.

## Limits

- Capacity and scope remedies are hypothetical scheduling tests, not contractor commitments.
- Added capacity cost, equipment availability, and supervision are not modelled.
- Scope reduction is a proportional hours test, not a risk-ranked deferral policy.
- The calendar is assumed: independent weather loss and a fixed outage block.
- Only first-year shift scheduling is tested; access, later years, and safety are not certified.
