Static budget-headroom plans
============================

The static-plan comparison asks what happens when an agency cannot re-plan every year. It evaluates
existing frontier plans against a **common actual annual budget** and the same annual cost,
productive-hours, and capacity factors used by the rolling-policy experiment.

This is candidate selection from the existing frontier, not robust optimization. The candidate's
nominal budget is the budget used to build its treatment schedule; the actual budget is the common
60,000 CAD/year constraint against which all candidates are tested.

## Network result

- 8,737 ha, 59 segments, 2027-2031.
- 20 annual-factor episodes, seed 7.
- Actual budget 60,000 CAD/year; actual capacity 6,000 hours/year.
- Budget-risk limit for the starred candidate: 5%.

.. list-table::
   :header-rows: 1

   * - Candidate
     - Nominal budget
     - 5-year cost P10-P90
     - Mean risk
     - Budget violation
   * - milp-budget-20000
     - 20,000
     - 88,293-110,903
     - 0.1741
     - 0.0%
   * - milp-budget-30000 *
     - 30,000
     - 132,246-166,121
     - 0.1009
     - 0.0%
   * - milp-budget-45000
     - 45,000
     - 198,832-249,729
     - 0.0526
     - 10.0%
   * - milp-budget-60000
     - 60,000
     - 265,469-333,438
     - 0.0294
     - 95.0%
   * - milp-budget-80000
     - 80,000
     - 353,128-443,639
     - 0.0142
     - 100.0%
   * - milp-budget-100000
     - 100,000
     - 442,405-555,672
     - 0.0093
     - 100.0%

The 30,000 CAD target is the lowest-risk candidate within the 5% budget-risk limit. The 45,000 CAD
target has lower risk but breaches the actual budget in about 10% of episodes. The 60,000 CAD balanced
plan has lower risk still but breaches in 95% of episodes because it commits a schedule that uses
essentially the whole nominal budget.

## Decision trade

The static candidates leave budget headroom by building to a lower nominal budget:

- 30,000 target: 132,246-166,121 CAD five-year cost, risk 0.1009, no budget violation.
- 45,000 target: 198,832-249,729 CAD, risk 0.0526, 10% budget violation.
- Rolling policy: 298,123-299,398 CAD, risk 0.0296, no budget violation.

Rolling gives much lower risk than the static candidates at a higher treatment cost. The static
30,000 target is the low-cost option, not the risk-minimizing option.

## Limits

- Candidate evaluation, not robust optimization or a probabilistic guarantee.
- The actual budget is fixed at 60,000 CAD/year for this comparison.
- Twenty episodes and independent annual factors are a demonstration sample.
- The MILP is exact only for the declared linear risk state at 59 segments.
- No field calibration, outage constraint, safety certification, or asset-owner approval.
