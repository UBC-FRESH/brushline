Optimization evaluator
======================

The exact evaluator replays a formulation assignment through the P4 growth and treatment models and
returns the four-objective vector, feasibility, named violations, cost accounts, and a per-segment
period trail.

.. code-block:: python

   from brushline.optimization.evaluator import (
       EvaluationConfig,
       ScheduleEvaluator,
       SegmentContext,
   )

   evaluator = ScheduleEvaluator(formulation, contexts, EvaluationConfig(discount_rate=0.03))
   result = evaluator.evaluate(evaluator.initial_assignment())
   assert set(result.objective_vector) == {
       "present_cost",
       "service_risk",
       "service_attainment",
       "uncertainty",
   }

Context
-------

``SegmentContext`` supplies the initial ``StateDistribution``, functional group, service standard,
segment length, growth environment, swath width, and optional asset height. The context length must
match the formulation segment length.

Each period is a growth step of ``end_year - start_year + 1`` years. A selected treatment is applied at
the period start with a post-delay regrowth horizon of one year less than the period length. A period
without a treatment grows the current state for the full period. An unknown group or out-of-domain
environment is a named hard violation; it is never extrapolated.

Costs
-----

Treatment cost is the formulation option's ``cost_per_ha * area_ha + fixed_cost``, where
``area_ha = length_m * treatment_width_m / 10000``. Monitoring cost is charged once per selected span
and period, then allocated evenly across the span's segments for the period trail. The total is not
multiplied by the number of segments.

``total_cost`` is undiscounted. ``discounted_cost`` divides each period's cost by
``(1 + discount_rate) ** (period_start - base_year)``. ``present_cost`` is the discounted total.

Service and uncertainty
-----------------------

For each segment and period, the evaluator records:

- the service height margin;
- the clearance margin, when an asset height is known;
- the probability that mean height exceeds the service height or the clearance threshold, using a
  normal height interval;
- whether the mean state attains the service standard;
- one minus state confidence after monitoring.

The objective vector weights these results by segment length and the number of periods:

.. list-table::
   :header-rows: 1
   :widths: 26 74

   * - Objective
     - Definition
   * - ``present_cost``
     - Discounted treatment and monitoring cost.
   * - ``service_risk``
     - Length- and period-weighted exceedance probability.
   * - ``service_attainment``
     - Length- and period-weighted share of periods that meet the standard.
   * - ``uncertainty``
     - Length- and period-weighted one-minus-confidence after the last period.

Monitoring reduces the height, cover, and density standard deviations by
``1 - 0.5 * sampling_intensity`` and raises confidence by the same factor. This is a transparent
prototype rule, not a sensor-specific measurement model.

Feasibility and named violations
--------------------------------

Hard violations make ``feasible`` false:

- ``EVALUATION-ASSIGNMENT``: missing or extra variables.
- ``EVALUATION-OPTION``: an option index is outside the variable's options.
- ``EVALUATION-ACCESS``: a treatment is selected in an inaccessible segment/period.
- ``EVALUATION-BUDGET``: treatment cost exceeds the period budget.
- ``EVALUATION-MONITORING-BUDGET``: monitoring cost exceeds the period budget.
- ``EVALUATION-CAPACITY``: treated area exceeds a method capacity.
- ``EVALUATION-TREATMENT``: the treatment transition is blocked or invalid.
- ``EVALUATION-GROWTH``: the growth step is blocked or invalid.
- ``EVALUATION-SERVICE``: the service standard is missed and the service constraint is hard.

A service miss is soft when the matching service constraint has ``hard = false``. Soft violations are
reported in ``soft_violations`` and do not make the plan infeasible.

Incremental path
----------------

``IncrementalEvaluator`` wraps the exact evaluator with a resident assignment and typed
``AssignmentChange`` apply/undo. Budgets, capacities, service, and coupled growth make an unproved
delta unsafe, so the declared rule is **full exact recomputation**. The wrapper caches exact results,
reports ``mode = "full_fallback"``, and counts new recomputations in ``fallbacks``. Apply/undo restores
the exact prior assignment and result.

Limits
------

- The evaluator is a decision-support prototype; it is not an engineering clearance or safety model.
- The risk probability uses a normal height interval and ignores serial correlation.
- Monitoring is a cost and uncertainty rule, not a full sensor simulator.
- The exact evaluator is the reference for the P5.3 operators and P5.4 search.
