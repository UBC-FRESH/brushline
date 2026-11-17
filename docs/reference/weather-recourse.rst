Weather/outage-aware recourse
=============================

This comparison adds an observed annual crew calendar to the rolling-recourse policy. Each year
observes cost, hours, capacity, and a calendar containing five fixed outage days plus independent
20% weather-loss probability per day in a 75-day fall window.

Two cases are compared:

- **calendar-naive**: keep the resource-feasible plan and accept partial execution;
- **calendar-aware**: defer unscheduled actions until every retained action fits the observed
  calendar.

The calendar is observed before commitment. This is an ex-post feasible-scope policy, not a
forecast, and not a stochastic dynamic program.

## Results

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
   * - Calendar-aware
     - 0.0%
     - 87.6%
     - 87.6%
     - 0.0502
     - 297,088
     - 0.0
     - 39.9

Calendar-naive completes 88.8% of planned hours on average but leaves 605.9 h unscheduled.
Calendar-aware retains 87.4% of planned scope and schedules all retained work. Awareness costs
1.4 percentage points of mean scope and raises mean risk by 0.0021; it is a completion-certainty
tradeoff, not a risk improvement.

## Limits

- The calendar is observed before deferral; this is not a forecast policy.
- Weather loss is independent per day and assumed, not measured.
- The outage block is assumed, not an asset-owner schedule.
- Whole actions are deferred when they cannot be completed, so the aware case is conservative.
- No safety, asset-owner priority, access, or field-calibration claim.
