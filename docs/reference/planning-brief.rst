Planning brief
==============

The planning brief is a self-contained decision record for the network prototype. It packages the
selected frontier point, annual MILP schedule, tactical demand, shift summary, workforce scenarios,
commercial check, execution uncertainty, hindsight-adaptive comparison, rolling-horizon policy,
first-year policy execution and all-episode scan, static budget-headroom candidates, weather and
outage stress and all-episode calendar scan, capacity/scope remedies, risk-ranked scope deferral,
multi-year risk trajectory, rolling recovery, out-of-sample recovery, deferral-fraction frontier,
frontier validation, scenario-robust static plan, sampled budget chance constraint, chance capacity, 100-path chance, first-year and multi-year
two-stage operational recourse, rolling recourse, weather/outage-aware recourse, forecast-skill
sensitivity, fall-window capacity remedy, added-crew versus window remedy, scaling evidence,
caveats, and reproduction metadata into one document.

The brief is generated on demand from the network artifact set. It is not a new model result and it
does not hide the underlying assumptions:

- the network is a public-data prototype, not an asset-owner plan;
- costs, hours, productivity, access, and capacity are demo assumptions;
- the MILP is exact only for the declared linear risk state;
- the scenario-optimized comparison is a hindsight upper bound, not an executable policy;
- no field calibration, outage constraint, safety certification, or clearance standard is claimed.

## Formats

The studio exposes a **Planning brief** download. The endpoint returns either:

- ``text/html``: a self-contained, print-friendly HTML document with embedded CSS and no external
  assets;
- ``text/markdown``: the same sections as GitHub-flavoured Markdown.

Both formats are generated from the current model artifacts and include the active repository
commit when available.

## Endpoint

.. code-block:: text

   GET /api/studio/network/brief?instance_id=bc-hydro-network&format=html
   GET /api/studio/network/brief?instance_id=bc-hydro-network&format=markdown

HTML is served with ``Content-Disposition: inline`` so the studio link opens a readable page in a
new tab. Add ``download=1`` to force an attachment. Markdown remains an attachment. Filenames are
derived from the instance id.

## Scope

The brief is a lab-review artifact. It is not a public release of network-derived data. Public demo
content remains synthetic until data-sharing and release approval.
