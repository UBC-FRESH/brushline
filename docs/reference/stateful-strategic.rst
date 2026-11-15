Stateful strategic MILP
=======================

The stateful strategic model adds a risk state to each segment and carries it across periods. It is
a linearized mixed-integer program solved by HiGHS through SciPy.

State model
-----------

Each segment starts with an observed or derived risk index. At the start of every period, risk grows
by a declared annual amount. Selecting a treatment method applies that method's risk reduction with a
lower bound of zero. One method may be selected per segment and period. Annual budgets and crew-hour
capacities are hard constraints.

The formulation is exact for this declared linear state. It is not a full nonlinear shrub/tree growth
model, and it does not claim BC Hydro clearance compliance.

Objectives
----------

The default objective minimizes length-weighted mean risk, with annual budget and crew-hour
constraints. A cost weight, maximum mean risk, and solver time limit are explicit settings. Budget
sweeps produce a non-dominated cost/risk frontier.

Replay
------

After the solve, the selected actions are replayed through the same linear equations. The plan records
the solver, status, objective, annual outcomes, actions, and ``replay_ok``. A replay mismatch is
visible in the artifact rather than hidden.

Command-less package API
------------------------

The demo builder calls:

.. code-block:: python

   from brushline.strategic.stateful import (
       StatefulConfig,
       StatefulMethod,
       StatefulPeriod,
       StatefulSegment,
       build_stateful_plan,
   )

Limits
------

- The risk state is linear and generic.
- Treatment productivity and cost are caller inputs.
- Access, outages, environmental windows, and asset-owner standards are separate constraints.
- The model is a planning prototype, not a safety or regulatory determination.
