# ADR 0004: Three planning scales share one scenario and one plan contract

Status: shared decision
Date: 2026-11-14
Issues: #5

## Context

Strategic, tactical, and operational planners often use different spreadsheets, different time steps,
and different definitions of a work unit. The result is three incompatible truths: a strategic budget
that cannot be scheduled, a tactical plan that cannot be executed, and an operational plan that cannot be
compared with the budget.

The scales genuinely differ. Strategic planning needs a 10-to-30-year horizon and a portfolio view.
Tactical planning needs 1-to-5-year units, contractors, and access. Operational planning needs weeks,
crews, machines, and a work order.

## Decision

Use **one scenario contract, one vocabulary, one set of identifiers, and one versioned plan artifact**
across all three scales. The scales differ in:

- horizon;
- temporal resolution;
- spatial resolution;
- constraint set;
- optimization objective and search budget.

They do not differ in the definition of a segment, a treatment, a state, a cost line, or a plan version.
A tactical plan is a refinement of a strategic plan; an operational plan is a refinement of a tactical
plan. Each refinement records its parent plan and its changes.

The plan artifact is the exchange object. A scale that cannot read the artifact is not part of the
system.

## Consequences

- The data model must support the finest scale and aggregate upward.
- A scale transition is a recorded planning action, not a manual export.
- The owner, the tactical planner, the contractor, and the field supervisor read the same plan at
  different resolutions.
- A change at one scale can be traced to the others.
- The first release may implement the scales in sequence, but the contract is shared from the start.

## Alternatives considered

- **Separate tools per scale.** Rejected: it creates three truths and three audit trails.
- **One scale only.** Rejected: the value proposition spans budget, contract, and field execution.
- **Post-hoc disaggregation of a strategic plan.** Rejected: it does not respect access, capacity, or
  operational feasibility.
- **Post-hoc aggregation of operational plans.** Rejected: it cannot answer the budget and service-level
  question.
