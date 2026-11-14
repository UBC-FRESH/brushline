Fetch plan, materialization, and coverage
=========================================

P2.5 is plan-only. It reads the catalogue, estimates size and time, and records the approval and
coverage state. It does not download, order, read a private row, or call a secret store.

The four contracts are:

- ``brushline.fetch-plan.v1``: the plan-only preview.
- ``brushline.materialization.v1``: checksums, sizes, licences, and pointers.
- ``brushline.coverage.v1``: observed, stale, partial, missing, out-of-domain, and excluded states.
- ``brushline.gap-report.v1``: the next action and the stop/continue decision.

Fetch plan
----------

A ``FetchPlan`` has a plan id, a timezone-aware creation time, an AOI reference, ``mode =
plan_only``, and one item per requested source or connector. A ``FetchItem`` records:

- ``kind``: ``source`` or ``connector``;
- the source or connector id;
- the query or approved read scope;
- the licence or data-sharing record;
- the access status and classification;
- the estimated size in megabytes and time in seconds;
- the estimate basis;
- the bulk flag and optional approval;
- the materialization target and pointer;
- whether the item is required.

The plan copies metadata from the catalogue. This is a snapshot: if the catalogue licence or
classification changes later, ``validate_fetch_plan`` reports ``FETCH-DRIFT``.

Estimates
---------

The planner uses deterministic planning placeholders when the request does not supply an estimate.
They are not measurements.

.. list-table::
   :header-rows: 1
   :widths: 28 20 20 32

   * - Access method
     - Size (MB)
     - Time (seconds)
     - Basis
   * - ``bulk_download``
     - 5000
     - 3600
     - planning default
   * - ``stac``
     - 200
     - 120
     - planning default
   * - ``wfs``, ``api``, ``rest``
     - 50
     - 60
     - planning default
   * - ``wms``
     - 10
     - 30
     - planning default
   * - ``manual``
     - 0
     - 0
     - manual
   * - ``unknown``
     - 0
     - 0
     - unknown

A request can override an estimate with ``FetchEstimate(size_mb=..., seconds=..., basis="user")``.
The plan total is the sum of its items.

.. code-block:: python

   from datetime import UTC, datetime
   from brushline.integrations.catalogue import DataCatalogue
   from brushline.integrations.fetch import FetchRequest, plan_fetch, validate_fetch_plan

   catalogue = DataCatalogue.model_validate_json(
       open("notes/reference/data-catalogue.v1.json", encoding="utf-8").read()
   )
   plan = plan_fetch(
       catalogue,
       FetchRequest(aoi="aoi.geojson", source_ids=["lidarbc", "vri"]),
       plan_id="plan-1",
       created_utc=datetime(2026, 11, 14, tzinfo=UTC),
   )
   report = validate_fetch_plan(plan, catalogue)
   if not report.is_valid:
       raise SystemExit("\n".join(report.errors))

A bulk request requires an approval with ``scope="bulk"``. A missing approval, a single-scope approval,
or an incomplete approval fails. A non-bulk public item without an approval is a warning because the
plan is still a preview. An unapproved private connector is a ``FETCH-CONNECTOR`` error; the owner must
approve the catalogue connector first.

Materialization manifest
------------------------

A ``MaterializationManifest`` records what was retrieved, not the payload. A ``MaterializedItem`` has an
id, source id, status, instance-relative path, SHA-256, size in bytes, timezone-aware retrieval time,
licence, pointer, and reason.

Pointers are one of:

- ``data_lad:...`` for a DataLad or annex pointer;
- ``annex:...`` for an annex pointer;
- ``public_mirror:...`` for a public mirror;
- ``owner_store:...`` for a private owner store.

The pointer is metadata. The repository does not commit a payload.

.. code-block:: python

   from pathlib import Path
   from brushline.integrations.fetch import (
       MaterializationManifest,
       validate_materialization,
       materialization_decision,
   )

   report = validate_materialization(manifest, Path("."))
   if materialization_decision(manifest, Path(".")) == "stop":
       raise SystemExit("\n".join(report.errors))

