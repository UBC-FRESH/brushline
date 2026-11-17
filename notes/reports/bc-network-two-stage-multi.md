# Multi-year two-stage operational recourse

## Question

Can annual operational recourse keep a fixed five-year nominal plan feasible when cost, productivity,
and capacity factors vary each year?

## Method

- First-stage plan: nominal balanced, 230 actions over 2027-2031.
- 100 annual-factor scenarios, seed 23.
- Annual budget 60,000 CAD; annual capacity 6,000 hours.
- Each year, defer lowest-first-year-risk-reduction-per-hour actions only when the observed budget or
  capacity is exceeded.
- No future strategic re-optimization.

## Results

| Metric | Static | Multi-year recourse |
|---|---:|---:|
| Budget violation, any year | 93.0% | 0.0% |
| Capacity violation, any year | 0.0% | 0.0% |
| 5-year cost P50 | 300,710 | 296,000 |
| Completion P50 | 100.0% | 95.1% |
| Mean completion | 100.0% | 93.9% |
| Mean risk | 0.0294 | 0.0330 |

- Mean deferred workload: 13.0 actions, 306.0 hours.
- Mean risk loss: 0.0036.
- Static risk is constant; recourse risk increases slightly as actions are deferred.

## Interpretation

Annual operational recourse removes budget violations across the fixed five-year plan while keeping
most of the planned work. It is a practical middle ground between static execution and full strategic
re-planning, but it does not optimize risk across future years.

## Limits

- Fixed first-stage plan; no strategic re-optimization.
- No weather, outage, recurrence, safety, or asset-owner priority model.
- Risk ranking is first-year action benefit per hour.
- Not a stochastic dynamic program.
