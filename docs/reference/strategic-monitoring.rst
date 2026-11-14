Strategic monitoring policy
===========================

P6.3 treats monitoring as a decision. It selects a frequency, route, sensor, sampling intensity, and
event years from explicit options, ranked by an approximate value of information.

Inputs
------

``MonitoringSpan`` records the span, its segments, baseline uncertainty, service risk, and route length.
``MonitoringOption`` records a span, sensor, route, interval, sampling intensity, cost per event,
uncertainty reduction, and risk reduction.

``MonitoringConfig`` sets the horizon, start year, total budget, value per unit, cost penalty, and
minimum net value. An option is eligible only when its net value is positive.

Value of information
--------------------

The declared proxy is:

.. code-block:: text

   gross = value_per_unit * (
       baseline_uncertainty * uncertainty_reduction
       + service_risk * risk_reduction
   )
   total_cost = cost_per_event * number_of_events
   net = gross - cost_weight * total_cost

Events are scheduled at ``start_year``, then every ``interval_years`` through the horizon. The policy
selects at most one option per span, in descending net value, while the total cost fits the budget.
It is not a fixed calendar because the interval and option are chosen by the value proxy.

.. code-block:: python

   from brushline.strategic.monitoring import build_monitoring_policy

   policy = build_monitoring_policy(
       policy_id="strategy-v1",
       instance_id="corridor-1",
       spans=spans,
       options=options,
   )
   assert policy.decisions

Reports
-------

``MonitoringDecision`` records the span, option, sensor, route, interval, sampling intensity, start and
end years, event years, total cost, gross value, net value, and expected uncertainty/risk reductions.
``MonitoringPolicy`` aggregates total cost, budget, reductions, net value, feasibility, violations, and
caveats.

Caveats
-------

The value-of-information proxy is an assumption. It is not a structural sensor simulation, a mission
routing engine, or a field-calibrated information value. Event dates remain subject to route, weather,
and operational feasibility. A missing budget or unavailable route is explicit.

Limits
------

- Only one option per span is selected.
- The proxy ignores information's effect on later decisions beyond the declared reductions.
- The total budget is a planning cap, not a per-year cash constraint.
- No live sensor, flight, or field campaign is executed.
