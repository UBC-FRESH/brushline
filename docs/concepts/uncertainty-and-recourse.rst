Uncertainty and recourse
========================

The prototype distinguishes several questions that are easy to blur together.

Factors and scenarios
---------------------

**Factors** are multiplicative annual changes in cost, hours, or capacity. A **scenario** is one
path through those factors. A **band** reports percentiles across a set of paths. A band is not a
probability distribution unless the sampling design says so.

Static, robust, and chance plans
--------------------------------

- A **static** plan is fixed before the factors are observed.
- A **robust** plan is selected against a set of sampled scenarios.
- A **chance** plan limits violations on a sampled training set; out-of-sample violations can still
  occur.
- A **two-stage** or **recourse** plan defers some actions after factors are observed.
- A **rolling** policy re-solves future years as time advances.

The multi-year and weather pages compare these policies on common paths. They are decision
experiments, not proofs that a policy is optimal or distributionally safe.

What recourse means here
------------------------

Recourse is **fixed-plan annual deferral** or **rolling re-optimization** with a two-year lookahead.
It is not a stochastic dynamic program. It does not compute an optimal policy over the full
uncertainty distribution.

Weather, outage, and forecast skill
-----------------------------------

The weather experiments use an assumed calendar: five fixed outage days plus independent 20% daily
weather loss in a 75-day window. The calendar-aware case observes the calendar before deferral. The
forecast-aware case plans against an independent synthetic forecast and executes under the actual
calendar. The forecast-skill sweep is a diagnostic, not a weather forecast product.

The weather model is documented in :doc:`../reference/weather-recourse`,
:doc:`../reference/forecast-skill`, and :doc:`../reference/window-remedy`.

Claims to avoid
---------------

Do not report any of these as a result:

- a distributional guarantee from a sampled chance constraint;
- a globally optimal policy from a heuristic;
- a field-validated safety or clearance standard;
- a forecast service from the synthetic calendar draw.
