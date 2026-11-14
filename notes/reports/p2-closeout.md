# Phase close-out report: P2 FEMIC-extended instance builder

Phase: P2 FEMIC-extended instance builder
Parent issue: #24
Pull request: #32, `feature/p2-instance-builder` into `main`
Evidence head: `01cb725`, the docs-fix head that the CI run below covers
Report commit: the commit that adds this report and the CI result. CI runs on pull request #32.
Date: 2026-11-14
Status: queued for approval. Not merged.

## Recommendation

Approve these actions. The agent carries them out in this order, and reads back each result.

1. Squash-merge pull request #32, and delete the branch `feature/p2-instance-builder`.
2. Close parent issue #24 with a closeout comment that cites the merge commit.
3. Launch P3 (State, LiDAR, and terrain): create its branch, set the phase statuses in `ROADMAP.md`,
   create its child issues as sub-issues, and start P3.1.

Settings changes, each with its exact command. Each one runs only after its own approval.

- None. The repository is already public and Pages is enabled.

## 1. Objectives and acceptance

| Criterion | Evidence | Status |
| --- | --- | --- |
| A new Brushline instance is scaffolded and built through FEMIC's instance and FreshForge surfaces | `c8b6a3f`/`ea14180` template and two specs; `bcd614d` provider; local FEMIC `validate-spec` check in P2.2; `8283827` synthetic local build | met with limits: the template and provider contract are verified; a live FEMIC graph run is not verified |
| The extension is optional; Brushline core installs and simulates without FEMIC | Core tests and docs build run without the `femic` extra; `tests/test_femic_boundary.py` pins the optional boundary | met |
| A missing source, licence, or coverage gap stops the build or is reported, not fabricated | `tests/test_catalogue.py`; `tests/test_fetch_plan.py`; `tests/test_model_builder.py` | met |
| Private data cannot reach a prompt, a tracked file, or a public artifact without approval | `tests/test_catalogue.py`; `tests/test_capabilities.py`; `tests/test_model_builder.py` | met |
| Every capability has a validator that can fail and an offline fake-provider test | `tests/test_capabilities.py`; 6 capabilities and 6 validators | met |
| The dashboard is green | Section 3; local dashboard at `8283827` | met |

### 1.1 Stated limits

- No live FEMIC/FreshForge graph execution was run in CI or in P2.7. The template passes FEMIC's
  `validate-spec`; the provider is tested offline; the model-builder synthetic build uses the
  Brushline fixture compiler. A live graph run remains a P3 integration item.
- The model-builder prototype is synthetic and local. It has no real spatial coverage query, no
  private connector read, and no production authentication.
- The fetch layer is plan-only. There is no downloader, DataLad materialization, or live owner
  connector read in P2.
- The browser tests are in-process contract and static-shell tests. There is no browser automation.

## 2. Workflow compliance

- Parent issue before the branch: #24 was created and the phase activated on
  `feature/p2-instance-builder` before P2.1.
- Branch from `main`: `feature/p2-instance-builder` was created after P1 merged as `58b3065`.
- Commit messages that start with task IDs: the P2.1 to P2.7 commits do.
- Gates for each commit: section 3.
- Roadmap and changelog in step: the P2.1 to P2.7 entries; P2.3's missed checkbox was corrected in
  P2.4.
- Child issues closed with closeout evidence: #25 to #31.
- Approval gates: no merge, branch deletion, parent-issue close, tag, release, visibility change, Pages
  change, branch-protection change, or private data access has been performed.

### 2.1 Deviations

