Contract index
==============

Every Brushline contract has a schema version, a model module, a validator, stable named errors, and a
test suite. This page is the map.

.. list-table::
   :header-rows: 1
   :widths: 22 18 20 40

   * - Contract
     - Schema
     - Validator
     - Checks
   * - Compiled dataset
     - ``brushline.dataset.v1``
     - ``validate_dataset``
     - Manifest, schema, relative paths, tables, columns, dtypes, keys, row counts, checksums, digest
   * - Corridor graph
     - ``brushline.corridor.v1``
     - ``validate_corridor_network``
     - Ids, CRS, references, span order, contiguous sequence, treatment units, access, structures, length
   * - State and treatment
     - ``brushline.state.v1``
     - ``validate_state_contract``
     - State keys, ranges, unknown states, years, references, required segments
   * - Plan
     - ``brushline.plan.v1``
     - ``validate_plan``
     - Action and assumption ids, segments, currencies, parent, assumptions
   * - Run
     - ``brushline.run.v1``
     - ``validate_run_manifest``
     - Artifact ids, availability, hashes, status
   * - Pareto archive
     - ``brushline.pareto.v1``
     - ``validate_pareto_archive``
     - Objectives, scalarizations, member keys, dominance
   * - Operations timeline
     - ``brushline.timeline.v1``
     - ``validate_timeline``
     - Event ids, ordering, segment references, open events
   * - Demo manifest
     - ``brushline.demo.v1``
     - ``validate_demo_manifest``
     - Slug, sources, licences, artifacts, caveats, publication status
   * - Data catalogue and connectors
     - ``brushline.catalogue.v1``
     - ``validate_catalogue``
     - Sources, licences, classifications, coverage, connectors, auth references, scope, outputs, audit, approval, secret scan
   * - Fetch plan
     - ``brushline.fetch-plan.v1``
     - ``validate_fetch_plan``
     - Items, estimates, licences, access, materialization pointers, bulk approvals, catalogue drift
   * - Materialization
     - ``brushline.materialization.v1``
     - ``validate_materialization``
     - Checksums, sizes, paths, containment, licences, pointers, retrieval time, missing reasons
   * - Coverage and gaps
     - ``brushline.coverage.v1``, ``brushline.gap-report.v1``
     - ``validate_coverage``, ``validate_gap_report``
     - Six coverage states, evidence, reasons, next action, and stop/continue
   * - Agent capabilities
     - ``brushline.capabilities.v1``, ``brushline.capability-outcome.v1``
     - ``validate_capability_registry``, ``validate_capability_outcome``
     - Six capabilities, prompt ids, tool allowlists, validators, retry budgets, private markers, authority fields, sanitized outcomes
   * - Model builder session
     - ``brushline.model-builder-session.v1``, ``brushline.model-builder-review.v1``,
       ``brushline.handoff.v1``
     - ``BuilderSession``, ``ReviewSummary``, ``HandoffRecord``
     - AOI, plan preview, availability, approvals, stages, review, handoff, and dry-run artifacts
   * - FEMIC LiDAR bundle
     - ``femic.lidar.product.v1``, ``femic.lidar.bundle.v1``, ``femic.lidar.selection.v1``
     - ``validate_lidar_bundle``
     - Producer pin, selection digest, product checksums, CRS, datum, resolution, licence, paths, and provenance
   * - Terrain support
     - ``brushline.terrain-support.v1``
     - ``validate_terrain_support``
     - Raster CRS, resolution, datum, buffer, statistic, valid pixels, coverage, slope, aspect, terrain class, and access proxy
   * - Canopy support
     - ``brushline.canopy-support.v1``
     - ``validate_canopy_support``
     - CHM CRS, datum, buffer, height statistics, cover thresholds, structure, optional tree, VRI comparison, and applicability
   * - Initial vegetation state
     - ``brushline.state-initialization.v1``
     - ``validate_state_initialization``
     - Field/CHM rules, evidence coverage, class probabilities, audit decisions, model card, and state-contract validity
   * - LiDAR coverage and applicability
     - ``brushline.lidar-coverage.v1``
     - ``validate_lidar_coverage``
     - Acquisition recency, usable coverage, valid pixels, domain, six coverage states, next action, and stop/continue
   * - LiDAR benchmark
     - ``brushline.lidar-benchmark-request.v1``, ``brushline.lidar-benchmark.v1``
     - ``validate_lidar_benchmark``
     - Bundle pin, shared contract, absolute/relative tolerance, missing values, case statuses, and bundle hash
   * - Low-vegetation state space
     - ``brushline.state-space.v1``
     - ``validate_state_projection``
     - Functional groups, variables, thresholds, coverage states, class probabilities, uncertainty, and state-contract conversion
   * - Growth
     - ``brushline.growth.v1``
     - ``validate_growth_result``
     - Group curves, site/climate/competition modifiers, monotonicity, asymptotes, age, uncertainty, and domain
   * - Treatment transitions
     - ``brushline.treatment.v1``
     - ``validate_treatment_result``
     - Method/season efficacy, top-kill, residual, resprouting, delay, cost, trajectory, and monotonicity
   * - Treatment calibration
     - ``brushline.treatment-calibration.v1``
     - ``validate_treatment_calibration``
     - Evidence, pooling, shrinkage, intervals, sample sizes, source ids, and leave-one-out checks
   * - Hazard and service indicators
     - ``brushline.hazards.v1``
     - ``validate_hazard_report``
     - Clearance, fall-in, fuel, access, reliability components and weights, unknown states, and caveats
   * - Vegetation validation
     - ``brushline.vegetation-validation.v1``
     - ``validate_vegetation_validation``
     - Spatial holdout, group error, interval coverage, time-lag sensitivity, candidate benchmark, and exclusions
   * - Low-vegetation model card
     - ``brushline.low-vegetation-model-card.v1``
     - ``validate_model_card``
     - Predictors, training/validation evidence, metrics, candidates, uncertainty, domain, licence, citation, caveats, and decision boundary
   * - Optimization formulation
     - ``brushline.optimization-formulation.v1``
     - ``validate_formulation``
     - Stable variables, options, periods, targets, hard/soft constraints, and four objectives
   * - Optimization evaluation
     - ``brushline.optimization-evaluation.v1``
     - ``EvaluationResult``
     - Exact four-objective result, costs, feasibility, named violations, and period trail
   * - Optimization search
     - ``brushline.optimization-search.v1``
     - ``SearchRun``
     - Adapter, seed, budget, assignment, objective vector, evidence, checkpoint, and replay flag
   * - Promotion record
     - ``brushline.promotion.v1``
     - ``PromotionRecord``
     - Promoted plan, parent, reason, objective vector, time, and promoter
   * - Tiny optimum
     - ``brushline.tiny-optimum.v1``
     - ``TinyOptimum``
     - Enumerated assignment count, best assignment/vector, ties, and exact/batch agreement
   * - Tiny validation
     - ``brushline.tiny-validation.v1``
     - ``TinyValidationReport``
     - Optimum, optional search, gap, reach flag, replay, and expected-match evidence
   * - Search budget
     - ``brushline.optimization-budget.v1``
     - ``QualityBudgetReport``
     - Per-budget and per-seed objectives, feasibility, evaluations, replay, and no-optimality caveat
   * - Budget report
     - ``brushline.optimization-budget-report.v1``
     - ``BudgetReport``
     - Quality, scaling, checkpoint, adapter and Fresh Solutions versions, and caveat
   * - Optimization event
     - ``brushline.optimization-event.v1``
     - ``TelemetryEvent``
     - Progress event with run, seed, budget, payload, objective, plan, and evidence references
   * - Optimization telemetry
     - ``brushline.optimization-telemetry.v1``
     - ``EventStream``
     - Versioned run, model/data versions, archive path, and ordered events
   * - Strategic dynamic program
     - ``brushline.strategic-dp.v1``
     - ``validate_dynamic_program``
     - States, actions, transitions, weights, horizon, discount, and terminal values
   * - Strategic DP result
     - ``brushline.strategic-dp-result.v1``
     - ``DynamicProgramResult``
     - Policy, value table, expected cost, service, risk, and uncertainty
   * - Strategic portfolio
     - ``brushline.strategic-portfolio.v1``
     - ``StrategicPortfolio``
     - Selections, period budgets/capacity, service/risk/uncertainty, continuity, and violations
   * - Strategic monitoring
     - ``brushline.strategic-monitoring.v1``
     - ``MonitoringPolicy``
     - Span decisions, frequency, route, sensor, cost, value of information, and reductions
   * - Strategic BAU
     - ``brushline.strategic-bau.v1``
     - ``BauPlan``
     - Fixed-cycle selections, period summaries, outcomes, baselines, and budget/capacity flags
   * - Strategic report
     - ``brushline.strategic-report.v1``
     - ``StrategicReport``
     - Optimized/BAU yearly cost, budget, service, risk, uncertainty, monitoring, and comparison
   * - Strategic scenario
     - ``brushline.strategic-scenario.v1``
     - ``StrategicScenario``
     - Data/model/config/seed versions, artifact digests, paths, and replay
   * - Strategic scenario archive
     - ``brushline.strategic-scenario-archive.v1``
     - ``ScenarioArchive``
     - Versioned scenario set with creation metadata

