# ADR 0007: The planning studio reads artifacts, and skins are checked manifests

Status: accepted
Date: 2026-11-14
Issues: #8

## Context

The sibling projects already run browser surfaces over the artifacts their command lines write. That
pattern has three advantages: one source of truth, a small service boundary, and a browser that can be
replaced without changing the model. It has one cost: the artifact schema becomes a public contract.

A planning studio also needs role-specific views: an owner, a tactical planner, an operations
supervisor, a contractor, a monitoring specialist, and a reviewer should not see the same panels or be
able to take the same actions. Forking the application per role would multiply maintenance.

## Decision

Build **one optional FastAPI service and one static browser shell** over the artifacts:

- the service reads the run directory, the plan, the schedule, the account series, the Pareto archive,
  the operations timeline, and the reports;
- the service never owns model state and does not compute a value the CLI cannot reproduce;
- the 2D map uses MapLibre; the 3D scene uses Three.js; both are vendored and offline-capable;
- the 2D and 3D views share one selection and time state;
- **skins are checked JSON manifests** of panels, layers, actions, and a read-only flag;
- a read-only skin cannot carry a mutating action, and the loader enforces the rule;
- live search uses server-sent events and a control file; pause and stop produce the usual artifacts;
- the bind is loopback by default; a remote bind needs an explicit opt-in; the first release has no
  authentication.

The skin set is `model-builder`, `owner-strategic`, `tactical-planner`, `operations-planner`,
`contractor-bid`, `monitoring`, and `reviewer`.

## Consequences

- The artifact schemas need versioning, validation, and tests.
- The browser can be static or interactive without a second model runtime.
- A new role is a new manifest, not a new application.
- The service is small enough to audit and to deploy behind a proxy.
- The UI cannot hide a missing artifact; it must name it.

## Alternatives considered

- **A server-side model that computes values in the browser.** Rejected: it creates a second runtime and
  a second source of truth.
- **A separate application per role.** Rejected: it multiplies maintenance and drifts.
- **A desktop GIS plugin only.** Rejected: it limits the owner and contractor audience and does not give
  a shared browser surface.
- **A hosted multi-tenant SaaS in the first release.** Rejected: it requires authentication, tenancy, and
  operations that are out of scope.
