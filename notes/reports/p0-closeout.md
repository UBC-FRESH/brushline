# Phase close-out report: P0 Bootstrap and scope

Phase: P0 Bootstrap and scope
Parent issue: #1
Pull request: #14, `feature/p0-bootstrap` into `main`
Evidence head: `da9a215`, the head that the gates and the CI runs below cover
Report commit: the commit that adds this report. Its CI run is posted on the pull request.
Date: 2026-11-14
Status: queued for approval. Not merged.

## Recommendation

Approve these actions. The agent carries them out in this order, and reads back each result.

1. Squash-merge pull request #14, and delete the branch `feature/p0-bootstrap`.
2. Close parent issue #1 with a closeout comment that cites the merge commit.
3. Launch P1 (Contracts and prototype): create its branch, set the phase statuses in `ROADMAP.md`,
   create its child issues as sub-issues, and start P1.1.

Settings changes, each with its exact command. Each one runs only after its own approval.

- Change the repository visibility from private to public:
  `gh repo edit UBC-FRESH/brushline --visibility public --accept-visibility-change-consequences`
- Enable GitHub Pages for the docs workflow:
  `gh api repos/UBC-FRESH/brushline/pages -X POST -f build_type=workflow`
- Enable branch protection on `main`: no command is proposed until the maintainer chooses the rule set.

## 1. Objectives and acceptance

| Criterion | Evidence | Status |
| --- | --- | --- |
| The repository identifies its licence, citation, conduct policy, and contribution path | `65c8c87`; `LICENSE`, `CITATION.cff`, `CODE_OF_CONDUCT.md`, `CONTRIBUTING.md` | met |
| `python -m pip install -e .` installs a package whose `brushline --version` and `brushline --help` work | `e1635fe`; `pip install -e .`, `brushline --version` -> `brushline 0.1.0`, `--help` -> `status` | met |
| The scope states the problem, users, scope, out-of-scope items, and success criteria | `f1c5894`; `notes/design/brushline-scope.md` | met |
| The architecture covers the domain, dynamics, planning stack, optimization, monitoring, exchange, instance builder, studio, artifacts, integrations, and open questions | `41a020a`; `notes/design/brushline-architecture.md`; ADRs 0001-0012 | met |
| The phase map is complete, ordered, and testable | `3c1dac5`; `ROADMAP.md`; validator green | met |
| The planning studio design covers 2D, 3D, skins, live search, Pareto explorer, and animation | `fab7ffe`; `notes/design/brushline-ui.md` | met |
| The optimization design covers the NP-hard formulation, adapter, archive, and exact validation | `1cf4687`; `notes/design/brushline-optimization.md` | met |
| The open LiDAR design covers the FEMIC producer boundary, contracts, coverage, site index, roads, and 3D | `5a8be16`; `notes/design/brushline-lidar-and-open-data.md` | met |
| The instance-builder design extends FEMIC and does not create a second package | `a9b1f70`; `notes/design/brushline-instance-builder.md`; ADR 0008 and 0012 | met |
| The demo-portal design is public-data-only, read-only, and includes the pilot funnel | `4a9fd45`; `notes/design/brushline-demo-portal.md`; ADR 0010 | met |
| The literature review assesses the obvious open models and states the from-scratch rationale | `167d06b`; `notes/reference/shrub-young-tree-growth-models.md`; `notes/reference/codex-library-search-prompt.md` | met with the stated limits |
| `python scripts/dashboard.py` reports `OVERALL: GREEN` | `43a7043`; see section 3 | met |
| The close-out report is queued for approval | This report; pull request #14 | met |

### 1.1 Stated limits

- The literature review is not a systematic review. Some papers are abstract-only or pending the Codex
  library package. No candidate was run on Brushline data.
- The LiDAR coverage figures and model-card limits are cited from the IRSS notes and the sibling
  repositories; they were not re-measured here.
- The future phase acceptance criteria are design statements, not tested behaviour.
- Phase 0 does not implement the vegetation model, data ingestion, optimization, or UI.

## 2. Workflow compliance

- Parent issue before the branch: #1 was created and the phase activated on `feature/p0-bootstrap` before
  P0.1. The seed commit `6e39d87` is the activation baseline.
- Branch from `main`: `feature/p0-bootstrap` was created from `main` at `6e39d87`.
- Commit messages that start with task IDs: every task commit starts with `P0.<n>`; the activation commit
  starts with `P0`; the seed commit is the seed baseline.
- Gates for each commit: section 3.
- Roadmap and changelog in step: `3c1dac5` (roadmap), `43a7043` (changelog and design index), and the
  task commits that updated the changelog.
- Child issues closed with closeout evidence: #2, #3, #4, #5, #6, #12, #13. #7, #8, #9, #10, and #11
  are closed with this report.
- Approval gates: no tag, release, visibility change, Pages deployment, branch protection change,
  private data access, or repository deletion was performed. The repository was created private with
  the maintainer's explicit request.

