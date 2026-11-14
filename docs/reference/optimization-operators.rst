Optimization move operators
===========================

P5.3 adds typed moves and a deterministic repair pass. A ``Move`` is a reversible bundle of
``AssignmentChange`` records. Every change stores the variable, the exact before option, and the exact
after option. Apply validates every before value; undo validates every after value and reverses the
order.

Operators
---------

.. list-table::
   :header-rows: 1
   :widths: 22 78

   * - Operator
     - Move
   * - ``toggle``
     - Set one variable to a random alternative option.
   * - ``method_change``
     - Change a selected treatment to an option with a different method.
   * - ``shift``
     - Clear a selected treatment and select the same option in the adjacent period for the segment.
   * - ``swap``
     - Exchange the options of two eligible variables of the same kind.
   * - ``block_move``
     - Set a contiguous period block for one segment to one treatment option.
   * - ``monitoring_move``
     - Change one monitoring option.
   * - ``destroy_repair``
     - Reset a seeded subset of selected variables and repair feasibility.

All operators take a seeded ``random.Random``. The same assignment and seed produce the same move, or
``None`` when no eligible move exists.

``default_operators(evaluator)`` returns the seven-operator portfolio. ``OperatorState`` holds the
formulation, option lookup, period order, locked variables, and access rule.

Access and locks
----------------

``OperatorConfig.respect_access`` defaults to true; treatment variables in a segment's inaccessible
periods are not proposed. ``locked_variables`` is an explicit list of variable indices that no operator
or repair may change. An unknown locked index raises ``OperatorError``.

Repair
------

``repair_assignment(evaluator, assignment)`` loops on the first hard violation:

- access: clear the offending treatment;
- treatment budget or capacity: clear the highest-index selected treatment in the period, filtered by
  method for capacity;
- monitoring budget: clear the highest-index selected monitoring variable in the period;
- service: select a non-``none`` treatment option for the segment and period;
- blocked growth, blocked treatment, assignment, and option problems: stop and report the remaining
  violation.

The repair result records the repaired assignment, applied changes, feasibility, and remaining hard
violations. It never converts a blocked model result into a fabricated state.

.. code-block:: python

   from brushline.optimization.operators import (
       Move,
       default_operators,
       repair_assignment,
   )

   operators = default_operators(evaluator)
   move = operators[0].propose(assignment, random.Random(7))
   if move is not None:
       candidate = move.apply(assignment)
       assert move.undo(candidate) == assignment
   repaired = repair_assignment(evaluator, assignment)
   assert repaired.feasible or repaired.remaining

Validation
----------

``validate_move(formulation, move)`` checks that every touched variable exists and every before/after
option is in range. The named errors are ``MOVE-VARIABLE`` and ``MOVE-OPTION``.

Limits
------

- Operators are a heuristic portfolio, not an exhaustive neighbourhood enumeration.
- Repair is greedy and may stop with a remaining violation when no admissible fix exists.
- A service repair can add cost; the next repair step removes budget or capacity violations if needed.
- The P5.4 adapter exposes one reversible change at a time to Fresh Solutions; compound moves remain
  available to the Brushline operator layer.
