Studio and public demo
======================

Run the studio
--------------

.. code-block:: bash

   python -m uvicorn brushline.web.studio:app --host 127.0.0.1 --port 8801

Open ``http://127.0.0.1:8801/``. The service reads artifacts; it does not own model state. The
synthetic and observed public instances are always available when their files exist. The BC network
instance appears only when ``runtime/private/bc-network/model/`` is present.

The studio exposes summary, plan, Pareto, timeline, block, scene, skins, and progress endpoints.
The 2D/3D views are context displays; positions are not invented when unknown.

Build the public demo
---------------------

.. code-block:: bash

   brushline demo build --out build/demo
   python -m http.server 8000 --directory build/demo

The public demo is synthetic and read-only. Do not copy private network artifacts into it.

Port discipline in this workspace
---------------------------------

- ``8765``: fresh-irss-demo;
- ``8799``: Nemora;
- ``8801``: Brushline.

Use a different port or stop a service before starting another one.

Contracts
---------

- :doc:`../reference/studio`
- :doc:`../reference/demo-portal`
