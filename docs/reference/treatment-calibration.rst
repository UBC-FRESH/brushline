Treatment calibration
======================

P4.4 calibrates treatment efficacy, top-kill, resprouting, and regrowth delay from before/after
observations. It shrinks thin evidence toward the P4.3 priors, records intervals and the evidence level,
and runs deterministic leave-one-out checks. It does not acquire field data or change the plan schema.

The committed evidence fixture is ``notes/reference/treatment-calibration.v1.json``.

Evidence
--------

A ``TreatmentObservation`` records:

- method, season, and functional group;
- before/after height and cover;
- before/after density, when known;
- observed regrowth delay;
- sample size, date, source, and source version;
- notes.

The derived quantities are:

.. code-block:: text

   height_efficacy = 1 - after_height / before_height
   cover_efficacy  = 1 - after_cover / before_cover
   resprout_factor = max(0, after_density / before_density - 1)

The model rejects an after height or cover above the before value. A density pair must be complete.

Pooling and shrinkage
---------------------

For each method/season/group cell, the evidence level is:

1. ``exact`` when there are enough exact records;
2. ``method_group`` when the exact cell is thin but the method/group cell is not;
3. ``method`` when the method/group cell is also thin;
4. ``prior`` when no usable records remain.

Pooled and prior cells are flagged. The posterior is:

.. code-block:: text

   posterior = (data_mean * effective_n + prior * prior_strength)
               / (effective_n + prior_strength)

The intervals combine the observed weighted spread, sample size, and a normal multiplier. A thin record
does not become a precise estimate.

.. code-block:: python

   from datetime import UTC, datetime
   from pathlib import Path
   from brushline.vegetation.calibration import (
       TreatmentObservation,
       calibrate_treatment,
       validate_treatment_calibration,
   )

   payload = __import__("json").loads(
       Path("notes/reference/treatment-calibration.v1.json").read_text()
   )
   observations = [
       TreatmentObservation.model_validate(item) for item in payload["observations"]
   ]
   report = calibrate_treatment(
       observations,
       created_utc=datetime(2026, 11, 14, tzinfo=UTC),
   )
   assert validate_treatment_calibration(report).is_valid

Holdout checks
--------------

The calibration sorts observations by id and holds out every nth record. It refits on the remaining
records, predicts the held-out cover efficacy, and records the absolute error and tolerance. A failed
check is an error in the report validator; it is not hidden.

The committed fixture currently performs two leave-one-out checks, both within the default tolerance.

Applying the calibration
------------------------

``CalibratedTreatmentParameters.to_treatment_parameters(base)`` replaces the base efficacy, top-kill,
resprouting, and delay while preserving the method's cost and notes. The P4.3 transition model consumes
the calibrated parameters unchanged.

Output
------

``TreatmentCalibrationReport`` carries:

- calibrated cells with method, season, group, efficacy, top-kill, resprout, delay, intervals, sample
  size, effective sample size, evidence level, source ids, and model card;
- leave-one-out checks;
- reviewer open questions.

Named errors
------------

.. list-table::
   :header-rows: 1
   :widths: 32 68

   * - Prefix
     - Meaning
   * - ``CALIBRATION-TIME``
     - The report time is not timezone-aware.
   * - ``CALIBRATION-ID``
     - Duplicate calibration cell.
   * - ``CALIBRATION-EVIDENCE``
     - Unknown evidence level, a non-prior cell with no samples, or a prior not marked pooled.
   * - ``CALIBRATION-SOURCE``
     - A non-prior cell has no source ids.
   * - ``CALIBRATION-SAMPLE``
     - Effective sample weight is present without samples.
   * - ``CALIBRATION-HOLDOUT``
     - A leave-one-out check exceeds its tolerance.
   * - ``CALIBRATION-EMPTY``
     - No held-out checks (warning).

Limits
------

- The evidence fixture is synthetic; it is not a field calibration.
- The priors and posteriors are decision-support evidence, not a guarantee of treatment response.
- The model does not simulate chemical mode of action, fire behaviour, grazing preference, or safety
  permits.
- P4.6 validates the growth model; P4.7 publishes the model card and domain.
