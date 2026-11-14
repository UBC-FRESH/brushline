# P13 release preparation evidence

Version: 0.1.0
Date: 2026-11-14

## Prepared

- `RELEASE_NOTES.md` and `notes/reports/p13-known-gaps.md`.
- Wheel `dist/brushline-0.1.0-py3-none-any.whl` and sdist `dist/brushline-0.1.0.tar.gz`.
- `python scripts/check_release.py --install`: release artifacts ok; wheel installed in a temporary venv and `brushline --version` returned `brushline 0.1.0`.
- Clean checkout: `git archive HEAD` extracted to `/tmp/brushline-clean`; `python -m build --sdist --wheel` and `python scripts/check_release.py --install` succeeded.
- Static demo: `brushline demo build --out /tmp/brushline-demo`; portal validation passed with 7 pages.
- Docs: local Sphinx build with warnings-as-errors passes.

## PyPI trusted publishing

`.github/workflows/release.yml` is present for the pending PyPI/TestPyPI trusted publishers:
project `brushline`, repository `UBC-FRESH/brushline`, workflow `release.yml`, environments `pypi` and
`testpypi`. It builds once, runs `twine check`, publishes to TestPyPI on manual dispatch, and publishes
to PyPI on a published GitHub release.

## Not performed

- No annotated tag or GitHub release. P13.4 requires explicit maintainer approval.
- No published-release verification from GitHub. P13.5 remains open until P13.4.
- No visibility, Pages, or branch-protection change.

## Recommendation

Approve the release candidate and authorize the tag/release. Until then the release remains local-only.
