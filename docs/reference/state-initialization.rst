Initial vegetation state
========================

The initializer links validated terrain, canopy, field, inventory, and site-index evidence to the
``brushline.state.v1`` contract. It uses field evidence first, a conservative CHM rule second, and an
explicit unknown or partial state when the evidence is missing or out of domain.

It does not run the P4 growth or treatment model, fit a site-index model, or claim that a CHM resolves
shrub from young-tree species. The first release uses the prototype model card
``brushline.low-vegetation.prototype.v0``; P4 calibration is required before operational use.

Evidence
--------

``SegmentEvidence`` carries:

- P3.3 ``CanopySupport`` and its CHM ``LidarProductProvenance``;
- optional P3.2 ``TerrainSupport``;
- field observations with height, cover, density, errors, coverage, confidence, date, source, and
  optional model card;
- optional inventory height, cover, vintage, source, and model card;
- optional reconciled site index and species;
- climate, disturbance, treatment history, and an optional functional-group hint.

A field observation is used when it meets the configured minimum coverage and confidence. Otherwise
the CHM path is used and the report records an open question. A field observation is attached to the
state contract as an observation row.

Rules
-----

The first release uses these explicit prototype thresholds:

- ``grass_herb``: mean height at most 0.5 m and 2 m cover below 20 percent;
- ``shrub``: mean height at most 4 m and 5 m cover at least 20 percent;
- ``young_tree``: mean height at most 10 m, 10 m cover at least 20 percent, and species evidence from the
  tree product or a functional-group hint;
- ``mixed``: 2 m and 10 m cover both at least 20 percent;
- ``mature_edge``: maximum height at least 15 m, 10 m cover at least 20 percent, and a non-empty tree
  product;
- ``partial``: a CHM or canopy candidate that does not match a rule, lacks species evidence for a
  young tree, or has partial/out-of-domain coverage;
- ``unknown``: no usable canopy or field evidence.

A young-tree or mature-edge state without a species hint uses the conifer fallback and raises an open
question. A CHM top remains an observation, not a species determination.

Output
------

``initialize_state`` returns a ``StateInitializationReport`` with:

- the validated ``StateContract``;
- one ``StateDecision`` per segment with source, coverage, class probabilities, model card,
  observation id, reason, inventory vintage, site index, climate, and disturbance;
- open questions for unknown/partial states, fallback species, low-quality field evidence, and the
  prototype model card.

``class_probabilities`` records the selected class and the residual unknown probability. The state
contract carries the summary class, continuous height and cover, uncertainty, treatment history, source,
source version, model card, and observation id.

.. code-block:: python

   from datetime import UTC, datetime
   from brushline.state_init import (
       SegmentEvidence,
       StateInitializationConfig,
       initialize_state,
       validate_state_initialization,
   )

   report = initialize_state(
       [SegmentEvidence(segment_id="s1", canopy=canopy, canopy_source=chm_source)],
       StateInitializationConfig(state_year=2026),
       created_utc=datetime(2026, 11, 14, tzinfo=UTC),
   )
   assert validate_state_initialization(report).is_valid
   contract = report.contract

Named errors
------------

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Prefix
     - Meaning
   * - ``STATE-TIME``
     - The report time is not timezone-aware.
   * - ``STATE-ID``
     - Duplicate decision or contract id.
   * - ``STATE-DECISION``
     - A decision does not match its state, confidence, or group.
   * - ``STATE-MISSING``
     - A required segment has no state.
   * - ``STATE-REASON``
     - A decision has no reason (warning).
   * - ``STATE-OBSERVATION``
     - The contract has no observations (warning).
   * - ``STATE-PARTIAL``, ``STATE-UNCERTAIN``
     - Existing state-contract warnings for partial or low-confidence states.

Limits
------

- The rules are prototype thresholds, not a calibrated P4 model.
- A CHM cannot separate shrub from young-tree species; species evidence or a partial state is required.
- Inventory and site index are context only; they do not determine the low-vegetation class.
- The initializer does not create a treatment plan, a monitoring plan, or an operational
  recommendation.
