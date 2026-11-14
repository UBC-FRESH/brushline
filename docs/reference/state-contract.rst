Vegetation state and treatment contract
=======================================

The state contract carries the vegetation state, the treatment actions, the treatment transitions, and
the observations. The schema version is ``brushline.state.v1``. The contract is validated by
:func:`brushline.model.state.validate_state_contract`.

Objects
-------

.. list-table::
   :header-rows: 1
   :widths: 26 74

   * - Object
     - Meaning
   * - ``VegetationState``
     - One functional group's state on one segment in one year, with height, cover, density, biomass,
       age, uncertainty, treatment history, and provenance.
   * - ``Uncertainty``
     - Standard deviations and a confidence value for the state.
   * - ``TreatmentAction``
     - A planned, applied, or cancelled treatment with a method, season, intensity, efficacy, cost hooks,
       and status.
   * - ``TreatmentTransition``
     - The before-and-after state of a treatment, with the method, efficacy, regrowth delay, and source.
   * - ``Observation``
     - A remote or field observation with a sensor, date, product, coverage, error, model card, and
       provenance.

Functional groups and classes
-----------------------------

Functional groups: ``unknown``, ``shrub``, ``deciduous_sprout``, ``conifer``, ``grass_herb``.

State classes: ``unknown``, ``partial``, ``grass_herb``, ``shrub``, ``young_tree``, ``mixed``,
``mature_edge``.

An ``unknown`` state uses the ``unknown`` functional group and zero height and cover. A known state
must name a functional group. A ``partial`` state is allowed and is reported as a warning.

Treatment methods and sensors
-----------------------------

Treatment methods: ``manual``, ``mechanical``, ``chemical``, ``mowing``, ``grazing``,
``prescribed_fire``, ``other``.

Seasons: ``spring``, ``summer``, ``fall``, ``winter``, ``any``.

Sensors: ``lidar``, ``uav_lidar``, ``imagery``, ``field``, ``inspection``, ``other``.

Invariants
----------

The models and the validator check:

- the state key ``(segment_id, state_year, functional_group)`` is unique;
- height and density are non-negative; cover is between 0 and 100;
- an unknown state is empty and uses the unknown group;
- a known state names a functional group;
- years are between 1900 and 2200;
- a treatment action's intensity and efficacy are between 0 and 1;
- a treatment transition does not increase height or cover;
- an observation's coverage is between 0 and 100 and its errors are non-negative;
- every treatment, transition, and observation references a segment with a state;
- every required segment has at least one state;
- partial states, low confidence, partial coverage, and long regrowth delays are warnings.

Named errors use the prefixes ``STATE-ID``, ``STATE-REF``, and ``STATE-MISSING``. Named warnings use
``STATE-PARTIAL``, ``STATE-UNCERTAIN``, ``STATE-COVERAGE``, and ``STATE-DELAY``.

Example
-------

.. code-block:: json

   {
     "schema_version": "brushline.state.v1",
     "states": [
       {
         "segment_id": "s1",
         "state_year": 2026,
         "functional_group": "shrub",
         "state_class": "shrub",
         "height_m": 2.0,
         "cover_pct": 50.0,
         "density_per_ha": 1200.0,
         "age_years": 3,
         "uncertainty": {"height_m_sd": 0.2, "cover_pct_sd": 5.0, "confidence": 0.9},
         "source": "synthetic",
         "source_version": "1.0"
       }
     ],
     "treatments": [
       {
         "action_id": "a1",
         "segment_id": "s1",
         "year": 2026,
         "season": "summer",
         "method": "mowing",
         "intensity": 0.8,
         "efficacy": 0.7,
         "cost_per_ha": 1200.0,
         "status": "applied"
       }
     ],
     "transitions": [
       {
         "transition_id": "t1",
         "segment_id": "s1",
         "year": 2026,
         "method": "mowing",
         "before_height_m": 2.0,
         "after_height_m": 0.5,
         "before_cover_pct": 50.0,
         "after_cover_pct": 10.0,
         "efficacy": 0.75,
         "regrowth_delay_years": 2,
         "source": "synthetic"
       }
     ],
     "observations": [
       {
         "observation_id": "o1",
         "segment_id": "s1",
         "observed_date": "2026-07-01",
         "sensor": "lidar",
         "product": "CHM",
         "coverage_pct": 100.0,
         "height_m": 2.0,
         "cover_pct": 50.0,
         "height_error_m": 0.2,
         "cover_error_pct": 5.0,
         "source": "synthetic",
         "source_version": "1.0"
       }
     ]
   }

Python use
----------

.. code-block:: python

   from pathlib import Path
   from brushline.model.state import StateContract, validate_state_contract

   contract = StateContract.model_validate_json(Path("state.json").read_text())
   report = validate_state_contract(contract, required_segment_ids={"s1", "s2"})
   if not report.is_valid:
       raise SystemExit("\n".join(report.errors))
