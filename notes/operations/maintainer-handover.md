# Maintainer and handover guide

## Start here

1. Read `AGENTS.md`, `README.md`, `ROADMAP.md`, and `notes/reports/p12-verification.md`.
2. Run `python scripts/dashboard.py` and confirm `OVERALL: GREEN`.
3. Read `notes/reports/p13-known-gaps.md` before making a release or pilot claim.
4. Review `notes/operations/governance-register.md` and the model card.

## Repository map

- `brushline/model/`: shared contracts.
- `brushline/vegetation/`: growth, treatment, calibration, hazards, validation, model card.
- `brushline/optimization/`: formulation, evaluator, operators, adapter, archive, validation, budget, telemetry.
- `brushline/strategic/`, `brushline/tactical/`, `brushline/exchange/`, `brushline/monitoring/`: planning layers.
- `brushline/web/`, `brushline/demo/`: studio and public portal.
- `notes/design/`, `notes/reference/`, `notes/reports/`: design, evidence, and close-outs.

## Release

1. Update `RELEASE_NOTES.md`, the version, and known gaps.
2. Run `python scripts/dashboard.py`.
3. Build `python -m build --sdist --wheel` and run `python scripts/check_release.py --install`.
4. Get explicit approval, tag `vX.Y.Z`, create the GitHub release, and let `.github/workflows/release.yml` publish to PyPI via OIDC.
5. Verify the PyPI install and docs/demo links from a clean checkout.

## Pilot

- Start with public or synthetic data.
- Record the data boundary, owner, question, success metrics, and caveats.
- Do not put private data or credentials in the public portal.
- Use `notes/reports/p14-pilot-evidence.md` as the evidence template.
- Escalate model, licence, or domain gaps rather than hiding them.

## Cadence

Hold the monthly review in `notes/operations/review-cadence.md`; record decisions and actions even when the action is “no change”.
