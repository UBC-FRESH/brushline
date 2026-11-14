# ADR 0008: FEMIC owns LiDAR production and the instance builder; Brushline extends it

Status: accepted
Date: 2026-11-14
Issues: #10

## Context

The lab already has a producer pipeline for open LiDAR and a deployment-instance workflow:

- FEMIC discovers and materializes LidarBC tiles, derives terrain, canopy, tree, and bundle products,
  applies ALS inventory model cards, and reconciles site index.
- WS4 and FHOPS already consume the versioned `femic.lidar.product.v1` bundles.
- FEMIC has `instance init`, `config/rebuild.spec.yaml`, `femic instance rebuild`, FreshForge provider
  graphs, BC Data Catalogue discovery/fetch, DataLad materialization, and preflight checks.
- Fresh-road provides the ALSroads road-status bridge.

Building a second LiDAR pipeline or a second instance builder would duplicate maintenance, split the
provenance boundary, and create two incompatible data contracts.

## Decision

**FEMIC is the LiDAR producer and the instance builder.** Brushline consumes its contracts and extends
its provider vocabulary:

- consume `femic.lidar.product.v1` / `femic.lidar.bundle.v1` bundles, terrain, canopy, tree, and ALS
  inventory products;
- consume the climate, disturbance, EFI model-card, and site-index contracts;
- add a small FEMIC extension and instance template with `brushline.*` provider nodes for AOI
  validation, corridor segmentation, dataset compilation, state seeding, scenario validation, and demo
  export;
- use the FEMIC instance layout, rebuild spec, FreshForge graph, catalogue, DataLad, and preflight;
- do not download tiles, classify ground returns, compile terrain, or build a second instance workspace;
- do not derive a new ALS site-index model; use VRI, VDYP, and SIBEC;
- keep Brushline core installable without FEMIC; the extension is optional.

## Consequences

- Brushline inherits FEMIC's producer provenance, licences, and validation.
- The Brushline extension depends on FEMIC's CLI and provider entry points; those must stay stable and
  versioned.
- A new AOI is a FEMIC instance plus a Brushline scenario, not a new pipeline.
- The LiDAR coverage limits and model-card applicability remain visible in every derived state.
- A second consumer of the same bundle (WS4, FHOPS, Brushline) keeps the producer contract honest.

## Alternatives considered

- **Rebuild the LiDAR pipeline in Brushline.** Rejected: duplicate maintenance and two provenance
  boundaries.
- **Create a new instance-builder package.** Rejected: FEMIC already has the workspace, stages, graph,
  catalogue, materialization, and preflight.
- **Read LAZ directly in Brushline.** Rejected for the core: the producer owns point-cloud processing;
  a specialised low-vegetation metric may be added through the FEMIC extension if needed.
- **Derive a new ALS site index.** Rejected: the provincial products exist, and the VRI proxy is
  circular.
