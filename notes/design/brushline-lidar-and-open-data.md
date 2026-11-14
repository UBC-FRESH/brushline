# Brushline Open LiDAR, Terrain, Canopy, and Reuse

Status: draft for Phase 0 review
Phase: P0
Date: 2026-11-14
Task: P0.9
Related: ADR 0008, `notes/design/brushline-architecture.md`,
`notes/reference/shrub-young-tree-growth-models.md`

## 1. Purpose

Open LiDAR is one of the most useful inputs to Brushline, and one of the easiest things to duplicate
badly. The lab already has a producer pipeline, versioned contracts, and two consumers. Brushline must
consume them, not rebuild them.

This note records:

- the producer/consumer boundary;
- the contracts Brushline reuses;
- what LiDAR can and cannot tell us about low vegetation;
- the state-initialization workflow;
- the coverage and applicability rules;
- the site-index rule;
- the road-status path;
- the map and 3D use;
- the licence and provenance requirements;
- what Brushline will not rebuild.

## 2. Boundary

```text
LidarBC / OGL-BC open data
        |
        v
FEMIC (producer)
  discovery -> materialization -> terrain -> canopy -> trees
  -> inventory model cards -> product bundle
        |
        +----------------------+----------------------+
        |                      |                      |
        v                      v                      v
      WS4                   FHOPS                 Brushline
  dataset consumer      scenario consumer      state consumer
  lidar_* fields        lidar_products/support  segment state
        |                      |                      |
        +----------------------+----------------------+
                               |
                               v
                    source-preserving provenance
```

FEMIC owns:

- LidarBC discovery and tile selection;
- resumable materialization and checksums;
- terrain, slope, and stream candidates;
- CHM, canopy structure, and VRI comparison;
- optional individual-tree product ingestion;
- ALS inventory model cards and predictions;
- product bundle validation;
- site-index reconciliation.

WS4 owns:

- the compiled-dataset consumer;
- the `lidar_*` fragment and block fields;
- the dataset manifest registration;
- the web LiDAR tab.

FHOPS owns:

- the scenario consumer;
- `lidar_products` and `lidar_support`;
- operability and 3D operations use.

Brushline owns:

- the segment-level state initialization;
- the low-vegetation calibration and model card;
- the observation model and the monitoring decision;
- the plan and the studio layers.

Brushline does not own the producer pipeline, the tile download, or the terrain/canopy compilation.

## 3. Contracts to reuse

| Contract | Producer | Brushline use |
| --- | --- | --- |
| `femic.lidar.selection.v1` | FEMIC | Understand the AOI, products, and tile selection behind a bundle |
| `femic.lidar.materialization.v1` | FEMIC | Verify that the source tiles were materialized and checksummed |
| `femic.lidar.terrain_qa.v1` | FEMIC | DEM/DSM provenance, slope, and QA |
| `femic.lidar.canopy_qa.v1` | FEMIC | CHM provenance and QA |
| `femic.lidar.canopy_structure.v1` | FEMIC | Height and cover structure |
| `femic.lidar.individual_tree.v1` | FEMIC | Optional tree counts, heights, crowns, and species |
| `femic.lidar.product.v1` | FEMIC | Bundle manifest and product records |
| `femic.lidar.bundle.v1` | FEMIC | Bundle layout |
| `femic.inventory.als.v1` | FEMIC | Long ALS inventory attribute table |
| `femic.inventory.als.model.v1` | FEMIC | Model card and applicability domain |
| `femic.climate.v1` | FEMIC | Climate modifiers for growth |
| `femic.disturbance.v1` | FEMIC | Disturbance events and recovery context |
| `femic.efi.model.v1` | FEMIC | EFI model metadata |
| `fresh.road.status.v1` | fresh-road | ALSroads road status, source-preserving |

Brushline reads the manifest before any product file, pins the `bundle_id` and `bundle_version`, verifies
every product checksum, and honors the recorded CRS, resolution, and vertical datum.

## 4. What LiDAR provides

### 4.1 Terrain

- DEM and DSM at the native resolution.
- Slope, aspect, and terrain class.
- Drainage and stream candidates where the producer supplies them.
- Access and machine operability proxies.

