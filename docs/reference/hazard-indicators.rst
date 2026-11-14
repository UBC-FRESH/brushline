Hazard and service indicators
=============================

The P4.5 indicators turn a vegetation state and corridor context into inspectable decision aids:
clearance margin, fall-in reach, fuel connectivity, access, and a weighted reliability proxy.

They are not engineering certifications, fire-spread simulations, or outage predictions.

Inputs
------

A ``HazardRequest`` carries:

- segment id, mean height, cover, and height uncertainty;
- a corridor ``ServiceStandard``;
- an optional asset height;
- optional mature-edge height and distance;
- adjacent-segment fuel evidence;
- optional slope and source-preserving road evidence.

A missing input is ``unknown``. It is never treated as zero.

Clearance
---------

.. code-block:: text

   height_margin = service_max_height - vegetation_height
   clearance_gap = asset_height - vegetation_height - min_clearance

The status is:

- ``clear`` when the height margin meets the warning threshold and the asset gap is non-negative;
- ``at_risk`` when the margin is non-negative but below the warning threshold;
- ``exceeded`` when either the margin or the asset gap is negative.

Fall-in
-------

.. code-block:: text

   reach = edge_height * wind_factor
   risk  = clamp(1 - edge_distance / reach, 0, 1)

Risk below 0.25 is ``low``, below 0.6 is ``moderate``, and the rest is ``high``. Missing edge evidence is
``unknown``.

Fuel connectivity
-----------------

Fuel connectivity is a distance-weighted mean of adjacent-segment cover, divided by 100. Below 0.25 is
``low``, below 0.6 is ``moderate``, and above is ``high``. No neighbours is ``unknown``.

Access
------

.. code-block:: text

   slope_factor = clamp(1 - slope / zero_slope, 0, 1)
   proxy        = slope_factor * road_score

The road status and its source are preserved. The record does not translate a source class into an
open/closed verdict. A high proxy is 0.7 or more, moderate is 0.4 or more, and low is below 0.4. No access
evidence is ``unknown``.

Reliability
-----------

The reliability proxy is a weighted mean of available component scores:

- clearance: 1 for clear, 0.5 for at risk, 0 for exceeded;
- fall-in: ``1 - risk``;
- fuel: ``1 - connectivity``;
- access: the access proxy.

Default weights are clearance 0.4, fall-in 0.25, fuel 0.15, and access 0.2. Missing components are
omitted and the remaining weights are renormalized. No available component gives ``unknown``.

.. code-block:: python

   from datetime import UTC, datetime
   from brushline.model.corridor import ServiceStandard
   from brushline.vegetation.hazards import (
       AccessEvidence,
       FuelNeighbor,
       HazardRequest,
       assess_hazards,
       validate_hazard_report,
   )

   report = assess_hazards(
       HazardRequest(
           segment_id="s1",
           height_m=2.0,
           cover_pct=40,
           service_standard=ServiceStandard(
               service_standard_id="clearance",
               max_height_m=4.0,
               min_clearance_m=1.0,
           ),
           asset_height_m=5.0,
           edge_height_m=12.0,
           edge_distance_m=8.0,
           neighbors=[FuelNeighbor(segment_id="s2", cover_pct=60, distance_m=10)],
           access=AccessEvidence(
               slope_deg=10,
               road_status="class_1",
               road_status_source="ALSroads",
               road_score=0.9,
               distance_m=20,
           ),
       ),
       created_utc=datetime(2026, 11, 14, tzinfo=UTC),
   )
   assert validate_hazard_report(report).is_valid

Output
------

``HazardReport`` records each component's status, inputs, formula, and units, plus the reliability
weights and available components. It includes caveats that the proxy is decision support, that road
status is source-preserving, and that weights are assumptions.

Named errors
------------

.. list-table::
   :header-rows: 1
   :widths: 32 68

   * - Prefix
     - Meaning
   * - ``HAZARD-TIME``
     - The report time is not timezone-aware.
   * - ``HAZARD-CLEARANCE``
     - Unknown status or an exceeded status with a non-negative margin.
   * - ``HAZARD-FALLIN``
     - Unknown status or a known status without risk.
   * - ``HAZARD-FUEL``
     - Unknown status with neighbours.
   * - ``HAZARD-ACCESS``
     - Unknown status or a known status without a proxy.
   * - ``HAZARD-RELIABILITY``
     - Unknown status, missing weights, weights that do not sum to 1, or a score with no components.
   * - ``HAZARD-CAVEAT``
     - The report has no caveats (warning).

Limits
------

- The clearance is a service-standard comparison, not an electrical or structural calculation.
- The fall-in reach is a scenario, not a tree-failure probability.
- Fuel connectivity is a proxy, not a fire-spread model.
- Road status is source-preserving; an access decision remains with the owner.
- The reliability weights are declared assumptions; they are not calibrated.
