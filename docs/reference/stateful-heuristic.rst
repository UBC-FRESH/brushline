Stateful heuristic
==================

The stateful MILP is exact for small clusters, but its binary count grows with segments × periods ×
methods. For larger networks Brushline uses the optional `fresh-solutions` local-search heuristic.

Adapter
-------

`StatefulHeuristicAdapter` exposes one discrete variable per segment-period. Options are
`none`, `mowing`, `manual`, and any other declared method. Evaluation replays the same linear risk
state, treatment transitions, budget, and crew-hour constraints as the MILP.

Search starts from a deterministic risk-per-dollar greedy seed, then uses Fresh Solutions simulated
annealing. The result is explicitly marked **feasible**, not optimal. Every incumbent is replayed;
the plan records the Fresh Solutions version, seed, iterations, evaluations, and accepted moves.

Scaling evidence
----------------

The network demo includes replicated stress cases at roughly 59, 590, 2,950, and 10,030 segments.
On the current dev server the 10,030-segment, 50,150-variable case completes in about 11 seconds with
20 local-search iterations after the greedy seed. The exact MILP remains the benchmark for the
59-segment case.

Limits
------

- The heuristic does not prove optimality.
- The linear risk state remains an abstraction.
- The greedy seed may dominate the search if the local-search budget is small.
- Access, weather, labour rules, and asset-owner standards are separate constraints.
