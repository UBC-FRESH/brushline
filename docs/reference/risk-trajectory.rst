Multi-year risk trajectory
==========================

The first-year scope remedies were evaluated for scheduling completion. This trajectory replay asks
what happens to residual risk over 2027-2031 when first-year actions are deferred and future actions
are held fixed.

It is a fixed-future replay, not a re-optimized adaptive policy. Future actions are not changed after
the first-year deferral, so the trajectory is a sensitivity, not a recommendation.

## Results

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
   * - Risk-ranked first-year 20%
     - 0.1546
     - 0.0560
     - 0.0473
     - 0.0480
     - 0.0486
     - 0.0413
     - 0.0413
   * - Proportional first-year 20%
     - 0.1581
     - 0.0594
     - 0.0508
     - 0.0515
     - 0.0520
     - 0.0448
     - 0.0448

Mean deferred fraction: 21.3%.

The first-year risk loss persists across the horizon under fixed future actions. Risk-ranked deferral
loses less first-year risk reduction than proportional deferral, but both leave a persistent gap in
2031.

## Limits

- Future actions are held fixed; no re-optimization after deferral.
- Risk ranking is first-year only and uses replay reductions.
- Whole actions are deferred; the actual fraction can overshoot.
- No multi-year re-optimization, recurrence, weather, outage, safety, or asset-owner model.
