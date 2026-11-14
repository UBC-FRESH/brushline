# ADR 0006: Optimization is an adapter over Fresh Solutions, with a Pareto archive

Status: accepted
Date: 2026-11-14
Issues: #5

## Context

The joint treatment and monitoring schedule is NP-hard. A realistic corridor has thousands of segments,
a multi-year horizon, budget and capacity constraints, spatial continuity, access windows, and multiple
objectives. An exact solver is not practical, and a bespoke metaheuristic would duplicate the search
infrastructure the lab already maintains.

Fresh Solutions provides a generic `ProblemAdapter` contract, exact resident state, local search,
population search, hybrid handoff, convergence stopping, checkpoints, seeds, telemetry, and replay. It
does not provide a multi-objective archive or a domain model.

## Decision

Implement a **Brushline adapter** over Fresh Solutions:

- Brushline supplies variables, option domains, the exact evaluator, batched evaluation, move proposal,
  apply, undo, initial and random assignments, mutation, and crossover.
- Fresh Solutions supplies the search engine and the replay contract.
- Brushline adds a multi-objective layer: scalarization portfolios, non-dominated filtering, diversity,
  and a `pareto.json` archive.
- The exact evaluator is the Brushline simulator. Every reported incumbent is replayable from its
  evidence record.
- Brushline does not fork, copy, or wrap the engine in a private fork.
- The dependency is optional and versioned; a core install can build, validate, and simulate without it.

## Consequences

- The search layer is reusable and tested once, not once per project.
- Brushline must keep the adapter contract stable and test exact/batch agreement.
- The scalar engine plus a Brushline archive is a deliberate split; multi-objective support may later
  move upstream if Fresh Solutions adopts it.
- The exact evaluator becomes the performance bottleneck; incremental evaluation and batching are
  required.
- Realistic instances carry no optimality claim; exact validation is limited to tiny instances.

## Alternatives considered

- **Write a bespoke metaheuristic.** Rejected: it duplicates Fresh Solutions and creates a second replay
  contract.
- **Reuse the WS4 optimizer directly.** Rejected: WS4's optimizer is coupled to its estate model and its
  account semantics.
- **Use a general-purpose genetic algorithm library.** Rejected: it would not provide the resident state,
  exact replay, or the hybrid handoff.
- **Use a MIP solver only.** Rejected: the spatial and monitoring problem is too large for exact MIP at
  corridor scale; MIP remains a small-instance bound.
