# AGENTS.md

This file is the working contract for coding agents in Brushline.

Brushline is a decision support system for optimal vegetation management along linear infrastructure corridors in forested landscapes. It couples shrub and young-tree growth, treatment transitions, strategic, tactical, and operational planning, adaptive remote monitoring, a multi-objective metaheuristic search, and an interactive planning studio for asset owners and contractors.

Keep this file short. Each rule below either checks itself or points to the page that explains it.
The workflow rules come from the UBC-FRESH dev workflow, which this project was seeded from. Project-
specific rules go at the end, each with its reason.

## Session start

Before you change anything, read in this order:

1. This file.
2. `ROADMAP.md`: the active phase and its "Detailed Next Steps Notes".
3. The latest entries in `CHANGE_LOG.md`.
4. The notes your task names, in `notes/`.
5. The docs pages that govern your task, in `docs/`.

Cite the pages you relied on in your report.

## Working principles

- **Evidence over trust.** Cite command output, diffs, commit hashes, and URLs.
- **One bounded move at a time.** Stop and report after each one.
- **No oracle, no capability.** A new agent-facing capability needs a validator that can fail.
- **Workflow as scaffold.** Create the parent issue, the branch, and the roadmap entry before the work.
- **Structured handoff.** Issues, the roadmap, notes, and the changelog carry the state.
- **Preserve uncertainty.** Say what you did not verify, and why.
- **Scope discipline.** Stay inside the active phase and task.
- **Sanitized output.** Keep private data, credentials, raw transcripts, and personal paths out of
  tracked files.

## The green dashboard rule

`python scripts/dashboard.py` runs every quality gate: lint, format, strict types, tests with a coverage
gate, the workflow validator, and the docs build with warnings as errors.

- Every commit leaves the dashboard green.
- Any change from green is investigated and fixed immediately. There are no exceptions.
- A failure you did not cause is still yours to fix, or to report with evidence before you continue.
- Do not weaken a gate to make it pass. A gate changes only with a changelog entry that explains why.
- Record the dashboard result in the changelog entry for each task that you close.

## Typing and docstrings

- Every function, method, and test has complete type annotations. `mypy --strict` must pass.
- Every public function has a numpy-style docstring. Its parameters and return value match its annotations.
- Do not use `Any`, `# type: ignore`, or `cast` without a comment that says why. A suppression names its error code.

## Testing policy

- Every function you write or change gets unit tests in the same change set. Tests must be able to
  fail, and each one asserts a specific behavior.
- Keep the layers: unit tests for each function, contract tests for public interfaces, integration
  tests for the command-line tools, property tests for invariants, and the self-check.
- The coverage gate is 95 percent branch coverage of `brushline/` and `scripts/`. Aim near 100 percent, with tests that
  assert something.

## Embedded agent capabilities

If this project ships complicated software, it may offer agents validated capabilities instead of
documentation alone. A capability is a prompt, a validator over real state, and a bounded retry
budget. No oracle, no capability. Each capability needs offline tests with a fake provider, and it
must say what its validator checks and what it does not.

## CI and merges

- CI runs every gate on every pull request, and on every push to `main`.
- No pull request merges while CI is red.
- A merge happens only as part of an approved phase close-out. Queue the pull request, write the report in `notes/reports/`, and wait for the maintainer's approval.

## Planning workflow

- One phase is one GitHub parent issue and one feature branch, `feature/p<n>-<slug>`.
- One task is one child issue, linked to the parent as a sub-issue.
- A subtask is a checklist item in the child issue body. Three levels at most.
- Keep `ROADMAP.md`, `CHANGE_LOG.md`, `notes/`, issue bodies, and PR descriptions in step.

## Approval gates

You may, within the active phase: create and commit to its branch, push that branch, open and update
its issues and pull requests, and run local checks.

After the maintainer approves a phase close-out, carry out what the report recommends: squash-merge the pull request, delete its branch, close the parent issue, and launch the next phase. Name every settings change, tag, release, or external account in the report, with its exact command, and wait for approval of each one.

