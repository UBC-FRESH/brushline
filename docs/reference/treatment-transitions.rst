Treatment transitions
=====================

A treatment is a transition, not a reset to zero. The P4.3 model applies a method- and season-specific
top-kill and cover reduction, changes density through resprouting, records a regrowth delay, and runs the
P4.2 growth model for the post-delay trajectory. The efficacy parameters are priors; P4.4 calibrates them.

Input
-----

A ``TreatmentRequest`` carries:

- the current state distribution and functional group;
- the method and season;
- operational intensity;
- treated area for cost;
- optional regrowth horizon;
- a growth environment.

A ``TreatmentConfig`` carries residual floors, season factors, growth rules, discretization rules, and
the maximum regrowth horizon.

Immediate transition
--------------------

For one treatment:

.. code-block:: text

   efficiency = min(1, base_efficacy * season_factor * intensity)
   height_after = max(min_height, height - height * efficiency * top_kill)
   cover_after = max(min_cover, cover - cover * efficiency)
   density_after = density * (1 + resprout_factor * efficiency)

The residual floor prevents a zero reset. A density increase records resprouting. The immediate age is
zero because the treatment is a disturbance. Immediate uncertainty grows with efficiency.

The immediate class is recomputed from the new height and cover. A residual that does not match a class
becomes ``partial``.

Post-delay trajectory
---------------------

When ``regrowth_years`` exceeds the method's ``regrowth_delay_years``, the model grows the immediate
state for the remaining years with the supplied ``GrowthEnvironment``. A blocked growth trajectory
leaves the immediate state in place and records the reason.

.. code-block:: python

   from brushline.vegetation.growth import GrowthEnvironment
   from brushline.vegetation.state_space import StateDistribution
   from brushline.vegetation.treatment import (
       TreatmentConfig,
       TreatmentRequest,
       apply_treatment,
       validate_treatment_result,
   )

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
   result = apply_treatment(
       TreatmentRequest(
           segment_id="s1",
           functional_group="shrub",
           current=current,
           method="mowing",
           season="spring",
           intensity=1.0,
           quantity_ha=2.0,
           regrowth_years=6,
           environment=GrowthEnvironment(),
       ),
       TreatmentConfig(),
   )
   assert validate_treatment_result(result).is_valid

Methods and priors
------------------

.. list-table::
   :header-rows: 1
   :widths: 20 12 12 12 14 16 14

   * - Method
     - Efficacy
     - Selectivity
     - Top-kill
     - Resprout
     - Delay
     - Cost/ha
   * - ``manual``
     - 0.55
     - 0.90
     - 0.70
     - 0.50
     - 1 year
     - 1,200
   * - ``mechanical``
     - 0.75
     - 0.70
     - 0.90
     - 0.60
     - 1 year
     - 900
   * - ``mowing``
     - 0.65
     - 0.80
     - 0.80
     - 0.70
     - 1 year
     - 500
   * - ``chemical``
     - 0.80
     - 0.60
     - 0.60
     - 0.30
     - 2 years
     - 700
   * - ``grazing``
     - 0.35
     - 0.40
     - 0.40
     - 0.40
     - 0 years
     - 300
   * - ``prescribed_fire``
     - 0.70
     - 0.30
     - 0.70
     - 0.60
     - 2 years
     - 1,100 + 2,500 fixed
   * - ``other``
     - 0.30
     - 0.50
     - 0.30
     - 0.50
     - 1 year
     - 0

Season factors are spring 1.0, summer 0.9, fall 0.8, winter 0.6, and any 1.0. These are priors and
must be calibrated in P4.4.

Cost
----

The cost is:

.. code-block:: text

   cost = cost_per_ha * quantity_ha + fixed_cost

The result records the cost and currency. It is an estimate hook, not a bid.

Output
------

``TreatmentResult`` carries:

- previous, immediate, and trajectory distributions;
- immediate and trajectory state classes;
- height and cover reduction, density change, and effective efficiency;
- cost, delay, horizon, environment, and reason;
- model card id.

``to_vegetation_state(state_year)`` uses the trajectory if present, otherwise the immediate state.

Named errors
------------

.. list-table::
   :header-rows: 1
   :widths: 32 68

   * - Prefix
     - Meaning
   * - ``TREATMENT-STATUS``
     - Unknown result status.
   * - ``TREATMENT-NEXT``
     - An applied result has no immediate state, a blocked result has one, or a trajectory has no class.
   * - ``TREATMENT-HEIGHT``, ``TREATMENT-COVER``
     - Cutting increased height/cover or a reduction is negative.
   * - ``TREATMENT-RESIDUAL``
     - Height was reset to zero or cover is negative.
   * - ``TREATMENT-EFFICIENCY``
     - Efficiency is outside 0 to 1.
   * - ``TREATMENT-COST``
     - Cost is negative.
   * - ``TREATMENT-REASON``
     - A blocked result has no reason.

Limits
------

- The parameters are priors, not calibrated values.
- The model does not simulate chemical mode of action, fire behaviour, or grazing preference.
- The cost is a hook for a later bid build-up, not a contractor price.
- The model does not decide whether a treatment is safe or permitted.
