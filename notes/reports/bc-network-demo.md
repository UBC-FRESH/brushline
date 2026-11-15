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

The strategic model uses period-static segment options, five annual periods from 2027 to 2031,
budget-constrained selection, and a risk/service objective. The scenarios are deliberately different
budget-and-risk postures, not an asset-owner policy.

| Scenario | Annual budget | Five-year cost | Mean service | Mean risk | Hours/year |
|---|---:|---:|---:|---:|---:|
| Constrained | 30,000 | 149,895 | 0.745 | 0.257 | 640 |
| Balanced | 60,000 | 299,375 | 0.793 | 0.211 | 1,295 |
| Risk-first | 100,000 | 499,969 | 0.853 | 0.151 | 2,188 |
| BAU five-year mowing | unpriced | 79,082 | 0.747 | 0.257 | 264 |

The fixed-cycle tradeoff is more interpretable than the static portfolio for the frequency question:

- Mowing cycle 2: 237,245 five-year cost, 791 hours/year, mean risk 0.165.
- Mowing cycle 5: 79,082 five-year cost, 264 hours/year, mean risk 0.306.
- Manual cycle 2: 819,062 five-year cost, 3,615 hours/year, mean risk 0.132.
- Manual cycle 5: 273,021 five-year cost, 1,205 hours/year, mean risk 0.295.

These numbers support the intended argument: minimize cost by treating rarely, but pay with a higher
cumulative risk. The current model does not yet carry the chosen treatment state forward as a
period-to-period transition, so the strategic portfolio is a screening example rather than a final
optimal policy.

## Tactical and operational examples

The balanced strategic scenario becomes a **25-action tactical program**:

- Tactical cost: 299,375 CAD over five years.
- Resource-plan cost: 347,840 CAD with modelling overheads.
- Modelled contractor capacity: 9,200 hours/year.
- Balanced demand: 1,295 hours/year, about 14 percent of modelled capacity.
- Operations: 25 work-ready orders with crew assignments and sequence days.

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
- The strategic options are period-static; growth and treatment carry-over are not yet coupled.
- No BC Hydro clearance standard, outage constraint, access permission, or safety certification is
  claimed.

## Evidence

- Generator: `tools/build_bc_network_demo.py`.
- Outputs: ignored runtime `runtime/private/bc-network/model/`.
- Studio API: `/api/studio/network?instance_id=bc-hydro-network`.
- Tests: network summary, block, scene, and planning artifact endpoints are covered when the runtime
  model is present; no raw public-data payload is tracked in the repository.
