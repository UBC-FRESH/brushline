# Rolling policy at 590 segments

## Question

Does the annual rolling policy retain its budget and cost behavior when the stateful instance is
scaled beyond the 59-segment network? This is a replicated stress test, not a real 590-segment
network.

## Method

- 590 segments: ten perturbed copies of the 59-segment network.
- Annual budget and capacity scaled to 600,000 CAD and 60,000 hours/year.
- Five-year horizon, 20 annual-factor episodes, seed 7.
- Two-year lookahead.
- Fixed plan: exact stateful MILP at 590 segments, optimal.
- Rolling policy: Fresh Solutions local search for each annual re-solve, 100 iterations, all
  feasible. This is not an optimality claim for the rolling policy.
- Annual cost sigma 0.18, productive-hours sigma 0.15, capacity sigma 0.15.

## Results

| Policy | 5-year cost P10 | P50 | P90 | Mean risk | Budget violation |
|---|---:|---:|---:|---:|---:|
| Fixed nominal, 590 exact | 2,655,911 | 3,008,496 | 3,335,908 | 0.0291 | 95.0% |
| Rolling policy, 590 heuristic | 2,902,237 | 2,995,818 | 2,998,129 | 0.0297 | 0.0% |

- Capacity violation probability: 0.0% for both.
- Mean risk-equivalent objective: fixed 0.1030; rolling 0.0297.
- Mean regret: 0.0733; P90 regret: 0.1222.
- Rolling improved the objective in 100% of episodes.
- Solve time: fixed exact 48.8 s; 20 rolling episodes 66.9 s.

The 59-segment result had a 265,469-333,437 CAD fixed band and a 298,123-299,398 CAD rolling band
with mean risk 0.0294 and 0.0296. The scaled test shows the same qualitative trade: a small nominal
risk sacrifice for a much narrower cost band and annual budget feasibility.

## Limits

- The 590-segment instance is replicated and perturbed, not a real network.
- The rolling policy uses heuristic annual plans; all were feasible, none is claimed optimal.
- Twenty episodes and independent annual factors are a demonstration sample.
- No field calibration, outage constraint, safety certification, or asset-owner approval.
