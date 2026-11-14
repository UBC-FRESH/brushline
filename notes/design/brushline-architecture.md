# Brushline Architecture

Status: draft for Phase 0 review
Phase: P0 (Bootstrap and scope)
Date: 2026-11-14
Related: `notes/design/brushline-scope.md`, `notes/adr/`

## 1. Purpose

This note records the architecture that later phases build against. It covers the domain model, the
vegetation and treatment dynamics, the observation loop, the three planning scales, the optimization
stack, the owner-contractor plan exchange, the instance builder, the interactive studio, the demo
portal, the data artifacts, and the integration boundaries.

The scope is in `notes/design/brushline-scope.md`. The decisions that constrain later phases are
recorded as ADRs in `notes/adr/`.

## 2. Design principles

1. **The corridor is the object.** Space is not a post-processing layer. Segments are the decision
   unit, and adjacency, access, and continuity are enforced in simulation and optimization.
2. **State carries uncertainty.** A vegetation state is a distribution over interpretable classes
   with continuous summaries. The plan says what is known, what is assumed, and what is missing.
3. **Treatments are transitions.** A treatment changes the state; it does not delete vegetation.
   Efficacy, selectivity, seasonality, and regrowth are part of the transition.
4. **Monitoring is a decision.** Flight frequency, route, sensor, and sampling intensity are chosen
   with their expected value of information, not from a fixed calendar.
5. **Three scales, one contract.** Strategic, tactical, and operational plans share the same scenario,
   vocabulary, and plan version. They differ in horizon, resolution, and constraints.
6. **Search is reusable.** The optimizer is a Brushline adapter over `fresh-solutions`, not another
   solver. Every reported incumbent is exactly replayable.
7. **The studio reads artifacts.** The browser service never owns model state. It reads the run
   directory, the plan, the archive, and the operations timeline.
8. **Build instances by extension, not duplication.** FEMIC owns the instance workspace, data
   acquisition, LiDAR production, and workflow graph. Brushline adds provider nodes and a domain
   compiler.
9. **Public demos are public-data-only.** The demo portal is a read-only showcase, not an operational
   deployment.
10. **Reproducibility is a feature.** Data version, model version, configuration, seed, package
    versions, and adapter versions travel with every result.

## 3. System context

```text
                    +--------------------------------------+
                    |  Asset owner / program manager       |
                    |  Tactical planner / field supervisor |
                    |  Contractor / monitoring specialist  |
                    +------------------+-------------------+
                                       |
                                       v
+------------------+       +----------------------+       +----------------------+
| External data    |       |  Brushline           |       |  Sibling tools       |
|                  |       |                      |       |                      |
| LidarBC / OGL-BC | ----> |  instance builder    | <---- |  FEMIC (producer)    |
| VRI / VDYP/SIBEC |       |  corridor compiler   |       |  WS4 (estate model)  |
| DRA / FTEN       |       |  growth + treatment  |       |  FHOPS (operations)  |
| NTEMS / climate  |       |  planner + studio    |       |  Fresh Solutions     |
| owner data       |       |  plan exchange       |       |  fresh-road / Nemora |
+------------------+       +----------+-----------+       +----------------------+
                                       |
                                       v
                    +--------------------------------------+
                    |  Artifacts: dataset, plan, schedule,  |
                    |  accounts, Pareto archive, timeline, |
                    |  reports, demo catalogue             |
                    +--------------------------------------+
```

### Actors

- **Asset owner executive:** sets service levels, risk appetite, and multi-year budget.
- **Vegetation program manager:** owns the corridor portfolio and the treatment policy.
- **Tactical planner:** turns the policy into treatment units, contracts, and access plans.
- **Field operations supervisor:** runs the work and records what happened.
- **Contractor estimator:** prices a work plan and defends the assumptions.
- **Monitoring specialist:** plans remote and field observations and recalibrates the model.
- **Analyst or researcher:** builds scenarios, checks sensitivity, and extends the model.
- **Reviewer or community liaison:** reads the plan, the evidence, and the caveats.
- **Coding or planning agent:** operates the deterministic tools through validated capabilities.

