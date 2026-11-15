# BC Hydro network demo prototype

## Purpose

This is a proof-of-concept decision-support instance at a scale that can be shown to a utility or
agency. It uses real public line geometry and real public forest-cover attributes, with explicit
prototype assumptions for cost, productivity, access, and contractor capacity.

## Scope

- AoI area: **8,737 ha**.
- Mapped network: **29.2 km** across **4 power-line features**.
- Two features are OSM-tagged **BC Hydro 500 kV** circuits; two are **25 kV distribution lines** with
  operator untagged in OSM.
- **59 segments**, grouped into **17 management units**.
- Public inputs:
  - OpenStreetMap power-line and tower geometry (ODbL-1.0).
  - BC Vegetation Resources Inventory 2020 stand attributes (BC Open Government Licence).
  - Copernicus DEM GLO-30 terrain (Copernicus licence).

## Strategic examples

The strategic model uses stateful segment risk, five annual periods from 2027 to 2031, budget and
crew-hour constraints, and a deterministic risk-per-dollar treatment policy. The scenarios are
deliberately different budget-and-risk postures, not an asset-owner policy.

| Scenario | Annual budget | Five-year cost | Mean service | Mean risk | Hours/year |
|---|---:|---:|---:|---:|---:|
| Stateful constrained | 30,000 | 147,399 | 0.881 | 0.119 | 491 |
| Stateful balanced | 60,000 | 299,859 | 0.967 | 0.033 | 1,000 |
| Stateful risk-first | 100,000 | 395,409 | 0.985 | 0.015 | 1,318 |
| BAU five-year mowing | unpriced | 79,082 | 0.590 | 0.410 | 264 |

The stateful fixed-cycle tradeoff carries risk forward between treatments:

- Mowing cycle 2: 237,245 five-year cost, 791 hours/year, mean risk 0.048.
- Mowing cycle 5: 79,082 five-year cost, 264 hours/year, mean risk 0.159.
- Manual cycle 2: 819,062 five-year cost, 3,615 hours/year, mean risk 0.018.
- Manual cycle 5: 273,021 five-year cost, 1,205 hours/year, mean risk 0.087.

These numbers support the intended argument: minimize cost by treating rarely, but pay with a higher
cumulative risk. The treatment policy is a deterministic risk-per-dollar heuristic, not an exact
multi-period optimizer.

## Tactical and operational examples

The stateful balanced scenario becomes a **75-action tactical program**:

- Tactical cost: 299,859 CAD over five years.
- Resource-plan cost: 276,103 CAD with modelling overheads.
- Modelled contractor capacity: 9,200 hours/year.
- Balanced demand: 1,000 hours/year, about 11 percent of modelled capacity.
- Operations: 75 work-ready orders with crew assignments and sequence days.

The resource comparison is useful in both directions: spare capacity can support recruitment
headroom, while a capacity shortfall would trigger a contractor ramp-up or a different allocation.

## Studio instance

The instance is `bc-hydro-network` in the lab studio. It shows the network map, VRI-based 3D stand
context, strategic budget table, fixed-cycle risk tradeoff, and operational work-order sequence.

## Limits

- The distribution-line ownership is not established by OSM tags.
- Costs, hours, productivity, access status, contractor capacity, and clearance outcomes are demo
  assumptions.
- Stand values are VRI attributes sampled to segment midpoints and VRI stand centroids, not a field
  survey or stem map.
- The strategic policy is a deterministic heuristic, not an exact multi-period optimizer.
- No BC Hydro clearance standard, outage constraint, access permission, or safety certification is
  claimed.

## Evidence

- Generator: `tools/build_bc_network_demo.py`.
- Outputs: ignored runtime `runtime/private/bc-network/model/`.
- Studio API: `/api/studio/network?instance_id=bc-hydro-network`.
- Tests: network summary, block, scene, and planning artifact endpoints are covered when the runtime
  model is present; no raw public-data payload is tracked in the repository.
