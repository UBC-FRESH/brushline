Multi-objective archive
=======================

P5.5 turns replayable P5.4 search runs into a validated ``brushline.pareto.v1`` archive. The archive
keeps feasible, non-dominated vectors, records diversity, evicts deterministically, and can promote one
member to a plan version.

Building an archive
-------------------

.. code-block:: python

   from brushline.optimization.pareto import build_archive, write_pareto_archive

   result = build_archive(runs, instance_id="tiny", run_id="tiny-v1")
   assert result.archive.members
   write_pareto_archive(result.archive, "runs/tiny/pareto.json")

``build_archive`` performs these steps in order:

1. Reject runs outside the declared instance.
2. Reject infeasible runs and record their plan ids.
3. Deduplicate identical four-objective vectors and record the duplicates.
4. Remove every dominated member using the declared directions.
5. Compute crowding distance and apply ``max_size`` if needed.
6. Validate the archive before returning it.

Objectives
----------

The archive uses the same four objectives as the formulation:

.. list-table::
   :header-rows: 1
   :widths: 28 18 16 38

   * - Objective
     - Direction
     - Unit
     - Meaning
   * - ``present_cost``
     - minimize
     - CAD
     - Discounted treatment and monitoring cost.
   * - ``service_risk``
     - minimize
     - index
     - Exceedance risk.
   * - ``service_attainment``
     - maximize
     - fraction
     - Share of service targets attained.
   * - ``uncertainty``
     - minimize
     - index
     - Remaining state uncertainty.

The scalarization portfolio is ``cost_first``, ``risk_first``, ``service_first``,
``uncertainty_first``, and ``balanced``. Its weights sum to one. A scalarization seeds search; the
archive preserves the vector.

Diversity and eviction
----------------------

Crowding distance is the sum of normalized neighbour gaps over the four objectives. Boundary members
receive the explicit ``1e9`` crowding sentinel, not infinity, so the archive serializes as strict JSON.
A constant objective span contributes zero to every member's distance.

If the archive exceeds ``max_size``, members with the highest crowding distance are kept. Ties are
broken by plan id. The eviction policy is recorded as ``crowding-distance-v1`` and the removed plan ids
are returned in ``ArchiveResult.evicted``.

Members
-------

Each member records:

- a stable plan id;
- an archive-relative ``plans/<plan_id>.json`` path;
- the full objective vector;
- feasibility, seed, and budget;
- an archive-relative ``evidence/<plan_id>.json`` path;
- mode, adapter, scalarization, source run, and crowding distance metadata.

The paths are references. P5.5 does not write the plan or evidence payloads; P5.8 freezes the telemetry
contract and P10 reads the artifacts.

Promotion
---------

``promote_member`` selects one archive member and returns a ``brushline.promotion.v1`` record with the
plan, optional parent plan, reason, objective vector, creation time, and promoter. A promotion cannot
parent itself. ``write_promotion`` and ``load_promotion`` round-trip the record.

.. code-block:: python

   from brushline.optimization.pareto import promote_member

   promotion = promote_member(
       result.archive,
       result.archive.members[0].plan_id,
       "best balanced trade-off",
       parent_plan_id="plan-prev",
   )

Promotion is an explicit decision record; it does not claim the member is globally best.

Named errors
------------

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Prefix
     - Meaning
   * - ``PARETO-SCALARIZATION``
     - A scalarization weights an unknown objective.
   * - ``PARETO-OBJECTIVE``
     - A member is missing or has an extra objective.
   * - ``PARETO-DOMINANCE``
     - A member is dominated.
   * - ``PARETO-EMPTY``
     - The archive has no members (warning).
   * - ``PROMOTION-OBJECTIVE``
     - A promotion does not carry the four objectives.

Limits
------

- A non-dominated archive is not a proof of global optimality.
- Crowding distance is a diversity proxy, not a decision preference.
- The archive does not write plan or evidence payloads; the paths are references.
- Promotion needs the plan and evidence writers from the later planning phases.
