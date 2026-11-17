Limitations and boundaries
==========================

Brushline is a working prototype. This page names the boundaries so a review does not build on a
guess. Each entry says what the boundary is and what to do instead.

Network and data
----------------

**The BC network is a public-data prototype, not an asset-owner plan.** It uses OSM lines and
towers, BC VRI context, and Copernicus terrain. It does not carry BC Hydro or MKRF asset records,
clearance standards, outage schedules, or field inspections.

**Private artifacts stay private until approval.** The public demo is synthetic. See
:doc:`private-public`.

**The 590- and 10,030-segment cases are replicated stress instances.** They test scaling and
algorithm behavior; they are not real networks.

Vegetation and evidence
-----------------------

**The growth and treatment model is not field-calibrated for a specific utility.** Its parameters,
uncertainty, and applicability domain are prototype values. See
:doc:`../reference/low-vegetation-model-card` and :doc:`../reference/growth-model`.

**Remote sensing is context and initialization evidence, not a stem map.** LiDAR and canopy
products carry applicability and coverage states. Missing or out-of-domain evidence is reported as
unknown or partial, not defaulted.

**The risk metric is a model quantity.** It is length-weighted state risk. It does not certify
clearance, fire behaviour, reliability, or safety.

Optimization
------------

**Exactness is limited to the declared model and small instances.** The stateful MILP is exact for
its linearized risk state. At 59 segments it is usable; larger cases use heuristics or cluster
repair. Heuristic status is not global optimality.

**The scenario, robust, and chance plans are sampled experiments.** Chance constraints are enforced
on training paths; out-of-sample violations can occur. Robust plans are scenario-robust, not
distributionally guaranteed.

**Recourse is not a stochastic dynamic program.** Multi-year and weather recourse use deferral or
re-optimization with a short lookahead. They do not solve for an optimal policy over a distribution.

Weather, calendar, and capacity
-------------------------------

**The weather calendar is assumed, not forecast.** Five outage days and independent 20% daily
weather loss are scenario assumptions. The calendar-aware case observes the calendar before
deferral; the forecast-aware case uses a synthetic forecast. The forecast-skill sweep is a
diagnostic, not a forecast product.

**Whole-action deferral is conservative.** Calendar-aware execution drops an action when it cannot
fit the observed calendar; it does not give partial treatment credit. This can make aware cases look
worse on scope or risk than naive partial execution.

**Capacity remedies are operational what-ifs.** Window extension and added-crew comparisons hold
the crew mix fixed, use prototype day rates, and do not model every seasonal overhead, supervision
rule, access constraint, or labour agreement.

Costs and commercial use
------------------------

**Costs, hours, productivity, access, and capacity are demo assumptions.** The plan and bid
artifacts are inspectable, but they are not a commercial offer, a contractor commitment, or an
asset-owner budget.

**The planning brief is lab-review material.** It is not a public release of network-derived data
and it is not an asset-owner decision record.

Release and field use
---------------------

**No field validation has been performed.** There is no field campaign, field-calibrated
coefficient, safety certification, or asset-owner acceptance.

**Release remains gated.** Data-sharing, release approval, field validation, and asset-owner review
are external. See :doc:`private-public` and :doc:`../reference/release-boundary`.
