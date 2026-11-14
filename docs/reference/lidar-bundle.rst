FEMIC LiDAR bundle
==================

Brushline consumes the producer's packaged LiDAR bundle. It does not discover tiles, download points,
compile terrain, or write payloads. The adapter is read-only: it validates the manifest and selection
provenance, verifies every product checksum, and returns source-preserving provenance for the later
segment-support stages.

The committed contract reference is ``notes/reference/femic-lidar-bundle.v1.json``. It records the
schema versions, the exact FEMIC pin, the product kinds, the required keys, and the consumer rules.

Producer boundary
-----------------

.. list-table::
   :header-rows: 1
   :widths: 24 76

   * - Item
     - Value
   * - Product manifest
     - ``femic.lidar.product.v1``
   * - Bundle layout
     - ``femic.lidar.bundle.v1``
   * - Selection provenance
     - ``femic.lidar.selection.v1``
   * - Producer
     - ``femic`` at the exact ``0.2.0a1`` pin
   * - Source
     - ``lidarbc`` / ``OGL-BC`` / ``EPSG:3005``
   * - Manifest path
     - ``manifest.json``
   * - Selection path
     - ``provenance/selection.json``
   * - Products directory
     - ``products/``

The adapter reads no product bytes until the manifest, selection digest, and paths pass. It never writes a
payload, and it does not call FEMIC internals.

Bundle layout
-------------

A bundle contains:

- ``manifest.json``: bundle identity, source, selection digest, processing, summary, product records,
  and consumer contract;
- ``provenance/selection.json``: the producer's selection manifest, whose canonical SHA-256 must equal
  ``manifest.selection.sha256``;
- ``products/``: the product files, each with a size and SHA-256 record.

The product kinds are ``point_cloud``, ``dem``, ``dsm``, ``chm``, ``canopy``, ``individual_tree``, and
``slope``. Raster kinds (``dem``, ``dsm``, ``chm``, ``canopy``, ``slope``) require a positive
``resolution_m``. Derived kinds (``chm``, ``canopy``, ``slope``) require ``derived = true`` and should
carry lineage notes.

Validation
----------

.. code-block:: python

   from pathlib import Path
   from brushline.integrations.lidar import (
       load_lidar_bundle,
       product_provenance,
       validate_lidar_bundle,
   )

   report = validate_lidar_bundle(Path("instance/data/lidar-bundle"))
   if not report.is_valid:
       raise SystemExit("\n".join(report.errors))
   manifest = load_lidar_bundle(Path("instance/data/lidar-bundle"))
   provenance = product_provenance(manifest)

The validator checks:

- the exact schema, layout, producer tool, and producer version;
- the bundle id, name, version, and timezone-aware creation time;
- the source id, licence, and native CRS, and their agreement with the selection provenance;
- the selection schema, canonical digest, AOI bbox, tiles, layers, and requested products;
- the processing version and the consumer-contract keys;
- the summary product count and total bytes;
- unique product ids and paths;
- product kind, raster resolution, derived flag, and lineage warning;
- product CRS, licence, source tiles, and source layers against the selection;
- path containment, file existence, size, and SHA-256;
- a warning when a requested product is not in the bundle.

Provenance
----------

``product_provenance`` returns one record per product with:

- ``bundle_id`` and ``bundle_version``;
- the producer FEMIC version;
- product id, kind, checksum, CRS, resolution, and vertical datum;
- licence, retrieval time, source tiles, and source layers;
- the derived flag and lineage notes.

The product manifest does not carry a low-vegetation model card. P3.4 and P3.5 attach the model card and
applicability to the derived state attributes. The adapter does not invent one.

Named errors
------------

.. list-table::
   :header-rows: 1
   :widths: 28 72

   * - Prefix
     - Meaning
   * - ``LIDAR-MANIFEST``
     - Missing, unreadable, non-object, or schema-invalid manifest.
   * - ``LIDAR-SCHEMA``, ``LIDAR-LAYOUT``, ``LIDAR-PIN``
     - Wrong schema, layout, producer tool, or producer version.
   * - ``LIDAR-TIME``
     - Non-ISO or non-timezone-aware timestamp.
   * - ``LIDAR-SOURCE``, ``LIDAR-LICENCE``, ``LIDAR-CRS``
     - Source identity, licence, or CRS problem.
   * - ``LIDAR-SELECTION``
     - Missing, unreadable, malformed, or digest-mismatched selection provenance.
   * - ``LIDAR-PROCESSING``
     - Missing processing version.
   * - ``LIDAR-CONTRACT``
     - Missing consumer-contract key.
   * - ``LIDAR-SUMMARY``
     - Product count or total bytes mismatch.
   * - ``LIDAR-PRODUCT``, ``LIDAR-RESOLUTION``, ``LIDAR-DERIVED``
     - Duplicate/unknown product, missing raster resolution, or inconsistent derived flag.
   * - ``LIDAR-TILE``
     - Product references an unknown source tile or layer.
   * - ``LIDAR-PATH``, ``LIDAR-SIZE``, ``LIDAR-CHECKSUM``
     - Path escape, missing file, size mismatch, or checksum mismatch.

What this page does not do
--------------------------

- It does not download, order, materialize, or resume a tile.
- It does not compile terrain or canopy.
- It does not read a point cloud, raster, or private source.
- It does not make a low-vegetation model card or an operational state.
- It does not replace the FEMIC producer validator; it is the Brushline consumer check.