### 2.1 Deviation: expanded Phase 0

The seed's Phase 0 had two tasks. During the phase, the maintainer directed additional first-class
surfaces: the interactive planning studio, the `fresh-solutions` optimization framework, open LiDAR and
FEMIC reuse, the FEMIC-extended instance builder, the public demo portal, and the shrub/young-tree
literature review. Phase 0 was expanded from six tasks to twelve, and P0.6 was deferred until the new
design notes were complete. The expansion is recorded in the parent issue and in this report.

## 3. Gate evidence

| Commit | Task | Gates | Result |
| --- | --- | --- | --- |
| `6e39d87` | Seed baseline | CI on `main` | success (run 43538876711); the Docs run 43538877064 failed because the seed docs workflow did not install the package, which P0.2 fixed |
| `65c8c87` | P0.1 | dashboard | green |
| `e1635fe` | P0.2 | dashboard, CLI, pytest | green; 142 passed, 100% coverage |
| `f1c5894` | P0.3 | dashboard | green |
| `41a020a` | P0.4 | dashboard | green |
| `3c1dac5` | P0.5 | validator, dashboard | green |
| `fab7ffe` | P0.7 | dashboard | green |
| `1cf4687` | P0.8 | dashboard | green |
| `5a8be16` | P0.9 | dashboard | green |
| `a9b1f70` | P0.10 | dashboard | green |
| `4a9fd45` | P0.11 | dashboard | green |
| `167d06b` | P0.12 | dashboard | green |
| `43a7043` | P0.6 design index and changelog | dashboard | green on lint, format, types, tests, validator, docs |
| `da9a215` | P0.6 terminal-independent CLI help test | dashboard, pytest | green; 142 passed, 100% coverage |

## 4. CI evidence

| Run ID | Head commit | Conclusion | Notes |
| --- | --- | --- | --- |
| 43538876711 | `6e39d87` | success | Seed CI on `main` |
| 43538877064 | `6e39d87` | failure | Seed Docs workflow lacked a package install; fixed in P0.2 |
| 43542525197 | `43a7043` | failure | The CLI help test assumed a wide terminal; Typer's rich table wrapped differently in CI. Fixed in `da9a215` by asserting on the option name, not the `--` prefix. |
| pending | `da9a215` | in progress | The CI run on the fix; its result is posted on pull request #14 |

The report commit will add its own CI run to the pull request. The phase is not complete until the CI run
on the report commit is green.

## 5. Deviations

| Deviation | Cause | Remedy |
| --- | --- | --- |
| Phase 0 expanded from two seed tasks to twelve | Maintainer added the studio, optimization, LiDAR, instance-builder, demo-portal, and literature-review requirements mid-phase | Recorded in the parent issue, roadmap, changelog, and this report; the new tasks are reviewed in the same pull request |
| The seed Docs workflow failed on `main` | The seed docs workflow installed only Sphinx, not the package | P0.2 adds `python -m pip install -e .` to `docs.yml` |
| The first phase CI run failed | The CLI help test assumed a wide terminal; the CI terminal wrapped the rich help table | `da9a215` makes the assertion terminal-independent; the full dashboard is green locally |
| The repository remains private | The seed guide says public only after review | A visibility change is named in section 6 and waits for approval |
| The literature package is not yet retrieved | Paywalled papers need the maintainer's library access | `notes/reference/codex-library-search-prompt.md` is ready for the Codex desktop agent |

## 6. Next phase

P1 (Contracts and prototype) starts after approval. Its goal is to fix the data, plan, run, archive,
timeline, and demo contracts and build the smallest end-to-end prototype on synthetic data.

Recommended P1 child issues:

- P1.1 Compiled corridor dataset and manifest contract
- P1.2 Corridor, segment, span, and treatment-unit contract
- P1.3 Vegetation state, treatment, and observation contract
- P1.4 Plan, run, Pareto archive, operations timeline, and demo manifest contracts
- P1.5 Synthetic corridor fixture
- P1.6 End-to-end prototype
- P1.7 Contract validation and property tests

Recommended defaults:

- The synthetic fixture has two corridors, mixed functional groups, one access gap, one monitoring gap,
  and one tiny instance with a known optimum.
- The first prototype uses a deterministic growth curve and a deterministic treatment transition; the
  calibrated model is P4.
- The dataset is Parquet with a JSON manifest; the plan and run artifacts are JSON plus CSV.
- The studio reads the artifacts, but the studio itself is P10.

Settings changes, each with its exact command, wait for approval:

- `gh repo edit UBC-FRESH/brushline --visibility public --accept-visibility-change-consequences`
- `gh api repos/UBC-FRESH/brushline/pages -X POST -f build_type=workflow`

## 7. Decision

- [ ] Approve as written.
- [ ] Approve with the changes stated here: <changes>.
