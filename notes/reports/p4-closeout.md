# Phase close-out report: P4 Vegetation dynamics and treatments

Phase: P4 Vegetation dynamics and treatments
Parent issue: #41
Pull request: queued on `feature/p4-vegetation` into `main`
Evidence head: `bde5ff4`, the head that the gates and local verification below cover
Report commit: the commit that adds this report. Its CI run is posted on the pull request.
Date: 2026-11-14
Status: queued for approval. Not merged.

## Recommendation

Approve these actions. The agent carries them out in this order, and reads back each result.

1. Squash-merge the P4 pull request, and delete the branch `feature/p4-vegetation`.
2. Close parent issue #41 with a closeout comment that cites the merge commit.
3. Launch P5 (Optimization framework and Pareto search): create its branch, set the phase statuses in
   `ROADMAP.md`, create its child issues as sub-issues, and start P5.1.

Settings changes, each with its exact command. Each one runs only after its own approval.

- None. The repository is already public and Pages is enabled.

## 1. Objectives and acceptance

| Criterion | Evidence | Status |
| --- | --- | --- |
| The growth model reproduces held-out observations within a stated error by functional group | `9768ef5` growth; `326c123` held-out validation; `notes/reference/vegetation-validation.v1.json` | met on the committed synthetic fixture; not a field validation |
| A treatment reduces height/cover and changes the subsequent trajectory; it does not reset to zero | `711d976`; residual floors, resprouting, delay, post-delay growth | met |
| The model card flags an out-of-domain segment instead of extrapolating silently | `bde5ff4`; `check_domain` and `require_in_domain` | met |
| The benchmark against at least one candidate is recorded, including disagreement | `326c123`; `notes/reference/vegetation-validation.v1.json`; candidate summaries | met with two committed candidates; no live sibling run |
| The dashboard is green | Section 3; local dashboard at `bde5ff4` | met |

### 1.1 Stated limits

- All calibration and validation evidence is synthetic. No field plot, private treatment record, or live
  LiDAR observation was read.
- No live MEDFATE, FVS/FFE, or Botequim run was performed. The candidate values are committed benchmark
  evidence.
- The model card is a prototype. Its thresholds, treatment priors, reliability weights, and domain are
  not field-calibrated.
- The model is not a mechanistic physiology, chemical mode-of-action, fire-spread, or structural
  engineering model.
- The P4 modules are not yet wired into the plan writer, optimizer, or UI. Those integrations are later
  phases.
- The model card declares a 95 percent interval level; the synthetic interval coverage is 1.0 and is
  not evidence of field calibration.
- No private data, credentials, or payloads entered the repository.

## 2. Workflow compliance

- Parent issue before the branch: #41 was created and the phase activated on
  `feature/p4-vegetation` before P4.1.
- Branch from `main`: `feature/p4-vegetation` was created from `main` at `98940d9`.
- Commit messages that start with task IDs: P4.1 to P4.7 do.
- Roadmap and changelog in step: activation `d2ac142`, task commits, and the closeout commit.
- Child issues closed with closeout evidence: #42 to #48.
- Approval gates: no merge, branch deletion, parent-issue close, tag, release, visibility change, Pages
  change, branch-protection change, or private-data access has been performed.

### 2.1 Deviations

| Deviation | Cause | Remedy |
| --- | --- | --- |
| Calibration and validation use synthetic evidence | No field or private data is available in the repository | The fixtures are explicit and the model card labels the model as a prototype |
| Candidate benchmark is offline | The sibling models are not installed or run in CI | The benchmark fixture records the disagreement; a live run remains future work |
| P4 modules are not wired into the planner or UI | The phase is the dynamics core, not the optimizer or studio | P5 and later integrate the model |
| P4.4 uses pooled and prior cells for thin evidence | The synthetic fixture does not cover every method/season/group | Pooling is flagged and intervals are recorded; field calibration remains required |

## 3. Gate evidence

| Commit | Task | Gates | Result |
| --- | --- | --- | --- |
| `d2ac142` | P4 activation | dashboard | green |
| `121d31a` | P4.1 | dashboard | green; 556 passed, 98% coverage |
| `9768ef5` | P4.2 | dashboard | green; 575 passed, 98% coverage |
| `711d976` | P4.3 | dashboard | green; 589 passed, 98% coverage |
| `c4db594` | P4.4 | dashboard | green; 605 passed, 98% coverage |
| `28b68cf` | P4.5 | dashboard | green; 618 passed, 98% coverage |
| `326c123` | P4.6 | dashboard | green; 631 passed, 98% coverage |
| `bde5ff4` | P4.7 | dashboard | green; 641 passed, 98% coverage |

The final local dashboard at the evidence head is `OVERALL: GREEN`. The workflow validator reports
`0 error(s), 0 warning(s)`. All seven P4 modules are at 100% statement and branch coverage.

## 4. Local verification

- State space: variables, groups, classes, probabilities, unknown/partial projection, state contract.
- Growth: saturating curves, site/climate/competition, monotonicity, asymptotes, domain blocking.
- Treatment: method/season effects, residual floors, resprouting, delay, post-delay growth, cost.
- Calibration: pooling, shrinkage, intervals, source evidence, leave-one-out checks.
- Hazards: clearance, fall-in, fuel, access, reliability weighting, missing-component handling.
- Validation: spatial holdout, group error, interval coverage, time lag, candidate disagreement.
- Model card: predictors, evidence, metrics, uncertainty, domain, licence, caveats, decision boundary.

## 5. CI evidence

| Run ID | Head commit | Conclusion | Notes |
| --- | --- | --- | --- |
| pending | `bde5ff4` plus the report | in progress | CI runs on the pull request; the result is posted on the PR |
| n/a | branch pushes | not run | CI runs on pull requests and `main`, not on plain feature-branch pushes |

## 6. Next phase

P5 (Optimization framework and Pareto search) starts after approval. Its goal is to connect the P4
evaluator to the `fresh-solutions` search framework and produce replayable Pareto archives.

Recommended defaults:

- Use the P4 model card and state distribution as the evaluator boundary.
- Record every incumbent with its adapter version, data/model versions, configuration, and seed.
- Keep the exact evaluator and the search operators separate.
- Validate the adapter on the tiny synthetic optimum before a larger search.

## 7. Decision

- [ ] Approve as written.
- [ ] Approve with the changes stated here: <changes>.