### 4.2 Canopy and vegetation structure

- CHM: canopy height model.
- Canopy height statistics: mean, median, p90, p95, p99, max.
- Cover at thresholds: 2, 5, 10, and 20 m.
- Canopy structure: vertical distribution where the product supplies it.
- Optional individual-tree products: tree count, height, crown radius, and species.

### 4.3 Inventory attributes

- ALS area-based predictions such as Lorey height, basal area, and gross volume.
- Model card: model id, training data, validation, RMSE or bias, predictor ranges, applicability.
- Site-index reconciliation from VRI, VDYP, and SIBEC.

### 4.4 Access and roads

- DEM/DSM for terrain and slope.
- `fresh-road` / ALSroads road status: class, width, cover, score, and passability evidence.
- Source class preserved; no open/closed verdict without a management decision.

### 4.5 Change and observations

- Repeat LiDAR or imagery for change detection.
- Canopy and cover change as an observation.
- Clearance and encroachment evidence where the data supports it.
- Monitoring coverage and gaps.

## 5. State initialization

### 5.1 Workflow

```text
segment geometry
  -> select the validated bundle(s)
  -> clip or aggregate products to segment support
  -> attach terrain, slope, canopy, cover, and optional tree metrics
  -> attach ALS inventory attributes and model cards
  -> attach climate, disturbance, and site index
  -> classify the low-vegetation state
  -> attach uncertainty, coverage, and applicability
  -> write the initial state table
```

### 5.2 Aggregation rules

- Use zonal statistics over the segment polygon or a buffer, not a point sample.
- Record the statistic: mean, median, p90, p95, min, max, or count.
- Record the buffer width and the minimum valid-pixel rule.
- Do not reproject or resample a delivered product silently.
- If a segment spans products or tiles, record the overlap and the weighting.
- If the valid coverage is below the threshold, mark the segment **missing** or **partial**.

### 5.3 Initial state classes

The first release uses:

- **unknown:** no usable observation;
- **partial:** a usable observation covers part of the segment;
- **grass/herb:** low cover, low height, no woody dominance;
- **shrub:** woody cover below the tree threshold, height in the shrub range;
- **young tree:** woody cover and height above the shrub threshold, below the mature-tree threshold;
- **mixed:** more than one functional group above the threshold;
- **mature edge:** mature trees at the corridor edge, a fall-in hazard and a seed source.

The thresholds are a Phase 4 decision, calibrated to the field data. The class is a summary of the
distribution, not a replacement for it.

### 5.4 Low-vegetation gap

The existing ALS area-based models predict mature-forest attributes: Lorey height, basal area, and gross
volume. They are not a shrub and young-tree model. A CHM can see the top of a shrub layer, but it does not
separate shrub height from young-tree height, and it does not observe resprouting, density, or species
composition reliably.

Brushline must calibrate its own low-vegetation state model. LiDAR supplies:

- a height observation;
- a cover observation;
- a change observation;
- a terrain and access context;
- a sampling frame for field plots.

It does not supply the low-vegetation model by itself. The model card must state the observation error and
the applicability domain.

### 5.5 Site index

Site index is a provincial product:

- VRI `SITE_INDEX` and `EST_SITE_INDEX`;
- VDYP primary-layer `ESTIMATED_SITE_INDEX`;
- SIBEC BEC-unit/site-series/species means and standard errors.

Brushline uses the reconciliation, not a new ALS site-index model. A canopy-height-to-site-index proxy is
circular when the target is itself derived from height and age. If a partner supplies a validated
species-specific model with exact plot coordinates and contemporary ALS, Brushline can consume it as a
model card; it does not fit one by default.

## 6. Coverage and applicability

### 6.1 Coverage states

- **observed:** a product covers the segment within the time window and the valid-pixel threshold.
- **stale:** a product covers the segment but the acquisition is older than the state year allows.
- **partial:** a product covers part of the segment; the rest is unknown.
- **missing:** no product covers the segment.
- **out of domain:** a product covers the segment but the model card's predictor range or region does not.
- **excluded:** the segment is outside the analysis mask (non-forest, water, structure, or access).

Coverage is a state of knowledge. It changes the observation model, the monitoring decision, and the
uncertainty. It is never a zero.