### External systems

- **FEMIC** is the producer of LiDAR bundles, terrain, canopy, ALS inventory attributes, model cards,
  and instance workspaces.
- **WS4** is the sibling forest estate model. Brushline borrows its compiled-dataset pattern, spatial
  discipline, run artifacts, and browser shell.
- **FHOPS** is the sibling operations planner. Brushline borrows its scenario contract, productivity
  and costing patterns, and 3D operations view.
- **Fresh Solutions** is the metaheuristic engine.
- **fresh-road** is the ALSroads road-status bridge.
- **Nemora** supplies fitting, sampling, synthetic landscapes, and uncertainty support.
- **GIS and asset registries** supply corridor geometry, structures, access, and treatment history.

## 4. Domain model

### 4.1 Corridor network

- **Corridor:** a linear asset and the land the owner manages along it, such as a transmission line,
  pipeline, railway, or road.
- **Segment:** the atomic decision unit. A length of corridor with stable site, vegetation, access,
  structure, and treatment attributes. It carries a linear reference, a geometry, a CRS, and a
  management standard.
- **Span:** a contiguous run of segments between access points, structures, or crossings. It is a
  runtime aggregate used for crew travel, work continuity, and reporting.
- **Treatment unit:** a set of segments scheduled and contracted together. It is a runtime aggregate,
  not a compilation unit.
- **Node and edge:** the corridor graph. Edges are segments; nodes are junctions, access points,
  structures, and endpoints. The graph supports adjacency, continuity, travel, and monitoring routes.

Fragments and blocks are not the Brushline vocabulary. A segment can be split for analysis, but the
compiled dataset and the plan use the segment as the stable key.

### 4.2 Vegetation state

A state is a vector of distributions over interpretable classes, plus continuous summaries:

- functional group: shrub, deciduous sprout, conifer, grass or herb, and site-specific additions;
- height class and continuous height;
- cover class and continuous cover;
- density or biomass class, where the data supports it;
- age since the last disturbance or treatment;
- treatment history and last observation;
- uncertainty: a distribution or interval per attribute, and a provenance record.

The state is not a single number. A plan that says "height 2.3 m" without an interval is incomplete.
A plan that says "no data" is a valid state, and it can trigger monitoring.

### 4.3 Treatment

A treatment is a method applied to a segment in a period:

- method: manual, mechanical, chemical, mowing, grazing, prescribed fire, or a site-specific method;
- intensity and selectivity;
- season and access window;
- immediate efficacy distribution: top-kill, mortality, cover reduction, debris;
- regrowth modifier: resprouting, delay, seed bank, competition release;
- cost build-up: labour, equipment, materials, travel, access, supervision, overhead, risk;
- constraints: weather, soil, slope, watercourse buffer, structure clearance, safety.

A treatment does not set vegetation to zero. It transitions the state, and the next growth step starts
from the transitioned state.

### 4.4 Observation

An observation is a measurement of a segment at a time:

- sensor: airborne LiDAR, UAV LiDAR, RGB or multispectral camera, field plot, or inspector record;
- product: DEM, DSM, CHM, canopy cover, height percentile, crown radius, species, treatment evidence;
- observation model: detection probability, measurement error, classification confusion, and
  coverage;
- provenance: bundle pin, checksum, acquisition date, CRS, resolution, licence, and model card.

An observation is evidence, not truth. It updates the state distribution and the model parameters.

### 4.5 Plan, scenario, run, and archive

- **Scenario:** the data versions, model versions, corridor selection, horizon, constraints, targets,
  prices, and seed.
- **Plan:** a versioned schedule of treatments and monitoring with quantities, costs, assumptions,
  risk notes, and provenance. It is the owner-contractor exchange object.
- **Run:** one execution of a build, simulation, or search, with its configuration and artifacts.
- **Pareto archive:** the non-dominated solutions from a multi-objective search, with their objective
  vectors, plan references, and evidence records.
- **Instance:** a versioned workspace with configuration, data pointers, compiled dataset, scenario,
  tests, runbooks, evidence, and documentation.

