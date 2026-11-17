Weather/outage-aware recourse
=============================

This comparison adds an assumed annual crew calendar to the rolling-recourse policy. Each year
observes cost, hours, and capacity, and the execution calendar contains five fixed outage days plus
independent 20% weather-loss probability per day in a 75-day fall window.

Three cases are compared:

- **calendar-naive**: keep the resource-feasible plan and accept partial execution;
- **forecast-aware**: plan against an independent synthetic forecast calendar, then execute under
  the actual calendar;
- **calendar-aware**: defer unscheduled actions until every retained action fits the observed
  calendar.

The forecast is a synthetic draw from the same assumed distribution, not a forecast product. The
observed-calendar case uses within-year calendar information before deferral. These are calendar
policies, not stochastic dynamic programs.

Results
-------

20 episodes, seed 7.

.. list-table::
   :header-rows: 1

   * - Case
     - Budget violation
     - Completed scope P50
     - Retained scope P50
     - Mean risk
     - Cost P50
     - Unscheduled h
     - Calendar deferrals
   * - Calendar-naive
     - 0.0%
     - 88.4%
     - 99.4%
     - 0.0480
     - 297,595
     - 605.9
     - 0.0
   * - Forecast-aware
     - 0.0%
     - 86.2%
     - 88.3%
     - 0.0526
     - 264,470
     - 64.7
     - 39.2
   * - Calendar-aware
     - 0.0%
     - 87.6%
     - 87.6%
     - 0.0502
     - 264,047
     - 0.0
     - 39.9

Forecast awareness reduces unscheduled work from 605.9 h to 64.7 h, but forecast error remains.
Observed-calendar awareness eliminates unscheduled retained work but costs about 1.4 percentage
points of mean scope versus forecast awareness and raises mean risk. Neither aware case lowers risk;
both convert partial work into deferred scope.

590-segment scale test
----------------------

A replicated 590-segment instance scales the workforce to 30 crews and 30 machines. The fixed plan
is exact; annual re-solves use Fresh Solutions.

.. list-table::
   :header-rows: 1

   * - Case
     - Budget violation
     - Completed scope P50
     - Retained scope P50
     - Mean risk
     - Cost P50
     - Unscheduled h
   * - Calendar-naive
     - 0.0%
     - 85.9%
     - 99.6%
     - 0.0617
     - 2,942,470
     - 7,377
   * - Forecast-aware
     - 0.0%
     - 83.6%
     - 86.4%
     - 0.0713
     - 2,539,520
     - 681.5
   * - Calendar-aware
     - 0.0%
     - 84.5%
     - 84.5%
     - 0.0667
     - 2,536,614
     - 0.0

Runtime: fixed exact 48.6 s; 20 weather episodes 220.8 s. Forecast error leaves 681.5 h
unscheduled at scale, while observed-calendar awareness eliminates unscheduled retained work. The
instance is replicated, not a real network, and the heuristic makes no global-optimality claim.

Limits
------

- Forecast awareness uses a synthetic calendar draw, not a weather forecast.
- Observed-calendar awareness uses within-year information before deferral.
- Weather loss is independent per day and assumed, not measured.
- The outage block is assumed, not an asset-owner schedule.
- Whole actions are deferred when they cannot be completed, so the aware cases are conservative.
- No safety, asset-owner priority, access, or field-calibration claim.
