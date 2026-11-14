Planning studio API
===================

The P10 service lives in ``brushline.web.studio``. It is optional and requires the ``web`` extra.
The public surface is documented in :doc:`../reference/studio`; Sphinx does not import the FastAPI app.

Endpoints
---------

- ``GET /api/studio/summary``
- ``GET /api/studio/plan/{plan_id}``
- ``GET /api/studio/pareto``
- ``GET /api/studio/timeline``
- ``GET /api/studio/blocks``
- ``GET /api/studio/scene/{block_id}?variant=pre|post``
- ``GET /api/studio/search/stream``
- ``GET /api/studio/skins``
