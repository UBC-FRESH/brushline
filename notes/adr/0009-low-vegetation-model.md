# ADR 0009: Build the low-vegetation state-transition core and reuse the components

Status: accepted
Date: 2026-11-14
Issues: #13

## Context

Brushline needs a model of shrub and young-tree height, cover, density, and resprouting, and of how a
treatment changes them. The review in `notes/reference/shrub-young-tree-growth-models.md` assessed 18
candidate models and families.

No open, validated, segment-level model was found that combines:

- shrub and young-tree state;
- method-specific treatment transitions and resprouting;
- corridor access and infrastructure clearance;
- uncertainty and observation updates;
- a runtime suitable for a metaheuristic search.

The closest candidates are MEDFATE (GPL/LGPL, R/C++, Mediterranean, cohort-based with shrub cohorts and
shrub cutting), FVS/FFE (public domain, tree-centric; live herb and shrub fuels are not dynamically
simulated), LANDIS-II (Apache-2.0, landscape cohorts), ST-Sim (CC BY-ND, framework), TASS/VDYP/TIPSY
(tree yield), and Botequim et al. (shrub biomass accumulation, CC BY-NC, Portugal).

## Decision

Build a lightweight, open, modular **low-vegetation state-transition model** as the Brushline core, and
reuse components where they are validated and licence-compatible:

- allometric and biomass equations for functional groups;
- published growth, recovery, and fuel-accumulation relationships as priors;
- cohort and state-transition concepts from MEDFATE, LANDIS-II, and the state-and-transition frameworks;
- FVS/FFE shrub and fuel relationships as a comparison and prior;
- field plots, LiDAR, and treatment history for calibration;
- Nemora for distribution fitting and uncertainty;
- Fresh Solutions for schedule search.

The model is benchmarked against MEDFATE, FVS/FFE, and Botequim-type curves on the same segments where
the data allow. It publishes a model card with its applicability domain, error, and caveats.

## Consequences

- Brushline owns the calibration and validation burden for the low-vegetation model.
- The model can be segment-level, treatment-aware, uncertainty-aware, and fast enough for the search.
- The open model is a contribution in its own right, not a private black box.
- The decision is revisitable if an open candidate passes the Brushline validation case.
- The model's domain is explicit; an out-of-domain segment is flagged, not predicted silently.

## Alternatives considered

- **Embed MEDFATE.** Rejected for the core: R runtime, Mediterranean calibration, stand scale, daily
  water/carbon cost, and missing corridor/treatment-cost layer. It remains a benchmark and a possible
  optional high-fidelity adapter.
- **Use FVS/FFE.** Rejected: it does not dynamically simulate live herb and shrub fuels and is
  tree-centric.
- **Use LANDIS-II.** Rejected: landscape scale and parameter burden.
- **Use ST-Sim.** Rejected: framework, not a growth model; the ND licence blocks derivative reuse.
- **Use a fixed growth rate or a look-up table.** Rejected: it cannot represent treatment transitions,
  uncertainty, or climate and site variation.
- **Buy a proprietary utility model.** Rejected: no inspectable evidence and no open validation.
