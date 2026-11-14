# ADR 0003: Treatments are transitions, not deletions

Status: accepted
Date: 2026-11-14
Issues: #5

## Context

The dominant dynamic on a rights-of-way is not growth from zero. It is regrowth after a treatment:
resprouting from cut stems, seed bank germination, release from competition, and a method-specific delay
before the next intervention. A model that sets vegetation to zero after treatment will under-predict
the next cycle and over-predict the treatment interval.

The treatment also has a method, a season, a selectivity, an efficacy, and a cost. Those are decision
variables, not post-processing assumptions.

## Decision

Represent every treatment as a **state transition**:

```text
s(t+) = g(s(t), treatment, season, site, uncertainty)
```

The transition carries:

- the method: manual, mechanical, chemical, mowing, grazing, prescribed fire, or a site-specific method;
- the intensity and selectivity;
- the immediate effect: top-kill, mortality, cover reduction, height reduction, and debris;
- the delayed effect: resprouting, regrowth delay, seed bank, and competition release;
- the cost build-up and the productivity assumptions;
- the constraints: weather, soil, slope, watercourse buffer, structure clearance, and safety.

A treatment does not set vegetation to zero. A treatment can fail or be partial, and the observed result
is recorded against the expected efficacy.

## Consequences

- The treatment library needs method-specific parameters and calibration.
- The state must carry treatment history, because the transition depends on it.
- The plan can compare methods on efficacy, cost, and regrowth, not only on hectares.
- The contractor cost build-up and the treatment transition share the same action record.
- A fixed-cycle baseline can be represented as a treatment policy, so the comparison is like-for-like.

## Alternatives considered

- **Reset vegetation to zero after treatment.** Rejected: it ignores resprouting and biases every
  interval.
- **A binary treated/untreated flag.** Rejected: it cannot represent method, efficacy, or regrowth.
- **A fixed treatment cycle.** Rejected as the model; it remains a useful baseline policy.
- **A separate treatment-cost model outside the state model.** Rejected: the method and the state
  determine the cost, and they must stay consistent.
