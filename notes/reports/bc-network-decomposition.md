# BC network cluster repair benchmark

## Method

The heuristic seed is the Fresh Solutions stateful heuristic with 100 local-search iterations. It is
a seed, not a convergence claim. The seed is partitioned into contiguous span clusters of at most
150 segments. `repair_stateful_clusters` computes each cluster's annual cost and crew-hours from the
seed and solves each cluster with the exact stateful MILP under those fixed budgets. The seed actions
are the fallback for a failed cluster.

This is budget-preserving fix-and-optimize, not a global optimization proof.

## Results

| Segments | Clusters | Heuristic seed s | Cluster repair s | Objective improvement | All clusters optimal | Replay |
|---:|---:|---:|---:|---:|---|---|
| 590 | 4 | 1.76 | 2.11 | 0.134% | yes | yes |
| 2,950 | 20 | 10.33 | 20.96 | 0.070% | yes | yes |
| 10,030 | 68 | 44.82 | 91.76 | 0.115% | yes | yes |

The repair improves the seed on all three cases, but the improvement is small. That is expected:
the seed is already a risk-per-dollar greedy solution, and repair can only rearrange within each
cluster's seed budget.

## Interpretation

- Cluster repair is a practical post-processing step for a heuristic seed.
- It does not eliminate the need for a global allocation/coordination layer.
- The 10k case is the first run in this work with **68/68 exact cluster MILPs reported optimal**, but
  the global plan remains feasible-only.
- No global optimality claim is made for 10k segments.

## Reproduction

`python tools/benchmark_stateful_decomposition.py`

Output: `runtime/private/bc-network/scaling/decomposition.json`.
