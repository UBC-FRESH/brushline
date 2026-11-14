"""Agent capability registry and offline capability harness.

A capability is a prompt id, a tool allowlist, a validator, and a bounded retry budget. The agent
cannot compute an authoritative number, coefficient, geometry, or validation result; the validator
decides. A failed validator stops the capability instead of retrying with a new assumption.

The harness is offline. It calls a provider protocol, and the committed test provider is a fake. No
live model provider is imported, configured, or contacted.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from typing import Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from brushline.integrations.fetch import FetchPlan, validate_fetch_plan
from brushline.model.demo import DemoManifest, validate_demo_manifest
from brushline.model.schema import DatasetManifest
from brushline.model.state import StateContract, validate_state_contract
from brushline.model.validation import ContractValidation, check_duplicates

CAPABILITY_SCHEMA_VERSION: Literal["brushline.capabilities.v1"] = "brushline.capabilities.v1"
CAPABILITY_OUTCOME_SCHEMA_VERSION: Literal["brushline.capability-outcome.v1"] = (
    "brushline.capability-outcome.v1"
)
CAPABILITY_IDS: tuple[str, ...] = (
    "select_aoi",
    "propose_fetch_plan",
    "seed_vegetation_state",
    "compile_dataset",
    "validate_scenario",
    "build_demo",
)
FINAL_STATES: tuple[str, ...] = ("succeeded", "stopped", "failed")
TOOL_STATES: tuple[str, ...] = ("ok", "blocked", "error")
FORBIDDEN_AUTHORITY_KEYS: tuple[str, ...] = (
    "authoritative",
    "coefficient",
    "geometry",
    "validation_result",
)
PRIVATE_DATA_PATTERN: re.Pattern[str] = re.compile(
    r"\b(?:PRIVATE[ _-]?DATA|CONFIDENTIAL[ _-]?DATA|PRIVATE ROW)\b",
    re.IGNORECASE,
)
SHA256_PATTERN: re.Pattern[str] = re.compile(r"^[0-9a-f]{64}$")


class ToolDefinition(BaseModel):
    """One tool that a capability may use.

    Parameters
    ----------
    id : str
        Stable tool identifier.
    description : str
        What the tool does.
    mutating : bool, optional
        Whether the tool writes an artifact. Defaults to ``False``.
    private_access : bool, optional
        Whether the tool reads private rows. Defaults to ``False``.
    approval_required : bool, optional
        Whether the tool needs an owner approval. Defaults to ``False``.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str = Field(min_length=1)
    description: str = Field(min_length=1)
    mutating: bool = False
    private_access: bool = False
    approval_required: bool = False


TOOL_REGISTRY: tuple[ToolDefinition, ...] = (
    ToolDefinition(id="aoi.read", description="Read an AOI GeoJSON in the approved workspace."),
    ToolDefinition(id="aoi.validate", description="Validate an AOI through the shared validator."),
    ToolDefinition(
        id="catalogue.read",
        description="Read public source and connector metadata; never private rows.",
    ),
    ToolDefinition(id="fetch.plan", description="Build the plan-only fetch preview."),
    ToolDefinition(
        id="instance.seed_state",
        description="Validate and write the seed vegetation-state artifact.",
        mutating=True,
    ),
    ToolDefinition(id="state.validate", description="Validate a state contract."),
    ToolDefinition(
        id="instance.compile_dataset",
        description="Compile the fixture into a validated dataset.",
        mutating=True,
    ),
    ToolDefinition(id="dataset.validate", description="Validate a compiled dataset."),
    ToolDefinition(id="scenario.read", description="Read scenario and targets YAML."),
    ToolDefinition(id="scenario.validate", description="Validate scenario and targets YAML."),
    ToolDefinition(
        id="demo.build",
        description="Write the demo manifest artifact.",
        mutating=True,
    ),
    ToolDefinition(id="demo.validate", description="Validate the demo manifest."),
)


