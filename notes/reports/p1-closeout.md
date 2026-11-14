# Phase close-out report: P1 Contracts and prototype

Phase: P1 Contracts and prototype
Parent issue: #15
Pull request: #23, `feature/p1-contracts-prototype` into `main`
Evidence head: `2b8bdea`, the head that the gates and the CI run below cover
Report commit: the commit that adds this report. Its CI run is posted on the pull request.
Date: 2026-11-14
Status: queued for approval. Not merged.

## Recommendation

Approve these actions. The agent carries them out in this order, and reads back each result.

1. Squash-merge pull request #23, and delete the branch `feature/p1-contracts-prototype`.
2. Close parent issue #15 with a closeout comment that cites the merge commit.
3. Launch P2 (FEMIC-extended instance builder): create its branch, set the phase statuses in
   `ROADMAP.md`, create its child issues as sub-issues, and start P2.1.

Settings changes, each with its exact command. Each one runs only after its own approval.

- None. The repository is already public and Pages is enabled.

## 1. Objectives and acceptance

| Criterion | Evidence | Status |
| --- | --- | --- |
| The dataset contract covers the manifest, tables, columns, keys, units, CRS, checksums, and digest | `37bf56d`; `brushline/model/schema.py`; `docs/reference/compiled-dataset.rst` | met |
| The corridor contract covers the graph, spans, treatment units, access, structures, and service standards | `dcc0b96`; `brushline/model/corridor.py`; `docs/reference/corridor-contract.rst` | met |
| The state contract covers functional groups, state classes, treatments, transitions, observations, and uncertainty | `713f14c`; `brushline/model/state.py`; `docs/reference/state-contract.rst` | met |
| The plan, run, archive, timeline, and demo contracts are defined | `8aee5f7`; `brushline/model/plan.py`, `run.py`, `archive.py`, `timeline.py`, `demo.py`; `docs/reference/artifacts.rst` | met |
| A synthetic corridor fixture exercises the contracts | `110d9cb`; `examples/synthetic-corridor/`; `docs/reference/synthetic-fixture.rst` | met |
| The fixture compiles, simulates, reports, and writes a run directory | `7e8c0e9`, `183f68a`; `brushline prototype`; `docs/reference/prototype.rst` | met |
| The same schedule reproduces the same accounts and state values | `tests/test_prototype.py`; `tests/test_contracts.py` | met |
| A malformed dataset, plan, archive, or schedule fails with a named error | `tests/test_dataset_schema.py`, `test_artifact_contracts.py`, `test_corridor_contract.py`, `test_state_contract.py`, `test_prototype.py` | met |
| Every contract has a JSON round-trip and a failing case | `2b8bdea`; `tests/test_contracts.py`; `tests/test_properties.py`; `docs/reference/contract-index.rst` | met |
| `python scripts/dashboard.py` reports `OVERALL: GREEN` | `2b8bdea`; section 3; CI run `43552069624` | met |

### 1.1 Stated limits

- The growth rule and treatment transition are deterministic prototypes, not the calibrated P4 model.
- The fixture is synthetic; it is not a real corridor, a real cost, or a calibrated model.
- The compiler and simulator read only the P1.1 to P1.4 contracts. The LiDAR adapter, instance builder,
  optimizer, studio, and demo portal are later phases.
- The property tests cover the P1 invariants, not the future search.

## 2. Workflow compliance

- Parent issue before the branch: #15 was created and the phase activated on
  `feature/p1-contracts-prototype` before P1.1.
- Branch from `main`: `feature/p1-contracts-prototype` was created from `main` at `e457a6b`.
- Commit messages that start with task IDs: the P1.1 to P1.7 commits and the P1.6 fix do.
- Gates for each commit: section 3.
- Roadmap and changelog in step: `03955e6` (activation), the task commits, and `2b8bdea` (P1.7).
- Child issues closed with closeout evidence: #16 to #22.
- Approval gates: no tag, release, visibility change, Pages change, branch protection change, private
  data access, or deletion beyond the named branch.

### 2.1 Deviations

| Deviation | Cause | Remedy |
| --- | --- | --- |
| P1.6's first commit was queued while the format gate was red | A shell pipeline masked the dashboard exit status | `183f68a` fixed the compiler format and the full dashboard is green |
| The synthetic fixture was regenerated during P1.6 | `PlanAction` gained `efficacy` so the plan carries its treatment transition parameter | Regenerated with the same seed; the fixture test compares the committed digests |
| The `.gitignore` `build/` rule hid `brushline/build/` | The seed rule was unanchored | Anchored to `/build/`; the package is tracked and the P1.6 commit includes it |

## 3. Gate evidence

| Commit | Task | Gates | Result |
| --- | --- | --- | --- |
| `03955e6` | P1 activation | validator | green |
| `37bf56d` | P1.1 | dashboard | green; 171 passed, 99.18% coverage |
| `dcc0b96` | P1.2 | dashboard | green; 193 passed, 98.92% coverage |
| `713f14c` | P1.3 | dashboard | green; 208 passed, 99.08% coverage |
| `8aee5f7` | P1.4 | dashboard | green; 231 passed, 98.17% coverage |
| `110d9cb` | P1.5 | dashboard | green; 245 passed, 97.22% coverage |
| `7e8c0e9` | P1.6 | dashboard | red: format on `brushline/build/compiler.py` |
| `183f68a` | P1.6 fix | dashboard | green; 255 passed, 96.42% coverage |
| `2b8bdea` | P1.7 | dashboard | green; 277 passed, 96.42% coverage |

## 4. CI evidence

| Run ID | Head commit | Conclusion | Notes |
| --- | --- | --- | --- |
| 43552069624 | `2b8bdea` | success | Quality gates, Pre-commit parity, and Green dashboard summary all passed |
| pending | report commit | in progress | The report commit's CI run is posted on pull request #23 |

## 5. Next phase

P2 (FEMIC-extended instance builder) starts after approval. Its goal is to extend FEMIC's instance,
rebuild-spec, FreshForge, catalogue, DataLad, and preflight surfaces to build Brushline instances from a
map-selected AOI, without creating a second instance-builder package.

Recommended P2 child issues:

- P2.1 Record and pin the FEMIC extension boundary and provider API.
- P2.2 Add the Brushline instance template and rebuild spec.
- P2.3 Add the Brushline provider nodes.
- P2.4 Add the data catalogue and connector registry.
- P2.5 Add the fetch plan, materialization, coverage, and gap report.
- P2.6 Add the agent capability contract and offline test harness.
- P2.7 Build the map-to-instance prototype and review screen.

Recommended defaults:

- Pin the FEMIC CLI/provider version and fail a contract test when the provider signature changes.
- Use the FEMIC instance layout and `config/rebuild.spec.yaml`; do not create a parallel workspace.
- Keep the agent optional; every capability needs a validator and an offline fake-provider test.
- Do not download private data; use public LidarBC or synthetic data for the first map-to-instance
  prototype.

## 6. Decision

- [ ] Approve as written.
- [ ] Approve with the changes stated here: <changes>.
