# ADR 0011: Reproducibility and provenance travel with every artifact

Status: accepted
Date: 2026-11-14
Issues: #5

## Context

A vegetation plan is a claim about the future. A search result is a claim about the best schedule found.
A contractor bid is a claim about cost. None of these is defensible without the data version, the model
version, the configuration, the seed, and the software versions that produced it.

The sibling projects already treat manifests, checksums, model cards, and seeds as part of the product.
Brushline must do the same, including for instances built by an agent.

## Decision

Every dataset, run, plan, Pareto archive, operations timeline, and demo manifest carries:

- the Brushline package version and the adapter version;
- the data version and manifest digest;
- the model ids and versions, including model cards;
- the configuration and the random seed;
- the Fresh Solutions version for a search;
- the FEMIC bundle pin, product checksums, CRS, vertical datum, and licence for LiDAR-derived state;
- the creation time and the operator or agent id;
- the parent plan and run, for a refinement or a replan.

The simulator is deterministic given a schedule. Every stochastic search records its seed. Every
incumbent has an evidence record that replays exactly. A number that cannot be traced to a source, a
rate, or a stated assumption is marked as an assumption or removed.

## Consequences

- Artifact schemas need versioning and contract tests.
- Runs carry more metadata; the storage overhead is small compared with the data.
- A replay test is part of the acceptance suite.
- An agent-built instance is auditable like a human-built one.
- A model change is visible in every downstream plan.

## Alternatives considered

- **Best-effort logs.** Rejected: a log is not a replay contract.
- **Configuration only.** Rejected: it does not capture the data, model, or bundle versions.
- **A central database.** Rejected for the first release: the artifact directory is portable and
  inspectable.
- **No provenance for demos.** Rejected: the demo is a public claim and needs the same discipline.