A materialized item requires a path, checksum, size, licence, retrieval time, and pointer. When a root
is supplied, the validator also checks that the path is relative, stays inside the root, exists, and
matches the checksum and size. A mismatch fails with ``MATERIALIZATION-CHECKSUM``,
``MATERIALIZATION-SIZE``, or ``MATERIALIZATION-PATH``. The decision is ``stop`` for any error.

A missing, partial, or failed item does not need a checksum, but it must have a reason. That is how a
gap is recorded without inventing a file.

Coverage states
---------------

A ``CoverageReport`` has one entry per source and target, where the target is a segment, span, or
``aoi``. The six states are:

.. list-table::
   :header-rows: 1
   :widths: 22 78

   * - State
     - Rule
   * - ``observed``
     - Positive coverage and an evidence reference.
   * - ``stale``
     - Evidence and a vintage are required.
   * - ``partial``
     - Coverage strictly between 0 and 100, with evidence.
   * - ``missing``
     - Zero coverage and a reason.
   * - ``out_of_domain``
     - A reason the source does not apply.
   * - ``excluded``
     - A reason the source was deliberately excluded.

The report does not impute coverage. An unknown or unavailable source is recorded as missing or
out-of-domain, with the evidence and the next action. ``coverage_counts`` returns one count per state
plus ``total``.

Gap report
----------

``build_gap_report`` turns every non-observed coverage entry into a ``GapRecord`` with a next action.

.. list-table::
   :header-rows: 1
   :widths: 24 76

   * - State
     - Recommended action
   * - ``missing``
     - Request or acquire the source, or mark the affected segments unknown.
   * - ``stale``
     - Refresh the source or treat the observation as historical.
   * - ``partial``
     - Fill the gap with another source, or mark the affected segments partial.
   * - ``out_of_domain``
     - Exclude the source or use a local calibration.
   * - ``excluded``
     - Confirm the exclusion and record the decision.

A required missing or out-of-domain source sets ``decision = stop``. A stale, partial, excluded, or
optional gap sets ``continue_with_caveat``. A report with no gaps is ``continue`` and uses
``next_action = none``. The first gap action becomes ``next_action``. The decision and the action are
validated together; a ``stop`` with no stopping gap, or a ``continue`` with a gap, fails.

Named errors
------------

.. list-table::
   :header-rows: 1
   :widths: 32 68

   * - Prefix
     - Meaning
   * - ``FETCH-ID``, ``FETCH-TIME``
     - Duplicate items and a non-timezone-aware plan.
   * - ``FETCH-KIND``, ``FETCH-LICENCE``, ``FETCH-CLASSIFICATION``, ``FETCH-ACCESS``
     - Item shape and access metadata.
   * - ``FETCH-ESTIMATE``, ``FETCH-MATERIALIZATION``
     - Negative estimates and pointer/target problems.
   * - ``FETCH-APPROVAL``
     - Missing, single-scope, incomplete, or unknown approval.
   * - ``FETCH-SOURCE``, ``FETCH-CONNECTOR``, ``FETCH-DRIFT``
     - Unknown references and catalogue drift.
   * - ``FETCH-EMPTY``
     - An empty plan (warning).
   * - ``MATERIALIZATION-*``
     - Status, path, checksum, size, licence, pointer, retrieval time, reason, or empty manifest.
   * - ``COVERAGE-*``
     - State, evidence, partial range, missing coverage, reason, duplicate, time, or empty report.
   * - ``GAP-*``
     - Decision, state, action, duplicate, time, or caveat.

What P2.5 does not do
---------------------

- It does not download or order data. P2.5 has no network call.
- It does not create a second downloader. A later stage uses FEMIC's catalogue and materialization
  paths.
- It does not approve a private connector. The owner approval lives on the catalogue connector.
- It does not place a payload in Git. Pointers and checksums are the record.
- It does not turn a missing or partial source into a value.
