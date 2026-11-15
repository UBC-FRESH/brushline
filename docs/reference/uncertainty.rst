Uncertainty and sensitivity
===========================

The uncertainty layer samples execution assumptions around a fixed tactical plan:

- cost multiplier;
- productive-hours multiplier (lower productivity increases hours);
- contractor-capacity multiplier.

It reports P10/P50/P90 for cost, hours, budget overrun, crew-hour shortfall, and contractor shortfall,
plus deterministic one-at-a-time cases for cost +20%, productivity -20%, capacity -20%, and combined
stress.

This is **execution uncertainty**, not a stochastic re-optimization. The plan is held fixed; the
sampler asks what happens if its cost, productivity, and capacity assumptions move. A later layer
could re-plan inside each sample.

The sampler is seeded and records every sampled outcome. It does not replace the MILP frontier or the
Fresh Solutions heuristic; it adds uncertainty around a selected plan.
