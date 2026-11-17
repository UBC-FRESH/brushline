Getting started
===============

Brushline is a pre-alpha decision-support prototype for vegetation management along linear
infrastructure corridors. It is not a field-calibrated operational system, and it is not approved
for asset-owner use.

There are two ways into the project:

- **Public synthetic example.** Start with :doc:`quickstart` to generate a deterministic corridor,
  compile it, simulate it, and build the static demo. This path needs no private data.
- **Private network prototype.** Start with :doc:`../howto/network-demo` when the BC network cache
  is available. That path builds plans, policy scenarios, and the planning brief from ignored
  private artifacts.

.. list-table::
   :header-rows: 1
   :widths: 26 74

   * - Page
     - What it covers
   * - :doc:`installation`
     - Requirements, optional dependencies, and the local verification commands.
   * - :doc:`quickstart`
     - The shortest working path through the public synthetic example.
   * - :doc:`first-study`
     - How to read the artifacts from a first run and what the numbers do and do not mean.
   * - :doc:`../guides/limitations`
     - The boundaries that matter before using a result.

.. toctree::
   :maxdepth: 2
   :hidden:

   installation
   quickstart
   first-study
