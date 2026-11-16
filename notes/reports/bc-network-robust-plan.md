# Scenario-robust static plan

## Question

Can a static multi-year plan be made robust to sampled budget and capacity uncertainty without
annual re-planning?

## Method

- 20 training paths from the rolling episode set.
- Shared segment-period-method decisions.
- One annual budget and one annual capacity row per training path, 200 robust rows.
- Risk objective only; treatment risk state remains nominal.
- Tested on 100 independent factor paths with a 60,000 CAD annual budget and 6,000-hour capacity.

## Results

| Plan | 5-year cost P10 | P50 | P90 | Mean risk | Budget violation | Capacity violation |
|---|---:|---:|---:|---:|---:|---:|
| Scenario-robust | 199,567 | 215,351 | 248,028 | 0.0516 | 23.0% | 0.0% |
| Nominal balanced | 269,679 | 291,824 | 333,777 | 0.0294 | 93.0% | 0.0% |

- Robust plan nominal cost: **221,876 CAD**; 170 actions.
- Training paths: 20; robust rows: 200.
- Out-of-sample budget violation falls from 93% to 23%, but remains above 5%.

## Interpretation

The scenario-robust plan materially reduces out-of-sample budget violations and costs less than the
nominal plan. It does not provide a distributional or chance-constrained guarantee because the robust
constraints cover only 20 training paths. It also gives up substantial risk reduction: mean risk is
0.0516 versus 0.0294.

A true guarantee would need more training scenarios, a chance-constrained formulation, or a robust
policy with recourse.

## Limits

- Shared static decisions; no scenario-specific recourse.
- Budget/capacity uncertainty only.
- 20 training paths; independent 100-path test.
- No risk, weather, outage, safety, asset-owner priority, or field-calibration model.
