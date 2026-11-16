# Rolling policy year-one execution

## Question

Can the rolling policy's first-year strategic actions be converted into a feasible tactical, access,
resource, and shift package? The studio's existing shift schedule belongs to the fixed balanced plan;
this test closes that handoff for one representative policy episode.

## Method

- Select the **median rolling five-year cost** episode from the 20-episode policy run.
- Use that episode's first-year actions (2027).
- Map segment actions to management units and aggregate them into tactical actions.
- Build access windows, contractor resource requests, work orders, and crew/machine shifts.
- Compare aggregate first-year cost and crew-hours with the fixed balanced plan.

## Selected episode

- Episode: **18**
- Five-year rolling cost: **298,947 CAD**
- Year: **2027**
- Observed factors: cost 1.01377, productive hours 0.82854, capacity 0.78205
- Policy year-one cost: **59,794 CAD**
- Policy year-one crew-hours: **814 h**
- Policy year-one risk: **0.1182**

## Handoff result

| Metric | Policy year 1 | Fixed year 1 |
|---|---:|---:|
| Segment treatments | 45 | 46 |
| Cost | 59,794 | 59,972 |
| Crew-hours | 814 | 1,000 |
| Tactical actions | 17 | n/a |
| Work orders | 17 | n/a |
| Shift assignments | 116 | n/a |

- Access checks: 17/17 open; 16,761.5 m of modelled route.
- Resource plan: feasible; 42,522 CAD modelled resource cost.
- Operations plan: feasible; 17 work orders.
- Shift plan: feasible; 813.7 productive hours and 8.5 travel hours.
- Cost delta versus fixed first year: **-178 CAD**; hours delta: **-186 h**.

## All-episode scan

The first-year handoff was repeated for all 20 rolling episodes.

- Fully feasible: **20/20 (100%)**
- Tactical feasible: 20/20
- Access open: 20/20
- Resource feasible: 20/20
- Operations feasible: 20/20
- Shift feasible: 20/20
- First-year cost P10-P90: **59,775-59,986 CAD**
- First-year crew-hours P10-P90: **699-1,295**
- First-year risk P10-P90: **0.070-0.147**
- Shift assignments: 87-213 per episode
- Failed episodes: 0

All first-year packages were feasible under the prototype tactical, access, resource, and shift
assumptions. This is an operability result for the assumptions, not a field guarantee.

## Interpretation

The median-cost policy episode can be handed to the tactical and shift layers for its first year. The
policy's first-year cost is essentially the same as the fixed plan, with lower modelled crew-hours and
a slightly higher annual risk. This is a single representative episode, not a claim that all policy
episodes are equally operable.

## Limits

- Selected by median five-year cost, not best or worst outcome.
- First-year package only; later years are re-planned.
- Tactical, access, resource, and shift values are prototype assumptions.
- No weather, outage, safety, asset-owner, or field-calibration claim.
