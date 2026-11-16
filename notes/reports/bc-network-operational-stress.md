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

## All-episode scan

The first-year calendar stress was repeated for all 20 rolling episodes, with 50 scenarios each.

- Baseline 75-day feasible: **10/20 (50%)**
- Scenario-level full completion: **13.2%**
- Episodes with full stress completion: **2/20**
- Mean work completion: **85.6%**
- Unscheduled hours P50: **127.5**
- Unscheduled hours P90: **372.3**
- Failure sources: fall window **10**, weather/outage **8**, crew capacity **0**, fully feasible **2**

Window sensitivity:

| Window | Scenario full completion | Mean unscheduled hours |
|---:|---:|---:|
| 75 days | 13.8% | 165.8 |
| 90 days | 40.3% | 83.7 |
| 105 days | 62.8% | 38.3 |

The 75-day window is the primary constraint. However, extending the window to 105 days still does
not reach full completion under the assumed weather calendar. A longer window, more crew/machine
capacity, a smaller scope, or explicit weather reserve would all need evaluation.

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