### 4.6 Identifiers and units

- Stable IDs: `corridor_id`, `segment_id`, `span_id`, `treatment_unit_id`, `plan_id`, `run_id`,
  `instance_id`.
- Units are explicit: metres, hectares, cubic metres, kilograms, CAD or the owner's currency, years,
  and dates.
- CRS is explicit and is never silently changed. A reprojection is a recorded decision with its own
  lineage.
- Time is a year or a period with a stated start and end. Operational time is a timestamp.

## 5. Vegetation dynamics

### 5.1 Functional groups and state variables

The first release targets the vegetation that actually threatens a corridor: shrubs, deciduous
sprouts, young conifers, and grasses or herbs. Mature timber is not the primary object, but mature
trees at the corridor edge are a fall-in hazard and a seed source.

The state variables are chosen for measurement, management, and tractability:

- height (m), cover (%), density (stems/ha or a class), biomass (kg/ha) where available;
- age since disturbance (years), and time since treatment;
- functional-group composition;
- site productivity, climate, and soil moisture proxies;
- disturbance and treatment history.

### 5.2 Growth model

The growth model is a calibrated state-transition model, not a mechanistic physiology model:

```text
s(t+1) = f(s(t), site, climate, disturbance, competition, uncertainty)
```

- Site and climate modifiers come from a provenance-bearing climate contract.
- Functional groups have different growth and shade-tolerance behaviour.
- Competition and canopy closure can slow or accelerate the target group.
- Disturbance (fire, insect, drought, wind, harvest) can reset or modify the trajectory.
- The model carries parameter uncertainty and residual uncertainty.
- The model has an explicit applicability domain: species, region, age, height, and data vintage.

The low-vegetation model is Brushline's own. Existing mature-forest EFI cards predict Lorey height,
basal area, and volume; they are not a shrub and young-tree model. A transfer test is required before
any of them is used on a low-vegetation target.

### 5.3 Treatment transitions

```text
s(t+) = g(s(t), treatment, season, site, uncertainty)
```

- Immediate effect: top-kill, mortality, cover reduction, height reduction, debris.
- Delayed effect: resprouting, regrowth delay, seed bank, competition release.
- Method-specific efficacy and selectivity, with distributions rather than point values.
- Cost and productivity are functions of the state, method, access, and terrain.
- A treatment can fail or be partial; the plan records the expected efficacy and the observed result.

### 5.4 Hazard and service indicators

- **Clearance:** the gap between vegetation height and the asset's required clearance.
- **Fall-in:** the probability that a stem or crown reaches the asset under wind or failure.
- **Fuel connectivity:** the continuity of the vegetation body along and across the corridor.
- **Access:** whether a crew, machine, or emergency response can reach the segment.
- **Reliability proxy:** the owner's outage or failure history, where available.
- **Treatment need:** a risk-weighted score that combines the indicators and the service standard.

Fire is treated as a hazard or expected-loss term. Brushline does not include a new fire-spread
simulator; the sibling fire work produced a documented negative result at the treated footprint.

### 5.5 Calibration and validation

- Calibration data: field plots, treatment history, inspection records, and LiDAR-derived metrics.
- Validation: held-out plots, spatial holdout, time-lag sensitivity, and a stated error.
- Model cards: model id, version, target, predictors, training data, validation design, RMSE or bias,
  applicability domain, licence, and caveats.
- A model outside its domain is flagged, not extrapolated silently.
- The validation record is part of the run and the plan.

## 6. Observation and monitoring

### 6.1 Observation sources

- **Open LiDAR:** LidarBC point clouds, DEM, DSM, CHM, canopy structure, optional individual-tree
  products, and ALS inventory attributes. Consumed through validated FEMIC bundles.
- **UAV LiDAR and imagery:** higher frequency, targeted coverage, and a smaller footprint.
- **Field plots and inspections:** the calibration and validation anchor.
- **Optical time series:** change detection and recovery context, not a real-time alert without a
  validated source and review path.
- **Road status:** ALSroads records through `fresh-road`, source-preserving and not an open/closed
  verdict.

