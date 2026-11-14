# ADR 0002: Vegetation state is a distribution over interpretable classes

Status: accepted
Date: 2026-11-14
Issues: #5

## Context

A plan that says "height 2.3 m" implies a precision that field plots, LiDAR, and young vegetation do
not support. The state also has to be tractable for a dynamic program and a metaheuristic search, and it
has to be inspectable by an owner, a contractor, and a reviewer.

A full continuous Bayesian state would be theoretically cleaner but expensive to propagate across
thousands of segments and many search evaluations. A single point estimate would be cheap but would hide
the uncertainty that should trigger monitoring or a treatment.

## Decision

Represent the vegetation state as a **distribution over interpretable classes**, with continuous
summaries:

- functional group: shrub, deciduous sprout, conifer, grass or herb, and site-specific additions;
- height class and continuous height;
- cover class and continuous cover;
- density or biomass class where the data supports it;
- age since disturbance and time since treatment;
- uncertainty per attribute, as a distribution or an interval;
- provenance: data version, model card, observation date, and applicability.

A state can be **unknown** or **out of domain**. That is a valid state, and it can trigger monitoring.
It is not a zero.

The plan reports the state version and the interval. A forecast without an interval is incomplete.

## Consequences

- The state space is larger than a point estimate, so the model needs approximation and sparse storage.
- The growth and treatment models operate on distributions, or on a small set of representative states.
- Observations update the distribution and the model parameters.
- The plan and the studio can show uncertainty honestly.
- The model card is mandatory for any derived attribute.
- The exact representation is a Phase 1 contract decision; this ADR fixes the principle.

## Alternatives considered

- **A single point estimate.** Rejected: it hides the risk and the reason to monitor.
- **A full continuous Bayesian state.** Rejected for the first release: too expensive for the search and
  too hard to explain; the class representation is a tractable approximation.
- **Use the remote-sensing raster as the state.** Rejected: a raster cell is not a management state and
  does not carry treatment history.
- **Store only the mean and variance.** Rejected: it cannot represent a multi-modal state after a partial
  treatment or a mixed-species segment.