class CapabilityDefinition(BaseModel):
    """One agent-facing build capability.

    Parameters
    ----------
    id : str
        Capability id, one of the six build steps.
    prompt_id : str
        Versioned prompt identifier.
    prompt_version : str
        Prompt version label.
    description : str
        What the capability does and does not do.
    tool_allowlist : list of str
        Tools the capability may call.
    validator_id : str
        Built-in outcome validator id.
    retry_budget : int, optional
        Maximum provider retries from 0 to 2. Defaults to ``1``.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str = Field(min_length=1)
    prompt_id: str = Field(min_length=1)
    prompt_version: str = Field(min_length=1)
    description: str = Field(min_length=1)
    tool_allowlist: list[str] = Field(min_length=1)
    validator_id: str = Field(min_length=1)
    retry_budget: int = Field(default=1, ge=0, le=2)


class CapabilityRegistry(BaseModel):
    """The versioned capability registry.

    Parameters
    ----------
    schema_version : {"brushline.capabilities.v1"}
        Registry schema version.
    capabilities : list of CapabilityDefinition
        Capability definitions.
    """

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["brushline.capabilities.v1"] = CAPABILITY_SCHEMA_VERSION
    capabilities: list[CapabilityDefinition] = Field(default_factory=list)


class ToolCall(BaseModel):
    """A sanitized tool call in a provider response.

    Parameters
    ----------
    tool_id : str
        Tool identifier.
    status : str, optional
        ``ok``, ``blocked``, or ``error``.
    summary : str, optional
        Short non-private summary.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    tool_id: str = Field(min_length=1)
    status: str = "ok"
    summary: str = ""


class AgentRequest(BaseModel):
    """The bounded request sent to a provider.

    Parameters
    ----------
    capability_id : str
        Capability id.
    prompt_id : str
        Versioned prompt id.
    prompt_version : str
        Prompt version.
    prompt : str
        Sanitized prompt text.
    input_sha256 : str
        SHA-256 of the canonical capability input.
    tool_allowlist : list of str
        Tools the provider may use.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    capability_id: str = Field(min_length=1)
    prompt_id: str = Field(min_length=1)
    prompt_version: str = Field(min_length=1)
    prompt: str = Field(min_length=1)
    input_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    tool_allowlist: list[str] = Field(min_length=1)


class AgentResponse(BaseModel):
    """A provider response with an outcome and sanitized tool calls.

    Parameters
    ----------
    outcome : dict of str to object
        Capability outcome for the validator.
    tool_calls : list of ToolCall, optional
        Tool calls that produced the outcome.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    outcome: dict[str, object] = Field(default_factory=dict)
    tool_calls: list[ToolCall] = Field(default_factory=list)


class AgentProvider(Protocol):
    """The provider protocol used by the offline harness."""

    def complete(self, request: AgentRequest) -> AgentResponse:
        """Return one response for a bounded request.

        Parameters
        ----------
        request : AgentRequest
            Capability request.

        Returns
        -------
        AgentResponse
            Outcome and tool calls.
        """
        ...


class FakeAgentProvider:
    """A scripted provider for offline tests.

    Parameters
    ----------
    responses : mapping of str to sequence of AgentResponse or Exception
        One scripted sequence per capability. Each call consumes the next item. A sequence that runs
        out raises ``KeyError``.
    """

    def __init__(
        self,
        responses: Mapping[str, Sequence[AgentResponse | Exception]],
    ) -> None:
        self._responses = {key: list(value) for key, value in responses.items()}
        self._positions: dict[str, int] = {}
        self.requests: list[AgentRequest] = []

    @property
    def calls(self) -> int:
        """Return the number of provider calls.

        Returns
        -------
        int
            Call count.
        """
        return len(self.requests)

    def complete(self, request: AgentRequest) -> AgentResponse:
        """Return the next scripted response.

        Parameters
        ----------
        request : AgentRequest
            Capability request.

        Returns
        -------
        AgentResponse
            Scripted response.

        Raises
        ------
        KeyError
            When the capability has no scripted response left.
        """
        self.requests.append(request)
        position = self._positions.get(request.capability_id, 0)
        items = self._responses.get(request.capability_id, [])
        if position >= len(items):
            raise KeyError(f"no scripted response for {request.capability_id}")
        self._positions[request.capability_id] = position + 1
        item = items[position]
        if isinstance(item, Exception):
            raise item
        return item