### 6.2 Observation model

Each observation has:

- coverage: which segments, what fraction, and what is missing;
- detection probability and measurement error;
- classification confusion for functional groups;
- temporal offset from the state year;
- provenance: sensor, bundle, model card, licence, and processing version.

Missing coverage is a state of knowledge. It is not zero vegetation, and it is not a reason to
fabricate a measurement.

### 6.3 Monitoring as a decision

The monitoring decision includes:

- when to observe;
- which segments or spans;
- which sensor and resolution;
- the flight route and pattern;
- the sampling intensity;
- how to use the observation to recalibrate or replan.

The objective is the expected value of information: the reduction in expected decision loss per unit
of monitoring cost. The first release uses a tractable approximation, not a full POMDP.

### 6.4 Adaptive replanning

- Observations update the state distribution and the model parameters.
- A forecast-error or uncertainty trigger starts a replan.
- The replan uses the same scenario and plan contract, with a new version.
- The old plan and the observation are retained for audit.

## 7. Planning stack

### 7.1 Strategic planning

- Horizon: 10 to 30 years, annual resolution.
- Scope: corridor portfolio or region.
- Decisions: budget, service levels, risk appetite, treatment policy, monitoring policy, and the
  business-as-usual comparison.
- Outputs: multi-year budget and cash forecast, service-level trajectory, risk trajectory, monitoring
  policy, and a Pareto archive of trade-offs.

### 7.2 Tactical planning

- Horizon: 1 to 5 years, seasonal or quarterly resolution.
- Scope: treatment units, contractors, access, and monitoring missions.
- Decisions: which units, which methods, which contractors, which seasons, and which monitoring
  flights.
- Outputs: a contracting plan, a capacity plan, an access plan, a monitoring plan, and a cost
  build-up.

### 7.3 Operational planning

- Horizon: weeks to a season, daily or shift resolution.
- Scope: crews, machines, treatment units, and access.
- Decisions: work order, sequence, assignment, and daily schedule.
- Outputs: a work-ready plan, productivity and cost estimates, and an operations timeline for the 3D
  view.
- FHOPS is the adapter for machine and crew productivity and 3D operations when that fidelity is
  needed.

### 7.4 Cross-scale exchange

```text
strategic policy and budget
        |
        v
tactical units, contracts, access, monitoring
        |
        v
operational work plan and timeline
        |
        v
observed outcome and cost
        |
        v
state update and replan
```

All three scales share the same scenario, segment IDs, state version, and plan version. A scale may
coarsen or refine, but it does not rename the objects or fork the data.

### 7.5 Business-as-usual baseline

The baseline is a fixed cycle or the owner's current policy, simulated with the same data and model.
The comparison reports present cost, service-level attainment, risk, monitoring cost, and the
uncertainty. The optimized plan is only interesting if it beats the baseline on a stated measure.

## 8. Optimization stack

### 8.1 Why it is hard

The joint treatment and monitoring schedule is NP-hard:

- a segment-period-action assignment with a combinatorial number of combinations;
- budget and cash constraints by year;
- contractor capacity, seasonality, and access windows;
- spatial continuity and adjacency along the corridor graph;
- service-level and risk constraints;
- monitoring decisions that change the information available for later decisions;
- multiple objectives that trade cost, risk, service, and uncertainty.

There is no claim of optimality for realistic instances. Exact validation is limited to tiny
instances.

### 8.2 Decision variables

- treatment action per segment and period: none, method A, method B, ..., intensity level;
- monitoring action per span and period: none, sensor A, sensor B, ..., sampling intensity;
- contractor or resource assignment, where the tactical model includes it;
- optional timing within a season;
- optional plan-level budget and service-level choices.

### 8.3 Constraints

- hard: budget, cash, capacity, access, safety buffers, asset clearance, contractual windows;
- soft: service-level targets, risk targets, budget smoothness, workforce smoothness, equity;
- spatial: corridor continuity, adjacency, work-crew travel, monitoring route;
- temporal: green-up or regrowth delay, seasonality, monitoring intervals;
- data: coverage, applicability, and observation availability.

