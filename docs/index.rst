=====================================
Brushline
=====================================

Brushline is a pre-alpha decision-support prototype for vegetation management along linear
infrastructure corridors: powerlines, pipelines, roads, railways, and the rights-of-way that keep
them accessible and safe.

It couples a low-vegetation state-transition model, strategic/tactical/operational planning,
scenario and recourse experiments, a planning studio, and artifact contracts. It is a working
research prototype, **not** a field-calibrated operational system.

Who this documentation is for
=============================

.. list-table::
   :header-rows: 1
   :widths: 22 24 54

   * - Reader
     - Start here
     - What you will learn
   * - New user
     - :doc:`getting-started/index`
     - Install the package, run the synthetic fixture, and read a first study.
   * - Analyst or planner
     - :doc:`concepts/index` and :doc:`howto/index`
     - The model, the planning stack, uncertainty/recourse, and the private network workflow.
   * - Reviewer or asset owner
     - :doc:`guides/limitations`
     - What the prototype does and does not claim, and which results are private or synthetic.
   * - LLM coding agent
     - ``AGENTS.md``, :doc:`reference/contract-index`, and :doc:`api/index`
     - The contracts, invariants, and commands to respect when changing the repository.

Start with the synthetic example
================================

The public path needs no private data:

.. code-block:: bash

   brushline fixture --out tmp/corridor
   brushline prototype --fixture tmp/corridor --out tmp/prototype --years 5
   brushline demo build --out build/demo
   python -m http.server 8000 --directory build/demo

The private BC network prototype is a separate workflow. It requires the cached network artifacts
under ``runtime/private/`` and must not be published before approval. See
:doc:`howto/network-demo` and :doc:`guides/private-public`.

Documentation map
=================

.. list-table::
   :header-rows: 1
   :widths: 22 78

   * - Section
     - Contents
   * - :doc:`getting-started/index`
     - Installation, quickstart, and a first study.
   * - :doc:`concepts/index`
     - The model, planning stack, uncertainty/recourse, and artifact/privacy model.
   * - :doc:`howto/index`
     - Network build, planning brief, studio, and release audit.
   * - :doc:`guides/index`
     - Limitations, private/public boundaries, and troubleshooting.
   * - :doc:`reference/index`
     - Contracts, methods, policy experiments, and artifact records.
   * - :doc:`design/index`
     - Scope, architecture, optimization, UI, LiDAR, and decision records.
   * - :doc:`api/index`
     - Public Python API, grouped by domain.

The reference section mixes **contracts** (which the code validates) with **experiment records**
(which report prototype results). Do not treat a benchmark page as a contract or a contract page as
evidence of field performance. The reference index says which is which.

What this documentation is not
==============================

- It is not a public release of BC Hydro, MKRF, or other private network data.
- It is not a field validation report, safety certification, or asset-owner standard.
- It does not turn a sampled scenario result into a distributional guarantee.
- It does not call a heuristic search state a globally optimal plan.

.. toctree::
   :maxdepth: 2
   :caption: Getting started

   getting-started/index

.. toctree::
   :maxdepth: 2
   :caption: Concepts

   concepts/index

.. toctree::
   :maxdepth: 2
   :caption: How-to guides

   howto/index

.. toctree::
   :maxdepth: 2
   :caption: Guides

   guides/index

.. toctree::
   :maxdepth: 2
   :caption: Reference

   reference/index

.. toctree::
   :maxdepth: 2
   :caption: Design record

   design/index

.. toctree::
   :maxdepth: 1
   :caption: API

   api/index

Indices and tables
==================

* :ref:`genindex`
* :ref:`search`
