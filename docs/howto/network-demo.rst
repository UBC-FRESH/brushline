Build the network prototype
===========================

This is a **private workflow**. It requires the cached OSM, VRI, DEM, and derived network inputs
under ``runtime/private/bc-network/``. A public checkout does not contain them.

Build the model
---------------

From the repository root:

.. code-block:: bash

   python tools/build_bc_network_demo.py

The builder writes the private model artifacts under:

.. code-block:: text

   runtime/private/bc-network/model/

The main outputs are the network, strategic, tactical, resources, operations, shifts, workforce,
bid, uncertainty, scenario-optimization, access, and planning-brief inputs. The build can take
several minutes.

Run policy comparisons
----------------------

The focused builders read the private model and write additional ignored artifacts:

.. code-block:: bash

   python tools/build_rolling_recourse.py
   python tools/build_weather_recourse.py
   python tools/build_forecast_skill.py
   python tools/build_window_remedy.py
   python tools/build_capacity_remedy.py

Scale artifacts for the replicated 590-segment stress instance are built with the matching
``*_scale.py`` tools. The 590 and 10,030-segment instances are replicated stress cases, not real
networks.

Inspect the model
-----------------

.. code-block:: bash

   python -m uvicorn brushline.web.studio:app --host 0.0.0.0 --port 8801

Open the studio and select the network instance. The planning brief is available at:

.. code-block:: text

   /api/studio/network/brief?instance_id=bc-hydro-network&format=html

The `8801` port is reserved for Brushline in this workspace. Do not reuse the demo ports `8765` or
`8799`.

Before sharing anything, run :doc:`release-audit`.
