Field validation
================

Brushline field validation turns a campaign CSV into normalized observations and checks them against
the planned plot points. It is the import gate for field evidence; it is not a calibration model and
does not make a treatment decision.

The MKRF campaign generator writes its private kit under ignored runtime storage. The committed
repository contains the schema, validator, command, and tests, but no MKRF coordinates or plot
measurements.

Observation fields
------------------

Required fields are ``plot_id``, ``visit_date``, ``observer``, ``unit_id``, ``position``, ``latitude``,
and ``longitude``. ``position`` is ``center`` or ``edge``. Optional fields cover GPS accuracy,
dominant shrub species, shrub height, cover, stem count, recent cutting, right-of-way width, tree
species, tree height, tree distance, conductor clearance, photo IDs, and notes.

Photo IDs are comma- or semicolon-separated. The recommended filename is
``<plot_id>_<YYYYMMDD>_<sequence>.jpg``.

Validation rules
----------------

The validator checks:

- required CSV columns and all model fields;
- known plot IDs from the plans GeoJSON;
- planned unit and position matches;
- duplicate plot/date observations;
- coordinates within 50 m of the planned plot; 25 to 50 m is a warning;
- numeric and date ranges;
- missing photo IDs and incomplete shrub height/cover as warnings.

Failures are returned as named row errors. A report is written as JSON only when ``--out`` is given.
The normalized observations remain field evidence, not a survey-grade or safety certification.

Command
-------

.. code-block:: bash

   brushline field validate \
     --csv field-observations.csv \
     --plots corridor-plots.geojson \
     --out field-observations-validated.json

The command exits with status 1 when the report is invalid. The private MKRF field kit adds the
planned plots, target LiDAR values, printable plot cards, an offline map, a CSV template, and photo-log
guidance.
