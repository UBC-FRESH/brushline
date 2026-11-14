Tactical program
================

P7.1 assembles a 1-to-5-year tactical treatment program from treatment units, actions, seasons, budgets,
and contractor allocations.

Inputs
------

``TreatmentUnit`` records a unit, span, segments, area, allowed methods, and allowed seasons.
``TacticalAction`` records the action, unit, year, season, method, contractor, cost, and capacity units.
``TacticalConfig`` records the horizon, start year, budget by year, and currency.

Validation
----------

The program rejects:

- unknown units;
- duplicate units or actions;
- actions outside the horizon;
- a method or season disallowed by the unit;
- a year cost above its budget.

Costs by year, contractor allocation, total cost, and named ``TACTICAL-*`` violations are reported.
An empty action set is a warning, not a hidden plan.

Limits
------

- Capacity and resource cost are P7.2.
- Access is P7.3; work orders are P7.4.
- The program does not claim an optimal selection.