Error prefixes
--------------

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Prefix
     - Contract
   * - ``DATASET-*``
     - Compiled dataset
   * - ``CORRIDOR-*``
     - Corridor graph
   * - ``STATE-*``
     - State and treatment
   * - ``PLAN-*``
     - Plan
   * - ``RUN-*``
     - Run
   * - ``PARETO-*``
     - Pareto archive
   * - ``TIMELINE-*``
     - Operations timeline
   * - ``DEMO-*``
     - Demo manifest
   * - ``CATALOGUE-*``
     - Data catalogue and connectors
   * - ``FETCH-*``
     - Fetch plan
   * - ``MATERIALIZATION-*``
     - Materialization manifest
   * - ``COVERAGE-*``, ``GAP-*``
     - Coverage and gap report
   * - ``CAPABILITIES-*``, ``AGENT-*``
     - Agent capabilities and sanitized outcome record
   * - ``LIDAR-*``
     - FEMIC LiDAR bundle
   * - ``TERRAIN-*``
     - Terrain support
   * - ``CANOPY-*``
     - Canopy support
   * - ``LIDAR-COVERAGE-*``
     - LiDAR coverage and applicability
   * - ``BENCHMARK-*``
     - LiDAR benchmark
   * - ``STATE-SPACE-*``
     - Low-vegetation state space
   * - ``GROWTH-*``
     - Growth model
   * - ``TREATMENT-*``
     - Treatment transitions
   * - ``CALIBRATION-*``
     - Treatment calibration
   * - ``HAZARD-*``
     - Hazard and service indicators
   * - ``VALIDATION-*``
     - Vegetation validation
   * - ``MODEL-CARD-*``
     - Low-vegetation model card
   * - ``FORMULATION-*``
     - Optimization formulation
   * - ``EVALUATION-*``
     - Optimization evaluation
   * - ``MOVE-*``
     - Optimization move validation
   * - ``PROMOTION-*``
     - Promotion record
   * - ``TELEMETRY-*``
     - Telemetry stream
   * - ``DP-*``
     - Strategic dynamic program
   * - ``PORTFOLIO-*``
     - Strategic portfolio
   * - ``MONITORING-*``
     - Strategic monitoring
   * - ``BAU-*``
     - Business-as-usual baseline
   * - ``REPORT-*``
     - Strategic reports
   * - ``SCENARIO-*``
     - Strategic scenario
   * - ``STUDIO-*``
     - Studio compatibility

