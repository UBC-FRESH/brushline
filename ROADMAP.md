# Brushline Roadmap

This roadmap is the plan of record and the issue tracker map for Brushline. Keep it in step with the
GitHub issues, `CHANGE_LOG.md`, and `notes/`. `scripts/check_workflow.py` parses the phase headers,
status lines, and checkboxes below, so keep their format.

Every phase starts as `planned` with `Parent issue: TBD`. Activate a phase only after its parent issue
exists and the maintainer approves it.

## Issue Tracker Map

| Phase | Parent issue | Branch | Status |
| --- | --- | --- | --- |
| P0 Bootstrap and scope | #1 | `feature/p0-bootstrap` | complete |
| P1 Contracts and prototype | #15 | `feature/p1-contracts-prototype` | complete |
| P2 FEMIC-extended instance builder | #24 | `feature/p2-instance-builder` | complete |
| P3 State, LiDAR, and terrain | #33 | `feature/p3-state-lidar` | complete |
| P4 Vegetation dynamics and treatments | #41 | `feature/p4-vegetation` | complete |
| P5 Optimization framework and Pareto search | #50 | `feature/p5-optimization` | complete |
| P6 Strategic planning and monitoring policy | #60 | `feature/p6-strategic` | active |
| P7 Tactical and operational planning | TBD | `feature/p7-tactical-operational` | planned |
| P8 Monitoring and adaptive replanning | TBD | `feature/p8-monitoring` | planned |
| P9 Plan and bid exchange | TBD | `feature/p9-plan-exchange` | planned |
| P10 Interactive planning studio | TBD | `feature/p10-studio` | planned |
| P11 Demo portal and pilot onboarding | TBD | `feature/p11-demo-portal` | planned |
| P12 Verification and the BAU case | TBD | `feature/p12-verify` | planned |
| P13 Release and deploy | TBD | `feature/p13-release` | planned |
| P14 Operate and maintain | TBD | `feature/p14-operate` | planned |

## Lifecycle Map

| Stage | Phases | Exit criteria |
| --- | --- | --- |
| Scope and design | P0 | Problem, users, scope, architecture, decisions, and phase map recorded |
| Contracts and prototype | P1 | Data, plan, run, archive, timeline, and demo contracts defined; smallest end-to-end prototype exercises them |
| Build | P2-P9 | Instance builder, state, LiDAR, dynamics, optimization, planning scales, monitoring, and exchange implemented one task at a time |
| Experience | P10-P11 | Planning studio and public demo portal implemented, tested, and deployable |
| Verify | P12 | Acceptance criteria and the optimal-versus-BAU case have evidence |
| Release and deploy | P13 | Tagged release, published artifacts and docs, verified from a clean checkout |
| Operate and maintain | P14 | Review cadence held, incoming ideas triaged, pilots supported, retirement decided and recorded |

## Conventions

- A phase is `P<n>`. A task is `P<n>.<m>`. A subtask is a checklist item inside the task's issue body.
  Three levels at most.
- Status values are `planned`, `active`, `pr-open`, `complete`, and `deferred`.
- A phase becomes `complete` only after its pull request merges to `main` and its parent issue closes.
- Every phase leaves `python scripts/dashboard.py` green.

## Phase 0: Bootstrap and scope

Parent issue: #1
Branch: `feature/p0-bootstrap`
Status: complete

Goal: give Brushline its identity, package, operating contract, product scope, architecture, decisions,
and phase map, and queue a reviewable close-out.

