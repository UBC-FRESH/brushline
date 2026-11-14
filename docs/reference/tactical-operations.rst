Operational work plan
=====================

P7.4 turns tactical actions into work-ready orders with a sequence, crew, day, and traceable source.

Inputs
------

``build_operations_plan`` consumes a ``TacticalProgram`` and an ``AccessPlan``. Each tactical action may
carry an ``access_window_id``. The operations plan refuses to schedule when:

- the action has no access window;
- the window is missing from the access plan;
- the access status is blocked (restricted, closed, or unknown).

``OperationsConfig`` sets the start year, start day, maximum orders per day, and crew ids.

Output
------

``WorkOrder`` records the work-order id, source action id, unit, contractor, crew, year, day, season,
method, cost, and status. The work order id is derived deterministically from the action id.
``OperationsPlan`` records the source program, orders, total cost, feasibility, and named
``OPERATIONS-*`` violations.

Limits
------

- Machine ids are not assigned by this prototype.
- Sequence is tactical action order, not a route optimization.
- A work order is a planning artifact, not a dispatch or safety release.
