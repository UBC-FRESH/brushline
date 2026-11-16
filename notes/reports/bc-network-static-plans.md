# Static budget-headroom plans

## Question

What fixed multi-year plan should an agency use if it cannot re-plan every year? The comparison tests
existing frontier plans against the same 60,000 CAD/year actual budget and the annual factors used by
the rolling-policy experiment.

This is candidate selection, not robust optimization.

## Method

- 8,737 ha, 59 segments, 2027-2031.
- Candidate plans: six existing MILP frontier points built to 20k-100k nominal annual budgets.
- Actual budget: 60,000 CAD/year.
- Actual capacity: 6,000 hours/year.
- 20 annual-factor episodes, seed 7; cost sigma 0.18, productive-hours sigma 0.15, capacity sigma
  0.15.
- Budget-risk limit for the starred candidate: 5%.

## Results

| Candidate | Nominal budget | 5-year cost P10 | P50 | P90 | Mean risk | Budget violation |
|---|---:|---:|---:|---:|---:|---:|
| milp-budget-20000 | 20,000 | 88,293 | 100,014 | 110,903 | 0.1741 | 0.0% |
| milp-budget-30000 * | 30,000 | 132,246 | 149,797 | 166,121 | 0.1009 | 0.0% |
| milp-budget-45000 | 45,000 | 198,832 | 225,235 | 249,729 | 0.0526 | 10.0% |
| milp-budget-60000 | 60,000 | 265,469 | 300,710 | 333,438 | 0.0294 | 95.0% |
| milp-budget-80000 | 80,000 | 353,128 | 399,973 | 443,639 | 0.0142 | 100.0% |
| milp-budget-100000 | 100,000 | 442,405 | 501,154 | 555,672 | 0.0093 | 100.0% |

The starred plan is the lowest-risk candidate within the 5% budget-risk limit.

## Interpretation

The 30,000 CAD nominal target leaves enough budget headroom to avoid a budget breach in all 20
episodes, but its mean risk is 0.1009 versus 0.0296 for the rolling policy. The 45,000 CAD target
reduces risk to 0.0526 at a 10% budget-violation rate. The 60,000 CAD balanced plan has lower risk
still but breaches the actual budget in 95% of episodes.

For an agency that cannot re-plan annually, this is a budget-risk versus risk-reduction choice.
Rolling dominates on risk and budget stability, but costs more than the low-budget static candidates.

## Limits

- Candidate evaluation, not robust optimization or a probabilistic guarantee.
- The actual budget is fixed at 60,000 CAD/year.
- Twenty episodes and independent annual factors are a demonstration sample.
- The MILP is exact only for the declared linear risk state at 59 segments.
- No field calibration, outage constraint, safety certification, or asset-owner approval.
