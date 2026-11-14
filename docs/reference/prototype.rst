Prototype: compile and simulate
================================

The P1.6 prototype is the smallest end-to-end path that exercises the contracts. It compiles the
synthetic fixture into a validated dataset, replays a plan or schedule, and writes a run directory with
the account values, state values, schedule, report, and ``run.json``.

It is **not** the calibrated model. The growth rule is linear and the treatment transition is a simple
fractional reduction. The calibrated model is P4.

Compile
-------

.. code-block:: bash

   brushline build --fixture examples/synthetic-corridor --out build/compiled

The compiler reads ``dataset/segments.csv``, ``corridor.json``, and ``state.json``, joins the service
standards and corridor attributes onto the segments, and writes:

- ``segments.parquet``: segment id, corridor, length, geometry, span, sequence, treatment unit, service
  standard, access point, maximum height, and minimum clearance.
- ``states.parquet``: segment, year, functional group, state class, height, cover, density, age,
  confidence, source, and source version.
- ``manifest.json``: the ``brushline.dataset.v1`` manifest with both tables, checksums, and the content
  digest.

Simulate
--------

.. code-block:: bash

   brushline simulate \
     --dataset build/compiled \
     --out runs/prototype \
     --plan examples/synthetic-corridor/plan.json \
     --years 5 \
     --start-year 2026

Or replay a schedule CSV:

.. code-block:: bash

   brushline simulate \
     --dataset build/compiled \
     --out runs/prototype \
     --schedule path/to/schedule.csv \
     --years 5

The schedule CSV columns are ``segment_id``, ``year``, ``action_id``, ``method``, ``intensity``,
``efficacy``, and ``cost``. Exactly one of ``--plan`` and ``--schedule`` is required.

The prototype writes:

- ``schedule.csv``: the replayed actions with ``applied`` or ``outside_horizon`` status.
- ``account_values.csv``: long account values by year.
- ``state_values.csv``: per-segment, per-year state values.
- ``reports/summary.md``: a short run report.
- ``run.json``: the ``brushline.run.v1`` manifest with the artifact index and summary.

One-command path
----------------

.. code-block:: bash

   brushline prototype \
     --fixture examples/synthetic-corridor \
     --out runs/prototype \
     --years 5

The command compiles under ``runs/prototype/dataset`` and simulates under ``runs/prototype/run``.

Prototype rules
---------------

- Growth: height increases by 0.25 m per year and cover by 2 percentage points per year, capped at
  10 m and 100 percent.
- Density: grows by 5 percent per year when it is known.
- Treatment: height and cover are multiplied by ``1 - efficacy``; density is multiplied by
  ``1 - 0.5 * efficacy``; the action cost is charged in its year.
- An unknown state does not grow and remains unknown.
- A clearing violation is a known state whose height exceeds the segment's service standard maximum.
- No action is invented: the simulator replays only the plan or schedule.

Accounts
--------

The prototype writes seven accounts:

.. list-table::
   :header-rows: 1
   :widths: 38 14 48

   * - Account
     - Unit
     - Meaning
   * - ``vegetation.mean_height_m``
     - m
     - Mean height across known states.
   * - ``vegetation.mean_cover_pct``
     - %
     - Mean cover across known states.
   * - ``vegetation.max_height_m``
     - m
     - Maximum height across known states.
   * - ``vegetation.unknown_segments``
     - count
     - Segments whose state is unknown.
   * - ``vegetation.clearing_violations``
     - count
     - Known states above the service standard maximum.
   * - ``treatment.cost``
     - currency
     - Cost charged in the year.
   * - ``treatment.segments``
     - count
     - Actions applied in the year.

Reproducibility
---------------

The simulator is deterministic given the dataset and the schedule. The same schedule reproduces the same
``account_values.csv`` and ``state_values.csv``. ``run.json`` records the dataset content digest, the
prototype model versions, the configuration, and the artifact checksums.

Validation
----------

The test suite compiles the fixture, simulates the plan, checks the five-year accounts, replays the
written schedule, compares the outputs, and exercises the three CLI paths. It also checks that a
schedule with an unknown segment fails.
