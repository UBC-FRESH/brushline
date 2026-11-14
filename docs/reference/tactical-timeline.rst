Operations timeline
===================

P7.6 maps work orders to a deterministic operations timeline and 3D data contract. Positions are only
shown when known.

Events
------

Each work order produces a ``start`` and a ``finish`` event. ``OperationEvent`` records the event id,
type, timestamp, work order, action, unit, segment ids, crew, machine, cost, position, and position
status.

``TimelineConfig`` sets the start time, shift duration, and known positions by work-order id. A missing
position is ``unknown``; it is not inferred from the unit, the previous event, or a centroid.

``OperationsTimeline`` records the events, total work-order cost, unknown-position event count, source
operations plan, and timezone-aware creation time.

.. code-block:: python

   from brushline.tactical.timeline import TimelineConfig, build_operations_timeline

   timeline = build_operations_timeline(
       timeline_id="timeline",
       instance_id="corridor",
       plan=operations,
       config=TimelineConfig(start_time=datetime(2026, 3, 1, tzinfo=UTC)),
   )
   assert timeline.unknown_position_events > 0

Rules
-----

- Start time must be timezone-aware.
- Position and position status must agree.
- Event type is ``start`` or ``finish``.
- Cost appears on the start event; finish cost is zero.
- Events are ordered by work-order year/day/id.

Limits
------

- No live GPS, machine telemetry, or route geometry.
- No studio renderer or animation.
- The timeline is a contract, not a second state model.