| Deviation | Cause | Remedy |
| --- | --- | --- |
| P2.3's roadmap checkbox remained unchecked after #27 closed | The P2.3 closeout edited the changelog but the roadmap replacement did not match the wrapped task line | Corrected in P2.4; the roadmap now matches the closed task |
| `tests/test_femic_boundary.py` was omitted from the P2.1 `git add` list | A path-list omission in the P2.1 commit | Committed with P2.2; the test content and P2.1 evidence are unchanged |
| P2.3 stage commands are thin wrappers | The provider contract needed stable commands before the map-to-instance orchestration | P2.7 uses the shared contracts; P3 and P5 replace the state and scenario stages |
| P2.7 uses a synthetic local build, not a live FEMIC graph | CI has no FEMIC service or network access; the prototype must be deterministic | Stated limit and a P3 integration item; no claim of a live graph run |
| P2.7 browser coverage is in-process | No browser automation dependency is approved | The static shell and every HTTP contract are tested; a browser test remains future work |
| FastAPI's test client emits a deprecation warning with the pinned httpx | Upstream test-client deprecation | The warning is non-fatal; the dashboard is green; a later test-client migration is recorded here |
| The first PR CI run failed the docs build on FastAPI autodoc import | The optional web dependency and the docs environment did not agree | The API page is prose-only, FastAPI is no longer a docs requirement, and the local dashboard is green |

## 3. Gate evidence

| Commit | Task | Gates | Result |
| --- | --- | --- | --- |
| `d85b242` | P2.1 | dashboard | green; 289 passed, 96.38% coverage |
| `c8b6a3f` | P2.2 | dashboard | green; 298 passed, 96.21% coverage; FEMIC `validate-spec` passed |
| `ea14180` | P2.2 fix | dashboard | green; 298 passed, 96.21% coverage |
| `bcd614d` | P2.3 | dashboard | green; 323 passed, 95.54% coverage |
| `c52a428` | P2.4 | dashboard | green; 349 passed, 95.94% coverage |
| `0bd6c31` | P2.5 | dashboard | green; 380 passed, 96.48% coverage |
| `e3cbdfb` | P2.6 | dashboard | green; 406 passed, 96.82% coverage |
| `8283827` | P2.7 | dashboard | green; 424 passed, 96.99% coverage |
| `01cb725` | P2.7 docs fix | dashboard | green; 424 passed, 96.99% coverage |

The integration modules are at 100% statement and branch coverage:
`brushline/integrations/catalogue.py`, `fetch.py`, and `capabilities.py`. The model builder is at 98%.

## 4. Local synthetic dry run

The required local dry run used the committed synthetic AOI and a temporary runtime root.

- Session status: `complete`.
- Stages: `validate_aoi`, `fetch_plan`, `segment_corridor`, and `review` passed; `fetch`,
  `compile_dataset`, `seed_vegetation_state`, `validate_scenario`, and `build_demo` skipped.
- Segments: 5.
- Initial state distribution: `grass_herb 1, mixed 1, shrub 1, unknown 1, young_tree 1`.
- Coverage: `observed 6`, `missing 7`, total 13.
- Gap decision: `continue_with_caveat`; 7 gaps; 3 open questions.
- Runtime files: only `fetch_plan.json` and `review.json`. No dataset, state, demo, or private row was
  written.

## 5. CI evidence

| Run ID | Head commit | Conclusion | Notes |
| --- | --- | --- | --- |
| 43561909308 | `56ad065` | failure | Docs build failed on the optional FastAPI autodoc import; fixed in `01cb725` |
| 43562164209 | `01cb725` | success | Quality gates, Pre-commit parity, and Green dashboard summary all passed |
| pending | report-only commit | in progress | The report update triggers a final CI run; the result is posted on PR #32 |
| n/a | branch pushes | not run | CI runs on pull requests and `main`, not on plain feature-branch pushes |

## 6. Next phase

P3 (State, LiDAR, and terrain) starts after approval. Its goal is to turn FEMIC's open LiDAR and
inventory products into a validated initial Brushline state, with coverage, applicability, and model
cards.

Recommended defaults:

- Reuse the FEMIC product contracts and bundle manifest; do not rebuild LiDAR discovery or processing.
- Calibrate the low-vegetation state model before treating it as operational.
- Mark partial or missing coverage as unknown or partial; do not impute a state.
- Add the live FEMIC/FreshForge graph run as a P3 integration check if the environment supports it.

## 7. Decision

- [ ] Approve as written.
- [ ] Approve with the changes stated here: <changes>.
