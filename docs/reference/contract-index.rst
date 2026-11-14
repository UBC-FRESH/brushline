Contract index
==============

Every Brushline contract has a schema version, a model module, a validator, stable named errors, and a
test suite. This page is the map.

.. list-table::
   :header-rows: 1
   :widths: 22 18 20 40

   * - Contract
     - Schema
     - Validator
     - Checks
   * - Compiled dataset
     - ``brushline.dataset.v1``
     - ``validate_dataset``
     - Manifest, schema, relative paths, tables, columns, dtypes, keys, row counts, checksums, digest
   * - Corridor graph
     - ``brushline.corridor.v1``
     - ``validate_corridor_network``
     - Ids, CRS, references, span order, contiguous sequence, treatment units, access, structures, length
   * - State and treatment
     - ``brushline.state.v1``
     - ``validate_state_contract``
     - State keys, ranges, unknown states, years, references, required segments
   * - Plan
     - ``brushline.plan.v1``
     - ``validate_plan``
     - Action and assumption ids, segments, currencies, parent, assumptions
   * - Run
     - ``brushline.run.v1``
     - ``validate_run_manifest``
     - Artifact ids, availability, hashes, status
   * - Pareto archive
     - ``brushline.pareto.v1``
     - ``validate_pareto_archive``
     - Objectives, scalarizations, member keys, dominance
   * - Operations timeline
     - ``brushline.timeline.v1``
     - ``validate_timeline``
     - Event ids, ordering, segment references, open events
   * - Demo manifest
     - ``brushline.demo.v1``
     - ``validate_demo_manifest``
     - Slug, sources, licences, artifacts, caveats, publication status
   * - Data catalogue and connectors
     - ``brushline.catalogue.v1``
     - ``validate_catalogue``
     - Sources, licences, classifications, coverage, connectors, auth references, scope, outputs, audit, approval, secret scan
   * - Fetch plan
     - ``brushline.fetch-plan.v1``
     - ``validate_fetch_plan``
     - Items, estimates, licences, access, materialization pointers, bulk approvals, catalogue drift
   * - Materialization
     - ``brushline.materialization.v1``
     - ``validate_materialization``
     - Checksums, sizes, paths, containment, licences, pointers, retrieval time, missing reasons
   * - Coverage and gaps
     - ``brushline.coverage.v1``, ``brushline.gap-report.v1``
     - ``validate_coverage``, ``validate_gap_report``
     - Six coverage states, evidence, reasons, next action, and stop/continue
   * - Agent capabilities
     - ``brushline.capabilities.v1``, ``brushline.capability-outcome.v1``
     - ``validate_capability_registry``, ``validate_capability_outcome``
     - Six capabilities, prompt ids, tool allowlists, validators, retry budgets, private markers, authority fields, sanitized outcomes
   * - Model builder session
     - ``brushline.model-builder-session.v1``, ``brushline.model-builder-review.v1``,
       ``brushline.handoff.v1``
     - ``BuilderSession``, ``ReviewSummary``, ``HandoffRecord``
     - AOI, plan preview, availability, approvals, stages, review, handoff, and dry-run artifacts
   * - FEMIC LiDAR bundle
     - ``femic.lidar.product.v1``, ``femic.lidar.bundle.v1``, ``femic.lidar.selection.v1``
     - ``validate_lidar_bundle``
     - Producer pin, selection digest, product checksums, CRS, datum, resolution, licence, paths, and provenance
   * - Terrain support
     - ``brushline.terrain-support.v1``
     - ``validate_terrain_support``
     - Raster CRS, resolution, datum, buffer, statistic, valid pixels, coverage, slope, aspect, terrain class, and access proxy
   * - Canopy support
     - ``brushline.canopy-support.v1``
     - ``validate_canopy_support``
     - CHM CRS, datum, buffer, height statistics, cover thresholds, structure, optional tree, VRI comparison, and applicability
   * - Initial vegetation state
     - ``brushline.state-initialization.v1``
     - ``validate_state_initialization``
     - Field/CHM rules, evidence coverage, class probabilities, audit decisions, model card, and state-contract validity
   * - LiDAR coverage and applicability
     - ``brushline.lidar-coverage.v1``
     - ``validate_lidar_coverage``
     - Acquisition recency, usable coverage, valid pixels, domain, six coverage states, next action, and stop/continue

Error prefixes
--------------

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Prefix
     - Contract
   * - ``DATASET-*``
     - Compiled dataset
   * - ``CORRIDOR-*``
     - Corridor graph
   * - ``STATE-*``
     - State and treatment
   * - ``PLAN-*``
     - Plan
   * - ``RUN-*``
     - Run
   * - ``PARETO-*``
     - Pareto archive
   * - ``TIMELINE-*``
     - Operations timeline
   * - ``DEMO-*``
     - Demo manifest
   * - ``CATALOGUE-*``
     - Data catalogue and connectors
   * - ``FETCH-*``
     - Fetch plan
   * - ``MATERIALIZATION-*``
     - Materialization manifest
   * - ``COVERAGE-*``, ``GAP-*``
     - Coverage and gap report
   * - ``CAPABILITIES-*``, ``AGENT-*``
     - Agent capabilities and sanitized outcome record
   * - ``LIDAR-*``
     - FEMIC LiDAR bundle
   * - ``TERRAIN-*``
     - Terrain support
   * - ``CANOPY-*``
     - Canopy support
   * - ``LIDAR-COVERAGE-*``
     - LiDAR coverage and applicability

Test layers
-----------

- Unit tests for each model and validator.
- Contract tests for the public interfaces.
- Integration tests for the CLI (``validate``, ``build``, ``simulate``, ``prototype``).
- Catalogue tests for licences, classifications, unknown references, connector scope, approval, and
  the secret scan.
- Fetch tests for estimates, bulk approval, catalogue drift, materialization checksums and containment,
  the six coverage states, and the gap decision.
- Capability tests for the six prompts, tool allowlists, validator failure, retry budget, fake provider,
  private markers, authoritative fields, and sanitized records.
- Model-builder tests for the static shell, plan preview, approvals, blocked builds, dry-run artifacts,
  progress SSE, review, handoff, and custom AOI gaps.
- LiDAR bundle tests for the producer pin, selection digest, checksums, CRS, datum, licence, path
  containment, product kinds, derived flags, and provenance.
- Terrain tests for buffered aggregation, coverage states, every statistic, slope and access classes,
  RASTER CRS/datum/resolution checks, and provenance.
- Canopy tests for height and cover statistics, optional structure/tree products, VRI comparison,
  partial/missing/out-of-domain states, and applicability.
- State-initialization tests for field-first selection, every prototype class, unknown/partial states,
  species fallback, audit decisions, probabilities, and contract validity.
- LiDAR coverage tests for observed, stale, partial, missing, out-of-domain, excluded, optional gaps,
  domain reasons, next actions, and stop/continue.
- Property tests for duplicate detection, dominance, corridor length conservation, and range checks.
- The self-check that the planning surfaces pass the workflow validator.

The committed synthetic fixture is the shared contract example. A fresh build must match its artifact
digests and content digest; the fixture tests enforce that.

Adding a contract
-----------------

1. Add the schema version and the models.
2. Add the validator and named error prefixes.
3. Add a valid example and at least one failing case per invariant.
4. Add the JSON round-trip.
5. Add the reference page and the API page.
6. Add the contract to this index.
7. Run ``python scripts/dashboard.py``.
