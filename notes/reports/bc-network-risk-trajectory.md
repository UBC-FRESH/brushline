# Multi-year risk trajectory

## Question

Does the first-year risk loss from scope deferral persist when future actions are held fixed? This is
a fixed-future replay, not a re-optimized adaptive policy.

## Method

- 20 rolling episodes.
- Start from network segment risks.
- Replay 2027-2031 with 3% annual growth and fixed future actions.
- Cases: full policy, risk-ranked first-year 20% deferral, proportional first-year 20% deferral.
- Mean actual deferred fraction: 21.3%.

## Results

| Case | 2027 | 2028 | 2029 | 2030 | 2031 | Mean loss | Final loss |
|---|---:|---:|---:|---:|---:|---:|---:|
| Full policy | 0.1133 | 0.0147 | 0.0060 | 0.0067 | 0.0073 | 0.0 | 0.0 |
| Risk-ranked first-year 20% | 0.1546 | 0.0560 | 0.0473 | 0.0480 | 0.0486 | 0.0413 | 0.0413 |
| Proportional first-year 20% | 0.1581 | 0.0594 | 0.0508 | 0.0515 | 0.0520 | 0.0448 | 0.0448 |

The first-year risk loss persists through 2031 under fixed future actions. Risk-ranked deferral
protects slightly more risk reduction than proportional deferral, but both leave a persistent gap.

## Interpretation

A first-year scope reduction is not only a first-year scheduling decision. If future actions are not
changed, the deferred risk remains in the system. Re-optimization could recover some of it, but that
recovery is not modelled here.

## Limits

- Future actions held fixed; no re-planning after deferral.
- First-year risk ranking only.
- Whole actions deferred; actual fraction can overshoot.
- No recurrence, multi-year re-optimization, weather, outage, safety, or asset-owner priority.
