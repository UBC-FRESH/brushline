Quickstart
==========

This walkthrough uses only the public synthetic fixture.

Generate and run the fixture
----------------------------

.. code-block:: bash

   brushline fixture --out tmp/corridor
   brushline prototype --fixture tmp/corridor --out tmp/prototype --years 5

The first command writes a deterministic two-corridor fixture. The second compiles it into a
validated dataset and writes a five-year prototype run under ``tmp/prototype``.

Inspect the result:

.. code-block:: bash

   find tmp/prototype -maxdepth 3 -type f | sort
   sed -n '1,80p' tmp/prototype/run/reports/summary.md

The run directory contains the compiled dataset, the simulated run, the schedule, and a summary
report. The exact filenames are defined by the artifact contracts in
:doc:`../reference/artifacts`.

Build the static demo
---------------------

.. code-block:: bash

   brushline demo build --out build/demo
   python -m http.server 8000 --directory build/demo

Open ``http://localhost:8000/``. The static demo is read-only and uses the checked synthetic example.

Run the studio
--------------

.. code-block:: bash

   python -m uvicorn brushline.web.studio:app --host 127.0.0.1 --port 8801

Open ``http://127.0.0.1:8801/``. With no private artifacts present, only the synthetic and observed
public instances are available. The network instance appears only when its ignored private artifact
set exists.

Private network prototype
-------------------------

The BC network prototype is a separate, private workflow. It requires the cached OSM, VRI, DEM, and
network artifacts described in :doc:`../howto/network-demo`. Do not run the network builder on a
clean public checkout and do not publish its output.

Next steps
----------

- :doc:`first-study` explains what the generated artifacts mean.
- :doc:`../concepts/index` explains the model and planning stack.
- :doc:`../guides/limitations` states what the prototype does not claim.
