Tactical validation
===================

P7.7 validates a deterministic synthetic tactical/operational case: program, access, resources,
work orders, FHOPS dry run, and timeline.

The committed result is ``notes/reference/p7-validation.v1.json``.

Checks
------

- ``CAPACITY``: program and contractor resource plans are feasible.
- ``ACCESS``: every access window is allowed under source status.
- ``SEASONALITY``: methods and seasons match the treatment units.
- ``TRACEABILITY``: every tactical action has a work order.
- ``DRY_RUN``: FHOPS is a dry run with positive cost.
- ``TIMELINE``: two events per work order.

Limits
------

- Synthetic only; no field, contract, or live FHOPS run.
- Not a dispatch release or safety certification.
- No global tactical/operational optimality claim.
