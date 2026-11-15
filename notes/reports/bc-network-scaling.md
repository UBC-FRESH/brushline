# BC network stateful scaling benchmark

## Method

The benchmark starts from the 59-segment BC network model and creates replicated, slightly
perturbed instances at factors 1, 2, 4, 8, and 16. The perturbations break exact copy symmetry while
preserving the corridor and vegetation structure. Annual budgets and crew-hour capacities scale with
the factor.

For each instance:

- exact stateful MILP: SciPy `milp`/HiGHS, 120 s limit, formulation and solve times recorded separately;
- heuristic: Fresh Solutions population + local search with a convergence rule, not a fixed
  iteration count;
- heuristic gap: relative to the exact `z*` where the MILP proved optimality;
- if the MILP did not prove optimality, report the incumbent gap and dual-bound gap separately.

Heuristic convergence settings:

- population 16, 4 generations, seed 7;
- 1000 local-search iterations;
- convergence: 500 local iterations per round, 5 patience rounds, `1e-4` relative improvement,
  100,000 evaluation cap;
- all runs stopped with `stop_reason=patience` and `converged=true`;
- 2,585 exact evaluations and 5 rounds in each run.

## Exact MILP results

| Segments | Binaries | Formulate s | Solve s | Status | MIP gap | z* |
|---:|---:|---:|---:|---|---:|---:|
| 59 | 885 | 0.0030 | 0.2347 | optimal | 0 | 0.029164 |
| 118 | 1,770 | 0.0076 | 0.6786 | optimal | 0 | 0.029145 |
| 236 | 3,540 | 0.0170 | 5.5660 | optimal | 3.16e-5 | 0.029129 |
| 472 | 7,080 | 0.0271 | 68.9021 | optimal | 0 | 0.029136 |
| 944 | 14,160 | 0.0533 | 120.1497 | time limit | 6.02e-3 | not proved |

The 944-segment run stopped at the 120 s limit with incumbent `0.02929819`, dual bound
`0.02912182`, and gap `6.02e-3`. A longer run may improve the incumbent, but direct MILP is already
behaving as a branch-and-bound problem rather than a useful 10k production path.

Log-log least-squares fit over the four optimal points:

`log(solve_seconds) = 2.763 * log(segments) - 13.1103`

The fitted exponent is **2.76**, which is superquadratic. Four points are not enough to identify the
asymptotic functional form, but they do rule out linear growth in this instance family and show that
the direct MILP is already impractical at 944 segments in this test.

## Fresh Solutions convergence results

| Segments | Heuristic s | Evaluations | Rounds | Converged | Heuristic z | Gap to exact z* |
|---:|---:|---:|---:|---|---:|---:|
| 59 | 3.02 | 2,585 | 5 | yes | 0.029164 | 0.000% |
| 118 | 7.10 | 2,585 | 5 | yes | 0.029190 | 0.152% |
| 236 | 14.72 | 2,585 | 5 | yes | 0.029195 | 0.229% |
| 472 | 35.01 | 2,585 | 5 | yes | 0.029159 | 0.078% |
| 944 | 69.70 | 2,585 | 5 | yes | 0.029163 | not available |

For 944 segments the exact z* is unknown. The heuristic objective is **better than the 120 s MILP
incumbent** (`0.02929819`) and **0.142% above the MILP dual bound** (`0.02912182`). This is a useful
signal, not an optimality proof, because the heuristic is compared with a bound and an incomplete
search.

Heuristic solve time is approximately linear in this range:

`heuristic_seconds ≈ 0.0724 * segments - 1.84`

The 944-segment convergence run takes about **70 seconds**; a 10,000-segment convergence run is
therefore expected to be roughly 12 minutes, not milliseconds. The earlier 10.9-second 10k figure
used only 20 iterations and is not a convergence result.

## Conclusions

- The exact MILP is excellent for the 59–236 segment range and useful as a benchmark oracle.
- It becomes branch-and-bound dominated at 472 segments and does not prove optimality at 944 within
  120 seconds; a longer run would need a separate time-budget study.
- The Fresh Solutions heuristic converged on every tested instance and stayed within **0.23%** of the
  exact objective where z* was known.
- The small gaps are encouraging but not a general optimality guarantee. The replicated instance
  family is easier than a diverse real network and must not be presented as a scale proof.
- Direct MILP should not be used for 10k segments. The next credible design is cluster/rolling-horizon
  exact repair around the heuristic, with the exact MILP retained for cluster-sized subproblems.

## Reproduction

`python tools/benchmark_stateful_scaling.py`

Output: `runtime/private/bc-network/scaling/scaling.json`.
