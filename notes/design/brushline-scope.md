# Brushline Scope

Status: draft for Phase 0 review
Phase: P0 (Bootstrap and scope)
Date: 2026-11-14

## Problem statement

Utilities, pipeline operators, railways, road agencies, and other owners of linear infrastructure
manage long corridors through forested landscapes. The corridor must stay accessible, and the
vegetation beside and beneath the asset must stay clear enough that trees and tall shrubs do not
contact, fall on, or obstruct the asset. The same vegetation also carries fire risk, hides access
hazards, and affects the cost of every inspection and repair.

The work is expensive and repetitive. A owner may treat thousands of kilometres of corridor on a
fixed cycle, region by region, because that is what the budget and the contract calendar allow. The
cycle is rarely the cheapest way to hit a service level, and it is almost never differentiated by
site productivity, species, access, structure density, or risk. Contractors bid from their own
assumptions about quantities, access, treatment method, and productivity, so two bids for the same
corridor can be hard to compare and hard to defend. When the work is done, the owner has a record of
spend but little evidence about the vegetation state that the spend bought.

Three gaps make the problem worse:

- **Growth models for the actual vegetation are scarce.** Open growth and yield models are built for
  merchantable timber, not for the shrubs, deciduous sprouts, and young conifers that dominate a
  rights-of-way. A usable model has to be assembled from site, climate, treatment, and observation
  data, and it has to say how uncertain it is.
- **The scheduling problem is combinatorial.** Treatment and monitoring choices interact across
  segments, years, contractors, access windows, and budgets, with spatial and temporal constraints.
  The problem is NP-hard, so a realistic planner needs a metaheuristic search and a way to inspect
  the trade-offs, not a single "optimal" answer presented without evidence.
- **Monitoring is treated as a calendar, not a decision.** Aerial or ground inspection is expensive.
  When and where to fly, which sensor to carry, and how much to sample are choices that change the
  value of the information the owner buys. A fixed annual sweep can be worse than a targeted one.

Open LiDAR is becoming available across British Columbia and other jurisdictions, and the lab already
has a producer pipeline for it. But the coverage is patchy, the products are built for mature-forest
inventory, and a canopy height model is not a shrub and young-tree state. Brushline has to reuse the
producer work without pretending that open data is universal or that a mature-forest model transfers to
the vegetation that actually threatens a corridor.

## Users and the decisions they make

| User | Decision | Scale |
| --- | --- | --- |
| Asset owner executive | What service level, risk appetite, and multi-year budget should the vegetation program carry? | Strategic, 10 to 30 years |
| Vegetation program manager | Which corridors and regions get treated, in what order, and what monitoring policy is affordable? | Strategic and tactical, 1 to 10 years |
| Tactical planner | Which treatment units, methods, contractors, and access windows make up the next 1 to 5 years? | Tactical, 1 to 5 years |
| Field operations supervisor | Which segments are worked this week, by which crew or machine, in what order? | Operational, days to a season |
| Contractor estimator | What quantities, rates, access, productivity, and risk belong in a defensible bid? | Tactical and operational |
| Monitoring specialist | Where, when, and with which sensor should the corridor be observed, and when should the growth model be recalibrated? | All scales |
| Remote-sensing or GIS analyst | Which LiDAR bundle, model card, terrain product, and applicability domain produced this state, and where is the coverage missing? | All scales |
| Analyst or researcher | Which model, data version, constraints, and search settings produced this result, and how sensitive is it? | All scales |
| Reviewer, auditor, or community liaison | Is the plan consistent with the stated service level, budget, and assumptions? | Read-only, all scales |
| Agent or automation | Can I run the same reproducible pipeline and inspect the same artifacts the human sees? | All scales |

The owner and the contractor are not separate products. They are two views of one plan. The owner
needs a budget and service-level forecast; the contractor needs operationally feasible quantities,
rates, access, and schedule. If the two views are built from different spreadsheets, the conversation
starts from disagreement.

## Goal

Deliver an open, reproducible, inspectable decision support system that:

- represents a linear corridor as a graph of decision segments;
- predicts vegetation state and its uncertainty through time;
- represents treatments as transitions with method-specific efficacy and regrowth;
- chooses treatment and monitoring actions across strategic, tactical, and operational scales;
- searches the NP-hard schedule space with a reusable metaheuristic engine and keeps a Pareto archive
  of cost, risk, service, and uncertainty trade-offs;