### 8.4 `fresh-solutions` adapter

Brushline implements a `ProblemAdapter`:

- `variable_count`, `option_count`, `option_at`;
- `initial_assignment`, `random_assignment`, `mutate`, `crossover`;
- `evaluate`, `evaluate_batch`;
- `propose`, `apply`, `undo`.

The exact evaluator is the Brushline simulator. The adapter uses incremental evaluation where it can
and falls back to the batch path where it cannot. `fresh-solutions` supplies local search, population
search, hybrid handoff, convergence stopping, checkpoints, seeds, telemetry, and replay.

### 8.5 Multi-objective layer

`fresh-solutions` is scalar by contract. Brushline adds a multi-objective layer:

- a portfolio of scalarizations over cost, risk, service, and uncertainty;
- a Pareto archive with dominance, diversity, and crowding;
- a `pareto.json` artifact with objective vectors, plan references, and evidence records;
- a promotion rule that turns a chosen archive member into a plan without rerunning the search.

### 8.6 Exact validation

- Exhaustive enumeration on a tiny instance with a known optimum.
- An independent mixed-integer or constraint-programming bound on a small instance where practical.
- A property test that the exact evaluator and the batch evaluator agree.
- A replay test for every reported incumbent.

### 8.7 Search budgets and evidence

- Every search records its seed, budget, stopping rule, and package versions.
- Every incumbent has an evidence record.
- A result is reported with its budget and its gap, not as a bare objective.
- A negative result is retained.

## 9. Plan and bid exchange

The plan is one versioned artifact:

- header: plan id, version, scenario, data version, model version, created date, author, status;
- corridor and segment selection;
- treatment units and actions;
- quantities: length, area, stems, volume, treatment hectares;
- cost build-up: labour, equipment, materials, travel, access, supervision, overhead, risk, margin;
- assumptions: rates, productivity, season, access, weather, site;
- risk notes and service-level evidence;
- monitoring actions and observations;
- provenance and approval record.

The owner view and the contractor view are two presentations of the same artifact:

- the owner sees budget, service levels, risk, and portfolio comparison;
- the contractor sees quantities, rates, access, schedule, and cost build-up;
- the comparison view attributes differences to named assumptions;
- a bid is an annotated plan, not a separate spreadsheet.

The plan exchange is a trust boundary. Every number is traceable to a source, a rate, or an
assumption. A number that cannot be traced is marked as an assumption or removed.

## 10. Instance builder and data pipeline

### 10.1 Boundary

FEMIC owns the instance workspace, the deterministic stage runner, the rebuild spec, the FreshForge
graph, data-catalogue discovery and fetch, DataLad and Arbutus materialization, preflight, the LiDAR
producer pipeline, inventory model cards, and site-index reconciliation.

Brushline adds a small FEMIC extension and instance template:

- `brushline.validate_aoi`;
- `brushline.segment_corridor`;
- `brushline.compile_dataset`;
- `brushline.seed_vegetation_state`;
- `brushline.validate_scenario`;
- `brushline.build_demo`.

The extension is optional. Brushline core can build, validate, and simulate a supplied dataset without
it.

### 10.2 Stage chain

```text
AOI intent
  -> data-availability scan
  -> fetch plan and approvals
  -> materialization
  -> preprocessing (LiDAR, terrain, canopy, inventory, access)
  -> corridor segmentation
  -> dataset compilation
  -> vegetation state seeding
  -> scenario and target scaffold
  -> dry-run validation
  -> review and handoff
  -> optional demo export
```

Each stage has an input contract, an output artifact, a deterministic tool, a validator, and a failure
mode. A stage cannot be skipped by the agent.

### 10.3 Agent layer

- The agent is optional. It plans, selects sources, drafts configuration, explains failures, and asks
  for approvals.
- The agent calls an allowlisted tool set. It does not browse arbitrary files, run arbitrary commands,
  or read private data without an approved connector.
- A capability is a prompt, a tool allowlist, a validator over real state, and a bounded retry budget.
- No validator, no capability.
- The agent never produces an authoritative number, coefficient, geometry, or validation result.
- A failed validator stops the capability and reports the evidence; it does not trigger a silent
  retry with a different assumption.

