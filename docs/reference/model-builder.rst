Model builder
=============

The model builder is the P2 map-to-instance prototype. It points at an AOI, shows public and missing
sources, previews the fetch plan, records approvals, runs a dry run, streams the stage progress, and
shows the review and handoff.

It is not the P10 planning studio, the P11 public demo portal, or a production authentication system.
It is a synthetic-data prototype over the P2 catalogue, fetch plan, coverage, gap, and capability
contracts.

Run the prototype
-----------------

.. code-block:: bash

   python -m pip install -e ".[web]"
   uvicorn brushline.web.model_builder:app --reload

Open ``http://127.0.0.1:8000``. The service loads
``notes/reference/data-catalogue.v1.json`` and the synthetic corridor fixture by default. Tests inject
a store with a temporary runtime root so they never write beside the repository artifacts.

Flow
----

1. **AOI.** Select the synthetic corridor or drag a rectangle on the map. A drawn AOI is honest about
   the prototype gap: every source is missing because there is no spatial coverage query.
2. **Availability.** The source list shows the provider, licence, access status, and coverage state.
   Private connectors are listed separately.
3. **Plan.** The plan preview is built before any network call. It shows the source, query, licence,
   estimate, access, and materialization pointer.
4. **Approvals.** Public sources, bulk scope, and private connectors have separate controls. A bulk
   plan without a bulk approval fails the plan validator. A private connector without an explicit
   approval stays blocked.
5. **Build.** The dry run validates the AOI, plan, corridor, and review, and skips materialization,
   compilation, state seeding, scenario validation, and demo export. It writes the plan and review
   metadata, not a dataset payload.
6. **Progress.** The stage stream names the stage, the validator, the status, and the evidence.
7. **Review.** Segment count, initial state distribution, model cards, coverage counts, gaps, open
   questions, licences, and provenance.
8. **Handoff.** The prototype writes a handoff record and creates a linked instance directory. It does
   not publish or promote the instance.

A synthetic local build is also available: it compiles the synthetic fixture, seeds the fixture state,
validates the template scenario, and copies the demo manifest. It still makes no network call. A custom
AOI is blocked after the validation stage because the prototype has no real segmenter or provider
pipeline.

API
---

.. list-table::
   :header-rows: 1
   :widths: 42 58

   * - Route
     - Purpose
   * - ``GET /``
     - Static model-builder shell.
   * - ``GET /static/model-builder.js``, ``.css``
     - Browser assets.
   * - ``GET /api/model-builder/aois``
     - Selectable AOIs, asset types, and standards.
   * - ``GET /api/model-builder/catalogue``
     - Agent-safe source and connector metadata.
   * - ``POST /api/model-builder/sessions``
     - Create a plan-only session.
   * - ``GET /api/model-builder/sessions/{id}``
     - Read a session.
   * - ``POST /api/model-builder/sessions/{id}/approve``
     - Record public, bulk, and private-connector approvals.
   * - ``POST /api/model-builder/sessions/{id}/build``
     - Run the dry run or the synthetic local build.
   * - ``GET /api/model-builder/sessions/{id}/progress``
     - Server-sent stage events.
   * - ``GET /api/model-builder/sessions/{id}/review``
     - Review summary.
   * - ``POST /api/model-builder/sessions/{id}/handoff``
     - Write the linked instance record.

Session contract
----------------

``brushline.model-builder-session.v1`` carries the AOI, asset type, management standard, horizon,
currency, selected sources and connectors, approvals, plan, availability, coverage, gap report, status,
stages, review, and handoff.

The status is ``planned``, ``approved``, ``blocked``, or ``complete``. A blocked session keeps the failed
stage, the validator, and the evidence so the reviewer can see why it stopped.

Dry-run outputs
---------------

A dry run writes, under the runtime root:

- ``fetch_plan.json``: the plan metadata;
- ``review.json``: the review metadata.

It does not write a dataset, a state artifact, a demo, or a private row. The handoff writes
``handoff.json`` and creates an empty linked ``instance`` directory. The synthetic local build adds the
compiled dataset, state, scenario validation report, and demo copy.

Safety and limits
-----------------

- The catalogue endpoint uses the P2 agent-safe view; it never returns an authentication reference.
- A private connector is selected only through the explicit approval endpoint.
- The dry-run default is ``True``.
- The browser surface has no external map library, CDN, telemetry, or live model provider.
- There is no production authentication. Run it locally only.
- The synthetic coverage is fixture evidence, not a real spatial query.
- The review requires a gap panel and open questions.
- A custom AOI remains blocked rather than borrowing synthetic coverage.

Tests
-----

``tests/test_model_builder.py`` covers the static shell, catalogue safety, AOI list, plan preview,
public/bulk/private approvals, blocked builds, dry-run outputs, progress streaming, review, handoff,
custom AOI gaps, the synthetic local build, missing routes, and malformed AOIs. It uses FastAPI's
in-process test client; it does not start a network server.
