Canopy and cover support
========================

Canopy support maps a validated FEMIC CHM to buffered corridor segments. It records height and cover
statistics, optional vertical structure, optional individual-tree summaries, and VRI comparison
evidence. It does not generate a CHM, segment trees, classify species, or decide the low-vegetation
state. A CHM top is an observation, not a shrub or young-tree classification.

Input contract
--------------

A ``CanopyRaster`` is a north-up two-dimensional CHM with:

- a western, southern, eastern, and northern edge;
- a CRS and a resolution in metres;
- a vertical datum;
- a validated ``LidarProductProvenance`` whose product kind is ``chm``;
- an optional nodata value.

A segment is a buffered ``SegmentWindow`` polyline in the CHM CRS. A segment CRS that differs from the
CHM CRS fails; there is no silent reprojection.

Metrics
-------

For each segment, the adapter records:

- valid and candidate cell counts and coverage percentage;
- mean, median, p90, p95, p99, and maximum height;
- cover at 2, 5, 10, and 20 metres;
- optional vertical canopy bands;
- optional tree count, mean height, mean crown radius, and species;
- optional VRI comparison evidence.

Cover at a threshold is the percentage of valid cells at or above that height. A CHM top is not a
species or a low-vegetation class.

.. code-block:: python

   from datetime import UTC, datetime
   from brushline.integrations.canopy import (
       CanopyRaster,
       CanopyConfig,
       aggregate_canopy_support,
       validate_canopy_support,
   )
   from brushline.integrations.terrain import SegmentWindow

   raster = CanopyRaster(
       values=chm_array,
       min_x=0.0,
       min_y=0.0,
       max_x=500.0,
       max_y=500.0,
       crs="EPSG:3005",
       resolution_m=1.0,
       vertical_datum="CGVD2013",
       provenance=chm_provenance,
   )
   report = aggregate_canopy_support(
       raster,
       [SegmentWindow(segment_id="s1", coordinates=[(0, 10), (500, 10)], buffer_m=20)],
       CanopyConfig(min_valid_pixels=4, min_coverage_pct=50),
       created_utc=datetime(2026, 11, 14, tzinfo=UTC),
   )
   assert validate_canopy_support(report).is_valid

Optional tree product
---------------------

A ``TreeSupport`` carries its own individual-tree provenance, checksum, licence, CRS, datum, and
resolution. It adds:

- tree count;
- mean height;
- mean crown radius;
- species labels;
- optional model card.

The tree product is optional. Its absence leaves ``tree = null`` and does not block the build.

VRI comparison
--------------

A ``VriObservation`` carries the VRI height, cover, vintage, source, and optional model card. The
adapter records a ``VriComparison`` with both values and the differences:

- ``height_difference_m`` = LiDAR mean height minus VRI height;
- ``cover_difference_pct`` = LiDAR 10 m cover minus VRI cover.

The comparison note states that no reconciliation was applied. A VRI difference is evidence, not an
automatic correction.

Coverage and applicability
--------------------------

The support states are:

- ``observed``: valid cells and coverage meet the configured thresholds;
- ``partial``: some valid cells exist, but a threshold is not met;
- ``missing``: no valid cells, no canopy values, and a reason;
- ``out_of_domain``: valid cells exist, but more than the configured fraction lies outside the
  applicability domain.

The domain is optional. A lower bound, an upper bound, or both can be set. The support records the
domain and the out-of-domain fraction. It does not hide the observed values.

Named errors
------------

.. list-table::
   :header-rows: 1
   :widths: 28 72

   * - Prefix
     - Meaning
   * - ``CANOPY-SOURCE``, ``CANOPY-CRS``, ``CANOPY-DATUM``, ``CANOPY-RESOLUTION``
     - Provenance product or metadata mismatch.
   * - ``CANOPY-TIME``
     - The report time is not timezone-aware.
   * - ``CANOPY-STATE``, ``CANOPY-PIXELS``
     - Unknown state or impossible pixel counts.
   * - ``CANOPY-MISSING``, ``CANOPY-REASON``, ``CANOPY-VALUE``
     - Missing pixels, a missing reason, or no height statistic.
   * - ``CANOPY-COVERAGE``
     - Observed support below the pixel or coverage threshold.
   * - ``CANOPY-TREE``, ``CANOPY-VRI``, ``CANOPY-STRUCTURE``
     - Segment mismatch, VRI mismatch, or an unordered band.
   * - ``CANOPY-EMPTY``
     - The report has no segment supports (warning).

Limits
------

- The adapter does not rasterize a CHM, segment crowns, or classify species.
- It does not read a point cloud.
- It does not reconcile VRI and LiDAR; it records the difference.
- A CHM top is not a shrub or young-tree measurement. P3.4 owns the low-vegetation state class.
