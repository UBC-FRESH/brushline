Added-crew versus window remedy
================================

One relief mowing crew and machine were added for all five years and compared with extending the
fall window. Calendar-aware execution is used throughout.

Added-resource cost uses:

- 1,200 CAD per crew-day;
- 900 CAD per machine-day;
- 8% supervision;
- 10% overhead;
- 2,500 CAD seasonal overhead per relief crew-year.

Results
-------

20 episodes, seed 7, 59 segments.

.. list-table::
   :header-rows: 1

   * - Case
     - Window
     - Extra crews
     - Completed P50
     - Mean risk
     - Action cost P50
     - Added resource P50
     - Total cost P50
   * - Baseline
     - 75
     - 0
     - 87.6%
     - 0.0502
     - 264,047
     - 0
     - 264,047
   * - Extra crew
     - 75
     - 1
     - 98.0%
     - 0.0332
     - 293,706
     - 529,411
     - 823,084
   * - Window
     - 90
     - 0
     - 95.9%
     - 0.0365
     - 285,490
     - 0
     - 285,490
   * - Window
     - 105
     - 0
     - 98.1%
     - 0.0333
     - 294,012
     - 0
     - 294,012

The added crew recovers almost all calendar-aware scope, but its total cost is about **823,000 CAD**
versus **294,000 CAD** for the 105-day window. Under these assumptions, extending the window is
substantially cheaper than adding a crew and machine. Seasonal overhead for the window itself is
not modelled.

590-segment scale test
----------------------

A replicated 590-segment instance uses 30 base crews, 10 relief mowing crews, and 10 relief
machines. The fixed plan is exact; annual re-solves use Fresh Solutions.

.. list-table::
   :header-rows: 1

   * - Case
     - Window
     - Extra crews
     - Completed P50
     - Mean risk
     - Action cost P50
     - Added resource P50
     - Total cost P50
   * - Baseline
     - 75
     - 0
     - 84.5%
     - 0.0667
     - 2,536,614
     - 0
     - 2,536,614
   * - Extra crew
     - 75
     - 10
     - 98.3%
     - 0.0325
     - 2,931,649
     - 5,357,421
     - 8,278,357
   * - Window
     - 90
     - 0
     - 95.9%
     - 0.0368
     - 2,844,469
     - 0
     - 2,844,469
   * - Window
     - 105
     - 0
     - 98.1%
     - 0.0328
     - 2,931,649
     - 0
     - 2,931,649

Runtime: fixed exact 49.7 s; remedy sweep 344.4 s for 20 episodes.

The extra-crew action cost already equals the 105-day window total, so **any positive resource rate**
makes the crew option more expensive. At 59 segments, the break-even resource rate is only 0.058% of
the assumed day rates. The window remedy dominates under these assumptions.

Limits
------

- 59 segments only; not a 590-segment cost comparison.
- Extra crew and machine are available for all five years.
- Added resource cost uses prototype day rates and overhead fractions.
- Window extension carries no added seasonal overhead or supervision in this comparison.
- No safety, access, asset-owner priority, or field-calibration claim.
