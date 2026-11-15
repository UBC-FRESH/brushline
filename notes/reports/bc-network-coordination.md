# BC network Lagrangian coordination result

## Experiment

For each cluster, remove the annual budget and crew-hour constraints, add non-negative prices to
the stateful objective, solve the cluster MILP exactly, and apply a subgradient update to the prices.
The maximum dual value is a valid lower bound.

The baseline primal was the exact stateful MILP at 59 segments and a heuristic seed at 590 segments.

## Result

| Segments | Baseline primal | Best dual | Relative gap |
|---:|---:|---:|---:|
| 59 | 0.029164 | 0.000000 | 100% |
| 590 | 0.029145 | 0.000000 | 100% |

At zero prices, each cluster treats all risk to zero and the priced objective is zero. Raising prices
reduces treatments and makes the dual negative. The dual is valid but vacuous.

## Decision

Do not integrate this coordinator or use it to allocate budget. The clustered problem needs a
stronger mechanism:

- Benders cuts from cluster MILPs;
- cluster value functions combined by a master budget allocation;
- or column generation with cluster plans as columns.

The budget-preserving cluster repair remains the practical post-processing step. It improved the
heuristic seed by 0.070–0.134% on the tested 590–10,030 segment cases.

## Reproduction

The package API is `brushline.strategic.coordination.coordinate_stateful`. The experiment is a
documented negative result, not a studio feature.
