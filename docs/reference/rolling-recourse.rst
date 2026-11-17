Rolling policy with recourse
============================

This comparison combines the fixed first-year nominal plan with the rolling policy and annual
operational deferral. It compares four cases on the same annual-factor paths:

- static fixed plan;
- fixed-future annual recourse;
- rolling-only;
- rolling recourse.

The first year is fixed. Later years are re-solved with the rolling persistence forecast and a
two-year lookahead. In the recourse cases, the current year's actions are deferred by lowest
first-year risk reduction per hour when budget or capacity is exceeded.

## Results

20 episodes, seed 7.

.. list-table::
   :header-rows: 1

   * - Policy
     - Budget violation
     - Completion P50
     - Mean completion
     - Mean risk
     - Cost P50
   * - Static fixed
     - 95.0%
     - 100.0%
     - 100.0%
     - 0.0294
     - 300,711
   * - Fixed-future recourse
     - 0.0%
     - 93.1%
     - 93.3%
     - 0.0335
     - 279,595
   * - Rolling-only
     - 55.0%
     - 100.0%
     - 100.0%
     - 0.0293
     - 300,236
   * - Rolling recourse
     - 0.0%
     - 99.4%
     - 98.8%
     - 0.0349
     - 297,451

Rolling recourse restores almost all first-year scope while remaining budget- and capacity-feasible.
It costs more future treatment than fixed-future recourse and does not reduce mean risk in this run.
The risk metric mixes the fixed first-year risk loss with re-optimized future years; it is not a
like-for-like multi-year risk improvement.

## Limits

- Fixed first year.
- No weather, outage, recurrence, safety, or asset-owner priority model.
- First-year risk ranking for deferral.
- Rolling policy is a persistence-forecast heuristic, not a stochastic dynamic program.
- 20 episodes.
