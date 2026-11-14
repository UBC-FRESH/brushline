"""Tests for the agent capability registry and offline harness."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import cast

import pytest
from brushline.build.compiler import compile_fixture
from brushline.integrations.capabilities import (
    BUILTIN_VALIDATORS,
    CAPABILITY_DEFINITIONS,
    TOOL_REGISTRY,
    AgentResponse,
    CapabilityDefinition,
    CapabilityOutcome,
    CapabilityRegistry,
    FakeAgentProvider,
    ToolCall,
    ToolDefinition,
    build_agent_request,
    default_capability_registry,
    run_capability,
    scan_for_authority_keys,
    scan_for_private_data,
    validate_capability_outcome,
    validate_capability_registry,
)
from brushline.integrations.catalogue import DataCatalogue
from brushline.integrations.fetch import FetchRequest, plan_fetch
from brushline.model.demo import DemoManifest
from brushline.model.state import StateContract
from pydantic import ValidationError

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "examples" / "synthetic-corridor"
CATALOGUE_PATH = ROOT / "notes" / "reference" / "data-catalogue.v1.json"
NOW = datetime(2026, 11, 14, tzinfo=UTC)


def _capability(capability_id: str) -> CapabilityDefinition:
    return next(
        capability
        for capability in default_capability_registry().capabilities
        if capability.id == capability_id
    )


def _catalogue() -> DataCatalogue:
    return DataCatalogue.model_validate_json(CATALOGUE_PATH.read_text(encoding="utf-8"))


def _aoi_outcome() -> dict[str, object]:
    return {
        "aoi_path": "aoi.geojson",
        "feature_count": 1,
        "source_sha256": "a" * 64,
    }


def _valid_outcomes(tmp_path: Path) -> dict[str, dict[str, object]]:
    plan = plan_fetch(
        _catalogue(),
        FetchRequest(aoi="aoi.geojson", source_ids=["vri"]),
        plan_id="plan-1",
        created_utc=NOW,
    )
    state = StateContract.model_validate_json((FIXTURE / "state.json").read_text(encoding="utf-8"))
    compiled = compile_fixture(FIXTURE, tmp_path / "dataset")
    demo = DemoManifest.model_validate_json((FIXTURE / "demo.json").read_text(encoding="utf-8"))
    return {
        "select_aoi": _aoi_outcome(),
        "propose_fetch_plan": {"plan": plan.model_dump(mode="json")},
        "seed_vegetation_state": {"state": state.model_dump(mode="json")},
        "compile_dataset": {
            "manifest": compiled.manifest.model_dump(mode="json"),
            "dataset_path": str(compiled.root),
        },
        "validate_scenario": {
            "scenario": {"schema_version": "brushline.scenario.v1"},
            "targets": {"schema_version": "brushline.targets.v1", "targets": []},
        },
        "build_demo": {"demo": demo.model_dump(mode="json")},
    }


def _validator_errors(result: CapabilityOutcome) -> list[str]:
    return cast("list[str]", result.validator_result.get("errors", []))


def _response(outcome: dict[str, object], capability_id: str) -> AgentResponse:
    capability = _capability(capability_id)
    return AgentResponse(
        outcome=outcome,
        tool_calls=[ToolCall(tool_id=capability.tool_allowlist[0])],
    )


def test_default_registry_has_the_six_bounded_capabilities() -> None:
    """Every capability has a prompt, tools, a validator, and a retry budget."""
    registry = default_capability_registry()
    report = validate_capability_registry(registry)
    assert report.is_valid
    assert report.counts["capabilities"] == 6
    assert report.counts["validators"] == len(BUILTIN_VALIDATORS)
    assert {capability.id for capability in registry.capabilities} == {
        "select_aoi",
        "propose_fetch_plan",
        "seed_vegetation_state",
        "compile_dataset",
        "validate_scenario",
        "build_demo",
    }
    for capability in registry.capabilities:
        assert capability.prompt_id
        assert capability.prompt_version
        assert capability.tool_allowlist
        assert capability.validator_id in BUILTIN_VALIDATORS
        assert 0 <= capability.retry_budget <= 2


def test_registry_rejects_a_missing_capability_and_a_missing_validator() -> None:
    """The six-capability set and a registered validator are required."""
    registry = default_capability_registry()
    missing = registry.model_copy(update={"capabilities": registry.capabilities[:-1]})
    missing_report = validate_capability_registry(missing)
    assert any(error.startswith("CAPABILITIES-MISSING") for error in missing_report.errors)
    no_validator = registry.capabilities[0].model_copy(update={"validator_id": "missing"})
    invalid = registry.model_copy(
        update={"capabilities": [no_validator, *registry.capabilities[1:]]}
    )
    assert any(
        error.startswith("CAPABILITIES-VALIDATOR")
        for error in validate_capability_registry(invalid).errors
    )


def test_registry_rejects_unknown_tools_duplicates_and_private_tools() -> None:
    """Unknown tools, duplicate capabilities, and private tools fail."""
    registry = default_capability_registry()
    duplicate = registry.model_copy(
        update={"capabilities": [*registry.capabilities, registry.capabilities[0]]}
    )
    assert any(
        error.startswith("CAPABILITIES-ID")
        for error in validate_capability_registry(duplicate).errors
    )
    unknown_tool = registry.capabilities[0].model_copy(update={"tool_allowlist": ["shell.exec"]})
    invalid = registry.model_copy(
        update={"capabilities": [unknown_tool, *registry.capabilities[1:]]}
    )
    assert any(
        error.startswith("CAPABILITIES-TOOLS")
        for error in validate_capability_registry(invalid).errors
    )
    private_tool = ToolDefinition(
        id="private.read",
        description="Reads private rows.",
        private_access=True,
    )
    private_capability = registry.capabilities[0].model_copy(
        update={"tool_allowlist": ["private.read"]}
    )
    private_invalid = registry.model_copy(
        update={"capabilities": [private_capability, *registry.capabilities[1:]]}
    )
    assert any(
        error.startswith("CAPABILITIES-PRIVATE")
        for error in validate_capability_registry(
            private_invalid,
            [*TOOL_REGISTRY, private_tool],
        ).errors
    )


def test_registry_warns_for_an_extra_capability_and_empty_registry() -> None:
    """An extra capability is a warning; an empty registry is a warning."""
    extra = CapabilityDefinition(
        id="extra",
        prompt_id="brushline.agent.extra.v1",
        prompt_version="v1",
        description="An extension capability.",
        tool_allowlist=["aoi.read"],
        validator_id="aoi_outcome",
        retry_budget=0,
    )
    registry = default_capability_registry().model_copy(
        update={"capabilities": [*CAPABILITY_DEFINITIONS, extra]}
    )
    report = validate_capability_registry(registry)
    assert any(warning.startswith("CAPABILITIES-EXTRA") for warning in report.warnings)
    empty_report = validate_capability_registry(CapabilityRegistry())
    assert not empty_report.is_valid
    assert any(warning.startswith("CAPABILITIES-EMPTY") for warning in empty_report.warnings)


def test_retry_budget_is_bounded_by_the_schema() -> None:
    """A retry budget outside 0 to 2 is rejected by the model."""
    with pytest.raises(ValidationError):
        CapabilityDefinition(
            id="extra",
            prompt_id="brushline.agent.extra.v1",
            prompt_version="v1",
            description="An extension capability.",
            tool_allowlist=["aoi.read"],
            validator_id="aoi_outcome",
            retry_budget=3,
        )


def test_build_agent_request_hashes_and_uses_the_allowlist() -> None:
    """A request has a stable input hash, the capability prompt, and its allowlist."""
    capability = _capability("select_aoi")
    first = build_agent_request(capability, {"aoi": "aoi.geojson"})
    second = build_agent_request(capability, {"aoi": "aoi.geojson"})
    assert first.input_sha256 == second.input_sha256
    assert len(first.input_sha256) == 64
    assert first.tool_allowlist == ["aoi.read", "aoi.validate"]
    assert "select_aoi" in first.prompt
    assert "authoritative number" in first.prompt
    assert scan_for_private_data(first.prompt) == ()
    override = build_agent_request(capability, {"aoi": "aoi.geojson"}, prompt="custom")
    assert override.prompt == "custom"


def test_all_six_capabilities_succeed_offline(tmp_path: Path) -> None:
    """The fake provider runs every capability through its real validator."""
    outcomes = _valid_outcomes(tmp_path)
    registry = default_capability_registry()
    responses = {
        capability.id: [_response(outcomes[capability.id], capability.id)]
        for capability in registry.capabilities
    }
    provider = FakeAgentProvider(responses)
    for capability in registry.capabilities:
        result = run_capability(
            capability,
            {"input": capability.id},
            provider,
            created_utc=NOW,
        )
        assert result.final_state == "succeeded", (capability.id, result.validator_result)
        assert result.attempts == 1
        assert result.outcome_sha256
        assert validate_capability_outcome(result).is_valid
    assert provider.calls == 6


def test_validator_failure_stops_without_retry() -> None:
    """A failing validator stops immediately and records the evidence."""
    capability = _capability("select_aoi")
    provider = FakeAgentProvider(
        {
            "select_aoi": [
                _response(
                    {
                        "aoi_path": "",
                        "feature_count": 0,
                        "source_sha256": "bad",
                    },
                    "select_aoi",
                )
            ]
        }
    )
    result = run_capability(capability, {"aoi": "aoi.geojson"}, provider, created_utc=NOW)
    assert result.final_state == "stopped"
    assert result.attempts == 1
    assert provider.calls == 1
    assert result.stopped_reason == "validator failed"
    assert result.validator_result["is_valid"] is False
    assert validate_capability_outcome(result).is_valid


def test_provider_retry_then_success() -> None:
    """A provider error retries up to the budget and then succeeds."""
    capability = _capability("select_aoi")
    valid = _aoi_outcome()
    provider = FakeAgentProvider(
        {
            "select_aoi": [
                TimeoutError("first attempt"),
                _response(valid, "select_aoi"),
            ]
        }
    )
    result = run_capability(capability, {"aoi": "aoi.geojson"}, provider, created_utc=NOW)
    assert result.final_state == "succeeded"
    assert result.attempts == 2
    assert provider.calls == 2


def test_provider_error_exhausts_retry_budget_and_sanitizes_the_message() -> None:
    """The final provider error records only its type, never its message."""
    capability = _capability("select_aoi")
    provider = FakeAgentProvider(
        {
            "select_aoi": [
                TimeoutError("PRIVATE-DATA should not leak"),
                TimeoutError("PRIVATE-DATA should not leak"),
            ]
        }
    )
    result = run_capability(capability, {"aoi": "aoi.geojson"}, provider, created_utc=NOW)
    assert result.final_state == "failed"
    assert result.attempts == 2
    assert "TimeoutError" in result.stopped_reason
    assert "PRIVATE-DATA" not in result.model_dump_json()
    assert result.validator_result["errors"] == ["AGENT-PROVIDER: TimeoutError"]


def test_no_scripted_response_fails_after_the_budget() -> None:
    """An empty fake-provider script fails as a provider error."""
    capability = _capability("select_aoi")
    provider = FakeAgentProvider({})
    result = run_capability(capability, {"aoi": "aoi.geojson"}, provider, created_utc=NOW)
    assert result.final_state == "failed"
    assert result.attempts == 2
    assert "KeyError" in result.stopped_reason


def test_tool_call_must_be_allowlisted_and_ok() -> None:
    """An unknown tool or a blocked tool stops the capability."""
    capability = _capability("select_aoi")
    unknown = FakeAgentProvider(
        {
            "select_aoi": [
                AgentResponse(
                    outcome=_aoi_outcome(),
                    tool_calls=[ToolCall(tool_id="shell.exec")],
                )
            ]
        }
    )
    unknown_result = run_capability(
        capability,
        {"aoi": "aoi.geojson"},
        unknown,
        created_utc=NOW,
    )
    assert unknown_result.final_state == "stopped"
    assert any(error.startswith("AGENT-TOOL") for error in _validator_errors(unknown_result))
    blocked = FakeAgentProvider(
        {
            "select_aoi": [
                AgentResponse(
                    outcome=_aoi_outcome(),
                    tool_calls=[ToolCall(tool_id="aoi.read", status="blocked")],
                )
            ]
        }
    )
    blocked_result = run_capability(
        capability,
        {"aoi": "aoi.geojson"},
        blocked,
        created_utc=NOW,
    )
    assert blocked_result.final_state == "stopped"
    assert any("ended with blocked" in error for error in _validator_errors(blocked_result))


def test_private_marker_in_prompt_stops_before_the_provider() -> None:
    """A private-data marker in the prompt fails before a provider call."""
    capability = _capability("select_aoi")
    provider = FakeAgentProvider({})
    result = run_capability(
        capability,
        {"aoi": "aoi.geojson"},
        provider,
        prompt="Please use PRIVATE-DATA from the owner.",
        created_utc=NOW,
    )
    assert result.final_state == "stopped"
    assert provider.calls == 0
    assert result.stopped_reason == "private marker in the prompt"
    assert any(error.startswith("AGENT-PRIVATE") for error in _validator_errors(result))


def test_private_marker_in_the_outcome_stops() -> None:
    """A private-data marker in an outcome fails after the call."""
    capability = _capability("select_aoi")
    provider = FakeAgentProvider(
        {
            "select_aoi": [
                AgentResponse(
                    outcome={
                        "aoi_path": "PRIVATE-DATA",
                        "feature_count": 1,
                        "source_sha256": "a" * 64,
                    }
                )
            ]
        }
    )
    result = run_capability(capability, {"aoi": "aoi.geojson"}, provider, created_utc=NOW)
    assert result.final_state == "stopped"
    assert result.stopped_reason == "private marker in the outcome"
    assert result.validator_result["errors"] == ["AGENT-PRIVATE: private marker found"]


def test_authoritative_field_stops_the_capability() -> None:
    """An agent-authored coefficient, geometry, or validation result is rejected."""
    capability = _capability("select_aoi")
    provider = FakeAgentProvider(
        {
            "select_aoi": [
                AgentResponse(
                    outcome={
                        "aoi_path": "aoi.geojson",
                        "feature_count": 1,
                        "source_sha256": "a" * 64,
                        "coefficient": 0.5,
                    }
                )
            ]
        }
    )
    result = run_capability(capability, {"aoi": "aoi.geojson"}, provider, created_utc=NOW)
    assert result.final_state == "stopped"
    assert result.stopped_reason == "outcome contains an authoritative field"
    assert result.validator_result["errors"] == [
        "AGENT-AUTHORITY: field 'coefficient' is not allowed"
    ]
    assert scan_for_authority_keys({"geometry": {}, "nested": [{"validation_result": []}]})


def test_capability_without_a_registered_validator_stops_before_the_provider() -> None:
    """A capability that names no built-in validator cannot run."""
    capability = _capability("select_aoi").model_copy(update={"validator_id": "missing"})
    provider = FakeAgentProvider({})
    result = run_capability(capability, {"aoi": "aoi.geojson"}, provider, created_utc=NOW)
    assert result.final_state == "stopped"
    assert provider.calls == 0
    assert "no registered validator" in result.stopped_reason


def test_outcome_record_validation_names_bad_fields() -> None:
    """Bad final state, hash, attempts, success evidence, reason, and tool status fail."""
    capability = _capability("select_aoi")
    provider = FakeAgentProvider({"select_aoi": [_response(_aoi_outcome(), "select_aoi")]})
    good = run_capability(capability, {"aoi": "aoi.geojson"}, provider, created_utc=NOW)
    bad = good.model_copy(
        update={
            "final_state": "maybe",
            "input_sha256": "bad",
            "outcome_sha256": "bad",
            "attempts": 9,
            "created_utc": datetime(2026, 11, 14),
            "tool_calls": [ToolCall(tool_id="aoi.read", status="maybe")],
        }
    )
    report = validate_capability_outcome(bad)
    prefixes = {error.split(":", 1)[0] for error in report.errors}
    assert "AGENT-OUTCOME" in prefixes
    failing = good.model_copy(
        update={
            "final_state": "succeeded",
            "validator_result": {"is_valid": False},
        }
    )
    assert any(
        "success has a failing validator" in error
        for error in validate_capability_outcome(failing).errors
    )
    stopped = good.model_copy(update={"final_state": "stopped", "stopped_reason": ""})
    assert any(
        "stopped or failed run has no reason" in error
        for error in validate_capability_outcome(stopped).errors
    )


def test_sanitized_record_has_no_prompt_or_raw_outcome() -> None:
    """The outcome record contains hashes, never the prompt or the raw outcome."""
    capability = _capability("select_aoi")
    outcome = {
        "aoi_path": "aoi.geojson",
        "feature_count": 1,
        "source_sha256": "a" * 64,
    }
    provider = FakeAgentProvider({"select_aoi": [_response(outcome, "select_aoi")]})
    result = run_capability(
        capability,
        {"aoi": "aoi.geojson"},
        provider,
        prompt="custom prompt with no marker",
        created_utc=NOW,
    )
    serialized = result.model_dump_json()
    assert "custom prompt" not in serialized
    assert "aoi.geojson" not in serialized
    assert result.input_sha256 in serialized
    assert result.outcome_sha256 in serialized
    assert json.loads(serialized)["capability_id"] == "select_aoi"


def test_builtin_validators_reject_missing_and_malformed_outcomes() -> None:
    """Every built-in validator has a fail path for a missing or malformed payload."""
    assert BUILTIN_VALIDATORS["aoi_outcome"]({}).errors
    assert BUILTIN_VALIDATORS["fetch_plan_outcome"]({}).errors
    assert BUILTIN_VALIDATORS["fetch_plan_outcome"]({"plan": "bad"}).errors
    assert BUILTIN_VALIDATORS["state_outcome"]({}).errors
    assert BUILTIN_VALIDATORS["state_outcome"]({"state": {"schema_version": "bad"}}).errors
    assert BUILTIN_VALIDATORS["dataset_outcome"]({}).errors
    assert BUILTIN_VALIDATORS["dataset_outcome"]({"manifest": {"schema_version": "bad"}}).errors
    assert BUILTIN_VALIDATORS["scenario_outcome"]({}).errors
    assert BUILTIN_VALIDATORS["scenario_outcome"](
        {
            "scenario": {"schema_version": "brushline.scenario.v1"},
            "targets": {"schema_version": "brushline.targets.v1", "targets": {}},
        }
    ).errors
    assert BUILTIN_VALIDATORS["demo_outcome"]({}).errors
    assert BUILTIN_VALIDATORS["demo_outcome"]({"demo": {"schema_version": "bad"}}).errors


def test_private_scan_is_case_insensitive_and_does_not_echo_the_marker() -> None:
    """The private marker scan is case-insensitive and returns a stable finding."""
    for marker in ("private-data", "PRIVATE_DATA", "Confidential Data", "private row"):
        findings = scan_for_private_data(f"prefix {marker} suffix")
        assert findings == ("AGENT-PRIVATE: private marker found",)
        assert "prefix" not in findings[0]
        assert "suffix" not in findings[0]
    assert scan_for_private_data("public metadata only") == ()


def test_registry_rejects_blank_prompt_tools_validator_and_retry_budget() -> None:
    """The registry names each missing capability field explicitly."""
    registry = default_capability_registry()
    cases = [
        ({"prompt_id": ""}, "CAPABILITIES-PROMPT"),
        ({"tool_allowlist": []}, "CAPABILITIES-TOOLS"),
        ({"validator_id": ""}, "CAPABILITIES-VALIDATOR"),
        ({"retry_budget": -1}, "CAPABILITIES-RETRY"),
    ]
    for updates, prefix in cases:
        capability = registry.capabilities[0].model_copy(
            update=updates  # type: ignore[arg-type]  # Heterogeneous test cases mirror fields.
        )
        candidate = registry.model_copy(
            update={"capabilities": [capability, *registry.capabilities[1:]]}
        )
        assert any(
            error.startswith(prefix) for error in validate_capability_registry(candidate).errors
        ), updates


def test_tool_call_with_unknown_status_stops() -> None:
    """A tool call with an unknown status fails before the outcome validator."""
    capability = _capability("select_aoi")
    provider = FakeAgentProvider(
        {
            "select_aoi": [
                AgentResponse(
                    outcome=_aoi_outcome(),
                    tool_calls=[ToolCall(tool_id="aoi.read", status="maybe")],
                )
            ]
        }
    )
    result = run_capability(capability, {"aoi": "aoi.geojson"}, provider, created_utc=NOW)
    assert result.final_state == "stopped"
    assert any("unknown status" in error for error in _validator_errors(result))


def test_outcome_record_without_tool_calls_warns() -> None:
    """A successful record with no tool calls is valid but warned."""
    capability = _capability("select_aoi")
    provider = FakeAgentProvider({"select_aoi": [AgentResponse(outcome=_aoi_outcome())]})
    result = run_capability(capability, {"aoi": "aoi.geojson"}, provider, created_utc=NOW)
    assert result.final_state == "succeeded"
    report = validate_capability_outcome(result)
    assert report.is_valid
    assert any(warning.startswith("AGENT-OUTCOME") for warning in report.warnings)


def test_fetch_plan_validator_rejects_a_malformed_plan() -> None:
    """A plan dict that fails the plan schema is reported as invalid."""
    report = BUILTIN_VALIDATORS["fetch_plan_outcome"](
        {"plan": {"schema_version": "brushline.fetch-plan.v1"}}
    )
    assert report.errors
    assert any("plan is invalid" in error for error in report.errors)


def test_dataset_validator_requires_a_path_and_tables(tmp_path: Path) -> None:
    """A valid manifest still needs a dataset path and at least one table."""
    outcome = _valid_outcomes(tmp_path)["compile_dataset"]
    missing_path = dict(outcome)
    missing_path.pop("dataset_path")
    path_report = BUILTIN_VALIDATORS["dataset_outcome"](missing_path)
    assert any("dataset_path is missing" in error for error in path_report.errors)


def test_outcome_record_scans_tool_summaries_for_private_markers(tmp_path: Path) -> None:
    """A private marker in a tool summary fails the record scan."""
    outcome = _valid_outcomes(tmp_path)
    capability = _capability("select_aoi")
    provider = FakeAgentProvider(
        {
            "select_aoi": [
                AgentResponse(
                    outcome=outcome["select_aoi"],
                    tool_calls=[
                        ToolCall(
                            tool_id="aoi.read",
                            summary="PRIVATE-DATA from the owner",
                        )
                    ],
                )
            ]
        }
    )
    result = run_capability(capability, {"aoi": "aoi.geojson"}, provider, created_utc=NOW)
    report = validate_capability_outcome(result)
    assert any(error.startswith("AGENT-PRIVATE") for error in report.errors)
