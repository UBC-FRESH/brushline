Release 0.1.0
=============

`RELEASE_NOTES.md` and `notes/reports/p13-known-gaps.md` define the release candidate, the delivered
phases, the known limits, and the use boundaries. `scripts/check_release.py` checks the wheel and sdist
contents and can install the wheel into a temporary venv.

Build locally:

.. code-block:: console

   python -m build --sdist --wheel
   python scripts/check_release.py --install
   brushline demo build --out /tmp/brushline-demo --artifact-root examples/synthetic-corridor

Tagging and publishing are a separate maintainer approval gate. No tag or GitHub release is created by
this page or the release script.
