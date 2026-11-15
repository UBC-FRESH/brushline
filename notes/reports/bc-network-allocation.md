# BC network column-master experiment

## Experiment

Each spatial cluster contributed exact stateful MILP columns under six annual budget/capacity
profiles relative to its risk-mass share. A multiple-choice master selected one column per cluster
under the global annual budget and crew-hour constraints.

## Result

| Segments | Clusters | Columns | Column generation s | Master s | Master integer | Plan risk | Plan cost |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 590 | 4 | 24 | 109.9 | 0.008 | 0.030538 | 0.0305 | 2,986,703 |
| 2,950 | 20 | 120 | 500.9 | 0.068 | 0.031659 | 0.0317 | 14,982,944 |

For comparison:

- exact 590-segment MILP: z* `0.029145`, about 0.68 s;
- exact 59-segment MILP: z* `0.029164`, about 0.23 s;
- cluster repair seed objective: about `0.0292`.

The column master is worse than both the global MILP at 590 and the heuristic/repair plans. It is
also far slower because it solves six exact cluster MILPs per cluster.

The master LP relaxation is a lower bound only for the **restricted column set**, not for the full
cluster problem. It cannot be reported as a global lower bound.

## Decision

Do not integrate this column master or use it for allocation. The fixed budget/capacity profiles
force an inefficient spatiotemporal allocation; the master cannot recover the flexibility of a
global annual budget.

The next credible method is Benders decomposition with cluster value functions or a master that
allocates annual budgets itself, rather than choosing from precomputed independent profiles.

## Reproduction

The experiment was run from the local bc-network scaling segments with six profiles
`(0, 0.5, 1, 1.5, 2, 3)` and 150-segment clusters. It is recorded here as a negative result; no
production module is retained.
