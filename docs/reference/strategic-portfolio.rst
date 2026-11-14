Strategic network portfolio
===========================

P6.2 selects at most one strategic option for each segment and period under period budgets, method
capacities, a service-level target, a risk target, and a spatial-continuity preference.

Inputs
------

``PortfolioSegment`` records a segment, its span and sequence, length, and no-treatment service, risk,
and uncertainty. ``PortfolioPeriod`` records a year, budget, and capacity by method.
``PortfolioOption`` records a segment/period option, action, method, cost, capacity units, service,
risk, and uncertainty.

Every option references a known segment and period. Option ids are unique. A no-treatment option must
have zero cost. The committed example is built in the tests; there is no separate portfolio fixture in
P6.2.

Selection
---------

``build_strategic_portfolio`` runs three deterministic passes:

1. **Service repair.** While aggregate service is below ``service_target``, pick the feasible option
   with the largest service gain per cost. Skip zero or negative gains.
2. **Objective improvement.** While a feasible option improves the weighted objective, add it.
3. **Local swap.** Replace a selected option with a better feasible option for the same segment and
   period.

Budget and method capacity are checked before every selection. The plan reports every hard violation.

Objective
---------

.. code-block:: text

   service_weight * service
   - risk_weight * risk
   - uncertainty_weight * uncertainty
   - cost_weight * total_cost
   - continuity_weight * (1 - continuity_score)

``service``, ``risk``, and ``uncertainty`` are length- and period-weighted. ``continuity_score`` is the
share of adjacent segment pairs in a span that both have a selected option in the same period. The
scalar objective never replaces the separate service, risk, uncertainty, cost, and feasibility fields.

Constraints and reports
-----------------------

- Budget and capacity violations are hard ``PORTFOLIO-BUDGET`` and ``PORTFOLIO-CAPACITY`` errors.
- A service miss is the hard ``PORTFOLIO-SERVICE`` error.
- A risk target miss is the soft ``PORTFOLIO-RISK`` warning.
- ``period_summary`` records cost, budget, capacity used, service, risk, uncertainty, and selection count
  per period.
- ``selections`` records the selected option and its outcome.
- The baseline service, risk, and uncertainty are reported for comparison.

Limits
------

- The greedy construction and local swap are heuristic, not a global optimum.
- The options and outcomes are supplied evidence; P6.7 wires them to the synthetic corridor.
- ``seed`` is a scenario identifier; the current construction is deterministic without randomness.
- A risk target is soft; a decision-maker must accept or reject the reported miss.
