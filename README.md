# Brushline

Brushline is a pre-alpha decision-support prototype for vegetation management along linear
infrastructure corridors in forested landscapes: powerlines, pipelines, roads, railways, and the
rights-of-way that keep them accessible and safe.

It couples a low-vegetation state-transition model, treatment transitions, strategic/tactical/
operational planning, scenario and recourse experiments, adaptive monitoring, and an artifact-first
planning studio. One versioned plan artifact is intended to serve both the asset owner and the
contractor, so budget, schedule, and bid can be inspected against the same evidence.

**Status:** working research prototype, not a field-calibrated operational system. The BC network
workflow uses private artifacts; the public demo is synthetic. See [Status](#status) and
[Documentation](#documentation).

## The problem

A utility or pipeline operator may manage thousands of kilometres of corridor through productive
forest. Vegetation left too long reduces clearance, blocks access, raises fire risk, and threatens
reliability. Treat it too often and the budget is wasted. The usual answer is a fixed cycle and a
spreadsheet, with each contractor bidding from a different set of assumptions.

Two things make the problem hard:

- Open growth-and-yield models for shrubs and young trees are scarce. Brushline carries its own
  state-transition model and states its uncertainty and applicability domain.
- The joint choice of where and when to treat, and where and when to monitor, is an NP-hard
  combinatorial problem with budget, capacity, access, spatial, temporal, and service constraints.
  Brushline uses metaheuristics and a Pareto archive for large instances; it does not claim global
  optimality.

## What the prototype includes

- **Corridor and network model.** Segments are decision units; spans and treatment units aggregate
  them at runtime. Segments carry site, vegetation, treatment, access, and observation context.
- **Vegetation state and treatments.** A state is a distribution over interpretable classes with
  continuous summaries. Treatments are transitions with method-specific efficacy, selectivity,
  resprouting, regrowth delay, and cost.
- **Three planning scales.** Strategic segment-year-method plans, tactical programs and contractor
  demand, and operational work orders and shift schedules.
- **Uncertainty and policy experiments.** Static frontier plans, scenario-robust plans, sampled
  chance constraints, two-stage deferral, rolling re-optimization, weather/outage-aware execution,
  forecast-skill sensitivity, and capacity remedies.
- **Studio and planning brief.** An artifact-only FastAPI service and static shell expose the plan,
  map, timeline, scenes, skins, Pareto archive, and a self-contained planning brief.
- **Artifact contracts.** Versioned dataset, plan, run, tactical, operations, and policy artifacts
  with validators and named errors.

## Status

The repository contains a working prototype across the model, planning stack, studio, and policy
experiments. It is **not**:

- field calibrated;
- safety-certified;
- asset-owner approved;
- a public release of BC Hydro, MKRF, or other private network data.

The private network artifacts live under `runtime/private/` and are ignored. The public demo is the
synthetic corridor under `examples/synthetic-corridor`. Release remains gated on data-sharing,
release approval, field validation, and asset-owner review. Run `python tools/audit_release.py` for
the repository boundary check.

`ROADMAP.md` remains the plan of record and `CHANGE_LOG.md` records changes.

## Quick start

```bash
python -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements-dev.txt
python -m pip install -e ".[geo,opt,web]"

brushline status
brushline fixture --out tmp/corridor
brushline prototype --fixture tmp/corridor --out tmp/prototype --years 5

brushline demo build --out build/demo
python -m http.server 8000 --directory build/demo
```

The synthetic fixture is the public quickstart. The BC network builder is a separate private
workflow:

```bash
python tools/build_bc_network_demo.py
python -m uvicorn brushline.web.studio:app --host 0.0.0.0 --port 8801
```

Do not run the private builder on a clean public checkout and do not publish its output.

## Documentation

- [Documentation home](https://ubc-fresh.github.io/brushline/) and local `docs/index.rst`
- **Getting started:** install, synthetic quickstart, first study
- **Concepts:** model, planning stack, uncertainty/recourse, artifacts and privacy
- **How-to:** private network workflow, planning brief, studio, release audit
- **Guides:** limitations, private/public boundary, troubleshooting
- **Reference:** contracts, methods, and policy experiment records
- **API:** public package reference, grouped by domain

The docs distinguish contracts from experiment records. A benchmark result is not a field
validation, and a sampled scenario is not a distributional guarantee.

## Verification

```bash
python scripts/dashboard.py
```

The dashboard runs lint, format, strict types, tests with a coverage gate, the workflow validator,
the docs build, and the docstring audit. It is the normal local and CI check.

## Repository map

| Path | Purpose |
| --- | --- |
| `AGENTS.md` | Operating contract for coding agents |
| `ROADMAP.md` | Plan of record and issue tracker map |
| `CHANGE_LOG.md` | Dated narrative of changes |
| `brushline/` | Python package, CLI, models, planners, and studio |
| `docs/` | Documentation site: getting started, concepts, how-to, guides, reference, API |
| `examples/synthetic-corridor/` | Public synthetic demo |
| `runtime/private/` | Ignored private network artifacts; never commit |
| `notes/design/` | Scope, architecture, optimization, and UI design records |
| `notes/adr/` | Architecture decisions |
| `notes/reports/` | Phase and experiment reports |
| `tools/` | Network builder, policy experiments, scale benchmarks, release audit |
| `tests/` | pytest suite |

## Relationship to the other FRESH tools

Brushline is a sibling of WS4, FHOPS, the FRESH urban-forest lab, and Fresh Solutions. It borrows
patterns, not internals:

- **WS4** supplies the pattern for a compiled, inspectable dataset, spatial decisions inside the
  model, artifact-based runs, and the web shell.
- **FHOPS** supplies the pattern for tactical and operational planning, machine and crew
  productivity, and 3D operations visualization.
- **Fresh Solutions** supplies the metaheuristic engine and the exact replay contract.
- **The FRESH urban-forest lab** supplies the pattern for the 2D/3D browser studio.

The adapters are versioned and optional. Brushline stays installable without the other tools.

## License

Apache-2.0. See [`LICENSE`](LICENSE) and [`CITATION.cff`](CITATION.cff).
