Data catalogue and connectors
=============================

The catalogue is a metadata contract. It says what data exists, which licence governs it, where it
covers, and how it may be read. It does not contain a row, a credential, or a promise that access is
available.

The committed example is ``notes/reference/data-catalogue.v1.json``. It is a
``brushline.catalogue.v1`` document with two collections: public or synthetic sources and private
connectors.

Public sources
--------------

.. list-table::
   :header-rows: 1
   :widths: 16 28 12 14 30

   * - Id
     - Dataset
     - Licence
     - Status
     - Coverage note
   * - ``lidarbc``
     - LidarBC point clouds, terrain, canopy, and trees
     - OGL-BC
     - available
     - British Columbia; tile availability and year vary by area
   * - ``vri``
     - Vegetation Resources Inventory
     - OGL-BC
     - available
     - Forested land in British Columbia
   * - ``vdyp``
     - VDYP7 yield projections
     - OGL-BC
     - request
     - Applicability domain of the yield model
   * - ``sibec``
     - SIBEC site-index means
     - OGL-BC
     - request
     - BEC units with SIBEC sampling coverage
   * - ``dra``
     - Digital Road Atlas
     - OGL-BC
     - available
     - Public roads; private roads may be absent
   * - ``ften``
     - Forest tenure polygons
     - OGL-BC
     - available
     - Administrative tenures, not access permission
   * - ``ntems``
     - NTEMS land cover and change
     - OGL-Canada
     - available
     - Canada at 30 m; thematic accuracy varies
   * - ``climate``
     - ClimateNA and SilvR21
     - ClimateNA academic terms
     - request
     - Point or gridded climate products
   * - ``bec``
     - Biogeoclimatic classification
     - OGL-BC
     - available
     - Map-unit boundaries, not site boundaries
   * - ``ownership``
     - Crown land ownership
     - OGL-BC
     - available
     - Parcel-level status may be generalized
   * - ``protected-areas``
     - Parks and protected areas
     - OGL-BC
     - available
     - Provincial protected areas
   * - ``boundaries``
     - TSA, FMU, and regional boundaries
     - OGL-BC
     - available
     - Administrative boundaries
   * - ``freshwater-atlas``
     - Streams, lakes, and wetlands
     - OGL-BC
     - available
     - Small or ephemeral channels may be absent

A source record has an id, name, provider, dataset, query, vintage, CRS, licence, classification,
coverage, access method, access status, optional URL, and optional description. The validator requires
a usable licence, a coverage note, a CRS, a query, and a vintage. A public source must be classified
``public`` or ``synthetic``.

The access status is part of the honesty of the catalogue:

- ``available``: a public access path is known;
- ``request``: access needs a request or a licence review;
- ``unknown``: not verified;
- ``unavailable``: known not to be reachable.

``request`` and ``unknown`` are not failures. They are knowledge states that the fetch plan and the
coverage report must carry forward. No download happens in P2.4.

Private connectors
------------------

.. list-table::
   :header-rows: 1
   :widths: 18 24 12 16 30

   * - Id
     - Owner
     - Class
     - Auth method
     - Allowed outputs
   * - ``asset-registry``
     - Infrastructure owner
     - private
     - environment
     - derived, aggregate
   * - ``treatment-history``
     - Infrastructure owner
     - private
     - environment
     - derived, aggregate
   * - ``inspections``
     - Infrastructure owner
     - private
     - secret store
     - derived, aggregate
   * - ``costs``
     - Infrastructure owner
     - restricted
     - managed identity
     - aggregate
   * - ``contracts``
     - Infrastructure owner
     - private
     - environment
     - derived, aggregate
   * - ``access-restrictions``
     - Infrastructure owner
     - private
     - environment
     - derived, aggregate

A connector record has an id, name, owner, description, classification, optional linked source ids,
authentication method, authentication reference, read scope, allowed outputs, audit rule, test
connection, and optional owner approval.

Authentication is a reference, never a value. The accepted forms are:

- ``env:NAME`` for an environment variable;
- ``secret_store:path`` for a secret-store item;
- ``managed_identity:name`` for a managed identity.

