FEMIC extension boundary
========================

Brushline extends FEMIC's instance, rebuild-spec, FreshForge, catalogue, DataLad, and preflight
surfaces. It does not import FEMIC internals, fork the provider, or build a second instance-builder
package. This page is the pinned boundary.

Exact pins
----------

.. list-table::
   :header-rows: 1
   :widths: 22 78

   * - Component
     - Pin
   * - FEMIC
     - ``==0.2.0a1``
   * - FreshForge
     - ``==0.1.0a5``
   * - Boundary schema
     - ``brushline.femic-boundary.v1``

FEMIC is an alpha package and its provider API can change between releases. The pin is exact on
purpose. A new FEMIC or FreshForge release is a deliberate boundary review with a new pin, a compatible
test run, and a changelog entry. It is not a silent dependency upgrade.

Install the optional extra only when the instance builder is needed:

.. code-block:: bash

   python -m pip install -e ".[femic]"

Brushline core, the contracts, the fixture, and the prototype install and run without FEMIC.

Provider ids
------------

- ``femic``
- ``femic.materialization``

FEMIC nodes
-----------

``validate_case``, ``geospatial_preflight``, ``compile_upstream``, ``accepted_btc_handoff``,
``btc_post_tipsy``, ``export_patchworks``, ``patchworks_preflight``, ``matrix_build``,
``export_woodstock``, ``ws3_bridge``, and ``ws4_quality``.

Materialization nodes
---------------------

``check_toolchain``, ``check_python_environment``, ``install_packages``, ``init_submodules``,
``init_annex``, ``enable_special_remote``, ``materialize_paths``, ``audit_annex_availability``, and
``write_materialization_report``.

FEMIC CLI commands
------------------

- ``femic instance init``
- ``femic instance rebuild``
- ``femic instance validate-spec``
- ``femic instance config show``
- ``femic freshforge workflows list``
- ``femic data bcdc-resolve``
- ``femic data bcdc-fetch``
- ``femic data bcdc-order``
- ``femic prep validate-case``
- ``femic prep geospatial-preflight``

FreshForge CLI commands
-----------------------

- ``freshforge validate``
- ``freshforge inspect``
- ``freshforge plan``
- ``freshforge run``
- ``freshforge providers``

Data contracts
--------------

- ``femic.lidar.product.v1``
- ``femic.lidar.bundle.v1``
- ``femic.inventory.als.v1``
- ``femic.inventory.als.model.v1``
- ``femic.climate.v1``
- ``femic.disturbance.v1``
- ``femic.efi.model.v1``

What Brushline may call
-----------------------

Only the commands and provider nodes above, plus the data contracts as read-only inputs. The
instance-builder extension adds ``brushline.*`` provider nodes that call the existing Brushline CLI.
The extension does not call FEMIC Python internals, private functions, or an unlisted command.

What Brushline may not call
---------------------------

- FEMIC's internal modules or private helpers.
- A FEMIC provider node that is not in the pinned list.
- A data contract that is not in the pinned list without a boundary review.
- A second data-acquisition or instance-builder package.

Compatibility check
-------------------

.. code-block:: python

   from brushline.integrations.femic import check_femic_compatibility

   report = check_femic_compatibility("0.2.0a1", "0.1.0a5")
   if not report.is_compatible:
       raise SystemExit("\n".join(report.errors))

The check rejects a different FEMIC version, a different FreshForge version, and an invalid version
string. A missing FreshForge version is a warning, not a pass.

The committed pin is ``notes/reference/femic-provider-api.v1.json``. It records the versions, the
provider ids, the node ids, the CLI commands, and the data contracts. The validator compares the pin
with the canonical manifest and fails if a provider, node, command, or contract is missing or extra.

Regenerate the pin
------------------

After a deliberate boundary review:

.. code-block:: bash

   python - <<'PY'
   from pathlib import Path
   from brushline.integrations.femic import write_boundary_pin
   write_boundary_pin(Path("notes/reference/femic-provider-api.v1.json"))
   PY

Then update the version constants, the compatibility tests, the changelog, and this page in the same
change set.

Drift policy
------------

- The pinned surface is the contract.
- A drift test fails when the pin and the canonical manifest disagree.
- A FEMIC upgrade requires a new pin, a review of the provider nodes, a compatibility run, and a
  changelog entry.
- A Brushline provider node may call only a declared FEMIC command or data contract.
- A missing provider or node is a blocker, not a warning to ignore.
