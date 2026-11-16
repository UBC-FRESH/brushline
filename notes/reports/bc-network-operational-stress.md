# Weather and outage stress

## Question

Does the median rolling-policy first-year package remain schedulable when an assumed weather and
outage calendar removes field days?

## Method

- Median rolling episode 18, first year 2027.
- 75-day fall work window.
- Fixed 5-day outage block.
- Independent 20% weather-loss probability on each day.
- 50 scenarios, seed 7.
- Baseline uses the same window with no blocked days.

## Results

| Metric | Baseline | Stress |
|---|---:|---:|
| Fully feasible | yes | 0.0% |
| Shift assignments | 116 | 107 median |
| Mean completion | 100% | 93.4% |
| Unscheduled hours P50 | 0 | 50.2 |
| Unscheduled hours P90 | 0 | 97.7 |
| Mean blocked days | 0 | 19.4 |

The baseline package schedules all 813.7 productive hours in 63 days. Under the assumed weather and
outage calendar, no sampled scenario schedules every work item; the median scenario leaves about 50
hours unscheduled.

## Interpretation

The package is calendar-sensitive. This is a useful operational finding: a shorter fall window and
weather losses consume the available scheduling slack. Possible responses are a longer window,
additional crews or machines, a smaller first-year scope, or explicit weather reserve in the policy.

This is not evidence that the policy is field-infeasible. Weather and outage assumptions are
prototype values.

## Limits

- Weather loss is independent per day; no forecast or serial correlation.
- Outage days are assumed, not asset-owner windows.
- Only the median episode and its first year are stressed.
- No field calibration, outage schedule, safety certification, or clearance standard.
