Troubleshooting
===============

Install and imports
-------------------

**``brushline: command not found``** — activate the virtual environment and reinstall with
``python -m pip install -e .``. Check ``brushline status``.

**Optional import errors** — install the appropriate extra, for example
``python -m pip install -e ".[geo,opt,web]"``. The base package intentionally keeps the web and
optimization paths optional.

**Docs build fails** — install ``docs/requirements.txt`` and run
``python -m sphinx -W -b html docs docs/_build/html``. The build treats warnings as errors.

Private network artifacts
-------------------------

**The network instance does not appear** — the studio only exposes it when
``runtime/private/bc-network/model/`` exists. A clean public checkout does not include it.

**A builder reports missing cache files** — the private OSM, VRI, DEM, or network cache is absent.
Do not fabricate it; restore the approved private cache or stay on the synthetic demo.

**I need to share a result** — stop. Run :doc:`../howto/release-audit`, read
:doc:`private-public`, and do not publish network-derived artifacts before approval.

Solvers and performance
-----------------------

**The MILP times out** — exact stateful MILP is intended for small instances. Use the Fresh
Solutions heuristic or cluster repair for larger cases, and report the search status rather than
calling it optimal.

**A heuristic result differs from an exact result** — they are different methods. Check the solver
status, seed, instance size, and whether the exact model is still within its intended range.

**A run is slower than expected** — the network builder, scenario sweeps, and 590-segment policy
experiments take minutes. Use the focused builders and cached artifacts rather than rebuilding the
full network for every change.

Studio and ports
----------------

**Port already in use** — in this workspace ``8765`` is fresh-irss-demo, ``8799`` is Nemora, and
``8801`` is Brushline. Stop the conflicting service or use another port.

**The studio shows stale data** — restart the service after regenerating artifacts, and check the
static asset version in the page source.
