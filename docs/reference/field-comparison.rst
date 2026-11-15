Field comparison
================

Field comparison reads a validated observation report and the planned plot targets, then reports
plot-level residuals and unit-level bias. It does not silently correct the LiDAR layer, the vegetation
model, or the treatment schedule.

The comparison uses different definitions on purpose:

- field shrub cover versus the LiDAR mean cover target;
- field shrub height versus the LiDAR maximum shrub-height target.

Positive cover or height deltas mean the field measurement is above the LiDAR target. Suggested
multipliers are review aids. They are not applied automatically.

Sample status
-------------

``insufficient`` means fewer than three complete cover/height pairs. ``provisional`` means at least
three, but fewer than eight complete pairs for either metric. ``adequate`` requires at least eight
complete pairs for both metrics. These thresholds are evidence-review gates, not statistical
confidence claims.

Treatment response remains ``not_tested`` until before/after field observations exist. The modelled
shrub reduction and annual regrowth are not calibrated by this report.

Command
-------

.. code-block:: bash

   brushline field compare \
     --observations field-observations-validated.json \
     --plots corridor-plots.geojson \
     --out field-comparison.json

The output contains plot rows, unit summaries, cover and height multipliers, recommendations, warnings,
and caveats. It is a review input for the next calibration decision.
