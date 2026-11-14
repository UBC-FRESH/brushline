# ADR 0012: Agent capabilities are prompts plus validators over deterministic tools

Status: accepted
Date: 2026-11-14
Issues: #11

## Context

The instance builder can use an LLM agent to plan a build, select data sources, draft configuration, and
explain failures. That is useful because the data landscape is complex and the user wants to point at a
map rather than write a pipeline.

It is also risky. An LLM can invent a dataset, a coefficient, a geometry, or a successful validation. It
can leak private data into a prompt. It can retry until it finds a plausible-looking answer instead of
stopping at a real failure.

The lab's contract already says: no oracle, no capability. A capability needs a validator that can fail.

## Decision

The agent is **optional**, and every agent-facing capability is:

- a prompt;
- an allowlisted tool set;
- a validator over real state;
- a bounded retry budget;
- a recorded outcome and evidence.

The LLM plans, selects, drafts, and explains. Deterministic tools do the fetching, processing, compiling,
and validating. The LLM never produces an authoritative number, coefficient, geometry, or validation
result.

A capability stops and reports when a validator fails. It does not silently change an assumption, a
source, or a coefficient to make the check pass.

Private data is metadata-only until the owner approves a connector. Credentials stay outside the
repository. A capability is tested offline with a fake provider and a real validator.

## Consequences

- The agent layer is more engineering than a free-form chat prompt, and it is auditable.
- Every capability has a test that can fail, which is the point.
- The agent cannot bypass an approval gate or a data boundary.
- A new capability is a small, reviewable unit.
- The deterministic stages remain usable without the agent.

## Alternatives considered

- **A free-form agent with shell access.** Rejected: it cannot be validated, and it can read or leak
  anything the user can.
- **No agent.** Rejected: the map-to-instance workflow is a core product capability.
- **A fully autonomous builder.** Rejected: it would publish or promote without review and would hide
  failures.
- **An agent that computes numbers directly.** Rejected: no oracle, no capability.