- presents one versioned plan artifact to owners and contractors, with a line-item cost build-up and
  named assumptions;
- exposes the plan, the runs, the trade-offs, and an animated operations view through a browser
  studio with role-specific skins; and
- records enough provenance that another analyst can replay the result.

## Value proposition

### For the asset owner

- A forward view of budget and cash need by year, region, and service level.
- A defensible answer to "what does this service level cost, and what does a lower one save?"
- A risk-ranked treatment program instead of a uniform cycle.
- A monitoring policy priced by the value of the information it buys.
- A procurement benchmark: the same plan and cost build-up the contractor sees.

### For the contractor

- A work plan with quantities, access, treatment methods, and timing that can be priced from evidence.
- A transparent cost build-up that shows labour, equipment, materials, travel, access, risk, and
  overhead assumptions.
- A way to show why a bid differs from another bid, rather than defending a lump sum.
- A shared object that shortens the clarification loop with the owner.

### For both

- Faster convergence on what a fair bid and a good plan look like.
- An audit trail from data version to model version to search seed to final schedule.
- A clear statement of what is uncertain, what was assumed, and what was not verified.

## In scope through the first release

### 1. Corridor and segment model

- A corridor is a linear asset with a route, a management standard, and a set of structures, access
  points, and crossings.
- A segment is the decision unit: a length of corridor with stable site, vegetation, access, and
  treatment attributes. Spans and treatment units are runtime aggregates.
- Linear referencing, CRS, units, topology, and adjacency are explicit and validated.
- The compiled corridor dataset is versioned, columnar, and carries a manifest. The simulator and
  planner read only that dataset.

### 2. Open LiDAR, terrain, and state initialization

- Consume validated FEMIC `femic.lidar.product.v1` bundles: DEM, DSM, CHM, canopy structure, optional
  tree products, ALS inventory attributes, and the model cards that describe them. Brushline does not
  discover, download, or compile source tiles.
- Reuse the WS4 P52 and FHOPS P13/P14 consumer patterns for bundle pinning, checksum validation,
  polygon support mapping, and dataset integration.
- Use open LidarBC and other OGL-BC products where they change a decision: initial vegetation state,
  terrain and slope, canopy height and cover, access and road status, and change detection.
- Use VRI `SITE_INDEX`, VDYP `ESTIMATED_SITE_INDEX`, and SIBEC for site index. Do not derive a new ALS
  site-index model from a circular VRI proxy.
- Calibrate a low-vegetation state model for shrub and young-tree height, cover, density, and
  resprouting against field plots. Do not transfer a mature-forest EFI card without a measured transfer
  test.
- Treat coverage as a knowledge state: no point cloud, no contemporary DEM, or an out-of-domain model is
  an explicit uncertainty that can trigger monitoring, not a zero.
- Record the bundle pin, product checksums, CRS, vertical datum, resolution, acquisition date, licence,
  model card, and applicability on every derived state.
- Reuse the `fresh-road` / ALSroads `fresh.road.status.v1` record for access where it is available,
  preserving the source class rather than inventing an open/closed verdict.

### 3. Vegetation state, growth, and treatment

- Functional groups for the vegetation that matters on rights-of-way: shrubs, deciduous sprouts,
  conifers, and grasses or herbs, with room for site-specific groups.
- State variables: height, cover, density or biomass, age since disturbance, and treatment history,
  with uncertainty.
- A site- and climate-sensitive growth model, calibrated from observations, with a stated validation
  and a stated domain of applicability.
- Treatment transitions for manual, mechanical, chemical, mowing, and other methods the owner uses,
  including efficacy, selectivity, seasonality, cost, and regrowth.
- Hazard and service indicators: clearance against the standard, fall-in distance, fuel connectivity,
  access impedance, and a reliability proxy where the owner has one.

### 4. Optimization and search

- The joint treatment and monitoring schedule is an NP-hard combinatorial problem.
- A `BrushlineAdapter` implements the `fresh-solutions` `ProblemAdapter` contract: variables,
  options, exact evaluation, batched evaluation, move proposal, apply, undo, initial and random
  assignments, mutation, and crossover.
- `fresh-solutions` supplies local search, population search, hybrid handoff, convergence stopping,
  checkpoints, seeds, telemetry, and exact replay.
