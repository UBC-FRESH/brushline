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

Test layers
-----------

- Unit tests for each model and validator.
- Contract tests for the public interfaces.
- Integration tests for the CLI (``validate``, ``build``, ``simulate``, ``prototype``).
- Catalogue tests for licences, classifications, unknown references, connector scope, approval, and
  the secret scan.
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