- [x] P0.1 Adapt the operating contract and repository identity (#2)
  - [x] Domain rules in `AGENTS.md`, the README, contribution guide, licence, conduct policy, and citation
- [x] P0.2 Add the package skeleton and the `brushline` command (#3)
  - [x] `pyproject.toml`, the package, the CLI, the API docs page, and the CLI tests
- [x] P0.3 Write the problem statement, users, and scope (#4)
  - [x] `notes/design/brushline-scope.md`
- [x] P0.4 Record the architecture and key decisions (#5)
  - [x] `notes/design/brushline-architecture.md` and ADRs 0001 to 0012
- [x] P0.5 Define the phase map and the success criteria (#6)
  - [x] This roadmap, the lifecycle map, and the detailed next steps
- [x] P0.6 Make the dashboard green and queue the close-out (#7)
- [x] P0.7 Record the interactive planning studio and solution-explorer design (#8)
  - [x] `notes/design/brushline-ui.md` and the UI ADR references
- [x] P0.8 Record the optimization framework and multi-objective search design (#9)
  - [x] `notes/design/brushline-optimization.md` and the optimization ADR references
- [x] P0.9 Record the open LiDAR, terrain, canopy, and reuse design (#10)
  - [x] `notes/design/brushline-lidar-and-open-data.md` and the LiDAR ADR references
- [x] P0.10 Record the FEMIC-extended instance builder and open-data onboarding design (#11)
  - [x] `notes/design/brushline-instance-builder.md` and the instance-builder ADR references
- [x] P0.11 Record the demo portal and partner-onboarding design (#12)
  - [x] `notes/design/brushline-demo-portal.md` and the demo ADR references
- [x] P0.12 Review open shrub and young-tree growth models (#13)
  - [x] `notes/reference/shrub-young-tree-growth-models.md` and `notes/reference/codex-library-search-prompt.md`

Acceptance criteria:

- The repository identifies its licence, citation, conduct policy, and contribution path.
- `python -m pip install -e .` installs a package whose `brushline --version` and `brushline --help` work.
- The scope, architecture, ADRs, phase map, UI, optimization, LiDAR, instance-builder, demo-portal, and
  literature-review notes are present and consistent.
- `python scripts/dashboard.py` reports `OVERALL: GREEN`.
- The close-out report is queued for maintainer approval.

## Phase 1: Contracts and prototype

Parent issue: #15
Branch: `feature/p1-contracts-prototype`
Status: complete

Goal: fix the data, plan, run, archive, timeline, and demo contracts, and build the smallest end-to-end
prototype that exercises them on synthetic data.

- [x] P1.1 Define the compiled corridor dataset and manifest contract
  - [x] Tables, keys, units, CRS, schema version, validator, and manifest
- [x] P1.2 Define the corridor, segment, span, and treatment-unit contract
  - [x] Graph, linear referencing, geometry, access, structures, and service standards
- [x] P1.3 Define the vegetation state, treatment, and observation contract
  - [x] Functional groups, state classes, distributions, treatment actions, observation records
- [x] P1.4 Define the plan, run, Pareto archive, operations timeline, and demo manifest contracts
  - [x] JSON/CSV/Parquet shapes, provenance fields, versioning, and examples
- [x] P1.5 Build a synthetic corridor fixture
  - [x] Two corridors, mixed growth, access, structures, monitoring gaps, and a known optimum case
- [x] P1.6 Build the end-to-end prototype
  - [x] Compile, grow, treat, simulate, report, and write a run directory
- [x] P1.7 Add contract validation and property tests
  - [x] Every schema has a failing case; every invariant has a property test

Acceptance criteria:

- A synthetic corridor compiles, simulates, and reports from the CLI.
- The dataset round-trips through its schema and validates against its manifest.
- The prototype writes every artifact the studio needs, even if some are empty.
- A deliberately malformed dataset, plan, or archive fails with a named error.
- The dashboard is green.

## Phase 2: FEMIC-extended instance builder

Parent issue: #24
Branch: `feature/p2-instance-builder`
Status: complete

Goal: extend FEMIC's instance, rebuild-spec, FreshForge, catalogue, DataLad, and preflight surfaces to
build Brushline instances from a map-selected AOI. Do not create a second instance-builder package.

- [x] P2.1 Record and pin the FEMIC extension boundary and provider API
  - [x] Version pin, entry points, compatibility policy, and a failing test if the API drifts
- [x] P2.2 Add the Brushline instance template and rebuild spec
  - [x] Config, scenario, targets, data pointers, tests, runbooks, docs, evidence, and demo manifest
- [x] P2.3 Add the Brushline provider nodes
  - [x] `validate_aoi`, `segment_corridor`, `compile_dataset`, `seed_vegetation_state`,
        `validate_scenario`, `build_demo`
- [x] P2.4 Add the data catalogue and connector registry
  - [x] Public sources, private connectors, licences, classifications, and allowlists
- [x] P2.5 Add the fetch plan, materialization, coverage, and gap report
  - [x] Plan-only preview, checksums, DataLad/annex pointers, coverage state, and gap report
- [x] P2.6 Add the agent capability contract and offline test harness
  - [x] Prompt, tool allowlist, validator, retry budget, fake provider, and evidence record
- [x] P2.7 Build the map-to-instance prototype and review screen
  - [x] AOI draw/select, data availability, approvals, progress, gap report, and instance handoff

Acceptance criteria:

- A new Brushline instance is scaffolded and built through FEMIC's instance and FreshForge surfaces.
- The extension is optional; Brushline core installs and simulates without FEMIC.
- A missing source, licence, or coverage gap stops the build or is reported, not fabricated.
- Private data cannot reach a prompt, a tracked file, or a public artifact without approval.
- Every capability has a validator that can fail and an offline fake-provider test.
- The dashboard is green.

## Phase 3: State, LiDAR, and terrain

Parent issue: #33
Branch: `feature/p3-state-lidar`
Status: complete

Goal: initialize the segment state from validated open LiDAR, terrain, canopy, inventory, and field data,
with coverage and applicability made explicit.

- [x] P3.1 Add the FEMIC LiDAR bundle adapter and provenance
  - [x] Bundle pin, checksums, CRS, vertical datum, resolution, licence, and product validation
- [x] P3.2 Map terrain and slope to segment support
  - [x] DEM/DSM support, aggregation rules, access proxy, and no silent reprojection
- [x] P3.3 Map canopy, cover, and optional tree products
  - [x] CHM, canopy structure, tree counts, crown radius, and VRI comparison evidence
- [x] P3.4 Initialize the vegetation state
  - [x] Link LiDAR metrics, inventory, field plots, and treatment history to state classes
- [x] P3.5 Report coverage, applicability, and observation gaps
  - [x] No point cloud, no contemporary DEM, out-of-domain model, and missing plot data
- [x] P3.6 Benchmark the adapter against the FEMIC/WS4/FHOPS consumer values
  - [x] Same bundle, same polygons, same aggregation; record the differences

Acceptance criteria:

- A validated FEMIC bundle maps to segment support with a recorded aggregation.
- Every derived attribute carries the bundle pin, product checksum, model card, and applicability.
- Missing coverage is a knowledge state, not a zero.
- The adapter does not download tiles or compile terrain.
- The benchmark against the sibling consumers agrees within a stated tolerance.
- The dashboard is green.

## Phase 4: Vegetation dynamics and treatments

Parent issue: #41
Branch: `feature/p4-vegetation`
Status: complete

Goal: implement the low-vegetation state-transition model and the treatment transitions, calibrate them,
and publish a model card.

- [x] P4.1 Define functional groups and state discretization
  - [x] Shrub, deciduous sprout, conifer, grass/herb; height, cover, density, age, and uncertainty
- [x] P4.2 Implement the growth model
  - [x] Saturating height/cover curves, site and climate modifiers, competition, and functional groups
- [x] P4.3 Implement the treatment transitions
  - [x] Method, season, efficacy, selectivity, resprouting, regrowth delay, and cost hooks
- [x] P4.4 Calibrate the treatment efficacy and resprouting
  - [x] Brushing, mowing, herbicide, manual, and grazing evidence where available
- [x] P4.5 Implement the hazard and service indicators
  - [x] Clearance, fall-in, fuel connectivity, access, and a reliability proxy
- [x] P4.6 Calibrate and validate against held-out plots and LiDAR
  - [x] Spatial holdout, time-lag sensitivity, benchmark against MEDFATE/FVS-FFE/Botequim-type curves
- [x] P4.7 Publish the model card and uncertainty contract
  - [x] Model id, version, predictors, training data, validation, error, domain, licence, caveats

Acceptance criteria:

- The growth model reproduces held-out observations within a stated error by functional group.
- A treatment reduces height/cover and changes the subsequent trajectory; it does not reset to zero.
- The model card flags an out-of-domain segment instead of extrapolating silently.
- The benchmark against at least one candidate is recorded, including disagreement.
- The dashboard is green.

## Phase 5: Optimization framework and Pareto search

Parent issue: #50
Branch: `feature/p5-optimization`
Status: complete

Goal: implement the Brushline adapter over Fresh Solutions, the multi-objective archive, and the exact
small-instance validation.

- [x] P5.1 Formulate the decision variables, constraints, and objective vector (#51)
  - [x] Treatment and monitoring actions, budget, capacity, access, service levels, risk, uncertainty
- [x] P5.2 Implement the exact evaluator and the incremental path (#52)
  - [x] Simulator-backed evaluation, full-recompute fallback, and batch evaluation
- [x] P5.3 Implement the move operators (#53)
  - [x] Toggle, shift, swap, block/segment moves, monitoring moves, and repair
- [x] P5.4 Integrate Fresh Solutions and exact replay (#54)
  - [x] Adapter, local search, population, hybrid, convergence, checkpoints, seeds, and evidence
- [x] P5.5 Implement the multi-objective archive and `pareto.json` (#55)
  - [x] Scalarization portfolio, dominance, diversity, archive members, and promotion rule
- [x] P5.6 Validate on tiny instances (#56)
  - [x] Exhaustive enumeration, exact/batch agreement, known optimum, and replay
- [x] P5.7 Certify the search budget and performance (#57)
  - [x] Quality-versus-budget curve, seed variance, scaling, and the no-optimality statement
- [x] P5.8 Freeze the archive and telemetry contract for the studio (#58)
  - [x] `pareto.json`, progress events, incumbent records, and evidence links

Acceptance criteria:

- The adapter satisfies the Fresh Solutions contract and replays every reported incumbent.
- The Pareto archive keeps only non-dominated solutions and preserves diversity.
- A tiny instance reaches the known optimum within a stated budget, or the gap is reported.
- The core install works without the `opt` extra; planning requires it.
- The dashboard is green.

## Phase 6: Strategic planning and monitoring policy

Parent issue: #60
Branch: `feature/p6-strategic`
Status: active

Goal: implement the 10-to-30-year strategic plan: budget, service levels, risk appetite, monitoring
policy, and the business-as-usual comparison.

- [x] P6.1 Implement the single-segment dynamic program (#61)
  - [x] State classes, actions, transition probabilities, discounting, and a policy
- [ ] P6.2 Implement the network portfolio search
  - [ ] Budget, service levels, risk, spatial continuity, and contractor capacity at strategic scale
- [ ] P6.3 Implement the monitoring policy
  - [ ] Frequency, route, sensor, sampling intensity, and value-of-information approximation
- [ ] P6.4 Implement the business-as-usual baseline
  - [ ] Fixed cycle, current policy, and like-for-like simulation
- [ ] P6.5 Build the strategic reports
  - [ ] Budget and cash forecast, service trajectory, risk trajectory, monitoring cost, and caveats
- [ ] P6.6 Add the scenario archive and reproducibility record
  - [ ] Data/model/config/seed versions and replay
- [ ] P6.7 Validate the strategic plan on the synthetic corridor
  - [ ] Service levels met, budget respected, and the BAU comparison measured

Acceptance criteria:

- A strategic plan covers the horizon and respects the budget and service-level constraints.
- The monitoring policy is a decision, not a fixed calendar.
- The BAU comparison reports present cost, service attainment, risk, and uncertainty.
- The plan is reproducible from its scenario and seed.
- The dashboard is green.

## Phase 7: Tactical and operational planning

Parent issue: TBD
Branch: `feature/p7-tactical-operational`
Status: planned

Goal: turn the strategic policy into a 1-to-5-year treatment program and a work-ready operational plan.

- [ ] P7.1 Implement the multi-year tactical program
  - [ ] Treatment units, methods, seasons, and contractor allocation
- [ ] P7.2 Implement contractor capacity, productivity, and cost
  - [ ] Crews, machines, rates, travel, supervision, overhead, and risk
- [ ] P7.3 Integrate access and road status
  - [ ] fresh-road/ALSroads, route length, access windows, and no invented open/closed verdict
- [ ] P7.4 Generate the operational work plan
  - [ ] Work order, sequence, assignment, and daily schedule
- [ ] P7.5 Build the FHOPS adapter
  - [ ] Brushline treatment unit to FHOPS scenario; return productivity, cost, and timeline
- [ ] P7.6 Build the operations timeline and 3D data contract
  - [ ] Timestamped events, crew/machine ids, segments, actions, and cost
- [ ] P7.7 Validate tactical and operational feasibility
  - [ ] Capacity, access, seasonality, and a dry-run work plan

Acceptance criteria:

- A tactical plan is feasible against capacity, access, and seasonality.
- The operational plan is work-ready and traceable to the tactical plan.
- The FHOPS adapter is optional and versioned.
- The operations timeline drives a 2D and 3D animation without invented positions.
- The dashboard is green.

## Phase 8: Monitoring and adaptive replanning

Parent issue: TBD
Branch: `feature/p8-monitoring`
Status: planned

Goal: implement the observation model, the UAV/LiDAR mission simulation, value of information, and the
recalibration and replanning loop.

- [ ] P8.1 Implement the observation model
  - [ ] Coverage, detection, measurement error, classification confusion, and latency
- [ ] P8.2 Implement the UAV/LiDAR mission simulation
  - [ ] Corridor graph, travel, endurance, sensor footprint, weather windows, and cost
- [ ] P8.3 Implement coverage and value of information
  - [ ] Expected decision loss, monitoring cost, and a tractable approximation
- [ ] P8.4 Implement recalibration
  - [ ] State update, parameter update, uncertainty update, and a model-card record
- [ ] P8.5 Implement the adaptive replanning trigger
  - [ ] Forecast error, uncertainty, and a new plan version
- [ ] P8.6 Validate the monitoring policy against a fixed calendar
  - [ ] Regret per monitoring dollar on a synthetic case, with the assumptions stated

Acceptance criteria:

- The observation model is explicit and testable.
- A monitoring mission is feasible on the corridor graph and priced.
- The adaptive policy beats a fixed calendar on expected regret per dollar, or the result is reported as
  a negative finding.
- A recalibration produces a new state and a recorded model update.
- The dashboard is green.

## Phase 9: Plan and bid exchange

Parent issue: TBD
Branch: `feature/p9-plan-exchange`
Status: planned

Goal: make one versioned plan artifact the shared surface for the owner and the contractor, with a
traceable cost build-up and a fair-bid comparison.

- [ ] P9.1 Implement the plan schema and cost build-up
  - [ ] Header, segments, actions, quantities, rates, assumptions, risk, provenance, and approval
- [ ] P9.2 Build the owner view
  - [ ] Budget, service levels, risk, portfolio, and BAU comparison
- [ ] P9.3 Build the contractor bid view
  - [ ] Quantities, access, schedule, productivity, cost build-up, and assumptions
- [ ] P9.4 Build the bid normalization and comparison
  - [ ] Named assumptions, rate differences, scope differences, and a fair-price range
- [ ] P9.5 Add the audit trail and approval record
  - [ ] Data/model/plan versions, reviewer, and approval status
- [ ] P9.6 Validate the exchange on a synthetic owner-contractor case
  - [ ] Same artifact, same cost total, every difference attributable

Acceptance criteria:

- The owner view and the contractor view derive from one plan artifact.
- The cost build-up reproduces to the cent.
- Every bid difference is attributable to a named assumption.
- The plan records its provenance and approval.
- The dashboard is green.

## Phase 10: Interactive planning studio

Parent issue: TBD
Branch: `feature/p10-studio`
Status: planned

Goal: deliver the optional FastAPI service and static browser shell with the 2D map, 3D scene, seven
skins, live search, Pareto explorer, and animated operations.

- [ ] P10.1 Implement the service and artifact endpoints
  - [ ] Summary, run, plan, accounts, targets, reports, layers, periods, Pareto, timeline, and skins
- [ ] P10.2 Build the 2D map shell
  - [ ] MapLibre, layer tree, period strip, segment selection, treatment/cumulative/monitoring layers
- [ ] P10.3 Build the 3D scene
  - [ ] Three.js, DEM, corridor, vegetation, structures, operations timeline, shared selection/time
- [ ] P10.4 Implement the seven skins
  - [ ] `model-builder`, `owner-strategic`, `tactical-planner`, `operations-planner`,
        `contractor-bid`, `monitoring`, `reviewer`; read-only enforcement
- [ ] P10.5 Implement live search
  - [ ] SSE progress, incumbent, target values, schedule changes, pause, and stop
- [ ] P10.6 Implement the Pareto explorer
  - [ ] Objective vectors, dominance, parallel coordinates, scatter matrix, comparison, promotion
- [ ] P10.7 Implement the operations animation
  - [ ] Play, pause, speed, timeline, and 2D/3D synchronization
- [ ] P10.8 Test and deploy the studio
  - [ ] Contract tests, browser tests, accessibility, proxy prefix, loopback, and read-only skins

Acceptance criteria:

- The studio reads only artifacts; the service holds no model state.
- The 2D and 3D views share one selection and time state.
- A read-only skin cannot carry a mutating action.
- The Pareto explorer can promote a solution without rerunning the search.
- The animation reads the operations timeline and invents no positions.
- The dashboard is green.

## Phase 11: Demo portal and pilot onboarding

Parent issue: TBD
Branch: `feature/p11-demo-portal`
Status: planned

Goal: publish a public-data-only, read-only demo portal with curated instances and a pilot-request path.

- [ ] P11.1 Define the demo portfolio and narratives
  - [ ] Four to six instances, each answering a partner question, with headline metrics and caveats
- [ ] P11.2 Implement the `brushline.demo.v1` manifest and static builder
  - [ ] `brushline demo build`, validation, links, licences, and a GitHub-Pages-compatible export
- [ ] P11.3 Build the instance pages
  - [ ] 2D map, 3D scene, plan timeline, target/account charts, Pareto explorer, methods, caveats
- [ ] P11.4 Build the pilot funnel and data boundary
  - [ ] Pilot brief, data-request checklist, success metrics, security/NDA path, and contact
- [ ] P11.5 Deploy the permanent and lab-preview surfaces
  - [ ] GitHub Pages, optional read-only service, proxy prefix, health, and access gate
- [ ] P11.6 Validate the portal
  - [ ] No private data, no broken links, every licence present, every caveat present, accessibility

Acceptance criteria:

- The public portal contains only public or synthetic data.
- The static export works without a server; the optional service is read-only by default.
- Every demo page separates "what this shows" from "what this does not show".
- The pilot-request path states what data is needed and how it is protected.
- The dashboard is green.

## Phase 12: Verification and the BAU case

Parent issue: TBD
Branch: `feature/p12-verify`
Status: planned

Goal: show that the build meets its acceptance criteria, with evidence, and demonstrate the
optimal-versus-business-as-usual value proposition.

- [ ] P12.1 Run the acceptance suite
  - [ ] Every success criterion in the scope, with evidence
- [ ] P12.2 Run the optimal-versus-BAU case
  - [ ] Present cost, service attainment, risk, and uncertainty on a synthetic or public case
- [ ] P12.3 Verify the monitoring value
  - [ ] Adaptive policy versus fixed calendar, with the observation model and assumptions
- [ ] P12.4 Verify the owner-contractor exchange
  - [ ] Same plan, same cost total, attributable differences
- [ ] P12.5 Verify performance and scale
  - [ ] 10,000 segments, 30 years, 1,000 evaluations, 8 cores; or the measured limit
- [ ] P12.6 Verify reproducibility
  - [ ] Same data/model/config/seed reproduces the schedule and accounts
- [ ] P12.7 Write the verification report and release recommendation
  - [ ] Evidence, failures, gaps, and the recommendation

Acceptance criteria:

- Every success criterion has evidence or a named reason it was not met.
- The BAU comparison reports a measured difference with uncertainty, not an assertion.
- The performance target is met or the measured limit and cause are reported.
- A clean checkout reproduces the verification case.
- The dashboard is green.

## Phase 13: Release and deploy

Parent issue: TBD
Branch: `feature/p13-release`
Status: planned

Goal: tag a release, publish the package and docs, and verify the published release from a clean
checkout.

- [ ] P13.1 Write the release notes and the known-gaps list
  - [ ] Version, changes, known limits, and the model-card boundaries
- [ ] P13.2 Build and verify the release artifacts
  - [ ] sdist, wheel, docs, and a clean-venv install
- [ ] P13.3 Publish the docs and the demo portal
  - [ ] GitHub Pages, the static demo portal, and the optional lab preview
- [ ] P13.4 Tag and publish the release (maintainer approval required)
  - [ ] Annotated tag, GitHub release, and artifact verification
- [ ] P13.5 Verify the published release
  - [ ] Clean checkout, install, CLI, docs, demo, and a sample run

Acceptance criteria:

- The release artifacts install and run from a clean checkout.
- The docs and the demo portal are reachable and current.
- The known gaps and model limits are stated.
- The tag and release were approved.
- The dashboard is green.

## Phase 14: Operate and maintain

Parent issue: TBD
Branch: `feature/p14-operate`
Status: planned

Goal: keep the project current, support pilots, and maintain the data and model governance.

- [ ] P14.1 Set the review cadence and triage incoming issues
- [ ] P14.2 Maintain dependencies, security, and the Fresh Solutions/FEMIC pins
- [ ] P14.3 Maintain the data and model governance
  - [ ] Model cards, licences, applicability domains, and validation records
- [ ] P14.4 Write the maintainer and handover guide
- [ ] P14.5 Support the first pilots and record their evidence

Acceptance criteria:

- The review cadence is held and recorded.
- Dependencies and pins are current or have a recorded reason.
- Every model and dataset has a current card and licence.
- A pilot can be handed to a new maintainer from the guide.
- The dashboard is green.

## Detailed Next Steps Notes

1. P0 is complete and merged: pull request #14 squash-merged as `0a6778c`, the branch deleted, and parent issue #1 closed. The repository is public and the docs are published at https://ubc-fresh.github.io/brushline/.
2. P1 is complete: pull request #23 squash-merged as `58b3065`, the branch deleted, and parent issue #15 closed. The close-out report is `notes/reports/p1-closeout.md`.
3. P2 is active on `feature/p2-instance-builder`, parent issue #24, with child issues #25 to #31. Start with P2.1, the FEMIC extension boundary and provider API pin.
4. Keep the instance builder an extension of FEMIC; do not create a parallel package or data-acquisition stack.
5. Do not start P12 until P1 to P11 have evidence.
