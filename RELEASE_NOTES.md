# Brushline 0.1.0 release notes

Status: release candidate prepared; tag and GitHub release require maintainer approval.

## What this is

Brushline is an open decision-support prototype for vegetation management along linear infrastructure
corridors. It provides a shared plan artifact, a strategic/tactical/operational planning stack, a
Pareto search adapter, a monitoring and replanning loop, a public demo portal, and a local planning
studio.

## Changes

- P0-P2: identity, contracts, synthetic fixture, FEMIC-extended instance builder, catalogue, fetch
  planning, capabilities, and model-builder prototype.
- P3: LiDAR bundle, terrain, canopy, state initialization, coverage, and sibling benchmark.
- P4: low-vegetation state space, growth, treatment transitions, calibration, hazards, held-out
  validation, and model card.
- P5: formulation, exact evaluator, operators, Fresh Solutions adapter, Pareto archive, tiny-instance
  validation, budget evidence, and studio telemetry.
- P6: strategic dynamic program, portfolio, monitoring policy, BAU, reports, scenario archive, and
  synthetic validation.
- P7: tactical program, contractor resources, access, work orders, FHOPS dry-run boundary, timeline,
  and validation.
- P8: observation, mission simulation, value of information, recalibration, replan trigger, and
  adaptive-versus-calendar validation.
- P9: shared plan cost build-up, owner/contractor views, bid comparison, approval, and exchange
  validation.
- P10: artifact-only planning studio with map, 3D context, forester POV walkthrough, pre/post
  toggle, skins, Pareto, and timeline.
- P11: public synthetic demo portfolio, static portal, pilot brief, and validation.
- P12: 16-criterion verification, BAU case, monitoring value, exchange, performance limit, replay, and
  release recommendation.

## Known gaps

- No field calibration of shrub/young-tree growth or treatment response.
- No mature-forest EFI transfer validation.
- No live FEMIC/FreshForge build, live LiDAR campaign, live FHOPS run, or live road feed.
- The 10,000-segment/30-year/1,000-evaluation/8-core target is not demonstrated. P12 measures a small
  case and reports the limit.
- The public demo is synthetic and static; the lab preview is not a production service.
- No authentication, production dispatch, safety certification, or engineering clearance claim.
- The 3D scene and POV walkthrough are context views; they are not survey-grade and invent no
  positions.
- Monitoring value of information and budget/performance evidence use approximations and synthetic
  assumptions.

## Model and use boundaries

Use Brushline to structure evidence and compare transparent scenarios. Do not use it as the sole basis
for field treatment, contract award, safety clearance, or regulatory approval. Read the model card,
verification report, caveats, and known-gaps list before citing a result.

## Publishing

- PyPI trusted publisher: project `brushline`, repository `UBC-FRESH/brushline`, workflow `release.yml`, environment `pypi`.
- TestPyPI trusted publisher: same project/repository/workflow, environment `testpypi`.
- A published GitHub release publishes the wheel and sdist to PyPI. A manual `Release` run publishes to TestPyPI.

## Verification

- P12 verification report: `notes/reports/p12-verification.md`
- P12 close-out: `notes/reports/p12-closeout.md`
- License: Apache-2.0
