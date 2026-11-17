# Two-stage operational recourse

## Question

Can a fixed first-year strategic plan be made budget- and capacity-feasible by deferring low-benefit
actions after annual factors are observed?

## Method

- First-stage plan: nominal balanced, 46 first-year actions.
- 100 factor scenarios, seed 23.
- Budget 60,000 CAD/year; capacity 6,000 hours/year.
- Second stage defers whole actions by lowest first-year risk reduction per hour until budget and
  capacity are satisfied.

## Results

| Metric | Static | Two-stage recourse |
|---|---:|---:|
| Budget violation | 44.0% | 0.0% |
| Capacity violation | 0.0% | 0.0% |
| Cost P50 | 57,939 | 57,939 |
| Cost P90 | 71,471 | 59,592 |
| Completion P50 | 100.0% | 100.0% |
| Mean completion | 100.0% | 94.0% |
| Mean risk loss | 0.0000 | 0.0121 |

- Mean deferred workload: 2.75 actions, 60.2 crew-hours.
- Mean static risk: 0.1147; mean recourse risk: 0.1268.

The second stage eliminates first-year budget violations while retaining most of the planned work.
It does not guarantee multi-year feasibility or risk.

## Limits

- First-year only.
- First-stage plan fixed; no strategic re-optimization.
- No weather, outage, recurrence, future re-planning, or safety model.
- First-year risk reduction per hour only.