class CapabilityOutcome(BaseModel):
    """A sanitized record of one capability run.

    Parameters
    ----------
    schema_version : {"brushline.capability-outcome.v1"}
        Record schema version.
    capability_id : str
        Capability id.
    prompt_id : str
        Prompt id.
    input_sha256 : str
        SHA-256 of the canonical input.
    outcome_sha256 : str
        SHA-256 of the provider outcome, or an empty string before a response.
    validator_id : str
        Validator id.
    validator_result : dict of str to object
        Shared contract-validation report.
    tool_calls : list of ToolCall
        Sanitized tool calls.
    final_state : str
        ``succeeded``, ``stopped``, or ``failed``.
    attempts : int
        Provider attempts used.
    retry_budget : int
        Capability retry budget.
    stopped_reason : str
        Why a stopped or failed run ended.
    created_utc : datetime
        Timezone-aware creation time.
    """

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["brushline.capability-outcome.v1"] = CAPABILITY_OUTCOME_SCHEMA_VERSION
    capability_id: str = Field(min_length=1)
    prompt_id: str = Field(min_length=1)
    input_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    outcome_sha256: str = ""
    validator_id: str = Field(min_length=1)
    validator_result: dict[str, object]
    tool_calls: list[ToolCall] = Field(default_factory=list)
    final_state: str
    attempts: int = Field(ge=1)
    retry_budget: int = Field(ge=0, le=2)
    stopped_reason: str = ""
    created_utc: datetime


CAPABILITY_DEFINITIONS: tuple[CapabilityDefinition, ...] = (
    CapabilityDefinition(
        id="select_aoi",
        prompt_id="brushline.agent.select_aoi.v1",
        prompt_version="v1",
        description="Select and validate the AOI; never invent a geometry.",
        tool_allowlist=["aoi.read", "aoi.validate"],
        validator_id="aoi_outcome",
        retry_budget=1,
    ),
    CapabilityDefinition(
        id="propose_fetch_plan",
        prompt_id="brushline.agent.propose_fetch_plan.v1",
        prompt_version="v1",
        description="Propose the plan-only fetch and its gaps; never fetch.",
        tool_allowlist=["catalogue.read", "fetch.plan"],
        validator_id="fetch_plan_outcome",
        retry_budget=1,
    ),
    CapabilityDefinition(
        id="seed_vegetation_state",
        prompt_id="brushline.agent.seed_state.v1",
        prompt_version="v1",
        description="Seed the vegetation state from evidence; never invent observations.",
        tool_allowlist=["instance.seed_state", "state.validate"],
        validator_id="state_outcome",
        retry_budget=1,
    ),
    CapabilityDefinition(
        id="compile_dataset",
        prompt_id="brushline.agent.compile_dataset.v1",
        prompt_version="v1",
        description="Compile the dataset through the shared compiler and validator.",
        tool_allowlist=["instance.compile_dataset", "dataset.validate"],
        validator_id="dataset_outcome",
        retry_budget=1,
    ),
    CapabilityDefinition(
        id="validate_scenario",
        prompt_id="brushline.agent.validate_scenario.v1",
        prompt_version="v1",
        description="Validate the scenario and targets; never invent a target.",
        tool_allowlist=["scenario.read", "scenario.validate"],
        validator_id="scenario_outcome",
        retry_budget=1,
    ),
    CapabilityDefinition(
        id="build_demo",
        prompt_id="brushline.agent.build_demo.v1",
        prompt_version="v1",
        description="Build the reviewable demo manifest; never publish.",
        tool_allowlist=["demo.build", "demo.validate"],
        validator_id="demo_outcome",
        retry_budget=1,
    ),
)


