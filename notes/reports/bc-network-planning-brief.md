# BC network planning brief

## Purpose

The planning brief is a one-click decision record for the 8,737 ha network prototype. It packages
the model outputs into a document that a reviewer can read without navigating the studio tables.

## Contents

- decision summary and selected frontier point;
- public-data provenance and licences;
- method cost, hours, service, and risk assumptions;
- budget/risk frontier including the BAU row;
- selected five-year MILP schedule;
- annual tactical demand, work orders, shifts, and access summary;
- workforce scenarios;
- owner cost, mock bid, delta, and fair range;
- execution-uncertainty bands and shortfall probabilities;
- fixed versus hindsight-adaptive cost/risk comparison;
- rolling-horizon policy comparison;
- heuristic scaling evidence;
- caveats and reproduction metadata.

## Output

`GET /api/studio/network/brief?instance_id=bc-hydro-network&format=html` returns a self-contained
HTML document with embedded CSS and no external assets or scripts. The `format=markdown` variant
returns the same content as Markdown. Both responses use an attachment filename derived from the
instance id.

The brief is generated from `runtime/private/bc-network/model/` artifacts at request time. It
includes the checked-out commit when available. Network-derived content remains private until
data-sharing and release approval.

## What it does not do

- It does not re-optimize or change any plan.
- It does not turn the prototype stand state, costs, or capacities into field-calibrated values.
- It repeats the caveat that scenario-optimized planning is a hindsight upper bound, not an
  executable forecast-update policy.
- It does not make a safety, clearance, procurement, or asset-owner claim.

## Verification

- HTML rendering escapes artifact text and contains no script or external asset.
- The selected plan, frontier, workforce, commercial, uncertainty, and adaptive tables are populated
  from the generated artifacts rather than hard-coded UI strings.
- The studio exposes a **Planning brief** download only for the network instance.
