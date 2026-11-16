Rolling-horizon policy
======================

The rolling-horizon experiment turns the annual planning problem into an executable policy. At each
year it observes that year's cost, productive-hours, and capacity factors, assumes those conditions
persist over a short lookahead, re-solves the stateful MILP, and commits only the current year's
actions. The next year starts from the updated risk state and observes new factors.

The policy is a **persistence-forecast heuristic**, not a stochastic dynamic program and not a
globally optimal policy. Annual factors are independent across years; the policy never observes the
future. A two-year lookahead is used in the network demonstration.

## Comparison

The fixed nominal plan is evaluated under the same annual factors. Its treatment schedule does not
adapt, so its cost and hours move with the factors but its risk stays at the nominal plan's value.
The rolling policy re-solves with the observed current factors and updates its risk state.

Network demonstration:

- 8,737 ha, 59 segments, 2027-2031;
- 20 annual-factor episodes, seed 7;
- two-year lookahead;
- 100 annual MILP re-solves, all optimal.

.. list-table::
   :header-rows: 1

   * - Policy
     - 5-year cost P10-P90
     - Mean risk
     - Budget violation
     - Capacity violation
   * - Fixed nominal
     - 265,469-333,437
     - 0.0294
     - 95.0%
     - 0.0%
   * - Rolling policy
     - 298,123-299,398
     - 0.0296
     - 0.0%
     - 0.0%

The risk-equivalent objective was 0.1031 for the fixed plan and 0.0296 for the rolling policy, with
mean regret 0.0735. The objective includes a normalized budget/capacity penalty. The fixed plan's
high budget-violation rate reflects independent annual cost draws; it is not directly comparable to
the persistent-factor scenario set used in the hindsight experiment.

## Interpretation

The rolling policy trades a small amount of nominal risk reduction for a much narrower cost range and
annual budget feasibility. It adapts the current-year actions to observed conditions rather than
committing the nominal five-year schedule.

## First-year execution

The median-cost policy episode (episode 18) was converted into a first-year tactical, access,
resource, work-order, and shift package. This is an execution test, not a new optimization.

.. list-table::
   :header-rows: 1

   * - Metric
     - Policy year 1
     - Fixed year 1
   * - Segment treatments
     - 45
     - 46
   * - Cost
     - 59,794 CAD
     - 59,972 CAD
   * - Crew-hours
     - 814
     - 1,000
   * - Tactical actions
     - 17
     - n/a
   * - Work orders
     - 17
     - n/a
   * - Shift assignments
     - 116
     - n/a

The policy package is resource- and shift-feasible: 17/17 access checks open, 42,522 CAD modelled
resource cost, 813.7 productive hours, and 8.5 travel hours. It is one median-cost episode, not an
operability guarantee for every episode.

The first-year handoff was repeated for all 20 episodes. All 20 packages were tactical-, access-,
resource-, operations-, and shift-feasible under the prototype assumptions. First-year cost ranged
from 59,775 to 59,986 CAD, crew-hours from 699 to 1,295, and annual risk from 0.070 to 0.147. Failed
episodes: 0. This is an operability result for the assumptions, not a field guarantee.

## Scale test

The same policy was run on a replicated 590-segment stress instance with tenfold annual budget and
capacity. The fixed plan was solved exactly; the rolling policy used the Fresh Solutions heuristic for
each annual re-solve.

.. list-table::
   :header-rows: 1

   * - Segments
     - Policy
     - 5-year cost P10-P90
     - Mean risk
     - Budget violation
   * - 59
     - Fixed nominal
     - 265,469-333,437
     - 0.0294
     - 95.0%
   * - 59
     - Rolling exact
     - 298,123-299,398
     - 0.0296
     - 0.0%
   * - 590
     - Fixed exact
     - 2,655,911-3,335,908
     - 0.0291
     - 95.0%
   * - 590
     - Rolling heuristic
     - 2,902,237-2,998,129
     - 0.0297
     - 0.0%

The 590-segment case is a replicated stress instance, not a real network. The rolling annual plans
are feasible heuristic incumbents, not optimal plans.

## Limits

- Persistence forecast: current factors are assumed to persist over the two-year lookahead.
- Annual factors are independent; no serial correlation or calibrated forecast process is claimed.
- The policy commits only the current year and is evaluated on 59 segments.
- The MILP is exact only for the declared linear risk state.
- Twenty episodes are a demonstration sample, not a probability-calibrated policy evaluation.
- No field calibration, outage constraint, safety certification, or asset-owner standard is claimed.
