# Phase close-out report: P3 State, LiDAR, and terrain

Phase: P3 State, LiDAR, and terrain
Parent issue: #33
Pull request: #40, `feature/p3-state-lidar` into `main`
Evidence head: `c3edacc`, the head that the gates and local verification below cover
Report commit: `eb164ff`, with the PR number update in the next commit. CI runs on pull request #40.
Date: 2026-11-14
Status: queued for approval. Not merged.

## Recommendation

Approve these actions. The agent carries them out in this order, and reads back each result.

1. Squash-merge pull request #40, and delete the branch `feature/p3-state-lidar`.
2. Close parent issue #33 with a closeout comment that cites the merge commit.
3. Launch P4 (Vegetation dynamics and treatments): create its branch, set the phase statuses in
   `ROADMAP.md`, create its child issues as sub-issues, and start P4.1.

Settings changes, each with its exact command. Each one runs only after its own approval.

- None. The repository is already public and Pages is enabled.

## 1. Objectives and acceptance

| Criterion | Evidence | Status |
| --- | --- | --- |
| A validated FEMIC bundle maps to segment support with a recorded aggregation | `460c659` bundle adapter; `e3357bd` terrain support; `6dfe026` canopy support | met at adapter level; a single live bundle-to-support run is not wired |
| Every derived attribute carries the bundle pin, product checksum, model card, and applicability | `e3357bd`, `6dfe026` source provenance; `67e2ec8` state source and model card; `a173d27` model-card applicability | met at report/source level; the state table carries source and model card, not a separate checksum column |
| Missing coverage is a knowledge state, not a zero | `a173d27` six-state coverage and stop/continue | met |
| The adapter does not download tiles or compile terrain | `460c659` read-only adapter; no downloader in P3 | met |
| The benchmark against the sibling consumers agrees within a stated tolerance | `c3edacc`; committed `notes/reference/lidar-benchmark.v1.json`; 4 metrics, 12 comparisons, all pass | met on the committed fixture; live WS4/FHOPS runs are not performed |
| The dashboard is green | Section 3; local dashboard at `c3edacc` | met |

### 1.1 Stated limits

- No real FEMIC bundle payload, point cloud, DEM, CHM, field plot, or sibling runtime was read. The
  tests use deterministic synthetic arrays and provenance records.
- The P3 adapters are separate contracts. A single end-to-end orchestration from a validated bundle to
  terrain/canopy support and then to the state table is not wired in P3.
- The P3.4 classification thresholds are prototype rules with the prototype model card
  `brushline.low-vegetation.prototype.v0`. P4 calibration is required.
- Young-tree and mature-edge states without species evidence use a conifer fallback and an open
  question. The CHM does not resolve species.
- The P3.6 sibling values are committed benchmark evidence, not a live WS4 or FHOPS integration.
- The P2.7 review screen consumes the shared coverage/gap contract but was not changed in P3.
- No private data, credentials, or payloads entered the repository.

## 2. Workflow compliance

- Parent issue before the branch: #33 was created and the phase activated on
  `feature/p3-state-lidar` before P3.1.
- Branch from `main`: `feature/p3-state-lidar` was created from `main` at `c39f5f9`.
- Commit messages that start with task IDs: P3.1 to P3.6 do.
- Roadmap and changelog in step: activation `0dbbb90`, task commits, and the closeout commit.
- Child issues closed with closeout evidence: #34 to #39.
- Approval gates: no merge, branch deletion, parent-issue close, tag, release, visibility change, Pages
  change, branch-protection change, or private-data access has been performed.

### 2.1 Deviations

| Deviation | Cause | Remedy |
| --- | --- | --- |
| No live FEMIC payload was consumed | CI and the local environment have no producer run or payload store | Synthetic bundle and raster fixtures exercise the contracts; a live run is deferred to a later integration |
| P3 adapters are separate stages | Each task delivered a bounded contract before orchestration | P3 closeout states the limit; the P3.7/orchestration work is not claimed |
| P3.4 uses prototype thresholds and a conifer fallback | The P4 calibration does not exist yet | The prototype model card and open questions are explicit; P4 replaces them |
| P3.6 sibling values are committed evidence | The sibling consumers are separate repositories and not installed in CI | The benchmark is offline and deterministic; a live sibling run remains future work |
| Some attributes carry source/model card but not a checksum column | The `brushline.state.v1` contract has no per-attribute checksum field | The source version names the bundle/product and the report carries the product provenance; a future contract revision can add a checksum |

## 3. Gate evidence

| Commit | Task | Gates | Result |
| --- | --- | --- | --- |
| `0dbbb90` | P3 activation | dashboard | green |
| `460c659` | P3.1 | dashboard | green; 444 passed, 97% coverage; `lidar.py` 100% |
| `e3357bd` | P3.2 | dashboard | green; 471 passed, 97% coverage; `terrain.py` 100% |
| `6dfe026` | P3.3 | dashboard | green; 489 passed, 98% coverage; `canopy.py` 100% |
| `67e2ec8` | P3.4 | dashboard | green; 517 passed, 98% coverage; `state_init.py` 99% |
| `a173d27` | P3.5 | dashboard | green; 531 passed, 98% coverage; `lidar_coverage.py` 100% |
| `c3edacc` | P3.6 | dashboard | green; 539 passed, 98% coverage; `lidar_benchmark.py` 100% |

The final local dashboard at the evidence head is `OVERALL: GREEN`. The workflow validator reports
`0 error(s), 0 warning(s)`.

## 4. Local verification

- Bundle adapter: producer pin, selection digest, product checksums, paths, CRS, datum, resolution,
  licence, tiles, layers, derived flags, and provenance.
- Terrain: buffered support, all statistics, slope/aspect, classes, access proxy, coverage states,
  CRS/datum/resolution checks.
- Canopy: height/cover statistics, structure, optional tree products, VRI comparison, domain states.
- State: field-first selection, prototype classes, unknown/partial states, audit decisions,
  probabilities, and a valid `brushline.state.v1` contract.
- Coverage: observed, stale, partial, missing, out-of-domain, excluded, next actions, and stop/continue.
- Benchmark: 4 metrics, 12 comparisons, all within tolerance on the committed fixture.

## 5. CI evidence

| Run ID | Head commit | Conclusion | Notes |
| --- | --- | --- | --- |
| pending | `c3edacc` plus the report | in progress | CI runs on pull request #40; the result is posted on the PR |
| n/a | branch pushes | not run | CI runs on pull requests and `main`, not on plain feature-branch pushes |

## 6. Next phase

P4 (Vegetation dynamics and treatments) starts after approval. Its goal is to replace the prototype
state rules and structural transitions with a calibrated low-vegetation dynamics model and
method-specific treatment transitions.

Recommended defaults:

- Calibrate against field plots and repeated observations; keep the state a distribution.
- Keep treatments as transitions; do not reset a segment to zero.
- Keep monitoring as a decision variable.
- Preserve the P3 provenance and coverage contracts.
- Re-run the P3.6 benchmark after any change to the aggregation or state rules.

## 7. Decision

- [ ] Approve as written.
- [ ] Approve with the changes stated here: <changes>.
