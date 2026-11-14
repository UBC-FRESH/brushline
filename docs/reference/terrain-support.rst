Terrain and slope support
=========================

Terrain support maps a validated FEMIC DEM or DSM to a buffered corridor segment. It records the
aggregation statistic, buffer, valid-pixel rule, coverage, elevation, slope, aspect, terrain class, and
an explicit access proxy. It never reprojects, resamples, fills a missing cell, or downloads a raster.

Input contract
--------------

A ``TerrainRaster`` is a north-up two-dimensional elevation array with:

- a western and southern edge and an eastern and northern edge;
- a CRS and a resolution in metres;
- a vertical datum;
- a validated ``LidarProductProvenance`` whose product kind is ``dem`` or ``dsm``;
- an optional nodata value.

The raster provenance must agree with the raster CRS, resolution, and vertical datum. A mismatch fails;
there is no silent transform.

A ``SegmentWindow`` is a polyline in the raster CRS with a buffer distance. The buffer is the corridor
support around the segment. A segment CRS that differs from the raster CRS fails.

Aggregation
-----------

``aggregate_terrain_support`` samples cell centers within the segment buffer and computes:

- valid-cell count and candidate-cell count;
- coverage percentage;
- elevation statistic;
- slope statistic;
- circular mean aspect;
- terrain class;
- access proxy and access class.

The supported statistics are ``mean``, ``median``, ``min``, ``max``, and ``p90``. The configuration
records the minimum valid-pixel count and minimum coverage percentage.

.. code-block:: python

   from datetime import UTC, datetime
   from brushline.integrations.terrain import (
       SegmentWindow,
       TerrainConfig,
       TerrainRaster,
       aggregate_terrain_support,
       validate_terrain_support,
   )

   raster = TerrainRaster(
       values=dem_array,
       min_x=0.0,
       min_y=0.0,
       max_x=500.0,
       max_y=500.0,
       crs="EPSG:3005",
       resolution_m=1.0,
       vertical_datum="CGVD2013",
       provenance=dem_provenance,
   )
   report = aggregate_terrain_support(
       raster,
       [SegmentWindow(segment_id="s1", coordinates=[(0, 10), (500, 10)], buffer_m=20)],
       TerrainConfig(statistic="mean", min_valid_pixels=4, min_coverage_pct=50),
       created_utc=datetime(2026, 11, 14, tzinfo=UTC),
   )
   assert validate_terrain_support(report).is_valid

Coverage states
---------------

.. list-table::
   :header-rows: 1
   :widths: 18 82

   * - State
     - Rule
   * - ``observed``
     - Valid pixels and coverage meet the configured thresholds.
   * - ``partial``
     - Some valid cells exist, but a threshold is not met.
   * - ``missing``
     - No valid cells exist in the buffer; terrain values are empty and a reason is recorded.

A partial or missing state is not a zero. It is a knowledge state for the state build and the review.

Terrain classes
---------------

The slope classes are:

- ``flat``: less than 2 degrees;
- ``gentle``: 2 to less than 10 degrees;
- ``moderate``: 10 to less than 20 degrees;
- ``steep``: 20 to less than 30 degrees;
- ``very_steep``: 30 degrees or more.

The access proxy is ``max(0, 1 - slope / access_slope_deg)``, with a default 30-degree zero point. It is
an evidence input, not an operability verdict. The access classes are ``high`` at 0.8 or more,
``moderate`` at 0.5 or more, and ``low`` below 0.5. Missing support is ``unknown``.

Named errors
------------

.. list-table::
   :header-rows: 1
   :widths: 28 72

   * - Prefix
     - Meaning
   * - ``TERRAIN-CONFIG``
     - Unknown statistic or invalid aggregation rule.
   * - ``TERRAIN-SOURCE``
     - Provenance is not a DEM/DSM, or source metadata is wrong.
   * - ``TERRAIN-CRS``, ``TERRAIN-DATUM``, ``TERRAIN-RESOLUTION``
     - Source and report metadata disagree.
   * - ``TERRAIN-TIME``
     - The report time is not timezone-aware.
   * - ``TERRAIN-STATE``, ``TERRAIN-PIXELS``, ``TERRAIN-COVERAGE``
     - Unknown state, impossible pixel counts, or observed support below a threshold.
   * - ``TERRAIN-VALUE``, ``TERRAIN-MISSING``, ``TERRAIN-REASON``
     - Missing values, a missing state with valid pixels, or a missing reason.
   * - ``TERRAIN-ACCESS``
     - A non-missing support has no access proxy (warning).
   * - ``TERRAIN-EMPTY``
     - The report has no segments (warning).

Limits
------

- The adapter does not parse raster payloads; the caller supplies the validated elevation array.
- It does not reproject, resample, mosaic, or fill nodata.
- It does not decide machine operability, access permission, or an operational route.
- It does not choose the final terrain threshold for a partnership; that remains a documented
  configuration decision.
