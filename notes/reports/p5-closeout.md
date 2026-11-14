# Phase close-out report: P5 Optimization framework and Pareto search

Phase: P5 Optimization framework and Pareto search
Parent issue: #50
Pull request: #59, `feature/p5-optimization` into `main`
Evidence head: `c4a0aaa`, the head that the gates and local verification below cover
Report commit: this commit, a report-only update after the evidence head
Date: 2026-11-14
Status: queued for approval. Not merged.

## Recommendation

Approve these actions. The agent carries them out in this order and reads back each result.

1. Squash-merge the P5 pull request and delete the branch `feature/p5-optimization`.
2. Close parent issue #50 with a closeout comment that cites the merge commit.
3. Launch P6 (Strategic planning and monitoring policy): create its branch, set the phase statuses in
   `ROADMAP.md`, create its child issues as sub-issues, and start P6.1.

Settings changes, each with its exact command. Each one runs only after its own approval.

- None. The repository is already public and Pages is enabled.

## 1. Objectives and acceptance

| Criterion | Evidence | Status |
| --- | --- | --- |
| The adapter satisfies the Fresh Solutions contract and replays every reported incumbent | `77a7a68`; `BrushlineAdapter`, four search modes, exact replay and checkpoint tests; the core import test proves `fresh_solutions` is not imported by `brushline.optimization` | met |
| The Pareto archive keeps only non-dominated solutions and preserves diversity | `8beee14`; dominance, duplicate, infeasibility, crowding, eviction, and promotion tests | met |
| A tiny instance reaches the known optimum within a stated budget, or the gap is reported | `29d8a17`; `notes/reference/p5-tiny-optimum.v1.json`; 324 assignments, 72 feasible, unique optimum, local search at 100 iterations reaches it | met |
| The core install works without the `opt` extra; planning requires it | lazy imports in `adapter.py`; subprocess import test; `fresh-solutions` is an optional extra and a development test dependency | met |
| The dashboard is green | Section 3; local dashboard at the evidence head | met |

### 1.1 Stated limits

- Every instance, context, calibration, validation, and search result is synthetic. No field or private
  data was read.
- No live external solver, MIP/CP model, MEDFATE, FVS/FFE, or FHOPS run was performed. The tiny
  validation is finite exhaustive enumeration, not a realistic-corridor bound.
- P5 provides search and archive contracts. It does not claim a realistic-corridor global optimum.
- The budget and scaling report is local wall-clock and traced-memory evidence, not a production SLA or
  a hardware-normalized benchmark.
- The archive member plan and evidence paths are references. P5.5 does not write plan or evidence
  payloads; P10 reads them.
- Telemetry is a report of progress, not a second source of truth. No studio UI, live event bus, or public
  portal was built.
- The scalarization portfolio is declared, not preference-elicited from an owner or contractor.
- No private data, credentials, or payloads entered the repository.

## 2. Workflow compliance

- Parent issue before the branch: #50 was created and P5 was activated on
  `feature/p5-optimization` before P5.1.
- Branch from `main`: `feature/p5-optimization` was created from `main` at `c58ffc0`.
- Commit messages that start with task IDs: P5.1 to P5.8 do.
- Roadmap and changelog in step: activation, task commits, the P5.7 budget fixture, and this closeout.
- Child issues closed with closeout evidence: #51 to #58.
- Approval gates: no merge, branch deletion, parent-issue close, tag, release, visibility change, Pages
  change, branch-protection change, or private-data access has been performed.

### 2.1 Deviations

| Deviation | Cause | Remedy |
| --- | --- | --- |
| `budget.py` and `adapter.py` are not at 100% module coverage | Timing and optional-adapter branches are exercised but a few defensive branches remain | The modules are at 97% and 96%; the overall suite is at 98% and the dashboard requires 95% |
| The P5.7 budget fixture was added at closeout | The first P5.7 commit had tests but no committed reference artifact | `notes/reference/p5-budget.v1.json` is now committed and loaded by a test |
| No MIP/CP bound | No solver dependency is needed for a 324-assignment instance | Exhaustive enumeration is the bound for the tiny instance; a larger bound remains future work |
| The adapter test suite needs the optional solver | The development requirements include `fresh-solutions` for contract tests | The package import remains independent, proven by the subprocess test |
| Archive plan/evidence payloads are not written | P5.5 owns references; P9/P10 own plan and evidence payloads | The archive paths and compatibility checks are explicit |

