Rolling recovery after deferral
===============================

The fixed-future trajectory showed that first-year scope deferral leaves a persistent risk gap. This
experiment asks whether re-optimizing future years with the rolling policy closes that gap.

The first-year risk-ranked deferral is fixed; later years are re-solved with the same annual factors,
the persistence forecast, and a two-year lookahead. This is not a stochastic multi-year policy
guarantee.

Results
-------

.. list-table::
   :header-rows: 1

   * - Case
     - 2027
     - 2028
     - 2029
     - 2030
     - 2031
     - Mean loss
     - Final loss
   * - Full policy
     - 0.1133
     - 0.0147
     - 0.0060
     - 0.0067
     - 0.0073
     - 0.0
     - 0.0
   * - Deferred, no reoptimization
     - 0.1546
     - 0.0560
     - 0.0473
     - 0.0480
     - 0.0486
     - 0.0413
     - 0.0413
   * - Deferred, rolling reoptimization
     - 0.1546
     - 0.0318
     - 0.0063
     - 0.0067
     - 0.0073
     - 0.0117
     - 0.000003

Mean recovery: **0.0295**. Final recovery: **0.0413**.

The rolling policy spends the next year closing most of the deferral gap. By 2029 the risk path is
close to the full plan, and the final-year gap is effectively zero.

Cost
----

Mean five-year treatment cost over the 20 episodes:

- full policy: **298,797 CAD**;
- deferred, no reoptimization: **285,970 CAD**;
- deferred, rolling reoptimization: **285,825 CAD**.

The re-optimized path retains most of the first-year cost saving while recovering the risk gap under
the fixed-factor assumptions.

Limits
------

- First-year deferral is fixed; later plans cannot reverse it.
- Annual factors are fixed from the rolling episode; no new uncertainty is sampled.
- The rolling policy is a persistence-forecast heuristic, not a global or stochastic optimum.
- Risk ranking is first-year only.
- No recurrence, weather, outage, safety, or asset-owner priority model.
