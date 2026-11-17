100-path chance constraint
==========================

The budget chance constraint was retrained on 100 sampled future paths, allowing at most 10 budget
violations per year while keeping capacity hard. It is tested on 100 independent paths.

This remains a sampled chance constraint, not a distributional guarantee.

## Results

.. list-table::
   :header-rows: 1

   * - Plan
     - 5-year cost P10-P90
     - Mean risk
     - Budget violation
   * - Chance, 100 training paths
     - 176,580-220,447
     - 0.0671
     - 8.0%
   * - Chance, 20 training paths
     - 198,743-247,028
     - 0.0516
     - 21.0%
   * - Nominal balanced
     - 269,679-333,777
     - 0.0294
     - 93.0%

The 100-path plan costs 197,659 CAD nominally and has 155 actions.

Out-of-sample budget violation falls from 21% to **8%**, but risk rises from 0.0516 to 0.0671. The
plan is more conservative and still does not meet a 5% budget-risk target.

## Interpretation

More training paths move the chance plan closer to budget robustness, at the cost of substantially less
risk reduction. The sampled constraint remains sensitive to the training set and does not provide a
distributional guarantee.

## Limits

- Sampled budget chance; capacity hard.
- 100 training paths; 100 independent test paths.
- Shared static decisions; no recourse.
- No risk, weather, outage, safety, asset-owner priority, or field calibration.
