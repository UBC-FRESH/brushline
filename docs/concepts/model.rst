The model
=========

Decision units
--------------

A **segment** is the decision unit. A segment carries a corridor position, length, width, area,
site and vegetation attributes, treatment history, access context, and observation history.

**Spans** and **treatment units** are runtime aggregates. They let tactical and operational plans
group segments for access, contracting, and scheduling without changing the underlying decision
unit.

Vegetation state
----------------

A vegetation state is a distribution over interpretable classes plus continuous summaries. The
state is not a single height or a single cover percentage. Growth changes the distribution;
treatment applies a method- and season-specific transition.

The low-vegetation model is a Brushline state-transition core, not a generic forest growth-and-yield
model. Its parameters, evidence, uncertainty, applicability domain, and out-of-domain rejection are
documented in :doc:`../reference/low-vegetation-model-card` and
:doc:`../reference/growth-model`.

Treatments
----------

A treatment is a transition with method-specific efficacy, selectivity, top-kill, resprouting,
regrowth delay, and cost. It is not a reset to zero. The transition and calibration contracts are in
:doc:`../reference/treatment-transitions` and :doc:`../reference/treatment-calibration`.

Planning scales
---------------

- **Strategic** plans choose where and when to treat over a multi-year horizon, subject to budget,
  capacity, service, and risk objectives.
- **Tactical** plans turn selected segment actions into treatment units, contractor demand, access
  windows, and multi-year budgets.
- **Operational** plans turn tactical demand into work orders, crew and machine assignments, and a
  shift calendar.

The exact stateful MILP is suitable for small instances. Larger instances use Fresh Solutions
heuristics and cluster repair. Exactness, heuristic status, and global optimality are different
claims; see :doc:`../reference/stateful-strategic` and
:doc:`../reference/stateful-heuristic`.

Objective and risk
------------------

The prototype reports cost, crew-hours, service, and a length-weighted mean risk. The risk metric is
a model quantity, not an asset-owner risk standard. A lower number does not certify clearance,
reliability, fire behaviour, or safety.

What this model does not do
---------------------------

- It does not replace a field survey or a LiDAR/field stem map.
- It does not certify access, outage, clearance, or safety constraints.
- It does not claim that a synthetic calibration is a field calibration.
- It does not claim global optimality for the heuristic paths.
