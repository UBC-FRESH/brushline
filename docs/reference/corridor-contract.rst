Corridor graph contract
=======================

The corridor graph defines the decision units and the operational groupings. The schema version is
``brushline.corridor.v1``. The contract is validated by
:func:`brushline.model.corridor.validate_corridor_network`.

Objects
-------

.. list-table::
   :header-rows: 1
   :widths: 24 76

   * - Object
     - Meaning
   * - ``Corridor``
     - A linear asset and the land managed along it. Carries a stable id, an asset type, a total length,
       and the CRS.
   * - ``Segment``
     - The decision unit. A length of corridor with a stable id, a zero-based position within its span,
       a length, a line geometry, a service standard, an optional access point, and optional structures.
   * - ``Span``
     - An ordered, contiguous run of segments between access points.
   * - ``TreatmentUnit``
     - A set of segments scheduled and contracted together, with a contract year window.
   * - ``AccessPoint``
     - A road, trail, landing, water, or other access point that serves a span or a segment.
   * - ``Structure``
     - A tower, pole, valve, crossing, or other asset structure with a required clearance.
   * - ``ServiceStandard``
     - A maximum vegetation height, a minimum clearance, and an access requirement.

Root fields
-----------

.. list-table::
   :header-rows: 1
   :widths: 26 74

   * - Field
     - Meaning
   * - ``schema_version``
     - ``brushline.corridor.v1``.
   * - ``crs``
     - Coordinate reference system for every geometry.
   * - ``corridors``
     - One or more corridors.
   * - ``segments``
     - One or more decision segments.
   * - ``spans``
     - One or more ordered spans.
   * - ``treatment_units``
     - One or more contracted treatment units.
   * - ``access_points``
     - Access points; optional at the root, but a referenced access point must exist.
   * - ``structures``
     - Structures; optional at the root, but a referenced structure must exist.
   * - ``service_standards``
     - One or more service standards.

Invariants
----------

The validator checks:

- every collection id is unique;
- every corridor CRS matches the root CRS;
- every segment references an existing corridor, span, treatment unit, and service standard;
- every segment is listed in its span and in its treatment unit;
- a span's segments have the contiguous sequence ``0 .. n-1`` in the listed order;
- no span or treatment unit repeats a segment;
- a segment belongs to at most one treatment unit;
- a treatment unit's contract window is ordered;
- a span's access points exist and belong to the same corridor;
- a structure's segment and corridor exist and agree;
- the sum of a corridor's segment lengths equals its declared length within the tolerance;
- a segment without an access point is a warning, not an error.

Named errors use the prefixes ``CORRIDOR-ID``, ``CORRIDOR-CRS``, ``CORRIDOR-REF``,
``CORRIDOR-SPAN``, ``CORRIDOR-SEQUENCE``, ``CORRIDOR-TU``, ``CORRIDOR-ACCESS``,
``CORRIDOR-STRUCTURE``, and ``CORRIDOR-LENGTH``.

Geometry
--------

Segment geometry is ``LINESTRING`` or ``MULTILINESTRING`` WKT. Access point geometry is ``POINT`` WKT.
All geometry is in the root CRS. A reprojection is an explicit, recorded decision, not an implicit
step.

Example
-------

.. code-block:: json

   {
     "schema_version": "brushline.corridor.v1",
     "crs": "EPSG:3005",
     "corridors": [
       {
         "corridor_id": "c1",
         "name": "Example transmission corridor",
         "asset_type": "transmission",
         "length_m": 30.0,
         "crs": "EPSG:3005"
       }
     ],
     "segments": [
       {
         "segment_id": "s1",
         "corridor_id": "c1",
         "span_id": "sp1",
         "treatment_unit_id": "tu1",
         "sequence": 0,
         "length_m": 10.0,
         "geometry_wkt": "LINESTRING (0 0, 10 0)",
         "service_standard_id": "std1",
         "access_point_id": "ap1",
         "structure_ids": ["st1"]
       },
       {
         "segment_id": "s2",
         "corridor_id": "c1",
         "span_id": "sp1",
         "treatment_unit_id": "tu1",
         "sequence": 1,
         "length_m": 20.0,
         "geometry_wkt": "LINESTRING (10 0, 30 0)",
         "service_standard_id": "std1",
         "access_point_id": "ap1"
       }
     ],
     "spans": [
       {
         "span_id": "sp1",
         "corridor_id": "c1",
         "segment_ids": ["s1", "s2"],
         "access_point_ids": ["ap1"]
       }
     ],
     "treatment_units": [
       {
         "treatment_unit_id": "tu1",
         "corridor_id": "c1",
         "segment_ids": ["s1", "s2"],
         "contract_start_year": 2027,
         "contract_end_year": 2031
       }
     ],
     "access_points": [
       {
         "access_point_id": "ap1",
         "corridor_id": "c1",
         "kind": "road",
         "location_wkt": "POINT (0 0)"
       }
     ],
     "structures": [
       {
         "structure_id": "st1",
         "corridor_id": "c1",
         "segment_id": "s1",
         "structure_type": "tower",
         "clearance_m": 6.0
       }
     ],
     "service_standards": [
       {
         "service_standard_id": "std1",
         "max_height_m": 3.0,
         "min_clearance_m": 6.0,
         "access_required": true
       }
     ]
   }

Python use
----------

.. code-block:: python

   from pathlib import Path
   from brushline.model.corridor import CorridorNetwork, validate_corridor_network

   network = CorridorNetwork.model_validate_json(Path("corridor.json").read_text())
   report = validate_corridor_network(network)
   if not report.is_valid:
       raise SystemExit("\n".join(report.errors))
