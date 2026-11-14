# Brushline

Brushline is decision support for vegetation management along linear infrastructure corridors in
forested landscapes: powerlines, pipelines, roads, railways, and the rights-of-way that keep them
accessible and safe.

The system couples a shrub and young-tree growth model, treatment transitions, strategic, tactical, and
operational planning, adaptive remote monitoring, and a multi-objective metaheuristic search. One
versioned plan artifact serves both the asset owner who hires the work and the contractor who bids on
it, so a budget, a schedule, and a bid can be inspected against the same evidence.

## The problem

A utility or pipeline operator may manage thousands of kilometres of corridor through productive
forest. Vegetation that is left too long reduces clearance, blocks access, raises fire risk, and
threatens reliability. Treat it too often and the budget is wasted. The usual answer is a fixed cycle
and a spreadsheet, with each contractor bidding from a different set of assumptions.

Two things make the problem hard:

- Open growth and yield models for shrubs and young trees are scarce. Brushline must carry its own
  calibrated state-transition model, and must state its uncertainty.
- The joint choice of where and when to treat, and where and when to monitor, is an NP-hard
  combinatorial problem with budget, capacity, access, spatial, temporal, and service constraints.
  Brushline therefore commits to a metaheuristic search framework and a Pareto archive of trade-offs,
  not to a claim of optimality.

## What the system will do

- **Build a corridor model.** Segments are the decision unit; spans and treatment units are runtime
  aggregates. Each segment carries site, vegetation, treatment, access, and observation history.
- **Grow and treat vegetation.** A state is a distribution over interpretable classes, with
  continuous summaries. Treatments are transitions with method-specific efficacy, selectivity, and
  regrowth.
- **Plan at three scales.** Strategic plans set budget, service levels, risk appetite, and monitoring
  policy over 10 to 30 years. Tactical plans set multi-year treatment programs, contractor capacity,
  and access. Operational plans set work-ready treatment units, methods, and schedules.
- **Decide when to monitor.** Flight frequency, route, sensor, and sampling intensity are decision
  variables priced by their expected value of information, and observations recalibrate the growth
  model.
- **Search the trade-offs.** A `fresh-solutions` problem adapter supplies exact evaluation, moves, and
  undo; the engine supplies local search, population search, checkpoints, seeds, telemetry, and exact
  replay. A Pareto archive keeps the cost, risk, service, and uncertainty trade-offs.
- **Compare owner and contractor views.** A plan carries a line-item cost build-up, assumptions,
  quantities, rates, and provenance. A bid is an annotated plan, not a separate spreadsheet.
- **Explore it in a planning studio.** One optional FastAPI service and one static browser shell read
  the run artifacts. MapLibre carries the 2D corridor map, Three.js carries the 3D operations scene,
  and checked skins cover owner-strategic, tactical, operations, contractor, monitoring, and reviewer
  roles. The studio animates deployment and explores the Pareto front without owning model state.

## Status

Phase 0 (bootstrap and scope) and Phase 1 (contracts and prototype) are complete and merged. Phase 2
(FEMIC-extended instance builder) is active: the repository is pinning the FEMIC provider surface and
building the map-to-instance workflow on top of it. It does not yet have a usable vegetation model or
planner. `ROADMAP.md` is the plan of record, and the GitHub issues carry the live status.

Brushline is a working name. It is easy to rename before the first public release.

## Quick start

```bash
python -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements-dev.txt
python -m pip install -e .
brushline --help
python scripts/dashboard.py
```

The dashboard runs lint, format, strict types, tests with a coverage gate, the workflow validator, the
docs build, and the docstring audit. Every commit leaves it green.

## How this project works

This project follows the UBC-FRESH dev workflow. Work is planned as phases, tasks, and subtasks in
`ROADMAP.md`, mirrored in GitHub issues, and recorded in `CHANGE_LOG.md`. The agent operating contract
is in `AGENTS.md`. Read `AGENTS.md`, then `ROADMAP.md`, before you change anything.

## Repository map

| Path | Purpose |
| --- | --- |
| `AGENTS.md` | Operating contract for coding agents |
| `ROADMAP.md` | Plan of record and issue tracker map |
| `CHANGE_LOG.md` | Dated narrative of changes |
| `brushline/` | The Python package and command line |
| `docs/` | Documentation site, including the design index |
| `notes/design/` | Scope, architecture, optimization, and UI design records |
| `notes/adr/` | Architecture decisions |
| `notes/reports/` | Phase close-out reports |
| `scripts/check_workflow.py` | Workflow validator |
| `tests/` | pytest suite, including the planning-surface self-check |

## Relationship to the other FRESH tools

Brushline is a sibling of WS4, FHOPS, the FRESH urban-forest lab, and Fresh Solutions. It borrows
patterns, not internals:

- **WS4** supplies the pattern for a compiled, inspectable dataset, spatial decisions inside the model,
  artifact-based runs, and the web shell.
- **FHOPS** supplies the pattern for tactical and operational planning, machine and crew productivity,
  and 3D operations visualization.
- **Fresh Solutions** supplies the metaheuristic engine and the exact replay contract.
- **The FRESH urban-forest lab** supplies the pattern for a 2D/3D browser studio with vendored,
  offline-capable map and scene libraries.

The adapters are versioned and optional. Brushline stays installable without the other tools.

## License

Apache-2.0. See [`LICENSE`](LICENSE) and [`CITATION.cff`](CITATION.cff).