def default_capability_registry() -> CapabilityRegistry:
    """Return the six-capability registry.

    Returns
    -------
    CapabilityRegistry
        Default registry.
    """
    return CapabilityRegistry(capabilities=list(CAPABILITY_DEFINITIONS))


def validate_capability_registry(
    registry: CapabilityRegistry,
    tools: Sequence[ToolDefinition] = TOOL_REGISTRY,
) -> ContractValidation:
    """Validate capabilities, prompts, tools, validators, and retry budgets.

    Parameters
    ----------
    registry : CapabilityRegistry
        Registry to validate.
    tools : sequence of ToolDefinition, optional
        Known tool registry.

    Returns
    -------
    ContractValidation
        Errors, warnings, and counts.
    """
    errors: list[str] = []
    warnings: list[str] = []
    check_duplicates(
        "CAPABILITIES",
        "capability",
        [capability.id for capability in registry.capabilities],
        errors,
    )
    check_duplicates(
        "CAPABILITIES",
        "prompt",
        [capability.prompt_id for capability in registry.capabilities],
        errors,
    )
    known_tools = {tool.id: tool for tool in tools}
    known_validators = set(BUILTIN_VALIDATORS)
    present = {capability.id for capability in registry.capabilities}
    for capability_id in CAPABILITY_IDS:
        if capability_id not in present:
            errors.append(f"CAPABILITIES-MISSING: capability {capability_id} is not registered")
    for capability in registry.capabilities:
        if capability.id not in CAPABILITY_IDS:
            warnings.append(
                f"CAPABILITIES-EXTRA: capability {capability.id} is not in the core six"
            )
        if not capability.prompt_id.strip() or not capability.prompt_version.strip():
            errors.append(
                f"CAPABILITIES-PROMPT: capability {capability.id} has no prompt id or version"
            )
        if not capability.tool_allowlist:
            errors.append(f"CAPABILITIES-TOOLS: capability {capability.id} has no tools")
        for tool_id in capability.tool_allowlist:
            tool = known_tools.get(tool_id)
            if tool is None:
                errors.append(
                    f"CAPABILITIES-TOOLS: capability {capability.id} allowlists unknown tool "
                    f"{tool_id}"
                )
            elif tool.private_access:
                errors.append(
                    f"CAPABILITIES-PRIVATE: capability {capability.id} allowlists private "
                    f"tool {tool_id}"
                )
        if not capability.validator_id.strip():
            errors.append(f"CAPABILITIES-VALIDATOR: capability {capability.id} has no validator")
        elif capability.validator_id not in known_validators:
            errors.append(
                f"CAPABILITIES-VALIDATOR: capability {capability.id} names unknown validator "
                f"{capability.validator_id}"
            )
        if not 0 <= capability.retry_budget <= 2:
            errors.append(
                f"CAPABILITIES-RETRY: capability {capability.id} retry budget is outside 0 to 2"
            )
    if not registry.capabilities:
        warnings.append("CAPABILITIES-EMPTY: the registry has no capabilities")
    counts: dict[str, int | float] = {
        "capabilities": len(registry.capabilities),
        "tools": len(tools),
        "validators": len(BUILTIN_VALIDATORS),
    }
    return ContractValidation(tuple(errors), tuple(warnings), counts)


