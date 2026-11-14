Business-as-usual baseline
==========================

P6.4 expands a fixed cycle or an explicit action into the same segment-period options as the optimized
portfolio. The comparison is like-for-like: same segments, periods, options, budget, capacity, and
outcome assumptions.

Fixed cycle
-----------

``BauConfig`` sets the cycle length, first cycle year, optional action id, and budget enforcement. For
each segment and period whose year is on the cycle, the baseline selects the first option with the
requested action. If no action is named, the first option is used.

``build_bau_plan`` records the selections, period summaries, present cost, service attainment, risk,
uncertainty, no-treatment baselines, feasibility, and violations.

Budget and capacity
-------------------

When ``enforce_budget`` is true, the baseline drops selected options until the hard budget and capacity
limits hold. The drop is not hidden: the plan records ``BAU-TRUNCATED`` and is infeasible. When
enforcement is false, the plan retains the fixed cycle and records ``BAU-BUDGET`` or ``BAU-CAPACITY``.

Comparison
----------

``compare_bau`` reports:

.. list-table::
   :header-rows: 1
   :widths: 30 22 48

   * - Field
     - Sign
     - Meaning
   * - ``present_cost_delta``
     - BAU - optimized
     - Negative means the optimized plan costs more.
   * - ``service_delta``
     - optimized - BAU
     - Positive means the optimized plan improves service.
   * - ``risk_delta``
     - optimized - BAU
     - Negative means the optimized plan lowers risk.
   * - ``uncertainty_delta``
     - optimized - BAU
     - Negative means the optimized plan lowers uncertainty.

``like_for_like`` is true only for the same instance and period scope. A mismatch is reported, not
reconciled silently. Both feasibility flags are retained.

.. code-block:: python

   from brushline.strategic.bau import BauConfig, build_bau_plan, compare_bau

   bau = build_bau_plan(
       policy_id="bau",
       instance_id="corridor",
       segments=segments,
       periods=periods,
       options=options,
       config=BauConfig(cycle_years=4, start_year=2026),
   )
   comparison = compare_bau(optimized, bau)
   assert comparison.like_for_like

Caveats
-------

- BAU is a scenario, not a claim about the owner's actual past decisions.
- A fixed cycle is one baseline; an explicit current-policy calendar is a later input.
- The same option outcomes are used, so the comparison isolates selection, not model error.
- A truncated baseline is infeasible and explicitly flagged.

Limits
------

- Tactical contracts, seasonality, and crew scheduling are out of scope.
- The baseline does not claim optimality or a real-world counterfactual.
- Budget enforcement changes the fixed cycle; the truncation flag is required to read the result.
