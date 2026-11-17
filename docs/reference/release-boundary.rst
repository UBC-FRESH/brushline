Release boundary audit
======================

``tools/audit_release.py`` is a read-only check of the private/public boundary. It does **not**
grant release approval and does not verify a data-sharing agreement.

Checks
------

- No tracked paths under ``runtime/``, ``data/private/``, ``local/``, ``tmp/``, or ``outputs/``.
- ``runtime/`` and ``data/private/`` remain in ``.gitignore``.
- No tracked text file contains local absolute paths such as a workstation or shared-storage root.
- The public synthetic demo contains no BC network or MKRF references.

Run it with:

.. code-block:: text

   python tools/audit_release.py

The JSON result has ``status: pass`` only when every check passes. A passing audit means the
repository boundary is clean; it does not approve release of network-derived artifacts.

External gates
--------------

The following remain external and must be completed before public release:

- data-sharing agreement and permissions for the BC network-derived artifacts;
- release approval for private model artifacts;
- field validation, which has not been performed;
- asset-owner review of safety, access, outage, and clearance assumptions.

The public demo remains synthetic until those gates are cleared.
