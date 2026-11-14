# ADR 0010: The public demo portal is read-only and public-data-only

Status: accepted
Date: 2026-11-14
Issues: #12

## Context

The lab's sibling projects use public portals to show the work and attract partners: the WS4 public
demo, the FHOPS web application, Fresh Fire Studio, Fresh Woodlots, and the urban-forest lab. The
portals work because they are curated, static-first, and honest about their limits.

A Brushline demo could easily become an operational-looking product that leaks partner data or implies a
precision the model does not have. The public portal and a private deployment have different trust
boundaries.

## Decision

The public demo portal is:

- **public-data-only**: synthetic or openly licensed data, never a real partner's asset, contractor, or
  personal data;
- **read-only**: no uploads, no arbitrary searches, no arbitrary run starts;
- **static-first**: a GitHub-Pages-compatible export from precomputed runs, with an optional read-only
  service for a lab preview behind the lab's access gate;
- **curated**: four to six demo instances, each answering a named partner question;
- **manifest-driven**: every instance has a `brushline.demo.v1` manifest with provenance, licences,
  scenarios, artifacts, headline metrics, caveats, and contact;
- **explicit about limits**: every page separates "what this shows" from "what this does not show".

A partner's data is handled in a separate private deployment with its own access controls, connectors,
and audit. It never enters the public portal.

## Consequences

- The portal is cheap to host and hard to break.
- The demo content is a product asset that needs curation and maintenance.
- The public portal cannot show a live search unless the service is explicitly enabled and read-only.
- A pilot conversation has a clear data-sharing boundary from the start.
- The portal's build validator can fail on a broken link, a missing licence, or a private-data marker.

## Alternatives considered

- **An interactive public sandbox.** Rejected: it invites arbitrary uploads and compute, and it hides the
  data boundary.
- **Put partner data in the public portal.** Rejected: privacy and trust violation.
- **A single demo instance.** Rejected: it cannot show the breadth of the decision problem.
- **No portal.** Rejected: the partner-acquisition value is part of the project's purpose.
