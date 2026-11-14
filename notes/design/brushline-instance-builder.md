# Brushline FEMIC-Extended Instance Builder

Status: draft for Phase 0 review
Phase: P0
Date: 2026-11-14
Task: P0.10
Related: ADR 0008, ADR 0012, `notes/design/brushline-lidar-and-open-data.md`

## 1. Purpose

Brushline should be agile to deploy: point at an area of interest on a map, resolve the available public
and approved private data, materialize and preprocess it, compile a corridor dataset, seed the vegetation
state, validate the result, and hand back a reviewable model instance.

The lab already has most of the machinery in FEMIC:

- `femic instance init` scaffolds a deployment workspace;
- `config/rebuild.spec.yaml` declares steps, dependencies, mutable artifacts, expected outputs, and
  invariants;
- `femic instance rebuild` runs the spec with a dry-run, baseline, and allowlist;
- FreshForge validates, inspects, plans, and runs a provider graph;
- `femic data bcdc-resolve`, `bcdc-fetch`, and `bcdc-order` discover and retrieve BC Data Catalogue
  sources, with plan-only and bulk guardrails;
- DataLad and Arbutus materialize large payloads with manifests and checksums;
- `femic prep validate-case` and `geospatial-preflight` check the environment and the inputs;
- the LiDAR, inventory, climate, disturbance, EFI, and site-index contracts are already defined.

**Brushline will not create a second instance-builder package.** It will add a small FEMIC extension and
instance template, and an optional agent layer on top of the deterministic stages.

## 2. Boundary

| Concern | Owner |
| --- | --- |
| Instance workspace, directories, config templates | FEMIC |
| Rebuild spec, dependency order, invariants | FEMIC |
| FreshForge graph validation, inspection, planning, run | FEMIC |
| Data catalogue discovery, fetch, order, bulk guardrails | FEMIC |
| DataLad, Arbutus, annex, checksums | FEMIC |
| Preflight and geospatial environment checks | FEMIC |
| LiDAR, terrain, canopy, trees, ALS inventory, model cards | FEMIC |
| Site-index reconciliation | FEMIC |
| Corridor segmentation,Brushline dataset compile, state seeding | Brushline provider nodes |
| Scenario, targets, plan, and studio contracts | Brushline |
| Low-vegetation model and observation model | Brushline |
| Agent capabilities and validators | Brushline extension, optional |

The extension is optional. Brushline core can build, validate, and simulate a supplied dataset without
FEMIC. The instance builder requires the FEMIC extension.

## 3. User journey

### 3.1 Point at the map

1. The user opens the model-builder skin.
2. The user draws or selects an AOI, or selects a corridor from an asset layer.
3. The user chooses the asset type: transmission line, pipeline, railway, road, or another linear feature.
4. The user sets the management standard, the planning horizon, and the currency.
5. The user sees a data-availability and coverage map: public sources, private connectors, and gaps.
6. The user reviews a fetch plan: source, query, estimated size, estimated time, licence, access status,
   and cost.
7. The user approves the public sources and any private connector.
8. The build runs as a FreshForge graph; the progress stream shows each stage.
9. The review screen shows the compiled dataset, the coverage, the gap report, the model cards, the
   initial state, the scenario, and the open questions.
10. The user accepts the instance, requests a change, or stops. Publication is a separate approval.

### 3.2 Command line

The same journey is available without the browser:

```bash
femic instance init --instance-name brushline-example --instance-root <path>
brushline instance plan --instance-root <path> --aoi aoi.geojson --asset-type transmission
brushline instance build --instance-root <path> --approve-public --plan-only
brushline instance build --instance-root <path> --approve-public
brushline instance review --instance-root <path>
```

The exact command names are a Phase 2 contract; the workflow is the stable part.

## 4. Stage chain

Each stage has an input, an output, a deterministic tool, a validator, and a failure mode. A stage cannot
be skipped by the agent.

| Stage | Input | Output | Tool | Validator | Failure mode |
| --- | --- | --- | --- | --- | --- |
| Intent | AOI, asset type, standard, horizon | `intent.yaml` | Brushline | Geometry valid, CRS, area, corridor intersection | Stop and ask |
| Data scan | Intent | `data_availability.json` | FEMIC catalogue + connectors | Source, licence, vintage, coverage | Report gaps; do not fabricate |
| Fetch plan | Availability | `fetch_plan.json` | FEMIC `plan-only` | Size, cost, licence, approval | Stop for approval |
| Materialize | Approved plan | `materialization.json`, payloads | FEMIC + DataLad | Checksum, size, licence, path containment | Stop and report |
| Preprocess | Payloads | Terrain, canopy, inventory, access | FEMIC | CRS, grid, resolution, model card, coverage | Stop and report |
| Segment | Corridor geometry | `segments.parquet` | Brushline | Geometry, topology, length, key | Stop and report |
| State seed | Segment + products | `state.parquet` | Brushline | Coverage, applicability, distribution | Mark unknown/partial |
| Compile | Segment + state + site + access | `dataset/` and manifest | Brushline | Schema, referential integrity, digest | Stop and report |
| Scenario | Dataset + standards + targets | `scenario/` | Brushline | Schema, target parse, dry-run | Stop and report |
| Validate | Instance | `review.json` | Brushline + FEMIC | Full validator set | Stop and report |
| Handoff | Review | Instance repo, docs, evidence | Brushline | Publication hygiene, licences, provenance | Stop for approval |

