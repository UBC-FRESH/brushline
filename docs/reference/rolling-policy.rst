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

## Limits

- Persistence forecast: current factors are assumed to persist over the two-year lookahead.
- Annual factors are independent; no serial correlation or calibrated forecast process is claimed.
- The policy commits only the current year and is evaluated on 59 segments.
- The MILP is exact only for the declared linear risk state.
- Twenty episodes are a demonstration sample, not a probability-calibrated policy evaluation.
- No field calibration, outage constraint, safety certification, or asset-owner standard is claimed.
