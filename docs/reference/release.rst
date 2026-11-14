Release 0.1.1
=============

`RELEASE_NOTES.md` and `notes/reports/p13-known-gaps.md` define the release candidate, the delivered
phases, the known limits, and the use boundaries. `scripts/check_release.py` checks the wheel and sdist
contents and can install the wheel into a temporary venv.

Build locally:

.. code-block:: console

   python -m build --sdist --wheel
   python scripts/check_release.py --install
   brushline demo build --out /tmp/brushline-demo --artifact-root examples/synthetic-corridor

Tagging and GitHub release creation are a separate maintainer approval gate. The `Release` workflow
publishes a published GitHub release to PyPI and supports a manual TestPyPI run through GitHub OIDC
trusted publishing. No token secret is stored in the repository.