## 3. Gate evidence

| Commit | Task | Gates | Result |
| --- | --- | --- | --- |
| `125bc0a` | P5.1 | dashboard | green; 650 passed, 98% coverage |
| `d629740` | P5.2 | dashboard | green; 662 passed, 98% coverage |
| `47fd0e1` | P5.3 | dashboard | green; 677 passed, 98% coverage |
| `77a7a68` | P5.4 | dashboard | green; 685 passed, 98% coverage |
| `8beee14` | P5.5 | dashboard | green; 693 passed, 98% coverage |
| `29d8a17` | P5.6 | dashboard | green; 700 passed, 98% coverage |
| `17766e1` | P5.7 | dashboard | green; 704 passed, 98% coverage |
| `25c186e` | P5.8 | dashboard | green; 711 passed, 98% coverage |
| closeout | P5 closeout | dashboard | green; 713 passed, 98% coverage |

The final local dashboard at the evidence head is `OVERALL: GREEN`. The workflow validator reports
`0 error(s), 0 warning(s)`. Module coverage is 100% for `formulation.py`, `evaluator.py`, and
`telemetry.py`; 99% for `operators.py` and `pareto.py`; 98% for `validation.py`; 97% for `budget.py`;
and 96% for `adapter.py`.

## 4. Local verification

- Formulation: stable variables, method-filtered options, monitoring options, budgets, capacities,
  access, service constraints, and four objectives.
- Evaluator: exact growth/treatment replay, costs, monitoring allocation, discounting, service risk and
  attainment, uncertainty, named hard/soft violations, and exact apply/undo fallback.
- Operators: typed reversible moves, every operator, access and locks, repair, and non-repairable blocked
  models.
- Adapter: the Fresh Solutions contract, five scalarizations, random/mutation/crossover, single and
  compound proposals, local/population/hybrid/convergence modes, checkpoints, and exact replay.
- Archive: non-dominance, duplicates, infeasible rejection, crowding, deterministic eviction,
  `pareto.json`, and promotion records.
- Tiny validation: 324 assignments, 72 feasible, unique balanced-scalar optimum at present cost 100
  with both periods mowed; exact/batch agreement for every assignment; local search at 100 iterations
  reaches the optimum with zero gap.
- Budget: committed `notes/reference/p5-budget.v1.json`; budgets 1, 10, and 100, seeds 1 and 2; budget 1
  has no feasible seed, budget 10 has one feasible seed, and budget 100 has two feasible seeds that both
  reach the committed optimum.
- Telemetry: committed valid stream and archive; exact compatibility; missing and mismatched artifacts
  are explicit; JSON and SSE writers.

## 5. CI evidence

| Run ID | Head commit | Conclusion | Notes |
| --- | --- | --- | --- |
| 43577813483 | `c4a0aaa` | success | Quality gates, Pre-commit parity, and Green dashboard summary passed; this report-only update follows |
| n/a | branch pushes | not run | CI runs on pull requests and `main`, not on plain feature-branch pushes |

## 6. Next phase

P6 (Strategic planning and monitoring policy) starts after approval. It will use the P5 archive and the
P4 state/growth/treatment evaluator to build strategic treatment and monitoring policies, with explicit
uncertainty and service trade-offs.

Recommended defaults:

- Keep the P5 archive as the only multi-objective frontier.
- Treat monitoring as a decision and carry its value-of-information evidence explicitly.
- Preserve exact replay and the no-optimality statement.
- Validate strategic policies on the tiny and synthetic fixtures before any realistic corridor claim.

## 7. Decision

- [ ] Approve as written.
- [ ] Approve with the changes stated here: <changes>.
