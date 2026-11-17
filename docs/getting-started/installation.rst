Installation
============

Brushline requires **Python 3.11 or newer**. It is developed and tested on Linux. macOS and Windows
are not verified.

From a clone of the repository:

.. code-block:: bash

   python -m venv .venv
   . .venv/bin/activate
   python -m pip install --upgrade pip
   python -m pip install -r requirements-dev.txt
   python -m pip install -e ".[geo,opt,web]"

The base package is enough for the synthetic fixture and the core model. The optional extras add:

- ``geo``: GeoPandas, Shapely, and spatial file support;
- ``opt``: the Fresh Solutions metaheuristic adapter;
- ``web``: FastAPI, Uvicorn, and the studio's map dependencies;
- ``femic`` and ``freshforge``: optional producer integrations.

Verify the install:

.. code-block:: bash

   brushline status
   brushline --help
   python scripts/dashboard.py

``python scripts/dashboard.py`` runs lint, formatting, strict types, tests with a coverage gate, the
workflow validator, and the documentation build. A green dashboard is the project's normal local
check.

Build the documentation directly with:

.. code-block:: bash

   python -m sphinx -W -b html docs docs/_build/html

Private data is not installed from the repository. The BC network prototype uses cached artifacts
under ``runtime/private/``; those files are ignored and are not part of a public checkout.

If a command fails, see :doc:`../guides/troubleshooting`.
