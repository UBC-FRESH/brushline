Contractor capacity and cost
============================

P7.2 builds a transparent contractor cost and capacity plan from explicit requests and profiles.

Profiles and requests
---------------------

``ContractorProfile`` records contractor id, offered methods, crews, machines, base rate per capacity
unit, travel rate, supervision fraction, overhead fraction, risk fraction, annual capacity, and
currency.

``ResourceRequest`` records request id, contractor, method, year, capacity units, and travel distance.

Cost build-up
-------------

For each request the plan records separate lines:

- ``base``: capacity units times rate;
- ``travel``: distance times travel rate;
- ``supervision``: base times supervision fraction;
- ``overhead``: base plus travel plus supervision times overhead fraction;
- ``risk``: base times risk fraction.

``resource_plan`` records cost by contractor and year. Every line names its request source.

Capacity
--------

Annual capacity is checked by contractor and year. A missing profile, an unoffered method, or excess
capacity is a named ``RESOURCE-*`` violation. Missing evidence is never replaced by a zero rate.

.. code-block:: python

   from brushline.tactical.resources import build_resource_plan

   plan = build_resource_plan(
       plan_id="resources",
       instance_id="corridor",
       requests=requests,
       profiles=profiles,
   )
   assert plan.feasible

Limits
------

- Capacity is annual, not daily or seasonal.
- The profile rates are supplied assumptions; no vendor quote is implied.
- The plan does not assign crews to days; P7.4 owns the work order.
