Access and road status
======================

P7.3 checks treatment access against source-preserving road links and access windows. Unknown is never
treated as open.

Models
------

``RoadLink`` records the link, source, status (``open``, ``restricted``, ``closed``, ``unknown``),
status source, and length. ``AccessWindow`` records the unit, link, year, and season. ``AccessResult``
records allowed/blocked, source, route length, reason, and caveats.

Rules
-----

- ``open`` is allowed.
- ``restricted`` is blocked pending operational approval; restriction terms are not modelled.
- ``closed`` is blocked.
- ``unknown`` is blocked and is not a negative verdict; verify with the source.

An unknown link or duplicate link ids fail explicitly. ``AccessPlan`` totals route length and reports
whether all windows are allowed.

.. code-block:: python

   from brushline.tactical.access import build_access_plan

   plan = build_access_plan(
       plan_id="access",
       instance_id="corridor",
       windows=windows,
       links=links,
   )
   assert plan.results[0].source

Limits
------

- No live fresh-road/ALSroads fetch; the caller supplies source status.
- No route optimization or road-condition forecast.
- A status is not a safety certification.