Test layers
-----------

- Unit tests for each model and validator.
- Contract tests for the public interfaces.
- Integration tests for the CLI (``validate``, ``build``, ``simulate``, ``prototype``).
- Catalogue tests for licences, classifications, unknown references, connector scope, approval, and
  the secret scan.
- Fetch tests for estimates, bulk approval, catalogue drift, materialization checksums and containment,
  the six coverage states, and the gap decision.
- Capability tests for the six prompts, tool allowlists, validator failure, retry budget, fake provider,
  private markers, authoritative fields, and sanitized records.
- Model-builder tests for the static shell, plan preview, approvals, blocked builds, dry-run artifacts,
  progress SSE, review, handoff, and custom AOI gaps.
- LiDAR bundle tests for the producer pin, selection digest, checksums, CRS, datum, licence, path
  containment, product kinds, derived flags, and provenance.
- Terrain tests for buffered aggregation, coverage states, every statistic, slope and access classes,
  RASTER CRS/datum/resolution checks, and provenance.
- Canopy tests for height and cover statistics, optional structure/tree products, VRI comparison,
  partial/missing/out-of-domain states, and applicability.
- State-initialization tests for field-first selection, every prototype class, unknown/partial states,
  species fallback, audit decisions, probabilities, and contract validity.
- LiDAR coverage tests for observed, stale, partial, missing, out-of-domain, excluded, optional gaps,
  domain reasons, next actions, and stop/continue.
