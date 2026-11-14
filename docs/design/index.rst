Design record
=============

Brushline is a decision support system for vegetation management along linear infrastructure corridors.
This page is the documentation index for the design record. The source notes live in the repository under
``notes/design/`` and ``notes/adr/``; this page states what is fixed, where the detail is, and what is
still open.

Reading order
-------------

1. ``notes/design/brushline-scope.md``: the problem, users, scope, success criteria, and open questions.
2. ``notes/design/brushline-architecture.md``: the system context, domain model, dynamics, planning stack,
   optimization, studio, instance builder, artifacts, and integrations.
3. ``notes/design/brushline-optimization.md``: the NP-hard formulation, the Fresh Solutions adapter, the
   Pareto archive, exact validation, and reproducibility.
4. ``notes/design/brushline-ui.md``: the 2D map, 3D scene, skins, live search, Pareto explorer, and
   animated operations.
5. ``notes/design/brushline-lidar-and-open-data.md``: the FEMIC producer/consumer boundary, the LiDAR
   contracts, the low-vegetation gap, coverage, site index, roads, and 3D use.
6. ``notes/design/brushline-instance-builder.md``: the FEMIC-extended instance builder, the stage chain,
   the agent capabilities, the validators, and the public/private boundary.
7. ``notes/design/brushline-demo-portal.md``: the public demo portfolio, the manifest, the static and
   interactive deployment, and the pilot funnel.
8. ``notes/reference/shrub-young-tree-growth-models.md``: the review of 18 open and published models and
   the from-scratch rationale.
9. ``notes/adr/``: the decisions that constrain later phases.

What is fixed
-------------

- The segment is the decision unit; spans and treatment units aggregate at runtime.
- The vegetation state is a distribution over interpretable classes with continuous summaries.
- A treatment is a transition with method-specific efficacy and regrowth, not a reset to zero.
- Strategic, tactical, and operational plans share one scenario and one plan contract.
- Monitoring is a decision variable, not a fixed calendar.
- The optimizer is an adapter over ``fresh-solutions``, with a Pareto archive and exact replay.
- The studio reads artifacts and uses checked skins.
- FEMIC is the LiDAR producer and the instance builder; Brushline extends its provider vocabulary.
- The low-vegetation model is a Brushline state-transition core with reused components.
- The public demo portal is read-only and public-data-only.
- Provenance and reproducibility travel with every artifact.
- Agent capabilities are prompts plus validators over deterministic tools.

What is open
------------

The open questions are recorded in the scope and in each design note. The largest are:

- the functional groups and state thresholds;
- the low-vegetation calibration data and model form;
- the uncertainty representation in the objective and the archive;
- the FEMIC provider API pin and the instance-builder boundary;
- the observation model and the value-of-information approximation;
- the multi-objective weights, normalization, and promotion rule;
- the pilot case and the six demo instances;
- the 3D fidelity limit.

Reference pages
---------------

- API: :doc:`../api/index`
- Project home: :doc:`../index`
- Repository contract: ``AGENTS.md``, ``ROADMAP.md``, ``CHANGE_LOG.md``
