Weather/outage remedies
=======================

The remedy comparison tests whether additional crew/machine capacity or a smaller first-year scope
improves the assumed weather/outage calendar result. It uses the same 20 rolling episodes and 50
calendars per episode as the all-episode stress scan.

## Results

.. list-table::
   :header-rows: 1

   * - Remedy
     - Scenario full completion
     - Mean completion
     - Unscheduled P50
   * - Baseline
     - 13.2%
     - 85.6%
     - 127.5
   * - +1 shared crew
     - 13.2%
     - 85.6%
     - 127.5
   * - +1 shared crew + machine
     - 92.9%
     - 99.8%
     - 0.0
   * - 10% scope reduction
     - 23.4%
     - 90.2%
     - 72.0
   * - 90-day window
     - 41.5%
     - 93.2%
     - 34.0

A crew without a machine does not help because mowing and mechanical work require machine capacity.
The shared crew plus machine is the strongest completion remedy. A 10% proportional scope reduction
is modest; a 90-day window helps but does not close the gap.

## Limits

- Capacity and scope remedies are hypothetical scheduling tests, not contractor commitments.
- Added capacity cost, equipment availability, and supervision are not modelled.
- Scope reduction is a proportional hours test, not a risk-ranked deferral policy.
- The calendar is assumed: independent weather loss and a fixed outage block.
- Only first-year shift scheduling is tested; access, later years, and safety are not certified.
