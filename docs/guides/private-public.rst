Private and public boundaries
=============================

The private boundary
--------------------

The network-derived prototype lives under ``runtime/private/``. The directory is ignored by git.
It contains source caches, model artifacts, and generated reports for the BC network. It must not be
copied into the public demo, docs, issue trackers, or release assets without approval.

The public boundary
-------------------

The public demo is the synthetic corridor under ``examples/synthetic-corridor``. It is checked in,
read-only, and contains no BC network or MKRF references.

The release audit
-----------------

.. code-block:: bash

   python tools/audit_release.py

The audit checks the repository boundary. A passing audit does not grant release approval and does
not replace a data-sharing agreement.

External gates
--------------

Before public release of network-derived artifacts:

1. complete the data-sharing agreement and permissions;
2. obtain release approval for the artifact set;
3. complete field validation for any claim that requires it;
4. complete asset-owner review of safety, access, outage, and clearance assumptions;
5. re-run the release audit on the release candidate.

Until then, keep the public demo synthetic and treat the network artifacts as private review
material.
