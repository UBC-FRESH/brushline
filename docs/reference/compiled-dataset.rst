Compiled corridor dataset
=========================

The compiled dataset is the boundary between ingestion and execution. The simulator and the planner read
the dataset and nothing else from the raw sources. A dataset directory contains a ``manifest.json`` and
one file per table.

Schema version: ``brushline.dataset.v1``.

Directory layout
----------------

.. code-block:: text

   dataset/
     manifest.json
     segments.parquet

The first release requires the ``segments`` table. P1.2 and P1.3 add the corridor, state, treatment,
observation, access, and structure tables. P1.4 adds the plan and run contracts, which live in the run
directory rather than the compiled dataset.

Manifest fields
---------------

.. list-table::
   :header-rows: 1
   :widths: 26 74

   * - Field
     - Meaning
   * - ``schema_version``
     - ``brushline.dataset.v1``.
   * - ``dataset_id``
     - Stable dataset identifier.
   * - ``name``, ``description``
     - Human-readable identity.
   * - ``created_utc``
     - Timezone-aware creation time.
   * - ``crs``
     - Coordinate reference system, for example ``EPSG:3005``.
   * - ``units``
     - Named units, such as ``{"length": "m", "area": "ha"}``.
   * - ``tables``
     - One :class:`TableSpec` per table.
   * - ``provenance``
     - Source, version, licence, creator, configuration, and model cards.
   * - ``content_digest``
     - SHA-256 of the canonical content fields.

Table fields
------------

.. list-table::
   :header-rows: 1
   :widths: 26 74

   * - Field
     - Meaning
   * - ``name``
     - Logical table name. ``segments`` is required.
   * - ``path``
     - Dataset-relative file path. Absolute paths and ``..`` are rejected.
   * - ``format``
     - ``parquet`` or ``csv``.
   * - ``primary_key``
     - One or more columns that must be present, non-null, and unique.
   * - ``columns``
     - Column contracts.
   * - ``row_count``
     - Expected row count.
   * - ``sha256``
     - SHA-256 of the table file.

Column fields
-------------

.. list-table::
   :header-rows: 1
   :widths: 26 74

   * - Field
     - Meaning
   * - ``name``
     - Column name.
   * - ``dtype``
     - Logical type: ``string``, ``int64``, ``float64``, ``bool``, ``datetime``, or ``date``.
   * - ``required``
     - Whether the column must be present. Defaults to true.
   * - ``unit``
     - Physical unit, when the column has one.
   * - ``description``
     - Short human description.

The ``segments`` table
----------------------

The P1.1 contract requires four columns:

.. list-table::
   :header-rows: 1
   :widths: 26 20 54

   * - Column
     - Type
     - Meaning
   * - ``segment_id``
     - string
     - Primary key.
   * - ``corridor_id``
     - string
     - Corridor that owns the segment.
   * - ``length_m``
     - float64
     - Segment length in metres.
   * - ``geometry_wkt``
     - string
     - Segment geometry as WKT.

P1.2 adds the span, treatment-unit, site, access, structure, and service-standard fields.

Content digest
--------------

The content digest covers the schema version, the dataset id, the CRS, and the table contracts: name,
path, format, primary key, row count, checksum, and column names, types, required flags, and units. It
does not cover ``created_utc``, ``name``, or ``description``, so a rebuild with the same content keeps the
same digest.

Validation
----------

Run:

.. code-block:: bash

   brushline validate --dataset build/compiled
   brushline validate --dataset build/compiled --json

The validator checks:

- the manifest exists and is valid JSON;
- the schema version is ``brushline.dataset.v1``;
- every table path is relative and stays inside the dataset;
- every table file exists and can be read;
- every required column is present and has the declared logical type;
- the primary key is present, non-null, and unique;
- the row count matches;
- the SHA-256 matches;
- the content digest matches;
- the required ``segments`` table is present.

Errors use stable prefixes: ``DATASET-MANIFEST``, ``DATASET-SCHEMA``, ``DATASET-PATH``,
``DATASET-TABLE``, ``DATASET-COLUMN``, ``DATASET-DTYPE``, ``DATASET-KEY``, ``DATASET-ROW-COUNT``,
``DATASET-CHECKSUM``, and ``DATASET-DIGEST``. An undeclared extra column is a warning
(``DATASET-EXTRA-COLUMN``), not an error.

Example
-------

.. code-block:: json

   {
     "schema_version": "brushline.dataset.v1",
     "dataset_id": "synthetic-corridor-v1",
     "name": "Synthetic corridor",
     "description": "A two-corridor contract fixture.",
     "created_utc": "2026-11-14T00:00:00Z",
     "crs": "EPSG:3005",
     "units": {"length": "m", "area": "ha"},
     "tables": [
       {
         "name": "segments",
         "path": "segments.parquet",
         "format": "parquet",
         "primary_key": ["segment_id"],
         "columns": [
           {"name": "segment_id", "dtype": "string", "required": true},
           {"name": "corridor_id", "dtype": "string", "required": true},
           {"name": "length_m", "dtype": "float64", "required": true, "unit": "m"},
           {"name": "geometry_wkt", "dtype": "string", "required": true}
         ],
         "row_count": 2,
         "sha256": "0000000000000000000000000000000000000000000000000000000000000000"
       }
     ],
     "provenance": {
       "source": "synthetic",
       "source_version": "1.0",
       "licence": "CC0-1.0",
       "created_by": "brushline"
     },
     "content_digest": "0000000000000000000000000000000000000000000000000000000000000000"
   }

The example digests are placeholders. A real manifest carries the actual file checksum and the computed
content digest.
