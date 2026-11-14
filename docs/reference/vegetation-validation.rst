Held-out validation
====================

P4.6 validates the growth and state model against held-out observations and benchmarks at least one
candidate model. The validation is deterministic, offline, and separate from the calibration set.

The committed fixture is ``notes/reference/vegetation-validation.v1.json``.

Dataset
-------

A ``ValidationRecord`` carries:

- segment id, spatial block, observation date, and prediction year;
- functional group;
- observed and predicted height, cover, and optional density;
- predicted height and cover standard deviations;
- observation coverage and domain status;
- treatment history, source, and source version;
- optional candidate predictions.

Density requires both observed and predicted values. Candidate names must be unique per record.
Out-of-domain records need a reason.

Holdout and eligibility
-----------------------

The config names one or more holdout blocks. A record is eligible when:

- it is in a holdout block;
- coverage meets the minimum;
- it is in domain, unless out-of-domain records are explicitly included;
- the absolute prediction lag is within the maximum.

Excluded records are counted by reason: ``coverage``, ``out_of_domain``, and ``time_lag``. A holdout
with no eligible records is an error.

Metrics
-------

For each functional group and variable, the report records:

- record count;
- observed and predicted means;
- RMSE, MAE, and bias;
- interval coverage: the share of records inside the predicted interval.

Height and cover are always reported when present; density is reported only when both observed and
predicted values exist.

Time-lag sensitivity
--------------------

Records are grouped by absolute prediction lag. Each lag reports height and cover RMSE and bias. This
shows whether a model degrades as the prediction moves away from the observation year.

.. code-block:: python

   from datetime import UTC, datetime
   from pathlib import Path
   from brushline.vegetation.validation import (
       ValidationConfig,
       ValidationDataset,
       validate_vegetation,
       validate_vegetation_validation,
   )

   payload = __import__("json").loads(
       Path("notes/reference/vegetation-validation.v1.json").read_text()
   )
   dataset = ValidationDataset.model_validate(
       {"schema_version": payload["schema_version"], "records": payload["records"]}
   )
   report = validate_vegetation(
       dataset,
       ValidationConfig.model_validate(payload["config"]),
       created_utc=datetime(2026, 11, 14, tzinfo=UTC),
   )
   assert validate_vegetation_validation(report).is_valid

Candidate benchmark
-------------------

Each candidate prediction contributes a ``CandidateSummary`` with height/cover RMSE and bias, plus the
RMSE difference from Brushline. A difference above the disagreement tolerance raises a reviewer
question. The disagreement is recorded; it is not hidden or automatically corrected.

Output
------

``VegetationValidationReport`` carries:

- group/variable metrics;
- lag summaries;
- candidate summaries and differences;
- exclusion counts;
- errors, warnings, and open questions;
- counts.

Named errors
------------

.. list-table::
   :header-rows: 1
   :widths: 32 68

   * - Prefix
     - Meaning
   * - ``VALIDATION-BLOCK``
     - A holdout block is not in the dataset.
   * - ``VALIDATION-HOLDOUT``
     - No records fall in the holdout blocks.
   * - ``VALIDATION-EMPTY``
     - No eligible records, or a metric/candidate has no records.
   * - ``VALIDATION-TIME``
     - The report time is not timezone-aware.
   * - ``VALIDATION-ID``
     - Duplicate metrics or candidate names.
   * - ``VALIDATION-METRIC``
     - An unknown validation variable.
   * - ``VALIDATION-INTERVAL``
     - Interval coverage is outside 0 to 1.
   * - ``VALIDATION-LAG``
     - A negative time lag.
   * - ``VALIDATION-CANDIDATE``
     - No candidate benchmark (warning).

Limits
------

- The fixture is synthetic; it is not a field validation.
- No live MEDFATE, FVS/FFE, or Botequim run is performed.
- The validation does not fit parameters; P4.4 calibrates treatment parameters.
- A candidate difference is a finding, not a verdict on which model is correct.
- The report shows error and interval coverage; it does not prove operational fitness.
