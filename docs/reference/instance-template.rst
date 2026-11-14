Brushline instance template
===========================

The Brushline instance template is an overlay on a FEMIC deployment instance. It adds Brushline
configuration, two rebuild specs, a runbook, and evidence placeholders. It does not replace the FEMIC
workspace.

Install
-------

.. code-block:: bash

   femic instance init --instance-root <path> --no-download-bc-vri
   brushline instance template --instance-root <path>

``femic instance init`` already writes ``config/rebuild.spec.yaml``, ``config/rebuild.allowlist.yaml``, ``QUICKSTART.md``, and ``runbooks/REBUILD_RUNBOOK.md``. The overlay skips those four files unless ``--force`` is passed. Use ``--force`` on a fresh FEMIC instance when you want the Brushline versions; otherwise the FEMIC defaults are kept.

Layout
------

.. code-block:: text

   <instance>/
     README.md
     QUICKSTART.md
     config/
       rebuild.spec.yaml
       rebuild.allowlist.yaml
       brushline/
         scenario.yaml
         targets.yaml
         standards.yaml
         rebuild.steps.yaml
     runbooks/
       REBUILD_RUNBOOK.md
     evidence/
       README.md
     tests/
       README.md

The template is installed beside the FEMIC config, data, runtime, and output directories. It does not
delete or overwrite unrelated files.

Two rebuild specs
-----------------

FEMIC's rebuild schema accepts only ``femic_command``, ``manual_boundary``, and ``quality_gate`` steps,
and its rebuild runner owns a fixed FEMIC stage list. The template therefore carries two specs:

``config/rebuild.spec.yaml``
   The FEMIC-compatible spec. It is validated by
   ``femic instance validate-spec`` and contains the FEMIC stages only.

``config/brushline/rebuild.steps.yaml``
   The Brushline extension spec. It declares the six ``brushline.*`` provider stages and their
   dependencies. It is validated by Brushline, not by FEMIC's rebuild-spec validator.

This split is deliberate. The FEMIC spec stays executable, and the Brushline extension stays
inspectable.

Brushline configuration
-----------------------

``config/brushline/scenario.yaml``
   Instance id, corridor selection, horizon, currency, service standards, and the targets and standards
   paths.

``config/brushline/targets.yaml``
   Target entries. The template starts empty.

``config/brushline/standards.yaml``
   Service-standard definitions. The template starts empty.

``config/brushline/rebuild.steps.yaml``
   The six provider stages: ``validate_aoi``, ``segment_corridor``, ``compile_dataset``,
   ``seed_vegetation_state``, ``validate_scenario``, and the optional ``build_demo``.

Validation
----------

.. code-block:: bash

   femic instance validate-spec --instance-root <path> --spec config/rebuild.spec.yaml
   python -m pytest tests/test_instance_template.py

The FEMIC spec is validated with FEMIC's own validator when FEMIC is installed. The Brushline spec is
checked for provider ids, unique step ids, dependency references, and required flags.

Python use
----------

.. code-block:: python

   from pathlib import Path
   from brushline.instance_template import install_instance_template

   result = install_instance_template(Path("<instance>"), force=False)
   print(len(result.written), len(result.skipped))

The installer uses ``importlib``-free package data from ``brushline/resources/instance`` and copies the
files with their directory structure.
