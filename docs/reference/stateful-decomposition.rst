Stateful decomposition
======================

The stateful MILP is exact but grows quickly with segments. The decomposition module provides two
spatial options for larger networks.

Risk-weighted allocation
------------------------

`decompose_stateful` groups contiguous spans into clusters, allocates each annual budget and
crew-hour capacity by cluster risk mass, solves each cluster with the exact MILP, redistributes
unused budget for a small number of rounds, and replays the aggregate plan.

This is a feasible decomposition, not a global optimum. Its allocation can underfund a high-value
cluster; use it as a screening baseline.

Budget-preserving repair
------------------------

`repair_stateful_clusters` takes an existing plan, computes each cluster's annual cost and crew-hours,
then solves each cluster exactly under those fixed budgets. The baseline remains the fallback when a
cluster solve fails. This is fix-and-optimize: it can improve a heuristic seed without changing the
global budget.

The result is still feasible-only. Cluster failures, timeouts, and replay mismatches are explicit in
the cluster results and the aggregate plan.

Limits
------

- Cluster boundaries are span-based and not optimized.
- Risk mass is a simple allocator.
- Repair preserves the heuristic's budget distribution.
- The linear risk state remains an abstraction.
