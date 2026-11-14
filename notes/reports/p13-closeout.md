# Phase close-out report: P13 Release and deploy

Parent issue: #121
Pull request: #127 (merged `6021078`)
Release: v0.1.0, https://github.com/UBC-FRESH/brushline/releases/tag/v0.1.0
PyPI: https://pypi.org/project/brushline/0.1.0/
Docs: https://ubc-fresh.github.io/brushline/
Demo: https://ubc-fresh.github.io/brushline/demo/

## Verified

- Annotated tag `v0.1.0` and published GitHub release.
- Release workflow 43626683914: build, twine check, PyPI trusted publishing succeeded; TestPyPI skipped on release event.
- Clean checkout at `v0.1.0`: sdist/wheel build and wheel install succeeded.
- PyPI install in a fresh venv: `brushline 0.1.0`; CLI version works.
- Docs and static demo return HTTP 200; demo has 7 pages.
- P13.1–P13.3 and P13.5 evidence is complete.
- Known minor issue: `brushline status` still prints the original Phase 1 prototype sentence. It does not affect planning; queue a 0.1.1 patch.

## Limits

No field calibration, live FEMIC/FHOPS/road feed, 10,000-segment scale proof, production authentication, or safety claim. See `notes/reports/p13-known-gaps.md`.

## Recommendation

0.1.0 is published as an internal prototype release. Next: P14 operations, and a 0.1.1 patch for the stale status text.
