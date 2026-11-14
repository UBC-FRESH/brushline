LiDAR coverage and applicability
================================

The LiDAR coverage adapter maps point-cloud, DEM, CHM, field-plot, inventory, climate, and site-index
evidence into the P2.5 coverage and gap contracts. It records acquisition age, usable coverage, valid
pixels, model-card applicability, a next action, and a stop/continue decision. It does not read a
payload, download a product, or fill a missing value.

Evidence
--------

A ``LidarCoverageRequest`` has an AOI, a plan id, segment ids, observations, required and optional
evidence kinds, and a config.

Each ``LidarEvidence`` records:

- segment id and evidence kind;
- acquisition date;
- source coverage and optional valid-pixel percentage;
- model-card applicability, with a reason when out of domain;
- evidence reference, source, and source version;
- optional exclusion and reason.

The default required kinds are ``point_cloud``, ``dem``, and ``chm``. The default optional kind is
``field_plot``. Inventory, climate, and site-index evidence can be added when a scenario needs them.

Coverage states
---------------

The adapter evaluates each segment/evidence pair:

1. ``excluded`` when the evidence is deliberately excluded;
2. ``missing`` when there is no evidence or usable coverage is zero;
3. ``partial`` when usable coverage or valid-pixel coverage is below the threshold;
4. ``stale`` when the acquisition is older than the contemporary window;
5. ``out_of_domain`` when the model-card applicability is false;
6. ``observed`` otherwise.

Usable coverage is ``min(source coverage, valid-pixel percentage)`` when a valid-pixel percentage is
provided. The report keeps both values, so a high source coverage with poor valid pixels is visible. A
missing or partial state is knowledge, not a zero.

.. code-block:: python

   from datetime import UTC, date, datetime
   from brushline.integrations.lidar_coverage import (
       Applicability,
       LidarCoverageConfig,
       LidarCoverageRequest,
       LidarEvidence,
       assess_lidar_coverage,
       validate_lidar_coverage,
   )

   request = LidarCoverageRequest(
       aoi="aoi.geojson",
       segment_ids=["s1"],
       observations=[
           LidarEvidence(
               segment_id="s1",
               kind="dem",
               acquisition_date=date(2026, 6, 1),
               coverage_pct=98,
               valid_pixel_pct=92,
               applicability=Applicability(model_card_id="dem-card"),
               evidence="bundle-1/dem",
               source="femic",
               source_version="0.2.0a1",
           )
       ],
       required_kinds=["point_cloud", "dem", "chm"],
       optional_kinds=["field_plot"],
       config=LidarCoverageConfig(state_year=2026, max_age_years=10),
   )
   report = assess_lidar_coverage(
       request,
       created_utc=datetime(2026, 11, 14, tzinfo=UTC),
   )
   assert validate_lidar_coverage(report).is_valid

Gap and stop/continue
---------------------

The adapter builds a P2.5 ``CoverageReport`` and ``GapReport``. A required missing or out-of-domain
evidence kind stops the state build. A stale, partial, excluded, or optional gap continues with a
caveat. The next action is the first recommended action:

- missing: request or acquire the evidence, or mark the affected state unknown;
- stale: refresh the evidence or treat it as historical;
- partial: fill the gap or mark the state partial;
- out-of-domain: exclude the model output or use a locally validated model;
- excluded: confirm the exclusion and record the decision.

The P2.7 review screen can show the gap report unchanged. The stop/continue decision is the handoff to
the state build.

Named errors
------------

.. list-table::
   :header-rows: 1
   :widths: 34 66

   * - Prefix
     - Meaning
   * - ``LIDAR-COVERAGE-TIME``
     - The report time is not timezone-aware.
   * - ``LIDAR-COVERAGE-ID``
     - Duplicate segment/evidence entry.
   * - ``LIDAR-COVERAGE-STATE``
     - Unknown coverage state.
   * - ``LIDAR-COVERAGE-VALID``, ``LIDAR-COVERAGE-COVERAGE``
     - Invalid valid-pixel value or usable coverage above source coverage.
   * - ``LIDAR-COVERAGE-ACTION``
     - A non-observed entry has no next action.
   * - ``LIDAR-COVERAGE-STALE``
     - A stale entry has no acquisition date.
   * - ``LIDAR-COVERAGE-DOMAIN``
     - An out-of-domain entry is not marked out of domain.
   * - ``LIDAR-COVERAGE-EXCLUDED``
     - An excluded entry has no reason.
   * - ``LIDAR-COVERAGE-REF``
     - The P2.5 coverage view is missing an entry or disagrees on state.
   * - ``LIDAR-COVERAGE-EMPTY``
     - The report has no entries (warning).

Limits
------

- The adapter does not check a point cloud, raster, or field plot payload.
- It does not decide whether a stale source is acceptable for a specific decision; it records the
  state and the action.
- It does not approve a model applicability domain; it records the model card and reason.
- It does not impute a missing value or a zero.