The validator rejects a raw URL with a password, a missing reference, a reference that does not match
its method, and an unknown method. A text scanner also rejects secret-shaped values in any field,
including a description or a sample metadata value.

Read scope names the tables, optional per-table columns, required row filters, and a maximum row
count. The validator rejects an empty table list, columns for a table that is not in the list, a
non-positive row limit, an empty output list, an unknown output, an empty audit location, and a
missing test reference.

Allowed outputs are:

- ``raw``: rows at the connector boundary, inside the owner's tenancy;
- ``derived``: a derived artifact that can be reviewed;
- ``aggregate``: a summary that does not expose a row.

A connector with a single allowed output of ``aggregate`` cannot produce a raw extract. The rule is
on the record, not in a prompt.

Approval gate
-------------

The agent sees the public catalogue and safe connector metadata. A connector is readable only when
its ``approval`` record exists. Approval needs an approver, a timezone-aware approval time, and a
data-sharing record.

.. code-block:: python

   from brushline.integrations.catalogue import (
       agent_can_read,
       agent_metadata,
       approved_connector_ids,
       run_connection_test,
   )

   view = agent_metadata(catalogue)
   assert "authentication_reference" not in str(view)
   connector = catalogue.connectors[0]
   assert not agent_can_read(connector)
   result = run_connection_test(catalogue, connector.id)

A blocked test returns ``blocked`` and no sample metadata. An approved environment connector checks
whether its variable is present without returning the value. A secret-store or managed-identity
connector needs an owner-side probe; this process returns ``not_configured`` rather than pretending
it can reach the owner's secret system.

The public demo uses public or synthetic data only. A private deployment uses the owner's tenancy and
access controls. A derived artifact is reviewed before it leaves that tenancy.

Validator
---------

.. code-block:: python

   from pathlib import Path
   from brushline.integrations.catalogue import DataCatalogue, validate_catalogue

   catalogue = DataCatalogue.model_validate_json(
       Path("notes/reference/data-catalogue.v1.json").read_text()
   )
   report = validate_catalogue(catalogue)
   if not report.is_valid:
       raise SystemExit("\n".join(report.errors))

The report uses the shared :class:`brushline.model.validation.ContractValidation` shape. Named errors:

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Prefix
     - Meaning
   * - ``CATALOGUE-ID``
     - Duplicate source or connector id.
   * - ``CATALOGUE-LICENCE``
     - Missing or unusable public licence.
   * - ``CATALOGUE-CLASSIFICATION``
     - A public source is private, or a private connector is public.
   * - ``CATALOGUE-COVERAGE``, ``CATALOGUE-CRS``, ``CATALOGUE-QUERY``, ``CATALOGUE-VINTAGE``
     - Missing source metadata.
   * - ``CATALOGUE-ACCESS``
     - Unknown access method or status.
   * - ``CATALOGUE-SOURCE``
     - A connector links an unknown source.
   * - ``CATALOGUE-AUTH``
     - Missing, raw, mismatched, or unknown authentication reference.
   * - ``CATALOGUE-SCOPE``, ``CATALOGUE-OUTPUT``, ``CATALOGUE-AUDIT``, ``CATALOGUE-TEST``
     - Connector scope, output, audit, or test-connection problems.
   * - ``CATALOGUE-APPROVAL``
     - Approval without an approver, record, or timezone-aware time.
   * - ``CATALOGUE-SECRET``
     - A secret-shaped value was found.
   * - ``CATALOGUE-TIME``
     - The catalogue creation time is not timezone-aware.

Unknown references
------------------

``resolve_source`` and ``resolve_connector`` raise
:class:`brushline.integrations.catalogue.UnknownCatalogueReferenceError` for an unregistered id. A
connector cannot call a source or a table that is not in its declared scope.

What this page promises
-----------------------

- Every committed source has a licence, a classification, and a coverage note.
- Every connector has a non-secret authentication reference, a read scope, and an allowed-output rule.
- The agent sees metadata only until an owner approval exists.
- The catalogue does not promise that a source is reachable; ``request`` and ``unknown`` are recorded.
- Downloading, ordering, materialization, and coverage reports are P2.5, not this page.
