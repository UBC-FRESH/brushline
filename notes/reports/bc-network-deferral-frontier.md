# Deferral-fraction frontier

## Question

Why defer 20% of first-year work? This frontier sweeps risk-ranked deferral from 0% to 25% and
reports calendar completion, residual risk, recovery, and five-year cost.

## Results

| Target | Actual deferred | Completion 75 | Completion 105 | Fixed final loss | Recovery final loss | Reopt cost |
|---:|---:|---:|---:|---:|---:|---:|
| 0% | 0.0% | 13.2% | 61.9% | 0.0000 | 0.000003 | 298,723 |
| 5% | 6.0% | 19.7% | 67.7% | 0.0109 | 0.000003 | 295,027 |
| 10% | 11.1% | 27.9% | 70.0% | 0.0209 | 0.000003 | 292,078 |
| 15% | 16.1% | 39.3% | 79.7% | 0.0307 | 0.000000 | 289,012 |
| 20% | 21.3% | 47.1% | 87.4% | 0.0413 | 0.000003 | 285,825 |
| 25% | 26.0% | 53.3% | 91.9% | 0.0509 | 0.000000 | 283,082 |

- All targets are first-year budget-feasible in 100% of scenarios.
- Higher deferral improves completion and lowers reoptimized cost.
- Fixed-future residual risk increases with deferral.
- Fixed-factor recovery closes essentially all of the final risk gap at every tested fraction.

## Interpretation

The frontier makes the 20% target a choice rather than an assumption. 25% gives the highest completion
and lowest reoptimized cost but the largest fixed-future risk loss; 5-10% protects more risk reduction
but is more calendar-sensitive. The table does not choose a risk appetite.

## Limits

- Fixed-factor recovery is a screening result; only the 20% point has out-of-sample validation.
- Whole actions are deferred; actual fractions overshoot.
- Risk ranking is first-year only.
- No recurrence, safety, asset-owner priority, weather, or field calibration in the risk model.
