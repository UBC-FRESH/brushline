Studio telemetry contract
=========================

P5.8 freezes the progress-event and archive references that the P10 studio reads. Telemetry reports a
run; it is not a second source of truth and does not carry private evaluator state.

The committed example is ``notes/reference/p5-telemetry.v1.json`` with archive
``notes/reference/p5-archive.v1.json``.

Event stream
------------

``EventStream`` uses ``brushline.optimization-telemetry.v1`` and carries:

- the run id and instance id;
- the vegetation-model and data versions;
- an optional archive-relative ``pareto.json`` path;
- an ordered event list.

Each ``TelemetryEvent`` uses ``brushline.optimization-event.v1`` and carries a stable event id,
zero-based sequence, type, timezone-aware time, run and instance ids, adapter, Fresh Solutions version,
seed, budget, payload, and optional objective vector, feasibility, plan id, and evidence path.

Event types are:

.. list-table::
   :header-rows: 1
   :widths: 20 80

   * - Type
     - Meaning
   * - ``start``
     - Search mode, seed, budget, and adapter are available.
   * - ``iteration``
     - Optional progress record.
   * - ``incumbent``
     - Assignment, objective vector, feasibility, evaluations, and history.
   * - ``archive``
     - Archive path and the member records the studio may display.
   * - ``checkpoint``
     - Checkpoint path.
   * - ``finish``
     - Stop reason and evaluation count.

Validation checks consecutive sequences from zero, unique event ids, the start/finish boundaries, one
run and instance id, and no event after finish. Named errors are ``TELEMETRY-SEQUENCE``,
``TELEMETRY-ORDER``, ``TELEMETRY-RUN``, ``TELEMETRY-INSTANCE``, and ``TELEMETRY-ARCHIVE``.

Building a stream
-----------------

.. code-block:: python

   from brushline.optimization.telemetry import (
       check_studio_compatibility,
       events_from_run,
       with_archive_event,
   )

   stream = events_from_run(
       run,
       run_id="tiny-run-1",
       model_version="brushline.low-vegetation.prototype.v0",
       data_version="synthetic-corridor.v1",
       archive_path="runs/tiny/pareto.json",
   )
   stream = with_archive_event(stream, archive, archive_path="runs/tiny/pareto.json")
   assert check_studio_compatibility(stream, archive).ok

``events_from_run`` creates start, incumbent, optional checkpoint, and finish events. It does not
fabricate an archive event. ``with_archive_event`` inserts one archive event before finish and verifies
the archive first.

Server-sent events
------------------

``to_sse`` renders the validated stream with ``id``, ``event``, and JSON ``data`` fields.
``write_event_stream`` writes JSON; ``write_sse`` writes the event stream. Both writers validate first.

Studio compatibility
--------------------

``check_studio_compatibility`` reads only the stream and archive:

- a missing archive is an explicit error;
- exactly one archive event is required;
- the stream and expected archive paths must match;
- event and archive plan ids must match;
- evidence paths and objective vectors must match.

It returns ``StudioCompatibility`` with ``ok``, errors, warnings, archive path, member count, and event
count. It does not inspect the evaluator, search internals, or unlisted files.

Schemas
-------

- ``brushline.optimization-event.v1``: one progress event.
- ``brushline.optimization-telemetry.v1``: versioned event stream.

Limits
------

- Telemetry is a report; the archive and plan artifacts remain authoritative.
- The stream carries assignment and objective records but not a full evaluator state.
- SSE is a rendering; a live event bus is a later deployment concern.
- A missing archive is never inferred or silently recreated.
