Strategic reports
=================

P6.5 builds a deterministic yearly report from a strategic portfolio, monitoring policy, and optional
BAU plan. Each row carries cost, budget, service, risk, uncertainty, and monitoring evidence.

Inputs and rows
---------------

``build_strategic_report`` receives the portfolio, monitoring policy, period definitions, optional BAU
plan, and optional comparison. It maps period ids to calendar years and allocates each monitoring event
cost evenly across its scheduled event years.

``YearRow`` records the scope (``optimized`` or ``bau``), year, period, treatment cost, monitoring cost,
total cost, budget, remaining budget, service, risk, uncertainty, and event count. A negative remaining
budget is an overrun and is not clamped. ``total_cost`` must equal treatment plus monitoring cost.

``StrategicReport`` records the rows, optimized total, optional BAU total, optional comparison, caveats,
and timezone-aware creation time.

.. code-block:: python

   from brushline.strategic.reports import build_strategic_report

   report = build_strategic_report(
       report_id="strategy-v1",
       instance_id="corridor-1",
       portfolio=portfolio,
       monitoring=monitoring,
       periods=periods,
       bau=bau,
       comparison=comparison,
   )

Budget and monitoring
---------------------

The period budget comes from the period definition. Monitoring cost is allocated to the event years;
a monitoring event outside the report periods is an explicit error. If monitoring plus treatment exceeds
the budget, the row reports a negative remaining budget. The report does not silently cap or rebalance it.

Writers
-------

``write_strategic_report`` writes formatted JSON and ``load_strategic_report`` round-trips it. The
report is a report artifact, not a second plan or archive.

Caveats
-------

- Costs are scenario costs, not a financial forecast or bid.
- Monitoring allocation is even across events; actual invoices may differ.
- Service, risk, and uncertainty are period means from the declared model/options.
- BAU is a scenario comparison, not a causal claim.

Limits
------

- No charts, PDF, or studio rendering.
- No discounted cash-flow model beyond the declared scenario values.
- The report does not hide an overrun or an infeasible plan.
