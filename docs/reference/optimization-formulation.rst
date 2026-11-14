Optimization formulation
========================

P5.1 defines the stable boundary between Brushline and Fresh Solutions: variables, options, constraints,
and the four-objective vector. The evaluator, operators, archive, and adapter all use these indices.

The committed example is ``notes/reference/p5-formulation.v1.json``.

Variables
---------

A ``Variable`` has a stable index, a kind, a target, a period, and an option list. Option 0 is always
``none``. The option list order is stable.

- A **treatment** variable targets one segment and one period.
- A **monitoring** variable targets one span and one period.

A segment's allowed methods filter its treatment options. A span's ``monitoring_allowed`` flag filters
monitoring options.

Options
-------

``TreatmentOption`` records method, intensity, season, variable cost per hectare, fixed cost, and a
label. ``MonitoringOption`` records sensor, sampling intensity, cost per span, and a label.

The formulation does not run a treatment or a monitoring mission. It declares the selectable actions.

Periods and targets
-------------------

``PeriodSpec`` records the year window, treatment budget, monitoring budget, method capacities, and
season. ``SegmentSpec`` records length, treatment unit, service standard, service height and clearance,
allowed methods, and inaccessible periods. ``SpanSpec`` records its segments and monitoring permission.

Constraints
-----------

``ConstraintSpec`` records a named hard or soft constraint:

- treatment budget per period;
- monitoring budget per period;
- capacity per period and method;
- access per segment and period;
- service maximum height per segment.

The formulation also has kinds for spatial and temporal constraints so the evaluator can add them
without changing the contract.

Objectives
----------

The four core objectives are:

.. list-table::
   :header-rows: 1
   :widths: 28 18 16 38

   * - Objective
     - Direction
     - Unit
     - Meaning
   * - ``present_cost``
     - minimize
     - currency
     - Treatment, monitoring, access, and supervision cost.
   * - ``service_risk``
     - minimize
     - index
     - Clearance, fall-in, fuel, access, and reliability risk.
   * - ``service_attainment``
     - maximize
     - fraction
     - Share of service-level targets attained.
   * - ``uncertainty``
     - minimize
     - index
     - Remaining state uncertainty after the plan.

A scalarization is a search choice; the archive keeps the vector.

.. code-block:: python

   from brushline.optimization.formulation import (
       MonitoringOption,
       PeriodSpec,
       SegmentSpec,
       SpanSpec,
       TreatmentOption,
       build_formulation,
       validate_formulation,
   )

   formulation = build_formulation(
       formulation_id="example",
       periods=[
           PeriodSpec(
               period_id="p2026",
               start_year=2026,
               end_year=2026,
               budget=100000,
               monitoring_budget=10000,
               capacity_by_method={"mowing": 30},
           )
       ],
       segments=[
           SegmentSpec(
               segment_id="s1",
               corridor_id="c1",
               length_m=100,
               treatment_unit_id="tu1",
               service_standard_id="std1",
               max_height_m=4.0,
               min_clearance_m=1.0,
               allowed_methods=["mowing"],
           )
       ],
       spans=[SpanSpec(span_id="sp1", corridor_id="c1", segment_ids=["s1"])],
       treatment_options=[
           TreatmentOption(
               option_id="mow",
               method="mowing",
               intensity=0.7,
               season="spring",
               cost_per_ha=500,
           )
       ],
       monitoring_options=[
           MonitoringOption(
               option_id="lidar",
               sensor="lidar",
               sampling_intensity=0.8,
               cost_per_span=2000,
           )
       ],
   )
   assert validate_formulation(formulation).is_valid
   assert formulation.initial_assignment() == {0: 0, 1: 0}

Named errors
------------

.. list-table::
   :header-rows: 1
   :widths: 32 68

   * - Prefix
     - Meaning
   * - ``FORMULATION-TIME``
     - Creation time is not timezone-aware.
   * - ``FORMULATION-ID``
     - Duplicate period, segment, span, option, variable, constraint, or objective.
   * - ``FORMULATION-INDEX``
     - Variable indices are not consecutive from zero.
   * - ``FORMULATION-OBJECTIVE``
     - The four core objectives are not present.
   * - ``FORMULATION-KIND``
     - Unknown variable kind.
   * - ``FORMULATION-REF``
     - Variable period/segment/span reference is unknown.
   * - ``FORMULATION-OPTION``
     - Variable option is unknown; unused options are warnings.
   * - ``FORMULATION-CONSTRAINT``
     - Unknown constraint kind or reference.
   * - ``FORMULATION-EMPTY``
     - No treatment or monitoring options (warning).

Limits
------

- The formulation does not evaluate a schedule; P5.2 owns the evaluator.
- Treatment units are soft groups; the variable stays segment-level.
- The formulation is deterministic and offline.
- No optimality claim is made.
