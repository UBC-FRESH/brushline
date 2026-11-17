Fall-window capacity remedy
===========================

Observed-calendar awareness defers whole actions when the 75-day fall calendar cannot fit them.
This remedy extends the work window to 90 and 105 days while holding the crew and machine mix
fixed. It is an operational what-if, not a field schedule or a costed seasonal plan.

Results
-------

20 episodes, seed 7.

.. list-table::
   :header-rows: 1

   * - Window days
     - Completed scope P50
     - Retained scope P50
     - Mean risk
     - Cost P50
     - Unscheduled h
     - Calendar deferrals
   * - 75
     - 87.6%
     - 87.6%
     - 0.0502
     - 264,047
     - 0.0
     - 39.9
   * - 90
     - 95.9%
     - 95.9%
     - 0.0365
     - 285,490
     - 0.0
     - 15.0
   * - 105
     - 98.1%
     - 98.1%
     - 0.0333
     - 294,012
     - 0.0
     - 4.6

The longer window recovers scope and lowers mean risk. Action cost rises because more work is
retained; added seasonal overhead, supervision, and weather exposure are not modelled.

590-segment scale test
----------------------

A replicated 590-segment instance scales the workforce to 30 crews and 30 machines. The fixed plan
is exact; annual re-solves use Fresh Solutions.

.. list-table::
   :header-rows: 1

   * - Window days
     - Completed scope P50
     - Retained scope P50
     - Mean risk
     - Cost P50
     - Calendar deferrals
   * - 75
     - 84.5%
     - 84.5%
     - 0.0667
     - 2,536,614
     - 484.3
   * - 90
     - 95.9%
     - 95.9%
     - 0.0368
     - 2,844,469
     - 182.0
   * - 105
     - 98.1%
     - 98.1%
     - 0.0328
     - 2,931,649
     - 58.8

Runtime: fixed exact 47.4 s; window sweep 244.9 s for 20 episodes. The remedy recovers almost all
calendar-aware scope at scale. Action cost rises because more work is retained; added seasonal
overhead, supervision, and weather exposure are not modelled.

Limits
------

- Window extension is not a field calendar.
- Crew and machine mix is held fixed.
- No added seasonal overhead or supervision cost.
- Whole-action deferral; no partial treatment credit.
- No safety, access, asset-owner priority, or field-calibration claim.
