# ADR 0005: Monitoring is a decision variable

Status: accepted
Date: 2026-11-14
Issues: #5

## Context

Vegetation management programs usually inspect on a fixed calendar. The calendar is easy to budget and
easy to defend, but it is not necessarily the best use of the monitoring budget. A corridor with slow
growth and good access may need less frequent observation than a fast-growing corridor with a low
clearance standard.

Remote sensing makes the choice richer: LiDAR, UAV imagery, fixed-wing imagery, and field plots have
different costs, coverage, accuracy, and latency. The observation also changes the growth-model
parameters through recalibration.

## Decision

Make monitoring a **decision variable** alongside treatment:

- when to observe;
- which segments or spans;
- which sensor and resolution;
- the flight route and pattern;
- the sampling intensity;
- how the observation updates the state and the model.

The objective is the **expected value of information**: the reduction in expected decision loss per unit
of monitoring cost. The first release uses a tractable approximation, not a full POMDP. The approximation,
its assumptions, and its error are documented.

The monitoring decision is part of the same plan and the same search as the treatment decision. It is
not a separate calendar.

## Consequences

- The action space grows; the search needs a monitoring operator and a budget constraint.
- The observation model becomes a first-class contract: coverage, detection, measurement error, and
  latency.
- Missing coverage is a state of knowledge that can trigger monitoring.
- The plan reports the monitoring cost and the expected information value.
- The model can be recalibrated on a shorter cycle than the treatment plan.

## Alternatives considered

- **A fixed annual or multi-year inspection calendar.** Rejected as the only policy; it remains a
  baseline.
- **A priority ranking of segments to inspect.** Rejected: it ignores the timing and the value of the
  information.
- **No monitoring decision in the first release.** Rejected: monitoring is a large part of the budget and
  a core differentiator.
- **A full POMDP.** Rejected for the first release: intractable at corridor scale; the value-of-information
  approximation is the practical path.
