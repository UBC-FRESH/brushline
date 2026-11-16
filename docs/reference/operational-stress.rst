Weather and outage stress
=========================

The operational stress test applies an assumed weather and outage calendar to the median rolling
policy's first-year shift package. It is a feasibility screen, not a forecast, outage schedule, or
safety certification.

## Assumptions

- 75-day fall work window.
- Fixed 5-day outage block.
- Independent 20% weather-loss probability on each day in the window.
- 50 scenarios, seed 7.
- The baseline uses the same 75-day window with no blocked days.

## Network result

Baseline: feasible, 116 shift assignments, 813.7 productive hours, 8.5 travel hours, 63 days used.

Stress:

- fully feasible in **0/50 scenarios**;
- mean work completion: **93.4%**;
- median unscheduled work: **50.2 hours**;
- P90 unscheduled work: **97.7 hours**;
- mean blocked days: **19.4**;
- median shift assignments: **107**.

The assumed calendar removes enough field days that no sampled scenario schedules every work item.
The package completes most hours but leaves a median 50 hours unscheduled. This is a capacity and
calendar finding, not evidence that the policy is field-infeasible.

## Interpretation

The first-year policy package was feasible with no weather or outage closures. Under the assumed
calendar, it is not fully schedulable. The likely remedies are a longer window, additional crews or
machines, a smaller first-year scope, or a policy that reserves weather slack. Those are design
choices, not automatic conclusions.

## Limits

- Weather loss is an independent per-day assumption, not a forecast or field record.
- The fixed outage block is assumed, not an asset-owner outage schedule.
- Only the median policy episode and its first year are stressed.
- No field calibration, safety certification, or clearance standard is claimed.
