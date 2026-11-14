Single-segment dynamic program
==============================

P6.1 solves a finite-horizon strategic policy for one segment. The state vocabulary is the P4 state
classes; an action is no treatment or a method/intensity/season with a cost and availability.

The committed program is ``notes/reference/p6-dynamic-program.v1.json``.

Model
-----

``DPState`` records a state id, P4 class, optional age, and label. ``StrategicAction`` records the
action id, method, intensity, season, cost, currency, and the states where it is available. A missing
method is a no-treatment action and must have zero cost.

``Transition`` is one state/action/outcome row with a one-period probability, service attainment, risk,
and uncertainty. Every available state/action pair must have at least one row and the probabilities must
sum to one. Unavailable actions need no rows and cannot be selected.

Reward
------

The declared scalar reward is:

.. code-block:: text

   service_weight * service_attainment
   - risk_weight * risk
   - uncertainty_weight * uncertainty
   - cost_weight * action.cost

The DP maximises the discounted expected reward. The result keeps the separate expected cost, service
attainment, risk, and uncertainty, so the scalar does not hide the vector.

.. code-block:: python

   from brushline.strategic.dynamic_program import solve_dynamic_program

   result = solve_dynamic_program(program)
   assert result.action_for(0, "shrub") == "mow"
   assert result.policy_value == result.values[0][program.initial_state]

Policy
------

Backward induction fills the value table from the terminal period. Ties are resolved by the
lexicographically smallest action id. The policy has one decision per state and period. A forward replay
produces the expected cost, service, risk, and uncertainty under that policy.

The result includes the value table at every period plus the terminal period. ``policy_value`` is the
value at the initial state and period zero.

Named errors
------------

- ``DP-STATE``: unknown state reference.
- ``DP-ACTION``: unknown action reference.
- ``DP-TRANSITION``: an available state/action pair has no outcomes.
- ``DP-PROBABILITY``: a transition row does not sum to one.
- ``DP-TERMINAL``: an unknown terminal state.
- ``DP-AVAILABILITY``: an unknown availability state, or a warning that every action is available
  everywhere.

Limits
------

- This is a single-segment scalarized DP, not the network portfolio.
- The transition probabilities and outcome indices are supplied evidence, not fitted field parameters.
- The discount rate is a scenario choice.
- A policy value is not a global optimum for a network or a realistic corridor.
