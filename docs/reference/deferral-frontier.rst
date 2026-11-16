Deferral-fraction frontier
==========================

The 20% scope target was chosen as an example. This frontier sweeps risk-ranked first-year deferral
from 0% to 25% and reports the trade between calendar completion, fixed-future residual risk, recovery,
and five-year cost.

Completion uses the assumed 75/105-day weather/outage calendars. Recovery uses fixed future factors;
it is a screening frontier, not out-of-sample validation for every point.

## Results

.. list-table::
   :header-rows: 1

   * - Target
     - Actual deferred
     - Completion 75
     - Completion 105
     - Fixed final loss
     - Recovery final loss
     - Reopt cost
   * - 0%
     - 0.0%
     - 13.2%
     - 61.9%
     - 0.0000
     - 0.000003
     - 298,723
   * - 5%
     - 6.0%
     - 19.7%
     - 67.7%
     - 0.0109
     - 0.000003
     - 295,027
   * - 10%
     - 11.1%
     - 27.9%
     - 70.0%
     - 0.0209
     - 0.000003
     - 292,078
   * - 15%
     - 16.1%
     - 39.3%
     - 79.7%
     - 0.0307
     - 0.000000
     - 289,012
   * - 20%
     - 21.3%
     - 47.1%
     - 87.4%
     - 0.0413
     - 0.000003
     - 285,825
   * - 25%
     - 26.0%
     - 53.3%
     - 91.9%
     - 0.0509
     - 0.000000
     - 283,082

All targets are first-year budget-feasible in 100% of scenarios.

Higher deferral improves calendar completion and lowers five-year reoptimized cost, but increases
fixed-future residual risk. Under fixed-factor recovery, the final risk gap is essentially closed at
every tested fraction.

## Limits

- Fixed-factor recovery is a screening result; only the 20% point has out-of-sample future validation.
- Risk ranking is first-year only and whole actions are deferred; actual fractions overshoot.
- No single utility or risk appetite is optimized; the table is a frontier, not a recommendation.
- Weather and outage calendars are prototype assumptions.
- No recurrence, safety, asset-owner priority, or field calibration.
