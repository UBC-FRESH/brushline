Search budget and performance
=============================

P5.7 records the search budget, seed variance, scaling, checkpoint/resume cost, and the explicit
no-optimality statement. Every point names its requested budget, actual exact evaluations, seed
outcomes, replay flag, and stopping rule.

Quality versus budget
---------------------

``run_budget_curve`` runs local search at every budget and seed. For each budget it records:

- feasible and total runs;
- best, median, and worst feasible objective;
- whether every feasible seed reaches a supplied known optimum;
- every per-seed objective, feasibility, evaluations, replay flag, and stop reason.

A positive gap or an infeasible seed remains visible. The report does not hide variance behind one
best number.

.. code-block:: python

   from brushline.optimization.budget import run_budget_curve

   report = run_budget_curve(
       evaluator,
       instance_id="tiny",
       budgets=[10, 50, 100],
       seeds=[1, 2, 3],
       optimum=25.0814,
   )
   assert report.points

Scaling
-------

``run_scaling`` measures each supplied instance size for one or more seeds:

- variable count;
- best feasible objective;
- median and maximum wall time;
- peak traced memory;
- replay result.

The timing is wall-clock and machine-dependent. It is evidence for a report, not a production SLA.

Checkpoint
----------

``measure_checkpoint`` saves a checkpoint, reloads and replays it, and records the file size, save time,
load time, objective, and replay flag. ``run_budget_report`` combines quality, scaling, checkpoint, and
the no-optimality statement.

No-optimality statement
-----------------------

.. code-block:: text

   Brushline reports a search incumbent with its budget, seed, and stopping rule; it does not claim
   global optimality on realistic corridors.

The statement is part of the report contract. ``QualityBudgetReport`` rejects a blank statement.

Schemas
-------

- ``brushline.optimization-budget.v1``: quality and seed evidence.
- ``brushline.optimization-budget-report.v1``: quality, scaling, checkpoint, adapter and Fresh Solutions
  versions, and the caveat.

Limits
------

- Timing changes with hardware and load; compare points from one run.
- The budget is a requested local-iteration count, not a guarantee of a fixed evaluation count.
- A single seed is not evidence of robustness.
- Global optimality is not claimed on realistic corridors.