- A multi-objective layer keeps a Pareto archive over cost, risk, service, and uncertainty, with
  scalarization portfolios and a documented promotion rule.
- Every reported incumbent is replayable from an evidence record. Realistic instances carry no
  optimality claim; tiny instances are validated by exhaustive enumeration.

### 5. Planning scales

- **Strategic:** 10 to 30 years, annual resolution, corridor or region, budget and service levels,
  risk appetite, monitoring policy, and a business-as-usual comparison.
- **Tactical:** 1 to 5 years, seasonal or quarterly resolution, treatment units, contractor capacity,
  access windows, and monitoring missions.
- **Operational:** weeks to a season, daily or shift resolution, work-ready treatment units, crews and
  machines, productivity, cost, and a 3D operations view.
- The three scales share one scenario contract, one vocabulary, and one plan version. They differ in
  horizon, resolution, and constraint set, not in data definitions.

### 6. Monitoring and adaptive replanning

- A mission model for UAV, aircraft, and ground inspection over the corridor graph, including travel,
  endurance, sensor footprint, weather windows, and cost.
- An observation model for LiDAR, imagery, and field samples, including detection probability and
  measurement error.
- Monitoring frequency, route, sensor, and sampling intensity as decision variables, priced by their
  expected value of information.
- A recalibration loop that updates growth and treatment parameters when observations arrive, and a
  trigger rule for replanning when forecasts drift.

### 7. Plan and bid exchange

- One versioned plan artifact with segments, actions, timing, quantities, methods, rates, cost
  build-up, assumptions, risk notes, and provenance.
- An owner view and a contractor view over the same artifact.
- Bid normalization and a comparison report that attributes differences to named assumptions.
- An audit trail from data version through model version, search seed, and approved plan.

### 8. Interactive planning studio

- One optional FastAPI service and one static browser shell over the same artifacts the command line
  writes. The service never owns model state.
- A 2D MapLibre map of corridors, segments, vegetation state, risk, planned and actual treatments,
  monitoring coverage, and bid deltas.
- A 3D Three.js scene of terrain, corridor, vegetation, structures, machines, and crews, with a
  synchronized timeline and animated deployment. It is a context view, not survey-grade geometry.
- Checked skins for owner-strategic, tactical-planner, operations-planner, contractor-bid,
  monitoring, and reviewer roles.
- A multi-objective explorer: Pareto front, parallel coordinates, scatter matrix, scenario
  comparison, and promotion of a chosen solution into the plan.
- Live search over server-sent events, with pause and stop, and the incumbent visible in the map and
  target charts.
- Offline-capable vendored MapLibre and Three.js assets, relative URLs behind a proxy prefix, loopback
  bind by default, and an explicit opt-in for remote access.

### 9. Instance builder and open-data onboarding

- Extend FEMIC's instance builder rather than create a second package. FEMIC owns `instance init`,
  `instance rebuild`, `rebuild.spec.yaml`, FreshForge graphs, BC Data Catalogue discovery and fetch,
  DataLad and Arbutus materialization, preflight, the LiDAR producer pipeline, inventory model cards,
  and site-index reconciliation.
- Brushline adds a small FEMIC extension and instance template with provider nodes for corridor
  segmentation, dataset compilation, vegetation state seeding, scenario and target creation, plan
  validation, and demo export.
- An optional LLM orchestrator plans and explains the build, while FEMIC and Brushline commands do the
  deterministic work. Every capability is a prompt, an allowlisted tool set, a validator over real
  state, and a bounded retry budget; there is no authoritative output from the model itself.
- A new AOI starts from a map selection, a data-availability and coverage scan, a fetch-plan preview,
  explicit approvals, materialization, preprocessing, compilation, validation, and a reviewable
  instance handoff.
- Public and private data are separated. Private connectors are allowlisted, credentials stay outside
  the repository, the agent sees metadata only until approved, and derived artifacts are the only
  output that leaves the owner's tenancy.
- The instance is a versioned repository with data pointers, manifests, checksums, licences, tests,
  runbooks, and evidence. Large payloads stay in DataLad, an annex, or the owner's storage.

### 10. Demo portal and pilot onboarding

- A public, read-only portal with four to six curated demo instances, each answering a partner
  question for a sector such as utilities, pipelines, rail, roads, or municipal corridors.