### 10.4 Data sources

Public sources include LidarBC, VRI, VDYP, SIBEC, DRA, FTEN, NTEMS, climate, BEC, ownership, and
protected areas. Private sources include the owner's asset registry, treatment history, inspections,
cost rates, contracts, and access restrictions.

Each source has a manifest: provider, dataset, query, vintage, CRS, licence, checksum, size, and
retrieval date. Large payloads stay in DataLad, an annex, or the owner's storage.

### 10.5 Public and private separation

- Public data can enter the public demo portal.
- Private data stays in a separate private deployment.
- The agent sees metadata only until the owner approves a connector.
- Credentials stay in the environment or a secret store, never in the repository.
- The prompt and the model provider never receive private rows.
- Derived artifacts are reviewed before they leave the owner's tenancy.

### 10.6 Instance layout

```text
instance/
  config/                 # scenario, targets, model cards, run profile
  data/                   # pointers, manifests, small fixtures
  dataset/                # compiled Brushline dataset
  scenarios/              # scenario and plan templates
  runs/                   # simulation and search artifacts
  tests/                  # contract and smoke tests
  runbooks/               # operator and agent runbooks
  docs/                   # instance documentation
  evidence/               # validation and close-out evidence
  README.md
```

The instance is a versioned repository. It does not carry large LiDAR or private payloads.

## 11. Artifacts and contracts

### 11.1 Compiled dataset

- Versioned columnar dataset with a manifest.
- Tables: segments, corridor graph, site, vegetation state, treatments, observations, access,
  structures, costs, and model cards.
- Schema validation, referential integrity, CRS and units checks, and a content digest.
- The simulator and planner read only this dataset.

### 11.2 Run directory

```text
run/
  run.json               # config, versions, seed, status
  plan.json              # or plan.csv plus a header
  schedule.csv           # segment, action, period
  account_values.csv     # service, risk, cost, quantity
  pareto.json            # archive, if a multi-objective search
  operations_timeline.jsonl
  telemetry.jsonl
  reports/
```

Every artifact is optional only if the run type does not produce it. The studio names the missing
artifact instead of showing an empty panel.

### 11.3 Plan artifact

A JSON header plus CSV or Parquet tables. It is readable by a human and by the studio. It carries the
cost build-up and the assumptions.

### 11.4 Pareto archive

`pareto.json` carries the objective names, directions, units, archive members, plan references,
evidence records, and the scalarization portfolio.

### 11.5 Operations timeline

`operations_timeline.jsonl` carries timestamped events: crew or machine id, segment or span, action,
start, end, state, and cost. It drives the 2D and 3D animation. It is a simulation artifact, not a
live telemetry feed.

### 11.6 Demo manifest

`brushline.demo.v1` carries the instance id, title, sector, region, AOI, data sources and licences,
scenarios, artifacts, headline metrics, caveats, contact, and status.

### 11.7 Provenance

Every dataset, plan, run, archive, and demo manifest carries:

- package version and adapter version;
- data versions and manifest digests;
- model ids and versions;
- configuration and seed;
- `fresh-solutions` version for a search;
- licence and attribution;
- creation time and operator or agent id.

## 12. Interfaces

### 12.1 Command line

The command surface grows by phase:

```text
brushline build       # compile a corridor dataset
brushline simulate    # replay a plan
brushline plan        # strategic, tactical, or operational search
brushline monitor     # plan and evaluate observations
brushline compare     # compare plans, bids, or scenarios
brushline validate    # validate a dataset, plan, or archive
brushline report      # write a report
brushline serve       # start the studio
brushline demo        # build or serve the demo portal
brushline instance    # delegate to the FEMIC extension
```

### 12.2 Python API

The same operations are available as typed functions and classes. The API is the stable surface; the
CLI is a thin wrapper.

### 12.3 Web API

The studio exposes read-only endpoints over artifacts, plus allowlisted actions such as target edits,
a search start, a pause or stop, and a demo build. The service does not compute a value the CLI cannot
reproduce.