- Benchmark tests for the committed fixture, absolute and relative tolerance, contract mismatch,
  required/optional/unexplained missing values, duplicate keys, and report consistency.
- State-space tests for every class, coverage state, strata, probabilities, config validation, unknown
  and partial projection, and state-contract conversion.
- Growth tests for monotonicity, asymptotes, all functional groups, site/climate/competition modifiers,
  domain blocking, uncertainty, conversion, and validator errors.
- Treatment tests for method/season effects, immediate residual, resprouting, delay, trajectory,
  cost, conversion, and validator errors.
- Calibration tests for exact/pooled/prior levels, shrinkage, intervals, holdout checks, model validation,
  and parameter application.
- Hazard tests for clearance statuses, fall-in risk, fuel connectivity, access, reliability weighting,
  missing components, caveats, and validator errors.
- Validation tests for spatial holdout, eligibility exclusions, group metrics, interval coverage, lag
  sensitivity, candidate disagreement, and report validation.
- Model-card tests for predictor/domain ranges, evidence, metrics, candidates, uncertainty, domain checks,
  out-of-domain rejection, and card validation.
- Formulation tests for stable indices, options, allowed methods, access constraints, objectives,
  validation, and build reproduction.
- Evaluator tests for exact growth/treatment replay, costs, budgets, capacity, access, service,
  monitoring allocation, discounting, batch equality, scalarization, and apply/undo.
- Operator tests for seeded determinism, every move kind, access and locks, move validation,
  apply/undo, budget/capacity/monitoring/access/service repair, and non-repairable blocked models.
- Adapter tests for the Fresh Solutions contract, scalarizations, random/mutation/crossover, single
  and compound proposals, all search modes, checkpoint replay, and rejected non-replayable results.
- Archive tests for dominance, duplicates, infeasible rejection, crowding, size eviction, round-trip,
  invalid archives, and promotion records.
- Tiny-validation tests for complete enumeration, the committed optimum, exact/batch agreement,
  search gap, replay, infeasible instances, ties, and report round-trips.
- Budget tests for every budget/seed point, feasible and infeasible runs, scaling timing and memory,
  checkpoint save/replay, composed reports, and input guards.
- Telemetry tests for committed stream/archive compatibility, run events, archive insertion, sequence
  and order validation, missing/mismatched artifacts, SSE, and JSON round-trips.
- Dynamic-program tests for the committed policy, transition/availability validation, tie-breaking,
  terminal values, expected outcomes, and invalid models.
- Portfolio tests for service repair, budget/capacity limits, risk warnings, continuity, local swaps,
  empty options, and invalid references.
- Monitoring tests for value-ranked selection, intervals/event years, budget/value floors, empty options,
  invalid references, and model guards.
- BAU tests for annual and multi-year cycles, budget truncation and unenforced violations, capacity,
  action filters, empty/invalid inputs, and like-for-like comparison.
- Report tests for optimized/BAU rows, monitoring allocation, overruns, mismatched scopes, row totals,
  and JSON round-trips.
- Scenario tests for canonical digests, artifact replay, missing/tampered artifacts, archive validation,
  model guards, and the committed example.
- Property tests for duplicate detection, dominance, corridor length conservation, and range checks.
- The self-check that the planning surfaces pass the workflow validator.

The committed synthetic fixture is the shared contract example. A fresh build must match its artifact
digests and content digest; the fixture tests enforce that.

Adding a contract
-----------------

1. Add the schema version and the models.
2. Add the validator and named error prefixes.
3. Add a valid example and at least one failing case per invariant.
4. Add the JSON round-trip.
5. Add the reference page and the API page.
6. Add the contract to this index.
7. Run ``python scripts/dashboard.py``.
