# Fall-window capacity remedy

## Question

Can a longer fall work window recover the scope lost when calendar-aware recourse defers
unschedulable actions, without adding crews or machines?

## Method

- 20 episodes, seed 7; observed-calendar awareness.
- 75-, 90-, and 105-day fall windows.
- Five fixed outage days and independent 20% weather-loss probability per day.
- Crew and machine mix held fixed.
- Whole-action deferral when the observed calendar cannot fit an action.

## Results

| Window days | Completed scope P50 | Retained scope P50 | Mean risk | Cost P50 | Unscheduled h | Calendar deferrals |
|---:|---:|---:|---:|---:|---:|---:|
| 75 | 87.6% | 87.6% | 0.0502 | 264,047 | 0.0 | 39.9 |
| 90 | 95.9% | 95.9% | 0.0365 | 285,490 | 0.0 | 15.0 |
| 105 | 98.1% | 98.1% | 0.0333 | 294,012 | 0.0 | 4.6 |

Extending the window recovers scope and lowers risk. Action cost rises because more work is
retained; added seasonal overhead, supervision, and weather exposure are not modelled.

## Interpretation

The 75-day window is the binding operational constraint for calendar-aware execution, not budget or
capacity. A 90-day window recovers most of the deferred scope; 105 days recovers almost all of it.
This is a capacity remedy through calendar length, not an additional crew or machine.

## Limits

- Not a field calendar; no access or crew-availability constraints.
- Crew and machine mix fixed.
- No added seasonal overhead or supervision cost.
- Whole-action deferral; no partial treatment credit.
- No safety, asset-owner priority, or field-calibration claim.