### 12.4 GIS interchange

GeoPackage, GeoJSON, and columnar formats with an explicit CRS. The source CRS is preserved; a
consumer-side reprojection is recorded.

## 13. Interactive planning studio

### 13.1 One application, several skins

The studio is one optional FastAPI service and one static browser shell. Skins are checked manifests:

| Skin | Primary user | Read-only |
| --- | --- | --- |
| `model-builder` | Analyst or agent building a new instance | no |
| `owner-strategic` | Asset owner executive and program manager | no |
| `tactical-planner` | Tactical planner | no |
| `operations-planner` | Field operations supervisor | no |
| `contractor-bid` | Contractor estimator | no |
| `monitoring` | Monitoring specialist | no |
| `reviewer` | Reviewer, auditor, or community liaison | yes |

A read-only skin cannot carry a mutating action. The loader enforces the rule.

### 13.2 2D map

MapLibre over vendored assets. Layers:

- corridor and segment geometry;
- vegetation height, cover, and uncertainty;
- treatment need and risk;
- planned, current, and cumulative treatments;
- monitoring coverage and gaps;
- access and road status;
- structures and crossings;
- bid deltas and scenario comparison.

The period strip folds years into the plan's periods. The layer tree groups the layers and names the
reason a layer is unavailable.

### 13.3 3D scene

Three.js over a DEM with:

- terrain and hillshade;
- corridor and structures;
- vegetation height and cover, as instanced or impostor geometry;
- mature-tree crowns where a tree product exists;
- machines, crews, and treatment units from the operations timeline;
- play, pause, speed, and timeline controls;
- a shared selection and time state with the 2D map.

The 3D scene is a context view. It is not survey-grade geometry and does not claim field accuracy.

### 13.4 Live search and Pareto explorer

- SSE streams progress, incumbent values, target values, and schedule changes.
- Pause and stop write a control file; the search writes its best schedule and summary.
- The Pareto explorer shows the objective vectors, dominance, parallel coordinates, a scatter matrix,
  and a scenario comparison.
- A chosen archive member can be promoted into the plan without rerunning the search.

### 13.5 Security and deployment

- Loopback bind by default.
- `--allow-remote` is explicit; the first release has no authentication.
- Actions are allowlisted; arbitrary commands and uploads are refused.
- Read-only skins are enforced in the loader.
- Relative URLs work behind a proxy prefix.
- The service reads artifacts; it does not own model state.

## 14. Demo portal

The demo portal is a separate public-data-only, read-only surface:

- a catalogue of four to six curated instances, one per partner question;
- a landing page, instance pages, a comparison view, a methods page, and a pilot-request path;
- a static-first build for GitHub Pages from precomputed runs;
- an optional read-only service for a lab preview behind the lab's access gate;
- a `brushline.demo.v1` manifest per instance;
- no private data, no arbitrary uploads, and no arbitrary searches.

The portal reuses the WS4 public demo shell and skins, the FHOPS operations scene, the Fresh Fire
Studio static export and 3D level-of-detail, the Fresh Woodlots catalogue and pilot framing, and the
urban-forest lab 2D/3D shell.

## 15. Integration architecture

### 15.1 FEMIC

- Producer of `femic.lidar.product.v1` bundles, terrain, canopy, tree, ALS inventory, model cards,
  climate, disturbance, and road-status contracts.
- Provider of the instance workspace, rebuild spec, FreshForge graph, catalogue, DataLad, and
  preflight.
- Brushline consumes the contracts and extends the provider vocabulary. It does not fork the
  pipeline.

### 15.2 WS4

- Sibling estate model.
- Brushline borrows the compiled-dataset pattern, spatial discipline, run artifacts, and browser shell.
- A WS4 adapter can exchange scenarios, accounts, and plans without making WS4 a dependency of
  Brushline core.

### 15.3 FHOPS

- Sibling operations planner.
- Brushline borrows the scenario contract, productivity and costing patterns, and 3D operations view.
- A FHOPS adapter turns a Brushline treatment unit into an FHOPS scenario and returns the productivity,
  cost, and timeline artifacts.

