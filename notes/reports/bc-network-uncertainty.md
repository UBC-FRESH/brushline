# BC network execution uncertainty

## Method

The uncertainty sampler held the balanced tactical plan fixed and varied:

- cost multiplier: lognormal, sigma 0.18;
- productive-hours multiplier: lognormal, sigma 0.15;
- contractor-capacity multiplier: lognormal, sigma 0.15.

500 samples, seed 7. Annual budget 60,000 CAD; annual crew-hour capacity 6,000 h.

## Results

| Metric | P10 | P50 | P90 | Mean |
|---|---:|---:|---:|---:|
| Total cost | 231,034 | 296,536 | 373,432 | 301,582 |
| Crew-hours | 4,090 | 5,014 | 5,956 | 5,016 |

- Budget-exceedance probability: **48.4%**
- Crew-hour capacity shortfall probability: **0.0%**
- Contractor capacity shortfall probability: **0.0%**

Deterministic stresses:

| Case | Cost | Hours | Budget overrun |
|---|---:|---:|---:|
| Baseline | 299,859 | 4,998 | 0 |
| Cost +20% | 359,831 | 4,998 | 59,831 |
| Productivity -20% | 299,859 | 6,248 | 0 |
| Capacity -20% | 299,859 | 4,998 | 0 |
| Combined stress | 359,831 | 6,248 | 59,831 |

## Interpretation

The plan is capacity-feasible under the sampled contractor capacity, but the annual budget has a
meaningful exceedance probability because the balanced plan sits close to the 60,000 CAD annual
budget. Cost variation dominates the immediate budget risk; crew capacity and contractor capacity are
not binding in this scenario.

This is execution sensitivity around a fixed plan. It does not re-optimize the plan inside each
sample. A stochastic adaptive policy would be a separate model.
