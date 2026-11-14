Brushline FreshForge provider
=============================

The Brushline provider exposes the instance stages to FreshForge. It is optional and stateless:
validation and planning do not mutate the instance, and execution only happens when FreshForge calls
``run_node``.

Install
-------

.. code-block:: bash

   python -m pip install -e ".[freshforge]"

The provider is registered under the ``freshforge.providers`` entry-point group:

.. code-block:: toml

   [project.entry-points."freshforge.providers"]
   brushline = "brushline.integrations.freshforge:provider_factory"

Provider id: ``brushline``.

Nodes
-----

.. list-table::
   :header-rows: 1
   :widths: 24 20 22 34

   * - Node
     - Inputs
     - Outputs
     - Parameters
   * - ``brushline.validate_aoi``
     - ``aoi``
     - ``aoi_validation``
     - ``aoi``, ``out``
   * - ``brushline.segment_corridor``
     - ``aoi_validation``
     - ``segments``
     - ``corridor``, ``out``
   * - ``brushline.compile_dataset``
     - ``segments``
     - ``dataset``
     - ``fixture``, ``out``, optional ``force``
   * - ``brushline.seed_vegetation_state``
     - ``dataset``
     - ``states``
     - ``state``, ``out``
   * - ``brushline.validate_scenario``
     - ``states``
     - ``scenario_validation``
     - ``scenario``, ``targets``, ``out``
   * - ``brushline.build_demo``
     - ``scenario_validation``
     - ``demo``
     - ``demo``, ``out``

Each node also declares one artifact key matching its output. The provider resolves each artifact path
against the FreshForge run context.

Execution
---------

Each node builds a ``python -m brushline instance ...`` command:

.. code-block:: text

   brushline instance validate-aoi --aoi <path> --out <dir>
   brushline instance segment-corridor --corridor <path> --out <dir>
   brushline instance compile-dataset --fixture <path> --out <dir> [--force]
   brushline instance seed-state --state <path> --out <dir>
   brushline instance validate-scenario --scenario <path> --targets <path> --out <dir>
   brushline instance build-demo --demo <path> --out <dir>

The stage commands are thin. P2.7 replaces the map-to-instance orchestration, and P3/P5 replace the
state seeding and scenario validation with the real models. The provider always calls the CLI; it does
not reimplement the stage.

Validation
----------

``validate_node`` reports a named diagnostic for every missing input, output, parameter, or artifact:

- ``brushline.validation.inputs.missing``
- ``brushline.validation.outputs.missing``
- ``brushline.validation.parameters.missing``
- ``brushline.validation.artifacts.missing``

Execution failures use:

- ``brushline.execution.parameters.invalid`` for a missing parameter,
- ``brushline.execution.command.failed`` for a non-zero command,
- ``brushline.execution.unsupported`` for an unknown node type.

Offline use
-----------

The provider accepts a command runner, so tests can exercise the metadata, validation, command
building, and result handling without a live FreshForge run:

.. code-block:: python

   from brushline.integrations.freshforge import BrushlineFreshForgeProvider

   provider = BrushlineFreshForgeProvider(my_runner)
   assert provider.metadata().id == "brushline"

The test suite uses this hook for every node and for the success, failure, missing-parameter, and
unknown-node paths.
