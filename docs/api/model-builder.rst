Model builder API
=================

The P2 model-builder API is intentionally small. The runnable app is
``brushline.web.model_builder:app``; tests inject a store with a temporary runtime root.

Public surface
--------------

- ``ModelBuilderStore``: in-memory sessions over a catalogue, fixture, and runtime root.
- ``create_app(store=None)``: build the FastAPI application. The default app is ``app``.
- ``BuilderSession``, ``AoiOption``, ``SourceAvailability``, ``BuildStage``, ``ApprovalRequest``,
  ``BuildRequest``, ``ReviewSummary``, and ``HandoffRecord``: the session contracts.
- ``BuilderSession`` methods: ``create_session``, ``get``, ``approve``, ``build``, ``review``, and
  ``handoff``.

The module is optional. Install the web extra before importing it:

.. code-block:: bash

   python -m pip install -e ".[web]"

The route contract, the dry-run outputs, and the stated limits are on
:doc:`../reference/model-builder`. The API page is prose-only so the documentation build does not
import the optional FastAPI dependency. The module docstrings remain the source of truth for the
Python signatures.
