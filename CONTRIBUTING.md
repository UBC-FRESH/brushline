# Contributing to Brushline

Read `AGENTS.md` and `ROADMAP.md` before non-trivial work. The domain rules at the end of
`AGENTS.md` are part of the design, not style advice.

## Setup

```bash
python -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements-dev.txt
python -m pip install -e .
pre-commit install
```

The pre-commit hooks call `python` from `PATH`, so commit from a shell where the environment is
active. A commit from a shell without it runs the hooks in the system Python, which lacks the dev
tools, and the hooks fail.

Optional extras are installed only when a task needs them:

```bash
python -m pip install -e ".[opt]"   # fresh-solutions metaheuristic engine
python -m pip install -e ".[web]"   # FastAPI, MapLibre assets, vector tiles
```

## The green dashboard

Run `python scripts/dashboard.py` before each commit. It must be green. Any change from green is
investigated and fixed immediately, with no exceptions. The pre-commit hooks run the same checks on
each commit.

## Workflow

- Work on the branch for the active phase, named `feature/p<n>-<slug>`.
- Start each commit message with the task ID, for example `P0.1 adapt the contract`.
- Write every function with full type annotations and a numpy-style docstring, and add unit tests for
  it in the same change set.
- Keep `ROADMAP.md`, `CHANGE_LOG.md`, `notes/`, and the matching GitHub issues in step with the work.
- Open pull requests with `Part of #<parent issue>` in the body. CI must be green. A merge happens only
  as part of an approved phase close-out.

## Domain guardrails

- A segment is the decision unit. Do not compile at a span or treatment-unit level.
- A vegetation state carries its uncertainty. Do not reduce a plan to a single point estimate without
  saying so.
- A treatment is a transition. Do not model it as a reset to zero vegetation.
- Monitoring is a decision. Do not hard-code a fixed flight calendar.
- Every reported incumbent must replay exactly from its evidence record.
- The studio reads artifacts. Do not put model state in the web service.
- Keep third-party code and documentation out of the repository. Adapters are interfaces, not copies.

## Control characters and public safety

- Write issue and pull request bodies to files, and post them with `--body-file`. Do not build them from
  escaped strings.
- Use LF line endings.
- Run `python scripts/check_workflow.py` before you push. To check one body file, run
  `python scripts/check_workflow.py --files path/to/body.md`.
- Keep private data, credentials, raw transcripts, and machine-specific paths out of the repository.
- Do not commit real asset, contractor, or personal data. Use synthetic fixtures or sanitized extracts
  with a recorded provenance note.