def build_agent_request(
    capability: CapabilityDefinition,
    capability_input: Mapping[str, object],
    *,
    prompt: str | None = None,
) -> AgentRequest:
    """Build a bounded request without calling a provider.

    Parameters
    ----------
    capability : CapabilityDefinition
        Capability to invoke.
    capability_input : mapping of str to object
        Non-private input. It is hashed and included in the prompt when ``prompt`` is omitted.
    prompt : str, optional
        Prompt override. It is still scanned by :func:`run_capability`.

    Returns
    -------
    AgentRequest
        Request with a stable input hash and the capability tool allowlist.
    """
    canonical = json.dumps(capability_input, sort_keys=True, default=str).encode("utf-8")
    prompt_text = prompt or _default_prompt(capability, capability_input)
    return AgentRequest(
        capability_id=capability.id,
        prompt_id=capability.prompt_id,
        prompt_version=capability.prompt_version,
        prompt=prompt_text,
        input_sha256=hashlib.sha256(canonical).hexdigest(),
        tool_allowlist=list(capability.tool_allowlist),
    )


def run_capability(
    capability: CapabilityDefinition,
    capability_input: Mapping[str, object],
    provider: AgentProvider,
    *,
    prompt: str | None = None,
    created_utc: datetime | None = None,
) -> CapabilityOutcome:
    """Run one capability with a validator, a retry budget, and sanitized evidence.

    A provider error may retry up to the capability budget. A validator failure, a private-data
    marker, an unknown tool, or an authoritative field stops immediately and is recorded.

    Parameters
    ----------
    capability : CapabilityDefinition
        Capability definition.
    capability_input : mapping of str to object
        Non-private input.
    provider : AgentProvider
        Provider, normally a :class:`FakeAgentProvider` in tests.
    prompt : str, optional
        Prompt override.
    created_utc : datetime, optional
        Creation time. Defaults to the current UTC time.

    Returns
    -------
    CapabilityOutcome
        Sanitized record with the validator result and final state.
    """
    now = created_utc or datetime.now(UTC)
    request = build_agent_request(capability, capability_input, prompt=prompt)
    if capability.validator_id not in BUILTIN_VALIDATORS:
        return _record(
            capability,
            request,
            final_state="stopped",
            stopped_reason="capability has no registered validator",
            validator=ContractValidation(
                (f"AGENT-VALIDATOR: {capability.validator_id!r} is not registered",),
                (),
                {},
            ),
            attempts=1,
            now=now,
        )
    private = scan_for_private_data(request.prompt)
    if private:
        return _record(
            capability,
            request,
            final_state="stopped",
            stopped_reason="private marker in the prompt",
            validator=ContractValidation(private, (), {}),
            attempts=1,
            now=now,
        )
    attempts = 0
    response: AgentResponse | None = None
    while True:
        attempts += 1
        try:
            response = provider.complete(request)
            break
        except Exception as exc:  # Provider errors are sanitized to their type.
            if attempts > capability.retry_budget:
                return _record(
                    capability,
                    request,
                    final_state="failed",
                    stopped_reason=(
                        f"provider error after {attempts} attempt(s): {type(exc).__name__}"
                    ),
                    validator=ContractValidation(
                        (f"AGENT-PROVIDER: {type(exc).__name__}",),
                        (),
                        {},
                    ),
                    attempts=attempts,
                    now=now,
                )
    assert response is not None
    tool_error = _tool_call_errors(capability, response.tool_calls)
    if tool_error:
        return _record(
            capability,
            request,
            final_state="stopped",
            stopped_reason="tool call is not allowed",
            validator=ContractValidation(tool_error, (), {}),
            attempts=attempts,
            tool_calls=response.tool_calls,
            now=now,
        )
    serialized_outcome = json.dumps(response.outcome, sort_keys=True, default=str)
    private = scan_for_private_data(serialized_outcome)
    if private:
        return _record(
            capability,
            request,
            final_state="stopped",
            stopped_reason="private marker in the outcome",
            validator=ContractValidation(private, (), {}),
            attempts=attempts,
            tool_calls=response.tool_calls,
            now=now,
        )
    authority = scan_for_authority_keys(response.outcome)
    if authority:
        return _record(
            capability,
            request,
            final_state="stopped",
            stopped_reason="outcome contains an authoritative field",
            validator=ContractValidation(authority, (), {}),
            attempts=attempts,
            tool_calls=response.tool_calls,
            now=now,
        )
    validation = BUILTIN_VALIDATORS[capability.validator_id](response.outcome)
    final_state = "succeeded" if validation.is_valid else "stopped"
    return _record(
        capability,
        request,
        final_state=final_state,
        stopped_reason="" if validation.is_valid else "validator failed",
        validator=validation,
        attempts=attempts,
        tool_calls=response.tool_calls,
        outcome=response.outcome,
        now=now,
    )


