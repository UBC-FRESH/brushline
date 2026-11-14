Low-vegetation state space
==========================

The state space is the shared vocabulary for P4 growth, treatment, calibration, hazard, and model-card
work. It defines the functional groups, continuous state variables, state classes, class probabilities,
uncertainty, and the deterministic projection to ``brushline.state.v1``.

It does not run growth or a treatment transition.

Variables and units
--------------------

.. list-table::
   :header-rows: 1
   :widths: 24 16 16 44

   * - Variable
     - Unit
     - Range
     - Unknown rule
   * - ``height_m``
     - m
     - 0 to 100
     - unavailable height becomes unknown or partial
   * - ``cover_pct``
     - %
     - 0 to 100
     - unavailable cover becomes unknown or partial
   * - ``density_per_ha``
     - stems/ha
     - 0 or more
     - unavailable density stays null
   * - ``biomass_kg_per_ha``
     - kg/ha
     - 0 or more
     - unavailable biomass stays null
   * - ``age_years``
     - years
     - 0 to 300
     - unavailable age stays null

Functional groups
-----------------

``shrub``, ``deciduous_sprout``, ``conifer``, ``grass_herb``, and ``unknown`` have profiles with a
typical height maximum, a minimum cover, a resprouting flag, and notes. The profiles are priors and
documentation; P4.6 calibrates the parameters.

Discretization
--------------

The default ``StateSpaceConfig`` uses:

- grass/herb at or below 0.5 m and woody cover below 20 percent;
- shrub at or below 4 m with cover at least 20 percent;
- young tree at or below 10 m with cover at least 20 percent;
- mature edge at or above 15 m with cover at least 20 percent;
- mixed when at least two observed strata have cover at least 20 percent.

The thresholds must increase. Coverage below 10 percent is unknown; coverage below 50 percent is
partial; an out-of-domain observation is partial and flagged.

The projection is deterministic. It does not invent a missing value. An observation that does not match
a rule is an observed unknown class with a reason, not a known class.

.. code-block:: python

   from brushline.vegetation.state_space import (
       StateObservation,
       StateSpaceConfig,
       project_state,
       validate_state_projection,
   )

   observation = StateObservation(
       segment_id="s1",
       state_year=2026,
       functional_group="shrub",
       height_m=2.4,
       cover_pct=45,
       density_per_ha=1200,
       age_years=3,
       coverage_pct=92,
       height_sd=0.3,
       cover_sd=6,
       source="field",
       source_version="2026",
   )
   projection = project_state(observation, StateSpaceConfig())
   assert validate_state_projection(projection).is_valid
   state = projection.to_vegetation_state()

Distribution
------------

``StateDistribution`` carries:

- class probabilities that sum to one;
- mean and standard deviation for height and cover;
- optional density and age;
- an overall confidence.

The selected class must have a positive probability. The distribution is the input to the P4 growth and
treatment models; the state contract is the summary that a plan reads.

Output states
-------------

Observed, partial, and unknown projections all convert to a valid ``brushline.state.v1`` state.
A partial or out-of-domain projection keeps the measured height and cover but marks the state partial.
An unknown projection has zero height and cover, an unknown functional group, and confidence zero.

Named errors
------------

.. list-table::
   :header-rows: 1
   :widths: 32 68

   * - Prefix
     - Meaning
   * - ``STATE-SPACE-GROUP``
     - An unknown class has a known group, or a known class has an unknown group.
   * - ``STATE-SPACE-VALUE``
     - An unknown class has non-zero height or cover.
   * - ``STATE-SPACE-PROBABILITY``
     - The selected class has no probability.
   * - ``STATE-SPACE-STATE``
     - The projection cannot convert to a valid state contract.
   * - ``STATE-SPACE-REASON``
     - A partial or out-of-domain projection has no reason.

Limits
------

- The thresholds are prototype rules, not a calibrated model.
- The state space does not include a growth, treatment, hazard, or model-card calculation.
- A class probability is a summary of the rules and observation uncertainty, not a fitted posterior.
