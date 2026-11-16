Frontier out-of-sample validation
=================================

The deferral-fraction frontier used fixed-factor recovery for screening. This validation retests every
candidate with resampled future cost, productivity, and capacity factors.

Paths: 100 for the 0% and 20% points; 40 for 5%, 10%, 15%, and 25%. Future years are re-solved with
the rolling persistence forecast and a two-year lookahead. Completion remains from the fixed-factor
calendar scan; this validation covers risk recovery and cost.

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
     - 40
     - -0.0008
     - 0.0082
     - 0.0121
     - 85.0%
     - 294,942
   * - 10%
     - 40
     - -0.0022
     - 0.0076
     - 0.0225
     - 85.0%
     - 292,022
   * - 15%
     - 40
     - 0.0003
     - 0.0068
     - 0.0291
     - 82.5%
     - 289,025
   * - 20%
     - 100
     - -0.0010
     - 0.0072
     - 0.0421
     - 87.0%
     - 285,927
   * - 25%
     - 40
     - -0.0015
     - 0.0050
     - 0.0530
     - 90.0%
     - 283,134

All tested fractions recover most or all of the fixed-future risk gap under resampled futures. The
25% point has the highest recovery and lowest median reoptimized cost, but also the largest
fixed-future risk loss. The table does not select a risk appetite.

## Limits

- Path counts differ between points; 5/10/15/25 use 40 paths, not 100.
- First-year deferral is fixed.
- Future factors are independent draws; no serial correlation or calibrated forecast model.
- The rolling policy is a persistence-forecast heuristic, not a stochastic dynamic program.
- No recurrence, weather, outage, safety, or asset-owner priority model.
