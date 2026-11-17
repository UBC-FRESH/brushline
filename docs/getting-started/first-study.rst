Your first study
================

The fast path in :doc:`quickstart` produces a synthetic study. This page explains what to read and
what not to infer from it.

Read the run in this order
--------------------------

1. **The run manifest** identifies the run type, status, data version, model versions, seed, and
   artifact index.
2. **The compiled dataset** is the decision-unit table: corridor segments and their site,
   vegetation, treatment, access, and observation attributes.
3. **A plan artifact** — when the workflow produces one — lists selected segment-year-method actions
   with costs, hours, assumptions, and risk notes.
4. **The simulation run** replays the plan or schedule through growth and treatment transitions.
   The synthetic prototype writes a ``schedule.csv``.
5. **The summary report** is a human-readable digest, not an additional source of truth.

The contracts behind these files are in :doc:`../reference/artifacts` and
:doc:`../reference/contract-index`. If a field is absent, do not infer a default from a report.

What the synthetic example demonstrates
---------------------------------------

- the fixture → compile → plan/replay → report path;
- a deterministic, inspectable dataset and plan;
- cost and service accounting against a declared budget;
- exact replay of a plan;
- artifact contracts that fail loudly on malformed input.

What it does not demonstrate
----------------------------

- a field-calibrated growth model;
- a real asset owner's access, outage, safety, or clearance standard;
- a globally optimal treatment schedule;
- a public release of any private network data.

Continue with :doc:`../concepts/model`, :doc:`../concepts/planning-stack`, and
:doc:`../guides/limitations`.
