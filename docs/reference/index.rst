Reference
=========

This section is the technical record: contracts, method descriptions, artifact schemas, and policy
experiment results. It is not a tutorial. If you are new, read :doc:`../getting-started/index` and
:doc:`../concepts/index` first.

The pages fall into three kinds:

- **contracts** that the code validates, with schema versions and named errors;
- **method pages** that explain a model or algorithm;
- **experiment records** that report a specific prototype run and its limits.

A benchmark number is not a contract. An experiment record is not a field validation. The contract
index states which pages are authoritative for interfaces: :doc:`contract-index`.

Contracts and artifacts
-----------------------

.. toctree::
   :maxdepth: 1

   contract-index
   artifacts
   compiled-dataset
   corridor-contract
   state-contract
   synthetic-fixture
   prototype
   instance-template

Inputs, data, and integrations
------------------------------

.. toctree::
   :maxdepth: 1

   data-catalogue
   fetch-plan
   femic-boundary
   freshforge-provider
   agent-capabilities
   model-builder
   lidar-bundle
   terrain-support
   canopy-support
   state-initialization
   lidar-coverage
   lidar-benchmark

Vegetation and evidence
-----------------------

.. toctree::
   :maxdepth: 1

   state-space
   growth-model
   treatment-transitions
   treatment-calibration
   hazard-indicators
   vegetation-validation
   low-vegetation-model-card

Optimization and strategic planning
-----------------------------------

.. toctree::
   :maxdepth: 1

   optimization-formulation
   optimization-evaluator
   optimization-operators
   optimization-adapter
   optimization-archive
   optimization-validation
   optimization-budget
   optimization-telemetry
   strategic-dynamic-program
   stateful-strategic
   stateful-heuristic
   stateful-decomposition
   stateful-coordination
   strategic-portfolio
   strategic-monitoring
   strategic-bau
   strategic-reports
   strategic-scenario
   strategic-validation

Tactical, operations, and monitoring
------------------------------------

.. toctree::
   :maxdepth: 1

   tactical-program
   tactical-resources
   tactical-access
   tactical-operations
   tactical-fhops
   tactical-timeline
   tactical-validation
   shift-scheduling
   operations
   observation-model
   mission
   monitoring-value
   recalibration
   replan
   monitoring-validation

Uncertainty, policy, and decision records
-----------------------------------------

These pages report prototype policy experiments. Read the method and limits on each page before
using a number. The conceptual distinctions are in :doc:`../concepts/uncertainty-and-recourse`.

.. toctree::
   :maxdepth: 1

   uncertainty
   scenario-optimization
   planning-brief
   rolling-policy
   static-plan
   operational-stress
   operational-remedies
   risk-ranked-scope
   risk-trajectory
   rolling-recovery
   out-of-sample-recovery
   deferral-frontier
   frontier-validation
   robust-plan
   chance-plan
   chance-capacity-plan
   chance-100-plan
   two-stage
   rolling-recourse
   weather-recourse
   forecast-skill
   window-remedy
   capacity-remedy

Studio, exchange, field, and release
------------------------------------

.. toctree::
   :maxdepth: 1

   studio
   demo-portal
   plan-exchange
   verification
   field-validation
   field-comparison
   release
   release-boundary