def scan_for_private_data(text: str) -> tuple[str, ...]:
    """Scan a prompt or outcome for an explicit private-data marker.

    Parameters
    ----------
    text : str
        Text to scan.

    Returns
    -------
    tuple of str
        ``AGENT-PRIVATE`` findings. The marker value is never echoed.
    """
    if PRIVATE_DATA_PATTERN.search(text):
        return ("AGENT-PRIVATE: private marker found",)
    return ()


def scan_for_authority_keys(value: object) -> tuple[str, ...]:
    """Scan an outcome for keys that claim an authoritative agent result.

    Parameters
    ----------
    value : object
        Outcome value, usually a mapping.

    Returns
    -------
    tuple of str
        ``AGENT-AUTHORITY`` findings.
    """
    findings: list[str] = []

    def visit(current: object) -> None:
        if isinstance(current, dict):
            for key, child in current.items():
                if str(key).casefold() in FORBIDDEN_AUTHORITY_KEYS:
                    findings.append(f"AGENT-AUTHORITY: field {str(key)!r} is not allowed")
                visit(child)
        elif isinstance(current, list):
            for child in current:
                visit(child)

    visit(value)
    return tuple(dict.fromkeys(findings))


def validate_capability_outcome(outcome: CapabilityOutcome) -> ContractValidation:
    """Validate the sanitized outcome record.

    Parameters
    ----------
    outcome : CapabilityOutcome
        Record to validate.

    Returns
    -------
    ContractValidation
        Errors, warnings, and counts.
    """
    errors: list[str] = []
    warnings: list[str] = []
    if outcome.final_state not in FINAL_STATES:
        errors.append(f"AGENT-OUTCOME: unknown final state {outcome.final_state!r}")
    if outcome.created_utc.tzinfo is None:
        errors.append("AGENT-OUTCOME: created_utc is not timezone-aware")
    if not SHA256_PATTERN.fullmatch(outcome.input_sha256):
        errors.append("AGENT-OUTCOME: input_sha256 is invalid")
    if outcome.outcome_sha256 and not SHA256_PATTERN.fullmatch(outcome.outcome_sha256):
        errors.append("AGENT-OUTCOME: outcome_sha256 is invalid")
    if outcome.attempts < 1 or outcome.attempts > outcome.retry_budget + 1:
        errors.append("AGENT-OUTCOME: attempts are outside the retry budget")
    if outcome.final_state == "succeeded":
        if not bool(outcome.validator_result.get("is_valid")):
            errors.append("AGENT-OUTCOME: success has a failing validator result")
    elif not outcome.stopped_reason.strip():
        errors.append("AGENT-OUTCOME: stopped or failed run has no reason")
    for call in outcome.tool_calls:
        if call.status not in TOOL_STATES:
            errors.append(f"AGENT-OUTCOME: tool {call.tool_id} has unknown status")
    private = scan_for_private_data(outcome.model_dump_json())
    errors.extend(private)
    if not outcome.tool_calls:
        warnings.append("AGENT-OUTCOME: the record has no tool calls")
    counts: dict[str, int | float] = {
        "tool_calls": len(outcome.tool_calls),
        "attempts": outcome.attempts,
        "retry_budget": outcome.retry_budget,
    }
    return ContractValidation(tuple(errors), tuple(warnings), counts)


