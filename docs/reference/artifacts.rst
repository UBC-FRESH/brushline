Artifact contracts
==================

The run directory and the demo catalogue use five artifact contracts:

- ``brushline.plan.v1``: the owner-contractor plan.
- ``brushline.run.v1``: the run manifest.
- ``brushline.pareto.v1``: the multi-objective archive.
- ``brushline.timeline.v1``: the operations timeline.
- ``brushline.demo.v1``: the public demo manifest.

Each contract has a Pydantic model, a validator, and a named-error report. The report uses the shared
:class:`brushline.model.validation.ContractValidation` shape.

Plan
----

A plan has a versioned header, one or more actions, and named assumptions.

- ``PlanHeader``: plan id, version, status, scenario, dataset, data version, model versions,
  configuration, currency, creation time, creator, parent plan, seed, service standards, and notes.
- ``PlanAction``: action id, segment, year, season, method, intensity, treatment unit, quantities, cost
  lines, assumptions, and risk notes.
- ``CostLine``: category, amount, description, optional quantity and rate, currency, and source.
- ``PlanAssumption``: assumption id, statement, source, and impact.

The validator checks duplicate action and assumption ids, unknown segments when a known set is supplied,
currency consistency, and a plan that names itself as its parent. An action without an explicit
assumption is a warning.

Run
---

A run manifest names the run type, status, data version, model versions, configuration, seed, artifact
index, and summary.

- ``RunArtifact``: name, relative path, schema version, media type, availability, SHA-256, and a reason
  when unavailable.
- ``RunManifest``: run id, run type, status, creation time, data version, model versions, configuration,
  artifacts, creator, seed, and summary.

An available artifact needs a SHA-256. An unavailable artifact needs a reason. A complete run with no
available artifact, or a failed run with an available artifact, is a warning.

Pareto archive
--------------

The archive keeps the non-dominated plans from a search portfolio.

- ``Objective``: name, direction (``minimize`` or ``maximize``), and unit.
- ``Scalarization``: id, weights, and description. The weights must be non-negative and sum to 1.
- ``ArchiveMember``: plan id, plan path, objective vector, feasibility, seed, evidence path, budget, and
  metadata.
- ``ParetoArchive``: instance, run, objectives, scalarizations, members, eviction policy, creation time,
  and creator.

The validator checks duplicate objective, scalarization, and member ids; unknown scalarization weights;
member objective keys; and non-dominance. A dominated member fails with ``PARETO-DOMINANCE``. An empty
archive is valid but warned.

Operations timeline
-------------------

The timeline is a sequence of timestamped events for the 2D map and 3D scene.

- ``TimelineEvent``: event id, resource id and type, segment, event type, start and end time, state,
  optional action, cost, currency, and notes.
- ``OperationsTimeline``: run id, events, creation time, and creator.

Timestamps are timezone-aware. An end time before the start time fails. The validator checks duplicate
event ids, non-decreasing start times, and segment references. An event without an end time is a
warning; the animation shows an open event rather than inventing a position.

Demo manifest
-------------

The demo manifest describes one public example.

- ``DemoSource``: name, licence, version, and URL.
- ``DemoMetric``: name, value, and unit.
- ``DemoArtifacts``: run, plan, reports, optional Pareto archive, and optional timeline.
- ``DemoManifest``: id, title, sector, region, AOI, question, sources, scenarios, artifacts, metrics,
  caveats, pilot link, status, creation time, and contact.

The id is a lowercase slug. A published demo needs a run, a plan, and reports. A draft or retired demo,
a missing Pareto archive, and a missing timeline are warnings. Artifact and AOI paths are relative and
must stay inside the demo directory.

Named errors
------------

.. list-table::
   :header-rows: 1
   :widths: 26 74

   * - Prefix
     - Meaning
   * - ``PLAN-ID``, ``PLAN-REF``, ``PLAN-CURRENCY``, ``PLAN-VERSION``
     - Duplicate ids, unknown segments, currency mismatches, and version problems.
   * - ``RUN-ID``, ``RUN-ARTIFACT``
     - Duplicate artifact names and status/availability warnings.
   * - ``PARETO-ID``, ``PARETO-OBJECTIVE``, ``PARETO-SCALARIZATION``, ``PARETO-DOMINANCE``,
       ``PARETO-EMPTY``
     - Duplicate ids, member keys, scalarization weights, dominance, and an empty archive.
   * - ``TIMELINE-ID``, ``TIMELINE-ORDER``, ``TIMELINE-REF``, ``TIMELINE-OPEN``
     - Duplicate events, ordering, segment references, and open events.
   * - ``DEMO-LICENCE``, ``DEMO-ARTIFACT``, ``DEMO-STATUS``
     - Missing licences, missing published artifacts, and non-published status.

Plan example
------------

.. code-block:: json

   {
     "header": {
       "schema_version": "brushline.plan.v1",
       "plan_id": "plan-1",
       "version": 1,
       "status": "proposed",
       "scenario_id": "scenario-1",
       "dataset_id": "dataset-1",
       "data_version": "sha256:abc",
       "model_versions": {"growth": "p1", "treatment": "p1"},
       "currency": "CAD",
       "created_utc": "2026-11-14T00:00:00Z",
       "created_by": "brushline"
     },
     "actions": [
       {
         "action_id": "a1",
         "segment_id": "s1",
         "year": 2026,
         "season": "summer",
         "method": "mowing",
         "intensity": 0.8,
         "quantity_ha": 1.0,
         "cost_lines": [
           {"category": "labour", "quantity": 10.0, "rate": 100.0, "amount": 1000.0}
         ],
         "assumptions": ["Rates from the 2026 contract."]
       }
     ],
     "assumptions": [
       {"assumption_id": "as1", "statement": "One pass per segment.", "source": "owner"}
     ]
   }

Python use
----------

.. code-block:: python

   from pathlib import Path
   from brushline.model.plan import Plan, validate_plan

   plan = Plan.model_validate_json(Path("plan.json").read_text())
   report = validate_plan(plan, known_segment_ids={"s1", "s2"})
   if not report.is_valid:
       raise SystemExit("\n".join(report.errors))
