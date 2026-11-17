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

Results
-------

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

590-segment scale test
----------------------

A replicated 590-segment stress instance uses the same policy. The fixed plan is exact; annual
rolling re-solves use the Fresh Solutions heuristic.

.. list-table::
   :header-rows: 1

   * - Policy
     - Budget violation
     - Completion P50
     - Mean risk
     - Cost P50
   * - Static fixed
     - 95.0%
     - 100.0%
     - 0.0291
     - 3,008,496
   * - Fixed-future recourse
     - 0.0%
     - 93.9%
     - 0.0329
     - 2,811,913
   * - Rolling-only
     - 55.0%
     - 100.0%
     - 0.0290
     - 2,969,701
   * - Rolling recourse
     - 0.0%
     - 99.6%
     - 0.0340
     - 2,942,470

Runtime: fixed exact 47.1 s; rolling heuristic 87.2 s for 20 episodes. The instance is replicated,
not a real 590-segment network, and the heuristic makes no global-optimality claim.

Limits
------

- Fixed first year.
- No weather, outage, recurrence, safety, or asset-owner priority model.
- First-year risk ranking for deferral.
- Rolling policy is a persistence-forecast heuristic, not a stochastic dynamic program.
- 20 episodes.
