FHOPS adapter
=============

P7.5 defines an optional, versioned boundary from a Brushline tactical action to a FHOPS scenario.
The core install and dry-run path do not require FHOPS.

Boundary
--------

``FhopsBoundary`` pins FHOPS ``1.1.0b1`` and declares the optional capability list. ``fhops_version``
reports the installed version or ``not-installed``.

``request_from_action`` maps a ``TacticalAction`` to a ``FhopsRequest`` with unit, action, area, method,
machines, shift hours, and days.

Dry run
-------

``dry_run`` is deterministic:

.. code-block:: text

   machine_hours = machines * shift_hours * days
   productivity_units_per_day = machines * shift_hours * units_per_machine_hour
   total_cost = machine_hours * cost_per_machine_hour + move_cost

``FhopsResult`` records the status, machine hours, productivity, total cost, notes, and time. The notes
state that no engine was executed and include the pinned and installed versions.

.. code-block:: python

   from brushline.tactical.fhops import request_from_action, dry_run

   request = request_from_action(action, area_ha=2)
   result = dry_run(request)
   assert result.status == "dry_run"

Limits
------

- No live FHOPS engine call is made in this prototype.
- The dry-run productivity and rates are assumptions.
- No machine-level route, shift, or downtime model is included.
- The adapter does not fork FHOPS or hide a missing dependency.
