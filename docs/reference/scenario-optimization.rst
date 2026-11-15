Scenario-optimized planning
===========================

The scenario-optimization experiment asks whether re-planning after uncertainty is revealed would
beat a fixed nominal plan. It samples cost, productive-hours, and capacity factors, evaluates the
fixed balance plan under each scenario, and re-solves the exact stateful MILP in each scenario.

The comparison is a **hindsight adaptive upper bound**, not a deployable adaptive policy. The
scenario-specific plan sees the sampled factors before choosing treatments. It measures the value of
being able to re-plan; it does not model forecast updates, contractual switching, or a policy that can
be executed without knowing the future.

## Scenarios

Each scenario draws lognormal multipliers with mean one:

- treatment cost, sigma 0.18;
- productive hours, sigma 0.15, where higher hours means lower productivity;
- contractor/crew capacity, sigma 0.15.

The network prototype uses 30 scenarios and seed 7. The fixed plan is the balanced 60,000 CAD/year
MILP plan. The adaptive plan uses the same annual budget and method set, with costs and hours scaled
and capacity scaled by the scenario factors.

## Fixed-plan evaluation

The fixed plan's actions are held constant. Cost and hours are scaled; its risk is unchanged because
risk depends on the treatment schedule, not on the cost or hours draws. Annual budget and capacity
violations are recorded separately.

The risk-equivalent objective adds a normalized feasibility penalty:

.. code-block:: text

   risk + cost_weight * cost / 100000 + hours_weight * hours / 100000
        + budget_overrun / total_budget + capacity_shortfall / total_capacity

The adaptive plan's objective uses the same risk/cost/hours weights and is feasible by construction.
Regret is the fixed objective minus the adaptive objective. The penalty is a declared scoring choice,
not a monetary fine.

## Result

For the 8,737 ha, 59-segment prototype:

- the fixed plan exceeded its annual budget in **56.7%** of scenarios;
- the fixed five-year cost band was 249,742–371,650 CAD;
- the adaptive five-year cost band was 298,055–299,452 CAD;
- the fixed plan's mean risk was 0.0294; the adaptive plan's mean risk was 0.0317;
- adaptive planning improved the risk-equivalent objective in **100%** of scenarios.

The adaptive plan buys budget and cost stability by giving up a small amount of nominal risk reduction.
That is the decision-relevant trade, not a claim that adaptation is free.

## Scope

The experiment re-solves the exact MILP for the declared linear risk state. It does not establish
global optimality for a nonlinear vegetation model, a full stochastic dynamic program, or a 10,000-
segment network. Twenty-nine to thirty scenarios are a demonstration sample, not a calibrated
probability model.
