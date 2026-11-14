# Phase close-out report: P6 Strategic planning and monitoring policy

Phase: P6 Strategic planning and monitoring policy
Parent issue: #60
Pull request: pending
Evidence head: `9b304bd`, the head that the gates and local verification below cover
Report commit: this commit, plus the pull-request number update
Date: 2026-11-14
Status: queued for approval. Not merged.

## Recommendation

Approve these actions. The agent carries them out in this order and reads back each result.

1. Squash-merge the P6 pull request and delete the branch `feature/p6-strategic`.
2. Close parent issue #60 with a closeout comment that cites the merge commit.
3. Launch P7 (Tactical and operational planning): create its branch, set the phase statuses in
   `ROADMAP.md`, create its child issues as sub-issues, and start P7.1.

Settings changes, each with its own exact command. Each one runs only after its own approval.

- None. The repository is already public and Pages is enabled.

## 1. Objectives and acceptance

| Criterion | Evidence | Status |
| --- | --- | --- |
| A strategic plan covers the horizon and respects the budget and service-level constraints | `a4102c8` DP, `87efb64` portfolio, `9b304bd` 10-year validation; service 0.707, budget checks pass | met on the synthetic case |
| The monitoring policy is a decision, not a fixed calendar | `18926aa`; value-of-information selection, interval, route, sensor, sampling, event years | met |
| The BAU comparison reports present cost, service attainment, risk, and uncertainty | `c5187a2`; `0d90a3d`; BAU service 0.413 versus optimized 0.707, cost 360 versus 920 | met |
| The plan is reproducible from its scenario and seed | `5e055c1`; canonical config/portfolio/report digests and exact replay; `9b304bd` replay check | met |
| The dashboard is green | Section 3; local dashboard at the evidence head | met |

### 1.1 Stated limits

- Every corridor, option, monitoring value, and BAU cycle is synthetic. No field or private data was
  read.
- The single-segment DP is scalarized. It returns separate service, risk, uncertainty, and cost, but the
  policy itself maximises the declared weighted reward.
- The network portfolio is a deterministic greedy construction with local swaps, not a global optimum.
- The monitoring value of information is an explicit option-level proxy, not a sensor simulation.
- The strategic report does not model tax, financing, inflation, or a full discounted cash-flow
  statement.
- BAU is a fixed-cycle scenario, not a claim about the owner's actual past decisions.
- No tactical contracts, crew schedules, work orders, studio UI, or public portal were built.
- No live external solver, field LiDAR campaign, or realistic-corridor validation was performed.
- The literature map is a cited public-source scan. The bundle PDFs are not committed because the bundle
  does not establish redistribution rights.
- No private data, credentials, or payloads entered the repository.

## 2. Workflow compliance

- Parent issue before the branch: #60 was created and P6 activated on `feature/p6-strategic` before
  P6.1.
- Branch from `main`: `feature/p6-strategic` was created from `main` at `c3df686`.
- Commit messages that start with task IDs: P6.1 to P6.7 do; the launch/literature commit carries the
  phase ID.
- Roadmap and changelog in step: launch, task commits, and this closeout.
- Child issues closed with closeout evidence: #61 to #67.
- Approval gates: no merge, branch deletion, parent-issue close, tag, release, visibility change, Pages
  change, branch-protection change, or private-data access has been performed.

### 2.1 Deviations

| Deviation | Cause | Remedy |
| --- | --- | --- |
| Portfolio is greedy plus local swaps | A strategic-scale exact MIP is not a P6 dependency | The no-optimality statement and the tiny/synthetic validation are explicit |
| Monitoring is one option per span | The first policy keeps the decision and evidence legible | Frequency, route, sensor, sampling, cost, and VOI are recorded; multi-option missions are later work |
| Reports are deterministic totals without a full financial model | P6 is a planning prototype, not a finance system | Caveats name inflation, tax, and financing omissions |
| BAU cycle is a scenario | The owner's actual historical calendar is not available | The fixed cycle is explicit and the comparison is like-for-like |
| The literature bundle is citation-only | Open access did not establish redistribution rights for the PDFs | `notes/reference/shrub-literature-map.md` records the citations, gaps, and next searches |
| Report coverage is 95% and three strategic modules are 97-99% | Defensive branches and optional edge paths are not all exercised | The overall suite is 98% and the dashboard requires 95% |

## 3. Gate evidence

| Commit | Task | Gates | Result |
| --- | --- | --- | --- |
| `1111a44` | P6 launch + literature map | dashboard | green; 712 passed, 98% coverage |
| `a4102c8` | P6.1 | dashboard | green; 717 passed, 98% coverage |
| `87efb64` | P6.2 | dashboard | green; 722 passed, 98% coverage |
| `18926aa` | P6.3 | dashboard | green; 726 passed, 98% coverage |
| `c5187a2` | P6.4 | dashboard | green; 731 passed, 98% coverage |
| `0d90a3d` | P6.5 | dashboard | green; 734 passed, 98% coverage |
| `5e055c1` | P6.6 | dashboard | green; 739 passed, 98% coverage |
| `9b304bd` | P6.7 | dashboard | green; 743 passed, 98% coverage |
| closeout | P6 closeout | dashboard | green; 743 passed, 98% coverage |

The final local dashboard at the evidence head is `OVERALL: GREEN`. The workflow validator reports
`0 error(s), 0 warning(s)`. Module coverage is 100% for `validation.py`; 99% for `dynamic_program.py` and
`scenario.py`; 98% for `bau.py`; 97% for `portfolio.py` and `monitoring.py`; and 95% for `reports.py`.

## 4. Local verification

- Dynamic program: transition/availability validation, discounting, backward induction, tie-breaking,
  terminal values, policy replay, and expected cost/service/risk/uncertainty.
- Portfolio: service repair, budget and capacity enforcement, risk warnings, continuity, local swaps,
  empty options, and invalid references.
- Monitoring: value-ranked span selection, interval and event years, budget/value floors, empty options,
  and invalid references.
- BAU: annual and four-year cycles, budget truncation, unenforced violations, capacity, action filters,
  and like-for-like comparison.
- Reports: ten optimized and ten BAU rows, monitoring allocation, overruns, mismatched scopes, totals,
  and round-trip.
- Scenario: canonical digests, artifact replay, missing/tampered artifacts, archive validation, and the
  committed example.
- Synthetic validation: 10-year optimized plan service 0.707, treatment cost 920; BAU service 0.413,
  cost 360; monitoring cost 200; all seven checks pass and the scenario replays.

## 5. CI evidence

| Run ID | Head commit | Conclusion | Notes |
| --- | --- | --- | --- |
| pending | pending | pending | CI runs on the pull request; the pull-request number and run will be recorded after opening it |
| n/a | branch pushes | not run | CI runs on pull requests and `main`, not on plain feature-branch pushes |

## 6. Next phase

P7 (Tactical and operational planning) starts after approval. It will turn the strategic policy and
budget into treatment units, contractor capacity, access, seasons, work orders, and a monitoring mission
plan.

Recommended defaults:

- Keep the P6 strategic plan as the budget and service envelope.
- Use the P5 archive and P6 scenario record as the replay boundary.
- Preserve the BAU comparison and the no-optimality statement.
- Do not build a new solver; tactical and operational adapters should reuse the existing contracts.

## 7. Decision

- [ ] Approve as written.
- [ ] Approve with the changes stated here: <changes>.
