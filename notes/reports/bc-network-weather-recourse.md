# Weather/outage-aware recourse

## Question

Does budget- and capacity-feasible rolling recourse remain schedulable once an assumed weather and
outage calendar is included, and how much forecast error remains if the policy cannot observe the
calendar before committing actions?

## Method

- 20 annual episodes, seed 7; same factor paths as the rolling-recourse comparison.
- 75-day fall window; five fixed outage days; independent 20% weather-loss probability per day.
- Calendar-naive keeps the resource-feasible plan and accepts partial execution.
- Forecast-aware plans against an independent synthetic forecast calendar and executes under the
  actual calendar.
- Calendar-aware defers unscheduled actions until every retained action fits the observed calendar.
- Crew and machine calendar uses the prototype contractor mix.

The forecast is a synthetic draw from the same assumed distribution, not a forecast product. The
observed-calendar case uses within-year calendar information before deferral.

## Results

| Case | Budget violation | Completed scope P50 | Retained scope P50 | Mean risk | Cost P50 | Unscheduled h | Calendar deferrals |
|---|---:|---:|---:|---:|---:|---:|---:|
| Calendar-naive | 0.0% | 88.4% | 99.4% | 0.0480 | 297,595 | 605.9 | 0.0 |
| Forecast-aware | 0.0% | 86.2% | 88.3% | 0.0526 | 264,470 | 64.7 | 39.2 |
| Calendar-aware | 0.0% | 87.6% | 87.6% | 0.0502 | 264,047 | 0.0 | 39.9 |

Forecast awareness reduces unscheduled work from 605.9 h to 64.7 h, but forecast error remains.
Observed-calendar awareness eliminates unscheduled retained work but costs about 1.4 percentage
points of mean scope and raises mean risk. Neither aware case lowers risk; both convert partial work
into deferred scope.

## 590-segment scale test

A replicated 590-segment instance scales the workforce to 30 crews and 30 machines. The fixed plan
is exact; annual re-solves use Fresh Solutions.

| Case | Budget violation | Completed scope P50 | Retained scope P50 | Mean risk | Cost P50 | Unscheduled h |
|---|---:|---:|---:|---:|---:|---:|
| Calendar-naive | 0.0% | 85.9% | 99.6% | 0.0617 | 2,942,470 | 7,377 |
| Forecast-aware | 0.0% | 83.6% | 86.4% | 0.0713 | 2,539,520 | 681.5 |
| Calendar-aware | 0.0% | 84.5% | 84.5% | 0.0667 | 2,536,614 | 0.0 |

Fixed exact plan: 48.6 s. Twenty weather episodes: 220.8 s. Forecast error leaves 681.5 h
unscheduled at scale, while observed-calendar awareness eliminates unscheduled retained work. The
instance is replicated, not a real network.

## Interpretation

Budget and capacity feasibility do not imply crew-calendar feasibility. Forecast-aware execution
reduces unscheduled work but cannot eliminate forecast error. Observed-calendar awareness removes
unscheduled work, with whole-action deferral trading scope for completion certainty without lowering
mean risk. These are policy comparisons, not forecast products or stochastic dynamic programs.

## Limits

- Forecast awareness uses a synthetic calendar draw, not a weather forecast.
- Observed-calendar awareness uses within-year information before deferral.
- Assumed independent weather loss and fixed outage block.
- Whole-action deferral; no partial treatment credit.
- No safety, access, field calibration, or asset-owner priority claim.