You must wait for an explicit approval before you: create a tag or a release; change repository visibility, settings, or branch protection; create an external account, repository, or server; touch private data or credentials; or delete anything beyond the branch that an approved report names.

## GitHub hygiene

- Audit read-only first: `gh issue list`, `gh issue view <n>`, `gh pr list`.
- Write bodies and comments to files, and post them with `--body-file`. Never build them from escaped strings.
- Read back every comment or edit with `gh issue view` before you report it as posted.
- Post a progress comment when a task or phase milestone completes, and a closeout comment before you close an issue.

## Formatting

- Put section labels on their own lines, such as `Phase identifier: P0`.
- Use real task-list syntax, one item per line.
- Wrap branch names, paths, commands, and commit hashes in backticks.
- Start commit messages with the task ID, for example `P0.1 add license`.

## Verification

Run the dashboard before you report a change as done:

```bash
python scripts/dashboard.py
```

Record the result in the changelog entry for the milestone.

## Public safety

- No private data, credentials, raw transcripts, unpublished documents, or machine-specific paths in
  tracked files.
- Use placeholders, repository-relative paths, or environment variables in examples.

## Project-specific rules

- **A corridor is a graph of segments, and the segment is the decision unit.** Spans and treatment
  units are runtime aggregates built from segments. Reason: treatments and monitoring happen along
  linear features, and compiling at an operational grouping would bake one contractor's layout into
  the data.
- **Vegetation state carries its uncertainty.** A state is a distribution over interpretable classes
  with continuous summaries, and every plan states the state version and interval. Reason: a point
  estimate hides the risk that should trigger monitoring or treatment.
- **Treatments are transitions, not deletions.** Every treatment moves a segment to a new state with
  method-specific efficacy, selectivity, and regrowth. Reason: resprouting and regrowth are the
  dynamics being managed; a reset-to-zero model biases every interval.
- **Monitoring is a decision variable.** Flight frequency, route, sensor, and sampling intensity are
  chosen with their expected value of information. Reason: data collection is part of the budget, and
  a fixed calendar cannot be optimal for every corridor.
- **One versioned plan artifact serves the owner and the contractor.** A bid is an annotated plan with
  a line-item cost build-up, assumptions, and provenance, not a separate spreadsheet. Reason: both
  sides must inspect and compare the same object.
- **Optimization is an adapter over `fresh-solutions`.** Brushline supplies variables, options, the
  exact evaluator, moves, and undo; `fresh-solutions` supplies search, population, checkpoints, seeds,
  telemetry, and replay. Never fork or copy its engine. Reason: one reusable, tested search framework
  and one replay contract.
- **Every reported incumbent is exactly replayable.** Record the adapter version, `fresh-solutions`
  version, data and model versions, configuration, and seed. Reason: a schedule that cannot be
  replayed is not evidence.
- **The studio reads artifacts; it does not own model state.** The FastAPI service and static shell
  read the run directory, plan, schedule, account series, Pareto archive, and operations timeline.
  Skins are checked manifests, and a read-only skin cannot carry a mutating action. Reason: one source
  of truth and a small, auditable service boundary.
- **Strategic, tactical, and operational plans share one scenario contract.** The scales differ in
  horizon, resolution, and constraints, not in vocabulary or data versions. Reason: three
  incompatible truths are worse than one coarse truth.
- **WS4, FHOPS, and the urban-forest lab are reached through adapters.** Do not copy their internals
  into Brushline. Reason: their release cycles and provenance remain theirs, and Brushline stays
  installable without them.
- **No safety-critical autonomy.** Brushline is decision support. Field verification, qualified
  judgment, and the asset owner's work-control rules govern any treatment near energised lines,
  pipelines, or roads. Reason: the consequences of a wrong clearance decision are physical.
- **Record units, CRS, data versions, model versions, and seeds.** Every dataset and run manifest names
  them. Reason: vegetation and cost results are meaningless without them.
- **Keep third-party provenance out of the repository.** Use original descriptions and neutral
  vocabulary. Reason: the project must stand on its own.