- A `brushline.demo.v1` manifest per instance: title, sector, region, AOI, data sources and licences,
  scenarios, artifacts, headline metrics, caveats, contact, and status.
- A static-first export for GitHub Pages from precomputed runs, plus an optional read-only service for
  a lab preview.
- A pilot funnel: a pilot brief, data-request checklist, success metrics, security and NDA path, and a
  scoped 6-to-8-week pilot offer.
- Public data or synthetic data only in the public portal. Any partner data stays in a separate private
  deployment, and the portal never accepts arbitrary uploads or runs.
- Reuse the WS4 public demo shell, FHOPS operations scene, Fresh Fire Studio static export and 3D
  level-of-detail, Fresh Woodlots catalogue and pilot framing, and the urban-forest lab 2D/3D shell.

### 11. Interfaces and integration

- A CLI with `build`, `simulate`, `plan`, `monitor`, `compare`, `validate`, `report`, and `serve`
  commands as the phases deliver them.
- A Python API for the same operations.
- A documented compiled-dataset and run-directory contract.
- Adapters for WS4, FHOPS, and the FRESH urban-forest lab patterns, installed only when needed.
- GIS interchange through GeoPackage, GeoJSON, and columnar formats with an explicit CRS.

### 12. Reproducibility and provenance

- Every dataset and run manifest names the data version, model version, configuration, seed, package
  version, `fresh-solutions` version, and adapter version.
- The simulator is deterministic given a schedule.
- Every stochastic search records its seed and every incumbent has an evidence record.
- The same inputs and seed reproduce the same outputs.

## Out of scope for the first release

- **Real-time control and SCADA integration.** Brushline plans work; it does not operate or trip
  assets.
- **Engineering design or structural assessment** of poles, towers, pipelines, or roads.
- **Herbicide selection, regulatory approval, or environmental permitting.** The product records the
  owner's prescriptions and constraints; it does not decide them.
- **Autonomous flight control or airspace management.** The monitoring model plans and prices
  missions; it does not fly aircraft.
- **A full physiological plant model.** The growth model is a calibrated state-transition model with
  a stated domain, not a mechanistic simulation of every plant process.
- **Rebuilding the LiDAR producer pipeline.** FEMIC owns discovery, materialization, terrain, canopy,
  tree, bundle, and ALS inventory products. Brushline consumes them.
- **A new ALS site-index model.** Site index is a provincial product (VRI, VDYP, SIBEC). Brushline
  consumes and reconciles it rather than deriving a circular proxy from canopy height.
- **A new instance-builder package or data-acquisition stack.** FEMIC owns instance bootstrap, rebuild
  specs, FreshForge, catalogue discovery, DataLad materialization, preflight, and the LiDAR producer
  pipeline. Brushline adds a provider extension.
- **A public portal with private data or arbitrary runs.** The public demo portal is read-only and
  public-data-only; partner data stays in a separate private deployment.
- **A national-scale LiDAR change-detection service.** Brushline may consume a change product; it does
  not become the producer.
- **Timber supply and carbon accounting.** Those remain WS4's domain; Brushline may consume a WS4
  scenario through an adapter.
- **A multi-tenant hosted service with billing, accounts, and tenant isolation.** The first release is
  a local or lab-hosted service with no authentication.
- **Safety certification or legal compliance.** The owner's work-control and regulatory processes
  remain authoritative.
- **Real asset, contractor, or personal data in the repository.** Examples and tests use synthetic or
  sanitized fixtures.
- **A replacement for field judgment.** Brushline is decision support; a qualified person inspects
  and approves the work.

## Success criteria

The first release is successful when all of the following are demonstrated with evidence:

1. **End-to-end synthetic corridor.** A synthetic corridor compiles, grows, treats, plans, and reports
   from the CLI, and the planning studio can read the resulting run directory.
2. **Growth and treatment validation.** The growth and treatment model reproduces held-out
   observations within a stated error, and the validation record names the data and the domain.
3. **FEMIC-extended instance builder.** A new Brushline instance is scaffolded and built through
   FEMIC's instance, rebuild-spec, and FreshForge surfaces, with a Brushline provider extension and no
   parallel instance-builder package.
4. **Agent capability.** Every agent-facing build capability has a validator that can fail and an
   offline test with a fake provider; the agent never fabricates a source, a coefficient, a geometry,
   or a successful validation.
