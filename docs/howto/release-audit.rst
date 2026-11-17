Release audit
=============

Run the read-only boundary audit:

.. code-block:: bash

   python tools/audit_release.py

It checks:

- private runtime paths are untracked;
- ``runtime/`` and ``data/private/`` remain ignored;
- tracked text has no local absolute paths;
- the public synthetic demo has no BC network or MKRF references.

A passing audit is necessary but not sufficient for release. The following remain external:

- data-sharing agreement and permissions for BC network-derived artifacts;
- release approval for private model artifacts;
- field validation;
- asset-owner review of safety, access, outage, and clearance assumptions.

Read :doc:`../guides/private-public` and :doc:`../reference/release-boundary` before publishing.
