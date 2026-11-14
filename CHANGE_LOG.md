# Change Log

Newest entries last. Each milestone gets a dated entry that matches the roadmap status and the GitHub issue comments.

## 2026-11-14

- Created Brushline from the UBC-FRESH dev workflow seed. The agent contract, roadmap, docs skeleton, and validator came from the seed. Every phase is planned, and no parent issues exist yet.
- P0.1: adapted the operating contract and repository identity. `AGENTS.md` now carries the domain rules for segments, uncertain vegetation states, treatment transitions, monitoring decisions, the shared plan artifact, the `fresh-solutions` adapter, exact replay, the artifact-reading studio, adapters, safety, and provenance. Added `README.md`, `CONTRIBUTING.md`, `LICENSE` (Apache-2.0), `CODE_OF_CONDUCT.md`, and `CITATION.cff`, and set the repository description and topics. Dashboard result: `python scripts/dashboard.py` reports `OVERALL: GREEN` on lint, format, types, tests, validator, and docs.
- P0.2: made Brushline an installable package with a tested command line. Added `brushline/__init__.py`, `brushline/cli.py` with `--version` and `status`, the `[project]` metadata and `brushline` console script, the runtime dependencies, the `geo`, `opt`, and `web` extras, the API page, and `tests/test_brushline_cli.py`. CI and the docs build install the package in editable mode. `python -m pip install -e .`, `brushline --version`, and `brushline --help` work. Dashboard result: `python scripts/dashboard.py` reports `OVERALL: GREEN`; test coverage is 100 percent.
