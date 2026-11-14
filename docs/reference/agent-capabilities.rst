Agent capabilities
==================

An agent capability is a bounded build step. It has a versioned prompt, a tool allowlist, a validator,
and a retry budget. The agent proposes; the validator decides. A failed validator stops the step and
keeps the evidence. It does not retry with a new assumption.

The committed registry is ``brushline.capabilities.v1``. The six core capabilities are:

.. list-table::
   :header-rows: 1
   :widths: 20 30 30 20

   * - Capability
     - Prompt
     - Tools
     - Validator
   * - ``select_aoi``
     - ``brushline.agent.select_aoi.v1``
     - ``aoi.read``, ``aoi.validate``
     - ``aoi_outcome``
   * - ``propose_fetch_plan``
     - ``brushline.agent.propose_fetch_plan.v1``
     - ``catalogue.read``, ``fetch.plan``
     - ``fetch_plan_outcome``
   * - ``seed_vegetation_state``
     - ``brushline.agent.seed_state.v1``
     - ``instance.seed_state``, ``state.validate``
     - ``state_outcome``
   * - ``compile_dataset``
     - ``brushline.agent.compile_dataset.v1``
     - ``instance.compile_dataset``, ``dataset.validate``
     - ``dataset_outcome``
   * - ``validate_scenario``
     - ``brushline.agent.validate_scenario.v1``
     - ``scenario.read``, ``scenario.validate``
     - ``scenario_outcome``
   * - ``build_demo``
     - ``brushline.agent.build_demo.v1``
     - ``demo.build``, ``demo.validate``
     - ``demo_outcome``

Every capability has a prompt version, a description, a non-empty tool allowlist, a registered
validator, and a retry budget from 0 to 2. A capability with no validator is rejected by the registry
validator and stops before a provider call.

Tools
-----

The tool registry describes what each allowlisted tool does and whether it mutates. The current tools
are read-only metadata, compiler, state, scenario, and demo steps. None reads a private row. A private
tool cannot be allowlisted.

A tool call in a provider response must be allowlisted and must end with status ``ok``. An unknown
tool, a blocked tool, or an errored tool stops the capability with ``AGENT-TOOL``.

Harness flow
------------

``run_capability`` follows a fixed order:

1. Build the request with a canonical input hash and the capability prompt.
2. Reject a private-data marker in the prompt before calling the provider.
3. Call the provider. A provider exception may retry up to the capability budget.
4. Reject an unknown, blocked, or errored tool call.
5. Reject a private-data marker in the outcome.
6. Reject an agent-authored ``authoritative``, ``coefficient``, ``geometry``, or ``validation_result``
   field.
7. Run the capability validator.
8. Record a sanitized outcome.

A validator failure is final. It does not consume the provider retry budget. A provider exception can
retry, but the record contains only the exception type, never the exception message.

Prompt and input
----------------

``build_agent_request`` hashes a canonical JSON form of the input. The request carries the prompt id,
prompt version, input hash, and tool allowlist. The default prompt tells the provider not to compute or
assert an authoritative number, coefficient, geometry, or validation result, and not to include
private rows or confidential values.

A caller can supply a prompt override for a test, but the harness still scans it. A private-data marker
in the prompt stops the run before the provider is called.

Outcome record
--------------

``CapabilityOutcome`` is the sanitized evidence record. It has:

- capability id and prompt id;
- input SHA-256 and outcome SHA-256;
- validator id and the shared validator report;
- sanitized tool calls;
- final state (``succeeded``, ``stopped``, or ``failed``);
- attempts, retry budget, stop reason, and creation time.

The record does not contain the prompt, a raw private row, or the unhashed outcome. A private marker in
a tool summary fails the record validator.

.. code-block:: python

   from datetime import UTC, datetime
   from brushline.integrations.capabilities import (
       AgentResponse,
       FakeAgentProvider,
       default_capability_registry,
       run_capability,
       validate_capability_outcome,
   )

   capability = default_capability_registry().capabilities[0]
   provider = FakeAgentProvider(
       {
           "select_aoi": [
               AgentResponse(
                   outcome={
                       "aoi_path": "aoi.geojson",
                       "feature_count": 1,
                       "source_sha256": "a" * 64,
                   }
               )
           ]
       }
   )
   result = run_capability(
       capability,
       {"aoi": "aoi.geojson"},
       provider,
       created_utc=datetime(2026, 11, 14, tzinfo=UTC),
   )
   assert result.final_state == "succeeded"
   assert validate_capability_outcome(result).is_valid

Validators
----------

The built-in validators are intentionally narrow:

- ``aoi_outcome`` checks the AOI path, a positive feature count, and the source hash.
- ``fetch_plan_outcome`` parses the P2.5 plan and runs ``validate_fetch_plan``.
- ``state_outcome`` parses the P2.3 state contract and runs ``validate_state_contract``.
- ``dataset_outcome`` parses the dataset manifest and requires a dataset path.
- ``scenario_outcome`` checks the scenario and targets schema versions and the target list.
- ``demo_outcome`` parses the demo manifest and runs ``validate_demo_manifest``.

The agent does not produce the authoritative number, coefficient, geometry, or validation result. The
validator sees the outcome and decides. A capability cannot silently skip a failing validator.

Named errors
------------

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Prefix
     - Meaning
   * - ``CAPABILITIES-*``
     - Registry problems: missing capability, prompt, tool, validator, private tool, retry budget, or
       empty registry.
   * - ``AGENT-PRIVATE``
     - A private-data marker was found in a prompt, outcome, tool summary, or record.
   * - ``AGENT-AUTHORITY``
     - An outcome contains a forbidden authoritative field.
   * - ``AGENT-TOOL``
     - A tool is not allowlisted, has an unknown status, or did not finish ``ok``.
   * - ``AGENT-PROVIDER``
     - The provider failed after the bounded retry budget.
   * - ``AGENT-VALIDATOR``
     - The capability has no registered validator, or the outcome validator failed.
   * - ``AGENT-OUTCOME``
     - The sanitized record has a bad state, hash, attempt count, evidence, or time.

What this page does not promise
-------------------------------

- It does not add a live model-provider integration. The tests use a fake provider.
- It does not approve a connector, fetch data, or bypass an owner gate.
- It does not make an agent-produced geometry, coefficient, number, or validation result authoritative.
- It does not turn a private row into prompt text, a tool summary, or an outcome record.
