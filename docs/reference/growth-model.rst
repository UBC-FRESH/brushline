Low-vegetation growth
=====================

The P4.2 growth model is a fast, deterministic, segment-level saturating model. It grows height, cover,
and density from the current state distribution, applies site, climate, and competition modifiers, and
preserves uncertainty and age. It does not apply a treatment transition.

Model form
----------

For each functional group:

.. code-block:: text

   next = asymptote - (asymptote - current) * exp(-rate * modifier * years)

Height and cover have separate asymptotes, rates, and uncertainty. Density is grown only when the
current distribution has a density and the group has a density asymptote. The modifier is:

.. code-block:: text

   site_factor * climate_factor * competition_factor

- Site factor uses ``site_index_m / reference`` and is clamped.
- Climate factor is bounded by the configured domain.
- Competition factor is ``1 - competition * competition_sensitivity``.

Height and cover are monotone during growth and never exceed their asymptotes. A state already at the
asymptote does not shrink.

.. code-block:: python

   from brushline.vegetation.growth import (
       GrowthConfig,
       GrowthEnvironment,
       GrowthRequest,
       grow,
   )
   from brushline.vegetation.state_space import StateDistribution

   current = StateDistribution(
       class_probabilities={"shrub": 0.8, "unknown": 0.2},
       height_m=2.0,
       height_sd=0.2,
       cover_pct=30.0,
       cover_sd=5.0,
       density_per_ha=1000.0,
       age_years=3,
       confidence=0.8,
   )
   result = grow(
       GrowthRequest(
           segment_id="s1",
           functional_group="shrub",
           current=current,
           years=3,
           environment=GrowthEnvironment(site_index_m=24, climate_factor=1.1, competition=0.2),
       ),
       GrowthConfig(),
   )
   assert result.status == "grown"

Functional groups
-----------------

The parameters are group-specific priors:

.. list-table::
   :header-rows: 1
   :widths: 20 14 14 14 14 24

   * - Group
     - Height max
     - Cover max
     - Height rate
     - Cover rate
     - Notes
   * - ``shrub``
     - 4 m
     - 90%
     - 0.35
     - 0.35
     - Cutting can increase density.
   * - ``deciduous_sprout``
     - 10 m
     - 95%
     - 0.25
     - 0.30
     - Resprouting hardwood.
   * - ``conifer``
     - 20 m
     - 90%
     - 0.12
     - 0.20
     - Young conifer or mature edge.
   * - ``grass_herb``
     - 0.6 m
     - 100%
     - 0.90
     - 0.80
     - Herbaceous, not woody cover.
   * - ``unknown``
     - n/a
     - n/a
     - n/a
     - n/a
     - Blocked.

Domain and result states
------------------------

A growth result is:

- ``grown`` when the environment is in domain and the group is known;
- ``out_of_domain`` when the environment is explicitly flagged or site index/climate lies outside the
  configured domain;
- ``unknown`` when the functional group is unknown.

An out-of-domain or unknown result has no next distribution and a reason. It does not extrapolate or
silently hold the state.

Output
------

``GrowthResult`` carries:

- previous and next distributions;
- the next state class;
- height and cover change;
- environment context;
- model card id and reason.

``to_vegetation_state(state_year)`` converts a grown result to a valid ``brushline.state.v1`` state.

Named errors
------------

.. list-table::
   :header-rows: 1
   :widths: 32 68

   * - Prefix
     - Meaning
   * - ``GROWTH-STATUS``
     - Unknown growth status.
   * - ``GROWTH-NEXT``
     - A grown result has no next distribution, or a blocked result has one.
   * - ``GROWTH-MONOTONE``
     - Height or cover decreased during growth.
   * - ``GROWTH-BOUND``
     - Height or cover exceeds its asymptote.
   * - ``GROWTH-PROBABILITY``
     - The next class has no probability.
   * - ``GROWTH-AGE``
     - Age did not advance by the step.
   * - ``GROWTH-REASON``
     - A blocked result has no reason.

Limits
------

- The parameters are priors, not calibrated values; P4.6 validates them.
- The model is not a physiological water/carbon model.
- It does not apply a method-specific treatment transition; P4.3 owns that.
- The model card’s applicability domain is enforced here and published in P4.7.