### 6.2 Evidence from the IRSS notes

The IRSS x Silva21 notes record the real coverage limits:

- the TSA 46 site-index pilot found point clouds at 1 of 17 sites and DEM at 2;
- the TSA 23 BA-only inventory pilot reached 14.9 percent coverage and was accepted as experimental, not
  operational;
- the height and volume products remain research-only;
- the VRI site-index proxy is circular and was parked;
- the NSR detection case-control was negative and is not an operational detector;
- DHI and recovery layers are static overlays, not real-time alerts.

Brushline treats these as design evidence, not as a reason to avoid LiDAR. They are the reason coverage
and applicability are first-class.

## 7. Road status

`fresh-road` wraps ALSroads and emits `fresh.road.status.v1`:

- segment id;
- source class;
- passability (unknown in the pilot);
- surface and road class;
- width, drivable width, cover, score, shoulders, sinuosity, and conductivity;
- geometry, source, date, CRS, and notes.

The class is source-preserving. `class_1` to `class_4` are not silently translated to open or closed. A
Brushline plan can use the status as access evidence and as a cost or risk input, but the management
decision remains explicit.

## 8. Map and 3D use

### 8.1 2D map

- Terrain hillshade and slope.
- Canopy height and cover.
- Vegetation state class and uncertainty.
- Observation coverage and gaps.
- Access and road status.
- Structures and crossings.

### 8.2 3D scene

- DEM terrain and hillshade.
- Corridor and structures.
- Vegetation height and cover as instanced or impostor geometry.
- Mature-tree crowns where a tree product exists.
- Machines and crews from the operations timeline.
- A context-view caveat; no survey-grade claim.

### 8.3 What the 3D scene does not do

- It does not reconstruct every stem.
- It does not claim that a crown shape is measured.
- It does not show a machine position that is not in the operations timeline.
- It does not replace a field inspection.

## 9. Licence and provenance

- LidarBC is OGL-BC. The attribution travels with the product and the derived layer.
- The bundle manifest carries the source, licence, CRS, resolution, vertical datum, retrieval date, and
  checksums.
- The Brushline state table carries the bundle pin, the product checksums, the aggregation rule, the model
  card, and the applicability.
- Large point-cloud and raster payloads stay in the instance's data store, DataLad, or an annex; they are
  not committed to the repository.
- A derived layer that leaves the instance carries the same licence and attribution.

## 10. What Brushline will not rebuild

- LidarBC tile discovery or selection.
- Tile materialization, checksum, or resume.
- DEM, DSM, slope, or stream compilation.
- CHM or canopy structure compilation.
- Individual-tree segmentation.
- The FEMIC product bundle or model card.
- The WS4 or FHOPS consumer.
- A new ALS site-index model.
- A fire-spread simulator.
- A national LiDAR change-detection service.

If Brushline needs a low-vegetation point-cloud metric that FEMIC does not expose, the metric is added
through the FEMIC extension and documented as a producer change, not a private Brushline pipeline.

## 11. Acceptance criteria

- A validated FEMIC bundle maps to segment support with a recorded aggregation.
- Every derived attribute carries the bundle pin, product checksum, model card, and applicability.
- Missing, stale, partial, and out-of-domain coverage are reported separately.
- The low-vegetation model does not claim a mature-forest EFI card transfers without a test.
- Site index comes from VRI/VDYP/SIBEC, not a circular ALS proxy.
- The 3D scene is labelled as a context view.
- The design names the producer contracts and the consumer boundary.
- The dashboard is green.

## 12. Open questions

| Question | Resolve in |
| --- | --- |
| Which point-cloud metrics best predict shrub and young-tree height and cover? | P3 and P4 |
| What valid-pixel and buffer thresholds are defensible for a segment? | P3 |
| How should a segment that spans two acquisitions be weighted? | P3 |
| Which low-vegetation field plots are available, and what is the minimum sample? | P3 and P4 |
| How should a coverage gap enter the state distribution and the monitoring policy? | P3 and P8 |
| How much canopy structure is useful in the 3D scene before it implies precision? | P10 |
| Which road-status fields are safe to use in a cost or access model? | P7 |
