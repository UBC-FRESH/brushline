The planning stack
==================

Brushline keeps three planning scales and several policy comparisons separate. They read the same
decision units and write versioned artifacts.

Strategic
---------

The strategic layer selects segment-year-method actions under budget and capacity constraints. The
stateful MILP carries risk forward from year to year and is exact for the declared linear risk state
on small instances. The heuristic path uses Fresh Solutions and cluster repair for larger instances.

Useful pages: :doc:`../reference/stateful-strategic`,
:doc:`../reference/stateful-heuristic`, :doc:`../reference/stateful-decomposition`.

Tactical
--------

The tactical layer groups segment actions into treatment units, assigns contractors and methods,
checks access windows and capacity, and builds a multi-year program. It is a prototype allocation
layer, not a committed contractor schedule.

Useful pages: :doc:`../reference/tactical-program`,
:doc:`../reference/tactical-resources`, :doc:`../reference/tactical-access`.

Operational
-----------

The operational layer creates work orders and a deterministic crew/machine shift schedule, then
exposes the result as a timeline. The scheduler respects method skills, shift hours, travel, and
blocked days. It does not model every real-world labour rule.

Useful pages: :doc:`../reference/tactical-operations`,
:doc:`../reference/shift-scheduling`, :doc:`../reference/tactical-timeline`.

Policy comparisons
------------------

The prototype also contains policy experiments above the base plan: static frontier plans,
scenario-robust plans, sampled chance constraints, two-stage deferral, rolling re-optimization,
weather-aware execution, forecast-skill sensitivity, and capacity remedies. These pages are
experiment records; they are not additional certifying standards. Start with
:doc:`uncertainty-and-recourse` and use the reference page for the specific comparison.

Artifact flow
-------------

The normal flow is:

``dataset`` → ``plan`` → ``run`` → ``tactical`` → ``resources`` → ``operations`` → ``shifts``

Each artifact has a schema version, a validator, and named errors. The map is in
:doc:`../reference/contract-index`.