## 5. FEMIC extension points

### 5.1 Instance template

The template adds to the standard FEMIC layout:

```text
config/
  brushline/
    scenario.yaml
    targets.yaml
    standards.yaml
    model_cards/
  rebuild.spec.yaml
  rebuild.allowlist.yaml
data/
  pointers/
  manifests/
dataset/
scenarios/
runs/
tests/
runbooks/
docs/
evidence/
demo/
```

The template is an instance-owned repository. Large payloads stay in DataLad, an annex, or the owner's
storage.

### 5.2 Rebuild spec

The `config/rebuild.spec.yaml` adds Brushline steps with explicit dependencies and invariants:

```yaml
steps:
  - step_id: "brushline_segment"
    kind: "brushline_command"
    command: "brushline instance segment --instance-root ${instance.root}"
    required: true
    depends_on: ["femic_lidar_products"]
    expected_outputs: ["data/brushline/segments.parquet"]

  - step_id: "brushline_compile"
    kind: "brushline_command"
    command: "brushline instance compile --instance-root ${instance.root}"
    required: true
    depends_on: ["brushline_segment", "brushline_state_seed"]
    expected_outputs: ["dataset/manifest.json"]

invariants:
  - invariant_id: "segment_key_unique"
    severity: "fatal"
    metric: "segment_duplicate_count"
    comparator: "eq"
    target: 0
    remediation: "Check the corridor split and the stable key rule."
```

The rebuild spec is the deterministic plan. The agent can propose a spec, but FreshForge validates it
before anything runs.

### 5.3 Provider nodes

Brushline registers provider nodes in the FreshForge graph:

| Node | Purpose |
| --- | --- |
| `brushline.validate_aoi` | Validate the AOI geometry, CRS, area, and corridor intersection |
| `brushline.segment_corridor` | Build the corridor graph and the segment table |
| `brushline.compile_dataset` | Compile the versioned Brushline dataset and manifest |
| `brushline.seed_vegetation_state` | Initialize the state from LiDAR, inventory, plots, and history |
| `brushline.validate_scenario` | Validate the scenario, targets, and a dry-run simulation |
| `brushline.build_demo` | Export a demo manifest and the static demo artifacts |

Each node is a thin wrapper over a Brushline command. It does not contain a second implementation of the
command.

### 5.4 Provider API pin

The extension pins:

- the FEMIC version or tag;
- the FreshForge version;
- the provider entry-point group;
- the contract tests that fail if the provider signature changes.

A FEMIC upgrade is a deliberate compatibility task, not a silent dependency update.

## 6. Agent architecture

### 6.1 Roles

The agent is an orchestrator, not a model runtime. It can:

- interpret the user's intent and ask clarifying questions;
- inspect the data availability and the fetch plan;
- propose a source selection and a rebuild spec;
- call the allowlisted FEMIC and Brushline tools;
- explain a validator failure and propose the next bounded action;
- draft the instance README, the runbook, and the review summary.

It cannot:

- compute an authoritative number, coefficient, geometry, or validation result;
- read a private data source without an approved connector;
- bypass a validator or an approval gate;
- publish, promote, or spend without approval;
- run an arbitrary shell command.

### 6.2 Capability contract

A capability is:

```text
prompt
  + tool allowlist
  + validator over real state
  + bounded retry budget
  + recorded outcome
```

Examples:

- **Select AOI capability:** prompt asks for the AOI and asset type; validator checks geometry, CRS, area,
  and corridor intersection; retry budget 2; failure asks the user.
- **Fetch-plan capability:** prompt proposes sources; validator checks licence, coverage, size, and
  approval; retry budget 1; failure reports the gap.
- **State-seed capability:** prompt maps products to state classes; validator checks coverage,
  applicability, and distribution; retry budget 1; failure marks the segment unknown or partial.
- **Compile capability:** prompt runs the compiler; validator checks schema, keys, and digest; retry
  budget 0; failure stops.

A capability without a validator is not shipped. Each capability has an offline test with a fake provider
and a real validator.

### 6.3 Prompt and transcript hygiene

- Prompts are versioned in the package or the instance.
- A prompt never contains private rows, credentials, or personal data.
- A raw transcript is not committed to the repository.
- The recorded outcome is a sanitized summary: the capability, the input hash, the validator result, the
  tool calls, and the final state.

## 7. Validators

