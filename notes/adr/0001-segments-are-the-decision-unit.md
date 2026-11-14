# ADR 0001: Segments are the decision unit; spans and treatment units aggregate at runtime

Status: accepted
Date: 2026-11-14
Issues: #5

## Context

A corridor can be represented as a single line, a set of operational work units, a raster, or a graph of
small homogeneous lengths. The choice determines what can be scheduled, how treatments and monitoring
are costed, and whether one dataset can serve several contractors and several planning scales.

Operational work units change with the contract, the crew, the access plan, and the season. Compiling at
that level would bake one layout into the data and force a rebuild whenever the contract changes.

## Decision

Compile and schedule at the **segment** level. A segment is a length of corridor with stable site,
vegetation, access, structure, and treatment attributes. It carries a stable id, a geometry, a linear
reference, and a CRS.

A **span** is a contiguous run of segments between access points, structures, or crossings. A
**treatment unit** is a set of segments scheduled and contracted together. Both are runtime aggregates
built from segments. They are not compilation units and they do not own state.

The corridor is a graph: segments are edges, and junctions, access points, structures, and endpoints are
nodes. Adjacency, continuity, travel, and monitoring routes are computed over that graph.

## Consequences

- One compiled dataset serves many span and treatment-unit layouts.
- A contractor can change the work grouping without a recompile.
- The runtime must aggregate segments to spans and treatment units for cost, access, and reporting.
- Operability is conservative: a span or treatment unit is operable only when its segments are.
- The segment is the stable key for observations, treatments, plans, and evidence.

## Alternatives considered

- **Compile at the treatment-unit level.** Rejected: it fixes one contract layout and duplicates data.
- **Compile at the corridor level.** Rejected: it hides the site and treatment variation that drives the
  decision.
- **Use a raster as the decision unit.** Rejected: the corridor is linear and the management object is a
  length, not a cell.
- **Use individual stems as the decision unit.** Rejected for the first release: the data and the
  treatment cost are not stem-level, and the search would be intractable. Stems remain an optional
  visualization and observation layer.