def _default_prompt(
    capability: CapabilityDefinition,
    capability_input: Mapping[str, object],
) -> str:
    payload = json.dumps(capability_input, indent=2, sort_keys=True, default=str)
    tools = ", ".join(capability.tool_allowlist)
    return (
        "You are a bounded Brushline build capability.\n"
        f"Capability: {capability.id}\n"
        f"Prompt: {capability.prompt_id} ({capability.prompt_version})\n"
        f"Allowed tools: {tools}\n"
        "Do not compute or assert an authoritative number, coefficient, geometry, or "
        "validation result. Return evidence references and let the validator decide.\n"
        "Do not include private rows or confidential values.\n"
        "Input:\n"
        f"{payload}\n"
    )


def _tool_call_errors(
    capability: CapabilityDefinition,
    tool_calls: Sequence[ToolCall],
) -> tuple[str, ...]:
    errors: list[str] = []
    for call in tool_calls:
        if call.tool_id not in capability.tool_allowlist:
            errors.append(
                f"AGENT-TOOL: tool {call.tool_id} is not in the allowlist for {capability.id}"
            )
        if call.status not in TOOL_STATES:
            errors.append(f"AGENT-TOOL: tool {call.tool_id} has unknown status")
        elif call.status != "ok":
            errors.append(f"AGENT-TOOL: tool {call.tool_id} ended with {call.status}")
    return tuple(dict.fromkeys(errors))


def _record(
    capability: CapabilityDefinition,
    request: AgentRequest,
    *,
    final_state: str,
    stopped_reason: str,
    validator: ContractValidation,
    attempts: int,
    now: datetime,
    tool_calls: Sequence[ToolCall] = (),
    outcome: Mapping[str, object] | None = None,
) -> CapabilityOutcome:
    outcome_sha256 = ""
    if outcome is not None:
        canonical = json.dumps(outcome, sort_keys=True, default=str).encode("utf-8")
        outcome_sha256 = hashlib.sha256(canonical).hexdigest()
    return CapabilityOutcome(
        capability_id=capability.id,
        prompt_id=capability.prompt_id,
        input_sha256=request.input_sha256,
        outcome_sha256=outcome_sha256,
        validator_id=capability.validator_id,
        validator_result=validator.to_dict(),
        tool_calls=list(tool_calls),
        final_state=final_state,
        attempts=attempts,
        retry_budget=capability.retry_budget,
        stopped_reason=stopped_reason,
        created_utc=now,
    )


def _validate_aoi_outcome(outcome: Mapping[str, object]) -> ContractValidation:
    errors: list[str] = []
    features = outcome.get("feature_count")
    if not isinstance(outcome.get("aoi_path"), str) or not str(outcome["aoi_path"]).strip():
        errors.append("AGENT-VALIDATOR: aoi_path is missing")
    if not isinstance(features, int) or features <= 0:
        errors.append("AGENT-VALIDATOR: feature_count must be a positive integer")
    digest = outcome.get("source_sha256")
    if not isinstance(digest, str) or not SHA256_PATTERN.fullmatch(digest):
        errors.append("AGENT-VALIDATOR: source_sha256 is invalid")
    return ContractValidation(
        tuple(errors), (), {"features": features if isinstance(features, int) else 0}
    )


def _validate_fetch_plan_outcome(outcome: Mapping[str, object]) -> ContractValidation:
    raw = outcome.get("plan")
    if not isinstance(raw, dict):
        return ContractValidation(("AGENT-VALIDATOR: plan is missing",), (), {})
    try:
        plan = FetchPlan.model_validate(raw)
    except ValidationError as exc:
        return ContractValidation((f"AGENT-VALIDATOR: plan is invalid: {exc}",), (), {})
    report = validate_fetch_plan(plan)
    return ContractValidation(report.errors, report.warnings, report.counts)