| Validator | What it checks | Failure |
| --- | --- | --- |
| AOI | Geometry valid, CRS, area, corridor intersection | Stop and ask |
| Source | Provider, dataset, licence, vintage, coverage | Report gap |
| Fetch plan | Size, cost, access, approval | Stop for approval |
| Materialization | Checksum, size, path containment, licence | Stop and report |
| Raster/vector | CRS, grid, resolution, alignment, no silent reprojection | Stop and report |
| Model card | Id, version, error, predictor range, region, licence | Flag out of domain |
| Segment | Geometry, topology, length, unique key | Stop and report |
| State | Coverage, applicability, distribution, sum | Mark unknown/partial |
| Dataset | Schema, keys, referential integrity, units, digest | Stop and report |
| Scenario | Targets parse, dry-run finite, budget/capacity | Stop and report |
| Replay | Same config and seed reproduce | Stop and report |
| Publication | No private data, no personal path, licences, provenance | Stop for approval |

## 8. Data catalogue and connectors

### 8.1 Public sources

- LidarBC (point cloud, DEM, DSM, canopy, trees);
- VRI, VDYP, SIBEC;
- DRA, FTEN, roads;
- NTEMS, HLS, Landsat;
- climate (ClimateNA/SilvR21);
- BEC, ownership, protected areas, TSA/FMU boundaries;
- terrain, hydrography, and stream candidates.

### 8.2 Private sources

- asset registry and structure inventory;
- treatment history and inspection records;
- contractor rates, contracts, and access restrictions;
- field plots and monitoring observations;
- cost, outage, and reliability history.

### 8.3 Connector registry

Each connector declares:

- id, owner, description, and classification;
- authentication method (outside the repository);
- read scope and row/column filters;
- allowed outputs (raw, derived, aggregate);
- audit and retention rules;
- a test connection and a sample metadata response.

A connector that is not registered cannot be called by the agent.

## 9. Public and private separation

- The public demo uses public or synthetic data only.
- A private deployment uses the owner's tenancy and access controls.
- The agent sees metadata only until the owner approves a connector.
- Credentials stay in the environment or a secret store.
- The prompt and the model provider never receive private rows.
- A derived artifact is reviewed before it leaves the owner's tenancy.
- The instance repository tracks pointers, manifests, and checksums, not payloads.

## 10. Approval gates

| Gate | Approval |
| --- | --- |
| Public network fetch | User, with a fetch plan |
| Bulk fetch | User, with `--allow-bulk` and a plan |
| Private connector | Owner, with a data-sharing record |
| Repository creation | Maintainer |
| Publication | Maintainer |
| Operational promotion | Owner and qualified reviewer |
| Spending or purchase | Owner |

The agent cannot grant an approval. It can request one and record the response.

## 11. Map experience

- **AOI:** draw a polygon, select a corridor, or upload a GeoJSON.
- **Availability:** public sources, private connectors, coverage, vintage, and licence.
- **Fetch plan:** source, query, size, time, cost, access, and approval.
- **Progress:** stage, tool, validator, elapsed time, and current artifact.
- **Gap report:** missing coverage, out-of-domain model, unavailable private source, and a recommended
  next action.
- **Review:** dataset summary, segment count, state distribution, model cards, scenario, targets, and open
  questions.
- **Handoff:** instance path or repository, documentation, evidence, and the next step.

The map is a data-availability and coverage map, not a decorative basemap.

## 12. Reproducibility

The instance records:

- the FEMIC version, FreshForge version, Brushline version, and provider version;
- the source manifests, checksums, and retrieval dates;
- the rebuild spec and the resolved configuration;
- the model cards and the state version;
- the seed for any stochastic step;
- the review and approval record.

A rebuild with the same inputs and versions reproduces the same dataset digest. A changed source, model, or
configuration produces a new digest and a new review.

## 13. Failure rules

- A missing required source stops the build.
- A coverage gap marks the affected segments unknown or partial; it does not stop the whole build unless
  the scenario requires full coverage.
- A licence ambiguity stops the source.
- A validator failure stops the capability and reports the evidence.
- A retry budget is bounded; exhaustion stops the capability.
- The agent never fabricates a source, a coefficient, a geometry, or a successful validation.
- The build never publishes or promotes automatically.

## 14. Acceptance criteria

- A new Brushline instance is scaffolded and built through FEMIC's instance, rebuild-spec, and FreshForge
  surfaces.
- The extension is optional; Brushline core installs without FEMIC.
- The design names the FEMIC extension points and the Brushline provider nodes.
- Every stage has an input, output, tool, validator, and failure mode.
- Every capability has a validator and an offline fake-provider test.
- Private data cannot reach a prompt, a tracked file, or a public artifact without approval.
- The review screen shows the coverage, gaps, licences, provenance, and open questions.
- The dashboard is green.

## 15. Open questions

| Question | Resolve in |
| --- | --- |
| Which FEMIC provider API is stable enough to pin? | P2 |
| Which Brushline stages belong in FEMIC's provider vocabulary versus the instance template? | P2 |
| What is the minimum data package for a useful first instance? | P2 |
| How should a partial-coverage segment enter the state distribution? | P3 |
| Which private connectors are safe to prototype without a partner? | P2 |
| How are agent prompts versioned and reviewed? | P2 |
| What is the publication checklist for an instance? | P2 |