### 15.4 Fresh Solutions

- Metaheuristic engine, versioned optional dependency.
- Brushline implements the adapter and consumes the engine.
- No fork and no copy of the engine.

### 15.5 fresh-road

- ALSroads road-status bridge.
- Brushline consumes `fresh.road.status.v1` as access evidence, preserving the source class.
- No open/closed inference without a management decision.

### 15.6 Nemora

- Distribution fitting, sampling, synthetic landscapes, and uncertainty support.
- Brushline uses it for calibration uncertainty and test fixtures.
- It is not a second fitting stack.

### 15.7 Urban-forest lab

- Sibling 2D/3D studio.
- Brushline borrows the FastAPI plus static shell, vendored MapLibre and Three.js, offline-capable
  assets, and shared selection state.

## 16. Performance and scale

The target scale is 10,000 to 1,000,000 segments, a 30-year horizon, and many scenarios. The design
uses:

- columnar data and vectorized state transitions;
- sparse or class-based state storage;
- incremental evaluation for the search;
- parallel scenarios and islands;
- cached terrain, canopy, and route products;
- vector tiles or PMTiles for the map;
- level-of-detail and instancing for the 3D scene;
- streamed artifacts for the studio.

The first performance target is provisional until the prototype measures the real cost.

## 17. Security, privacy, and safety

- Public demo: public or synthetic data only, read-only, no uploads.
- Private deployment: access controls, scoped connectors, audit logs, and no private rows in prompts
  or model-provider requests.
- Credentials: environment or secret store, never tracked.
- Repository: no private data, personal paths, raw transcripts, or credentials.
- Safety: Brushline is decision support. Field verification, qualified judgment, and the owner's work
  control rules govern any treatment near energised lines, pipelines, or roads.
- The 3D scene is labelled as a context view, not an engineering model.

## 18. Testing and verification

- Unit tests for every function and method.
- Contract tests for the dataset, plan, archive, timeline, demo manifest, and API.
- Integration tests for the CLI and the FEMIC provider nodes.
- Property tests for state conservation, schedule validity, Pareto dominance, and replay.
- Offline tests for agent capabilities with a fake provider.
- Golden fixtures for the synthetic corridor and the LiDAR bundle.
- A self-check that the planning surfaces pass the workflow validator.
- A green dashboard on every commit.

## 19. Open questions

| Question | Resolve in |
| --- | --- |
| Which functional groups and state thresholds are tractable and interpretable? | P1 and P4 |
| What calibration data exists for low vegetation, and how hierarchical must the model be? | P3 and P4 |
| How should uncertainty reach the objective and the Pareto archive? | P1 and P5 |
| Which stages belong in FEMIC's provider vocabulary and which in the instance template? | P2 |
| How stable is the FreshForge provider API? | P2 |
| Which parts of the schedule are exact and which are metaheuristic? | P5 |
| What is the observation model for LiDAR, imagery, and field samples? | P8 |
| How is value of information approximated at corridor scale? | P8 |
| How are multi-objective weights, normalization, and promotion audited? | P5 and P10 |
| What does a fair contractor cost build-up contain? | P9 |
| Which demo instances make the strongest pilot case? | P11 |
| How much 3D fidelity is useful before it implies survey precision? | P0 and P10 |
| What real or synthetic case validates the optimal-versus-BAU claim? | P12 |

## 20. Decision records

The architecture is constrained by the ADRs in `notes/adr/`:

- 0001: segments are the decision unit;
- 0002: vegetation state is a distribution;
- 0003: treatments are transitions;
- 0004: three scales share one scenario and plan contract;
- 0005: monitoring is a decision;
- 0006: optimization is an adapter over `fresh-solutions`;
- 0007: the studio reads artifacts and skins are manifests;
- 0008: FEMIC owns LiDAR production and the instance builder;
- 0009: low-vegetation calibration is Brushline's own model;
- 0010: the public demo portal is read-only and public-data-only;
- 0011: reproducibility and provenance travel with every artifact.