5. **LiDAR state initialization.** A validated FEMIC LiDAR bundle maps to segment support with a
   stated aggregation, and missing point-cloud, DEM, or model coverage is reported as a knowledge
   state rather than a zero.
6. **Low-vegetation calibration.** The Brushline low-vegetation model is fit and validated on
   held-out plots with a stated error, and the transfer of a mature-forest EFI card to the same target
   is measured or refused.
7. **Demo portal.** A public-data-only, read-only portal presents curated instances with provenance,
   caveats, and a pilot-request path, and the static build fails on a broken artifact, licence, or
   link.
8. **Exact small-instance check.** On at least one tiny instance, exhaustive enumeration and the
   `fresh-solutions` adapter agree on the best objective, and the adapter replays the incumbent
   exactly.
9. **Search quality under a stated budget.** On a small validation set, the search reaches a known or
   independently bounded solution within a stated gap and budget. No optimality claim is made beyond
   the validated instances.
10. **Business-as-usual comparison.** On a synthetic case with heterogeneous growth, access, and risk,
   the optimized plan meets the service levels at a lower present cost than a fixed-cycle baseline, or
   reduces risk at equal budget; the difference is measured with uncertainty and reported.
11. **Monitoring value.** An adaptive monitoring policy beats a fixed calendar on expected regret per
   monitoring dollar in a synthetic experiment, and the result states the observation model and its
   assumptions.
12. **Owner-contractor agreement.** The owner view and the contractor view derive from one plan
   artifact, the line-item cost build-up reproduces to the cent, and every bid difference is
   attributable to a named assumption.
13. **Studio contract.** The 2D map, 3D scene, skins, animated operations, and Pareto explorer read
   only artifacts; the service holds no model state; a read-only skin cannot carry a mutating action.
14. **Reproducibility.** The same data version, model version, configuration, and seed reproduce the
   same schedule and accounts.
15. **Scale.** A strategic scenario of 10,000 segments over 30 years completes 1,000 candidate
    schedule evaluations within 10 minutes on 8 cores, or the close-out reports the measured limit and
    the reason. This target is provisional until the prototype measures the real cost.
16. **Quality gates.** The dashboard is green, every public function has a docstring, and the docs
    build with warnings as errors.

## Constraints and assumptions

- Python 3.11 or newer on Linux; columnar data in Parquet and Arrow; a CLI-first workflow.
- The vegetation model is a calibrated state-transition model, not a mechanistic physiology model.
- The owner supplies a corridor inventory, treatment history, inspection records, service standards,
  cost rates, and access constraints. Missing data is expected and must be represented as uncertainty,
  not silently imputed.
- The growth model's domain of applicability is explicit. A corridor outside that domain is flagged,
  not predicted silently.
- Costs are in the owner's currency, with an explicit base year and discount rate. Physical units are
  metres, hectares, and dates; the CRS is recorded.
- Contractor capacity, seasonality, and access windows are constraints, not post-processing.
- Monitoring data may arrive late or be missing; the planner must remain usable with stale state.
- The first release is local or lab-hosted. It has no authentication, so it binds to loopback by
  default and requires an explicit opt-in for remote access.
- The `fresh-solutions` engine is an optional dependency. A core install can build, validate, and
  simulate without it; planning requires the `opt` extra.
- The web studio is an optional dependency. A core install can produce and read artifacts without it.
- Open LiDAR coverage is patchy. A missing tile, a missing contemporary DEM, or a model outside its
  applicability domain is recorded as a knowledge state, not imputed silently.
- OGL-BC and other licences travel with the data. Point-cloud bytes and large products stay out of the
  repository; the bundle pin, checksums, and attribution are tracked.
- Mature-forest EFI cards are not low-vegetation models. A transfer test is required before any
  existing area-based model is used on shrubs or young trees.
- FEMIC is an optional producer and builder dependency. Brushline core can build, validate, and
  simulate a supplied dataset without it; instance construction and LiDAR state initialization use the
  FEMIC extension.
- The public demo portal is static-first. It runs from precomputed artifacts on GitHub Pages, with no
  server, no uploads, and no arbitrary searches. A lab preview may add a read-only service behind the
  lab's access gate.

## Open questions