def _validate_state_outcome(outcome: Mapping[str, object]) -> ContractValidation:
    raw = outcome.get("state")
    if not isinstance(raw, dict):
        return ContractValidation(("AGENT-VALIDATOR: state is missing",), (), {})
    try:
        contract = StateContract.model_validate(raw)
    except ValidationError as exc:
        return ContractValidation((f"AGENT-VALIDATOR: state is invalid: {exc}",), (), {})
    report = validate_state_contract(contract)
    counts: dict[str, int | float] = {}
    counts.update(report.counts)
    return ContractValidation(report.errors, report.warnings, counts)


def _validate_dataset_outcome(outcome: Mapping[str, object]) -> ContractValidation:
    raw = outcome.get("manifest")
    if not isinstance(raw, dict):
        return ContractValidation(("AGENT-VALIDATOR: manifest is missing",), (), {})
    try:
        manifest = DatasetManifest.model_validate(raw)
    except ValidationError as exc:
        return ContractValidation((f"AGENT-VALIDATOR: manifest is invalid: {exc}",), (), {})
    errors: list[str] = []
    if not isinstance(outcome.get("dataset_path"), str) or not str(outcome["dataset_path"]).strip():
        errors.append("AGENT-VALIDATOR: dataset_path is missing")
    return ContractValidation(tuple(errors), (), {"tables": len(manifest.tables)})


def _validate_scenario_outcome(outcome: Mapping[str, object]) -> ContractValidation:
    errors: list[str] = []
    scenario = outcome.get("scenario")
    targets = outcome.get("targets")
    if not isinstance(scenario, dict) or scenario.get("schema_version") != "brushline.scenario.v1":
        errors.append("AGENT-VALIDATOR: scenario schema_version is invalid")
    if not isinstance(targets, dict) or targets.get("schema_version") != "brushline.targets.v1":
        errors.append("AGENT-VALIDATOR: targets schema_version is invalid")
    elif not isinstance(targets.get("targets"), list):
        errors.append("AGENT-VALIDATOR: targets must be a list")
    return ContractValidation(tuple(errors), (), {})


def _validate_demo_outcome(outcome: Mapping[str, object]) -> ContractValidation:
    raw = outcome.get("demo")
    if not isinstance(raw, dict):
        return ContractValidation(("AGENT-VALIDATOR: demo is missing",), (), {})
    try:
        demo = DemoManifest.model_validate(raw)
    except ValidationError as exc:
        return ContractValidation((f"AGENT-VALIDATOR: demo is invalid: {exc}",), (), {})
    report = validate_demo_manifest(demo)
    return ContractValidation(report.errors, report.warnings, report.counts)


BUILTIN_VALIDATORS = {
    "aoi_outcome": _validate_aoi_outcome,
    "fetch_plan_outcome": _validate_fetch_plan_outcome,
    "state_outcome": _validate_state_outcome,
    "dataset_outcome": _validate_dataset_outcome,
    "scenario_outcome": _validate_scenario_outcome,
    "demo_outcome": _validate_demo_outcome,
}


__all__ = [
    "BUILTIN_VALIDATORS",
    "CAPABILITY_DEFINITIONS",
    "CAPABILITY_IDS",
    "CAPABILITY_OUTCOME_SCHEMA_VERSION",
    "CAPABILITY_SCHEMA_VERSION",
    "FINAL_STATES",
    "FORBIDDEN_AUTHORITY_KEYS",
    "TOOL_REGISTRY",
    "AgentProvider",
    "AgentRequest",
    "AgentResponse",
    "CapabilityDefinition",
    "CapabilityOutcome",
    "CapabilityRegistry",
    "FakeAgentProvider",
    "ToolCall",
    "ToolDefinition",
    "build_agent_request",
    "default_capability_registry",
    "run_capability",
    "scan_for_authority_keys",
    "scan_for_private_data",
    "validate_capability_outcome",
    "validate_capability_registry",
]
