Stateful coordination
=====================

The coordination prototype applies Lagrangian prices to annual budget and crew-hour constraints.
Cluster subproblems remove those constraints, add non-negative prices to the objective, and are
solved exactly by the stateful MILP. A subgradient update raises prices when aggregate spend or hours
exceed the global limits. The maximum dual value is a valid lower bound.

Result on the network
---------------------

The prototype is valid but **vacuous** on the current stateful model. At zero price, each cluster
treats all risk to zero, so the dual value is zero. Raising prices removes treatments and produces
negative dual values. On both the 59-segment and 590-segment cases the best dual was `0.0` against a
primal objective near `0.029`, a 100 percent relative gap.

This is a property of the relaxed integer problem and the linear risk proxy, not an implementation
error. The method is retained as a documented negative result; it is not wired into the studio or
used for allocation.

What it would take
------------------

A useful global coordinator needs a stronger coupling method:

- Benders cuts from cluster MILPs;
- value functions over annual budget, combined by a master allocation;
- or column generation with cluster plans as columns.

A second subgradient implementation is not the answer.
