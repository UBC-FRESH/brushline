# Weather/outage-aware recourse

## Question

Does budget- and capacity-feasible rolling recourse remain schedulable once an assumed weather and
outage calendar is included, and what does it cost to defer work until every retained action fits
the observed calendar?

## Method

- 20 annual episodes, seed 7; same factor paths as the rolling-recourse comparison.
- 75-day fall window; five fixed outage days; independent 20% weather-loss probability per day.
- Each year observes cost, hours, capacity, and the calendar before committing actions.
- Calendar-naive keeps the resource-feasible plan and accepts partial execution.
- Calendar-aware defers unscheduled actions until every retained action fits the observed calendar.
- Crew and machine calendar uses the prototype contractor mix.

## Results

| Case | Budget violation | Completed scope P50 | Retained scope P50 | Mean risk | Cost P50 | Unscheduled h | Calendar deferrals |
|---|---:|---:|---:|---:|---:|---:|---:|
| Calendar-naive | 0.0% | 88.4% | 99.4% | 0.0480 | 297,595 | 605.9 | 0.0 |
| Calendar-aware | 0.0% | 87.6% | 87.6% | 0.0502 | 264,047 | 0.0 | 39.9 |

Calendar-naive completes 88.8% of planned hours on average but leaves 605.9 h unscheduled.
Calendar-aware retains 87.4% of planned scope and schedules all retained work. Awareness costs
1.4 percentage points of mean scope and raises mean risk by 0.0021.

## 590-segment scale test

A replicated 590-segment instance scales the workforce to 30 crews and 30 machines. The fixed plan
is exact; annual re-solves use Fresh Solutions.

| Case | Budget violation | Completed scope P50 | Retained scope P50 | Mean risk | Cost P50 | Unscheduled h |
|---|---:|---:|---:|---:|---:|---:|
| Calendar-naive | 0.0% | 85.9% | 99.6% | 0.0617 | 2,942,470 | 7,377 |
| Calendar-aware | 0.0% | 84.5% | 84.5% | 0.0667 | 2,536,614 | 0.0 |

Fixed exact plan: 48.6 s. Twenty weather episodes: 147.0 s. The same zero-budget-violation and
completion-certainty tradeoff persists. The instance is replicated, not a real network.

## Interpretation

Budget and capacity feasibility do not imply crew-calendar feasibility. Calendar-aware execution
removes unscheduled work, but with whole-action deferral it is conservative: it trades scope for
completion certainty and does not lower mean risk. It is a policy comparison, not a forecast or a
stochastic dynamic program.

## Limits

- Calendar observed before deferral; not a forecast.
- Assumed independent weather loss and fixed outage block.
- Whole-action deferral; no partial treatment credit.
- No safety, access, field calibration, or asset-owner priority claim.
