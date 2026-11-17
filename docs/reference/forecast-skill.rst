Forecast-skill sensitivity
==========================

The forecast-aware weather policy can be tested against a coarse forecast-skill model. With
probability equal to the plotted skill, the annual forecast equals the actual calendar; otherwise
it is an independent synthetic draw. Skill 0 is independent, skill 1 is perfect.

This is a diagnostic for forecast error, not a meteorological forecast product.

## Results

20 episodes, seed 7, 75-day fall window.

.. list-table::
   :header-rows: 1

   * - Forecast skill
     - Completed scope P50
     - Retained scope P50
     - Mean risk
     - Cost P50
     - Unscheduled h
   * - 0%
     - 86.2%
     - 88.3%
     - 0.0526
     - 264,470
     - 64.7
   * - 50%
     - 88.0%
     - 88.8%
     - 0.0497
     - 264,723
     - 41.9
   * - 100%
     - 87.6%
     - 87.6%
     - 0.0502
     - 264,047
     - 0.0

Unscheduled work falls monotonically as forecast skill rises. Completion and risk do **not**
improve monotonically: mid-skill planning retains more scope and happens to complete more work,
while the perfect-forecast case is conservative because it defers whole actions until the observed
calendar fits.

## Limits

- The skill model is a perfect/independent mixture, not a calibrated forecast.
- One annual forecast realization per episode; no within-year updates.
- Whole-action deferral; no partial treatment credit.
- No safety, asset-owner priority, access, or field-calibration claim.
