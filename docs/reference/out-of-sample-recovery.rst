Out-of-sample recovery
======================

The fixed-factor recovery test reused the original annual factors for 2028-2031. This test keeps the
first-year risk-ranked deferral fixed and resamples future cost, productivity, and capacity factors
independently for each future path.

Future years are re-solved with the rolling persistence forecast and a two-year lookahead. This is a
stochastic recovery test, not a stochastic dynamic program.

Method
------

- 20 rolling episodes.
- First-year risk-ranked deferral: 20% target, 21.3% actual mean deferral.
- Five independent future-factor paths per episode, 100 paths total.
- 2028-2031 re-solved for each path.
- Future factors sampled from the same lognormal assumptions as the rolling policy.

Results
-------

.. list-table::
   :header-rows: 1

   * - Metric
     - P10
     - P50
     - P90
     - Mean
   * - Final risk gap
     - -0.0078
     - -0.0010
     - 0.0072
     - -0.0008
   * - Recovery
     - 0.0340
     - 0.0421
     - 0.0491
     - 0.0421
   * - Final gap within 0.005
     - —
     - 87.0% of paths
     - —
     - —

A negative final gap means the reoptimized path ends below the full policy's final risk. The median
gap is slightly negative; 87% of paths are within 0.005 of the full policy.

Cost bands:

- reoptimized: 284,835-286,788 CAD, mean 285,868;
- no reoptimization: 227,290-272,072 CAD, mean 251,312;
- full policy: 273,213-326,472 CAD, mean 299,052.

The reoptimized path spends more than no reoptimization to recover risk, but less than the full policy
on average.

Limits
------

- First-year deferral is fixed.
- Future factors are independent draws; no serial correlation or calibrated forecast process.
- Future years use a persistence forecast and two-year lookahead, not a stochastic dynamic program.
- First-year risk ranking only.
- No recurrence, weather, outage, safety, or asset-owner priority model.
