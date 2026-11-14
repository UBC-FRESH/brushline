Synthetic corridor fixture
==========================

The synthetic corridor fixture is a public-safe, deterministic test case. It covers two corridors,
five segments, mixed functional groups, one access gap, one monitoring gap, one structure, a plan, a
Pareto archive, an operations timeline, a demo manifest, and a tiny known-optimum case.

Location: ``examples/synthetic-corridor/``.

Generate
--------

.. code-block:: bash

   brushline fixture --out examples/synthetic-corridor
   brushline fixture --out examples/synthetic-corridor --force

The generator is ``brushline.fixtures.synthetic.generate_fixture``. It uses a fixed seed and a fixed
creation time, so the committed fixture and a fresh build produce the same artifact digests.

Contents
--------

.. list-table::
   :header-rows: 1
   :widths: 34 66

   * - Path
     - Meaning
   * - ``dataset/manifest.json``, ``dataset/segments.csv``
     - The compiled dataset contract and the segment table.
   * - ``corridor.json``
     - The corridor graph: two corridors, five segments, two spans, two treatment units, two access
       points, one structure, and two service standards.
   * - ``state.json``
     - Five states, three treatment actions, one transition, and four observations.
   * - ``plan.json``
     - The 2026 plan with five actions and a CAD 5,300 total.
   * - ``plans/plan-a.json`` to ``plans/plan-c.json``
     - The three archive plans.
   * - ``pareto.json``
     - Three non-dominated cost/risk members and one balanced scalarization.
   * - ``operations_timeline.jsonl``
     - Five timestamped crew events.
   * - ``demo.json``
     - The public demo manifest.
   * - ``tiny_optimum.json``
     - The tiny known-optimum instance.
   * - ``fixture.json``
     - The fixture manifest: seed, expected counts, artifact digests, and content digest.

Expected values
---------------

.. list-table::
   :header-rows: 1
   :widths: 40 60

   * - Key
     - Value
   * - Corridors
     - 2
   * - Segments
     - 5
   * - States
     - 5
   * - Treatment actions
     - 3
   * - Observations
     - 4
   * - Structures
     - 1
   * - Access gaps
     - 1
   * - Monitoring gaps
     - 1
   * - Plan actions
     - 5
   * - Pareto members
     - 3
   * - Timeline events
     - 5
   * - Known optimum
     - ``mow-2026``
   * - Known optimum penalty
     - ``0.46``

Warnings
--------

The fixture is valid, but it deliberately records two warnings:

- segment ``s3`` has no access point;
- observation ``o2`` covers only 40 percent of segment ``s2``.

The unknown state on ``s3`` and the absence of an observation for ``s3`` are the monitoring gap.

Tiny known optimum
------------------

``tiny_optimum.json`` defines a one-segment choice between no treatment, mowing in 2026, and mowing in
2027. The objective is

.. code-block:: text

   penalty = 0.4 * (cost / 1000) + 0.6 * risk

The options are:

.. list-table::
   :header-rows: 1
   :widths: 24 20 20 36

   * - Option
     - Cost
     - Risk
     - Penalty
   * - ``none``
     - 0
     - 0.8
     - 0.48
   * - ``mow-2026``
     - 1000
     - 0.1
     - 0.46
   * - ``mow-2027``
     - 900
     - 0.2
     - 0.48

The optimum is ``mow-2026``. The search validation uses this case to check that an exact solver and the
metaheuristic adapter agree on a known answer.

Validation
----------

.. code-block:: bash

   brushline validate --dataset examples/synthetic-corridor/dataset

The test suite also validates the corridor, state, plan, archive, timeline, run, and demo contracts, and
rebuilds the fixture to compare its digests with ``fixture.json``.

Determinism
-----------

The fixture uses a fixed seed and a fixed ``2026-11-14T00:00:00Z`` creation time. JSON is written with
sorted keys and two-space indentation. The dataset table is CSV, not Parquet, so the table checksum does
not depend on a Parquet library version. A change to the generator changes the content digest; regenerate
the committed fixture and update the test expectation in the same change set.
