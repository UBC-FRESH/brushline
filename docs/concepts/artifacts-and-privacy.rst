Artifacts and privacy
=====================

Artifact families
-----------------

Brushline is artifact-first. The main families are:

- **dataset**: the compiled decision units and manifest;
- **plan**: selected actions, costs, assumptions, and provenance;
- **run**: simulation replay and report;
- **tactical/resources/operations/shifts**: the planning stack;
- **Pareto archive and timeline**: multi-objective and operational views;
- **planning brief**: a self-contained Markdown/HTML decision record;
- **policy experiment artifacts**: scenario, chance, two-stage, rolling, weather, forecast, and
  capacity comparisons.

The authoritative contract map is :doc:`../reference/contract-index`. The artifact overview is
:doc:`../reference/artifacts`.

Private and public
------------------

The network-derived prototype is **private**. Its source data and generated artifacts live under
``runtime/private/`` and are ignored by git. The public demo is synthetic and is checked in under
``examples/synthetic-corridor``.

The release boundary is checked by:

.. code-block:: bash

   python tools/audit_release.py

The audit verifies that private paths are untracked, the ignore boundary is intact, tracked text has
no local absolute paths, and the public demo contains no BC network or MKRF references. It does not
grant release approval.

Read :doc:`../guides/private-public` and :doc:`../reference/release-boundary` before sharing any
artifact outside the project.

Planning brief
--------------

The planning brief is generated from the network artifact set and packages the main results,
caveats, and reproduction metadata. It is a lab-review artifact, not a public release of
network-derived data. The endpoint and inline/download behavior are in
:doc:`../howto/planning-brief`.