| Question | Why it matters | Resolve in |
| --- | --- | --- |
| Which functional groups and state thresholds are both interpretable and tractable? | The state space drives the growth model, the DP, and the search. | P1 and P2 |
| What calibration data exists, and how hierarchical must the model be? | A model that cannot be calibrated is a guess with a user interface. | P2 |
| How should uncertainty reach the objective and the Pareto archive? | A plan that ignores uncertainty can look better than it is. | P1 and P3 |
| How are spatial adjacency, contiguous work, and access represented on a linear graph? | They change both feasibility and cost. | P1 and P3 |
| Which parts of the schedule are exact (DP or MIP) and which are metaheuristic? | The hybrid boundary determines quality and runtime. | P3 |
| What is the observation model for LiDAR, imagery, and field samples? | Monitoring value is meaningless without it. | P5 |
| How is value of information approximated at corridor scale? | Exact POMDPs are intractable. | P5 |
| How are multi-objective weights, normalization, and promotion chosen and audited? | The Pareto explorer must not hide a value judgment. | P3 and P7 |
| What does a fair contractor cost build-up contain, and what is comparable across bidders? | The exchange surface is the product's trust boundary. | P6 |
| How much 3D fidelity is useful before it implies survey precision? | A misleading scene is worse than no scene. | P0 and P8 |
| What real or synthetic case can validate the optimal-versus-BAU claim? | Without a case, the value proposition is untested. | P9 |
| How should owner, contractor, and monitoring data be separated and shared? | The first release has no authentication. | P6 and P8 |
| Which Brushline stages belong in FEMIC's provider vocabulary, and which belong in the instance template? | The boundary decides coupling and upgrade cost. | P2 |
| How stable is the FreshForge provider API, and what is the minimum version to pin? | The extension must survive FEMIC releases. | P2 |
| Which demo instances and partner sectors make the strongest pilot case? | The portal is a partner-acquisition surface, not a gallery. | P11 |
| How are agent capabilities tested offline without a live model provider? | A capability without a validator is not a capability. | P2 |
| How do we keep private data out of prompts, logs, and model-provider requests? | The public portal and the build agent have different trust boundaries. | P2 and P11 |

## Relationship to the other FRESH tools

- **WS4** is the sibling forest estate model. Brushline borrows its compiled-dataset pattern, its
  spatial-decision discipline, its run-directory artifacts, and its browser shell. WS4 remains the
  tool for timber supply and stand-level harvest scheduling.
- **FHOPS** is the sibling harvesting operations planner. Brushline borrows its tactical and
  operational planning patterns, machine and crew productivity model, and 3D operations view, and
  reaches FHOPS through an adapter when an operational work plan needs that fidelity.
- **Fresh Solutions** is the metaheuristic engine. Brushline supplies a domain adapter and consumes
  the engine's search, checkpoint, telemetry, and replay contracts. It does not fork the engine.
- **The FRESH urban-forest lab** is the sibling 2D/3D studio. Brushline borrows its FastAPI plus
  static shell, vendored MapLibre and Three.js, offline-capable assets, and shared selection state.
- **FEMIC** is the LiDAR producer. Brushline consumes versioned `femic.lidar.product.v1` bundles, the
  ALS inventory contract, and the model cards. It does not rebuild the discovery, materialization,
  terrain, canopy, tree, or bundle pipeline.
- **fresh-road** provides the ALSroads road-status record. Brushline may consume it as access evidence;
  it does not turn a source class into an open/closed verdict.
- **Nemora** provides distribution fitting, sampling, and synthetic-landscape support. Brushline uses it
  for calibration uncertainty and test fixtures, not as a second fitting stack.

## Glossary

- **Corridor:** a linear asset and the land along it that the owner manages.
- **Segment:** the atomic decision unit; a length of corridor with stable attributes.
- **Span:** a contiguous run of segments between access points or structures; a runtime aggregate.
- **Treatment unit:** a set of segments scheduled and contracted together.
- **State:** the vegetation condition on a segment, represented as a distribution over classes with
  continuous summaries.
- **Transition:** the change in state caused by growth, disturbance, or treatment.
- **Service level:** the owner's required vegetation condition and access availability.
- **Plan:** a versioned schedule of treatments and monitoring with quantities, costs, and assumptions.
- **Run:** one execution of a build, simulation, or search, with its configuration and artifacts.
- **Pareto archive:** the set of non-dominated solutions found by a multi-objective search.
