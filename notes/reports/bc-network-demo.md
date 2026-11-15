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
crew-hour constraints, and a linearized mixed-integer program solved with HiGHS through SciPy. The
risk state is exact for the declared linear growth/treatment definition and is independently
replayed after each solve. The scenarios are different budget postures, not an asset-owner policy.

| Scenario | Annual budget | Five-year cost | Mean service | Mean risk | Hours/year |
|---|---:|---:|---:|---:|---:|
| MILP constrained | 20,000 | 99,731 | 0.826 | 0.174 | 332 |
| MILP mid | 30,000 | 149,378 | 0.899 | 0.101 | 498 |
| MILP balanced | 60,000 | 299,859 | 0.971 | 0.029 | 1,000 |
| MILP risk-first | 100,000 | 499,719 | 0.991 | 0.009 | 1,620 |
| BAU five-year mowing | unpriced | 79,082 | 0.590 | 0.410 | 264 |

The budget sweep produces a non-dominated cost/risk frontier from about 98k (risk 0.200) to 395k
(risk 0.015). Capacity sensitivity at a 100k budget shows the resource constraint: 300 h/year yields
about 89k cost and risk 0.221; 1,000 h/year yields about 300k cost and risk 0.033; 1,500 h/year
reaches risk 0.015. The stateful fixed-cycle tradeoff carries risk forward between treatments:

- Mowing cycle 2: 237,245 five-year cost, 791 hours/year, mean risk 0.048.
- Mowing cycle 5: 79,082 five-year cost, 264 hours/year, mean risk 0.159.
- Manual cycle 2: 819,062 five-year cost, 3,615 hours/year, mean risk 0.018.
- Manual cycle 5: 273,021 five-year cost, 1,205 hours/year, mean risk 0.087.

These numbers support the intended argument: minimize cost by treating rarely, but pay with a higher
cumulative risk. The treatment policy is a deterministic risk-per-dollar heuristic, not an exact
multi-period optimizer.

## Tactical and operational examples

The Fresh Solutions heuristic provides a scalable path beyond the exact MILP. On the current dev
server, replicated cases scale from 59 segments (295 variables) to 10,030 segments (50,150 variables);
the largest case takes about 11 seconds with 20 local-search iterations after the greedy seed. It is
feasible-only, not an optimality proof.

The MILP balanced scenario becomes an **84-action tactical program**:

- Tactical cost: 299,859 CAD over five years.
- Resource-plan cost: 277,093 CAD with modelling overheads.
- Modelled contractor capacity: 9,200 hours/year.
- Balanced demand: 1,000 hours/year, about 11 percent of modelled capacity.
- Operations: 84 work-ready orders plus 698 crew/machine shift assignments.
- Shift scheduling includes travel and splits long jobs across days; it is a FHOPS-style prototype,
  not a FHOPS engine run.

The resource comparison is useful in both directions: spare capacity can support recruitment
headroom, while a capacity shortfall would trigger a contractor ramp-up or a different allocation.

## Studio instance

The instance is `bc-hydro-network` in the lab studio. It shows the network map, VRI-based 3D stand
context, MILP budget/frontier tables, Fresh Solutions scaling evidence, workforce scenarios, and
year-filtered shift assignments.

## Limits

- The distribution-line ownership is not established by OSM tags.
- Costs, hours, productivity, access status, contractor capacity, and clearance outcomes are demo
  assumptions.
- Stand values are VRI attributes sampled to segment midpoints and VRI stand centroids, not a field
  survey or stem map.
- The MILP is exact for the linearized risk definition, not for a full nonlinear vegetation model.
- The frontier and capacity tables are screening tools for budget and contractor discussions.
- No BC Hydro clearance standard, outage constraint, access permission, or safety certification is
  claimed.

## Evidence

- Generator: `tools/build_bc_network_demo.py`.
- Outputs: ignored runtime `runtime/private/bc-network/model/`.
- Studio API: `/api/studio/network?instance_id=bc-hydro-network`.
- Tests: network summary, block, scene, and planning artifact endpoints are covered when the runtime
  model is present; no raw public-data payload is tracked in the repository.
