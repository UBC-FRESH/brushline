Frontier out-of-sample validation
=================================

The deferral-fraction frontier used fixed-factor recovery for screening. This validation retests every
candidate with the same resampled future cost, productivity, and capacity factors.

Five future paths per episode, 100 paths per target. Future years are re-solved with the rolling
persistence forecast and a two-year lookahead. Completion remains from the fixed-factor calendar scan;
this validation covers risk recovery and cost.

## Results

.. list-table::
   :header-rows: 1

   * - Target
     - Paths
     - Final gap P50
     - Final gap P90
     - Recovery P50
     - Within 0.005
     - Reopt cost P50
   * - 0%
     - 100
     - 0.0000
     - 0.0000
     - 0.0000
     - 100.0%
     - 295,899
   * - 5%
     - 100
     - -0.0010
     - 0.0072
     - 0.0112
     - 87.0%
     - 295,043
   * - 10%
     - 100
     - -0.0010
     - 0.0072
     - 0.0214
     - 87.0%
     - 291,878
   * - 15%
     - 100
     - -0.0010
     - 0.0072
     - 0.0312
     - 87.0%
     - 289,012
   * - 20%
     - 100
     - -0.0010
     - 0.0072
     - 0.0421
     - 87.0%
     - 285,927
   * - 25%
     - 100
     - -0.0010
     - 0.0072
     - 0.0516
     - 87.0%
     - 283,018

The final-gap distribution is the same across targets because the same future path set is used and
reoptimization closes the gap in most paths. Recovery and cost vary with the deferral fraction.

All tested fractions recover most or all of the fixed-future risk gap under resampled futures. The
25% point has the highest recovery and lowest median reoptimized cost, but also the largest
fixed-future risk loss. The table does not select a risk appetite.

## Limits

- First-year deferral is fixed.
- Future factors are independent draws; no serial correlation or calibrated forecast model.
- The rolling policy is a persistence-forecast heuristic, not a stochastic dynamic program.
- No recurrence, weather, outage, safety, or asset-owner priority model.
