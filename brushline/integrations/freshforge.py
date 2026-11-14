"""FreshForge provider for the Brushline instance stages.

The provider declares six node types and runs them through the ``brushline instance`` CLI. It is
stateless: validation and planning are non-mutating, and execution only happens when FreshForge
calls ``run_node``.
"""

from __future__ import annotations

import subprocess
import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from freshforge.execution import RunContext
from freshforge.providers import NodeTypeMetadata, ProviderMetadata
from freshforge.records import (
    Diagnostic,
    DiagnosticSeverity,
    ProviderRunResult,
    RunStatus,
    WorkflowNode,
)

from brushline import __version__

BRUSHLINE_PROVIDER_ID = "brushline"
BRUSHLINE_PROVIDER_VERSION = __version__

CommandRunner = Callable[[tuple[str, ...]], subprocess.CompletedProcess[str]]


@dataclass(frozen=True)
class _NodeContract:
    id: str
    name: str
    description: str
    inputs: tuple[str, ...]
    outputs: tuple[str, ...]
    parameters: tuple[str, ...]
    artifacts: tuple[str, ...]


_NODE_CONTRACTS: tuple[_NodeContract, ...] = (
    _NodeContract(
        id="validate_aoi",
        name="Validate AOI",
        description="Validate the AOI GeoJSON and write the AOI report.",
        inputs=("aoi",),
        outputs=("aoi_validation",),
        parameters=("aoi", "out"),
        artifacts=("aoi_validation",),
    ),
    _NodeContract(
        id="segment_corridor",
        name="Segment corridor",
        description="Validate the corridor graph and write the segment table.",
        inputs=("aoi_validation",),
        outputs=("segments",),
        parameters=("corridor", "out"),
        artifacts=("segments",),
    ),
    _NodeContract(
        id="compile_dataset",
        name="Compile dataset",
        description="Compile the fixture into a validated Brushline dataset.",
        inputs=("segments",),
        outputs=("dataset",),
        parameters=("fixture", "out"),
        artifacts=("dataset_manifest",),
    ),
    _NodeContract(
        id="seed_vegetation_state",
        name="Seed vegetation state",
        description="Validate the state contract and write the seed state artifact.",
        inputs=("dataset",),
        outputs=("states",),
        parameters=("state", "out"),
        artifacts=("states",),
    ),
    _NodeContract(
        id="validate_scenario",
        name="Validate scenario",
        description="Validate the scenario and targets YAML and write the validation report.",
        inputs=("states",),
        outputs=("scenario_validation",),
        parameters=("scenario", "targets", "out"),
        artifacts=("scenario_validation",),
    ),
    _NodeContract(
        id="build_demo",
        name="Build demo",
        description="Validate the demo manifest and write the demo artifact.",
        inputs=("scenario_validation",),
        outputs=("demo",),
        parameters=("demo", "out"),
        artifacts=("demo_manifest",),
    ),
)


class BrushlineFreshForgeProvider:
    """FreshForge provider for the Brushline instance stages."""

    def __init__(self, command_runner: CommandRunner | None = None) -> None:
        self._command_runner = command_runner or _default_command_runner

    def metadata(self) -> ProviderMetadata:
        """Return the provider metadata and six node types.

        Returns
        -------
        ProviderMetadata
            Provider id, version, and node contracts.
        """
        return ProviderMetadata(
            id=BRUSHLINE_PROVIDER_ID,
            version=BRUSHLINE_PROVIDER_VERSION,
            name="Brushline instance provider",
            description="Provider for the Brushline corridor-compile and instance stages.",
            node_types=tuple(
                NodeTypeMetadata(
                    id=contract.id,
                    name=contract.name,
                    description=contract.description,
                    inputs=contract.inputs,
                    outputs=contract.outputs,
                    parameters=contract.parameters,
                    artifacts=contract.artifacts,
                )
                for contract in _NODE_CONTRACTS
            ),
        )

    def validate_node(
        self,
        node: WorkflowNode,
        node_type: NodeTypeMetadata,
        *,
        location: str,
    ) -> tuple[Diagnostic, ...]:
        """Validate one Brushline node without executing it.

        Parameters
        ----------
        node : freshforge.records.WorkflowNode
            Workflow node.
        node_type : NodeTypeMetadata
            Provider node metadata.
        location : str
            Workflow location for diagnostics.

        Returns
        -------
        tuple of Diagnostic
            Missing input, output, parameter, or artifact findings.
        """
        diagnostics: list[Diagnostic] = []
        diagnostics.extend(
            _missing_keys(
                required=node_type.inputs,
                actual=node.inputs,
                field_name="inputs",
                location=location,
            )
        )
        diagnostics.extend(
            _missing_keys(
                required=node_type.outputs,
                actual=node.outputs,
                field_name="outputs",
                location=location,
            )
        )
        diagnostics.extend(
            _missing_keys(
                required=node_type.parameters,
                actual=node.parameters,
                field_name="parameters",
                location=location,
            )
        )
        artifacts = node.artifacts if isinstance(node.artifacts, dict) else {}
        diagnostics.extend(
            _missing_keys(
                required=node_type.artifacts,
                actual=artifacts,
                field_name="artifacts",
                location=location,
            )
        )
        return tuple(diagnostics)

    def run_node(
        self,
        node: WorkflowNode,
        node_type: NodeTypeMetadata,
        *,
        context: RunContext,
    ) -> ProviderRunResult:
        """Execute one Brushline node through the Brushline CLI.

        Parameters
        ----------
        node : freshforge.records.WorkflowNode
            Workflow node.
        node_type : NodeTypeMetadata
            Provider node metadata.
        context : freshforge.execution.RunContext
            FreshForge run context.

        Returns
        -------
        ProviderRunResult
            The command result, outputs, artifacts, and diagnostics.
        """
        builder = _builders().get(str(node_type.id))
        if builder is None:
            return ProviderRunResult(
                status=RunStatus.FAILED,
                diagnostics=(
                    _diagnostic(
                        "brushline.execution.unsupported",
                        f"Brushline provider has no execution hook for node type {node_type.id!r}.",
                        f"nodes.{node.id}",
                    ),
                ),
            )
        try:
            command = builder(node, context)
        except ValueError as exc:
            return ProviderRunResult(
                status=RunStatus.FAILED,
                diagnostics=(
                    _diagnostic(
                        "brushline.execution.parameters.invalid",
                        str(exc),
                        f"nodes.{node.id}.parameters",
                    ),
                ),
            )
        completed = self._command_runner(command)
        diagnostics: tuple[Diagnostic, ...] = ()
        if completed.returncode != 0:
            diagnostics = (
                _diagnostic(
                    "brushline.execution.command.failed",
                    f"Brushline command for node {node.id!r} exited with "
                    f"return code {completed.returncode}.",
                    f"nodes.{node.id}",
                ),
            )
        data: dict[str, object] = {
            "command": list(command),
            "returncode": completed.returncode,
        }
        if completed.stdout:
            data["stdout"] = completed.stdout
        if completed.stderr:
            data["stderr"] = completed.stderr
        return ProviderRunResult(
            status=RunStatus.SUCCESS if completed.returncode == 0 else RunStatus.FAILED,
            outputs=dict(node.outputs) if isinstance(node.outputs, dict) else {},
            artifacts=_resolved_artifacts(node, context),
            diagnostics=diagnostics,
            data=data,
        )


def provider_factory() -> BrushlineFreshForgeProvider:
    """Return the Brushline provider for FreshForge entry-point discovery.

    Returns
    -------
    BrushlineFreshForgeProvider
        A stateless provider instance.
    """
    return BrushlineFreshForgeProvider()


def _builders() -> dict[str, Callable[[WorkflowNode, RunContext], tuple[str, ...]]]:
    return {
        "validate_aoi": _build_validate_aoi,
        "segment_corridor": _build_segment_corridor,
        "compile_dataset": _build_compile_dataset,
        "seed_vegetation_state": _build_seed_state,
        "validate_scenario": _build_validate_scenario,
        "build_demo": _build_demo,
    }


def _build_validate_aoi(node: WorkflowNode, context: RunContext) -> tuple[str, ...]:
    return _python_m_brushline(
        "instance",
        "validate-aoi",
        "--aoi",
        _path(node, "aoi", context),
        "--out",
        _path(node, "out", context),
    )


def _build_segment_corridor(node: WorkflowNode, context: RunContext) -> tuple[str, ...]:
    return _python_m_brushline(
        "instance",
        "segment-corridor",
        "--corridor",
        _path(node, "corridor", context),
        "--out",
        _path(node, "out", context),
    )


def _build_compile_dataset(node: WorkflowNode, context: RunContext) -> tuple[str, ...]:
    command = list(
        _python_m_brushline(
            "instance",
            "compile-dataset",
            "--fixture",
            _path(node, "fixture", context),
            "--out",
            _path(node, "out", context),
        )
    )
    if bool(node.parameters.get("force", False)):
        command.append("--force")
    return tuple(command)


def _build_seed_state(node: WorkflowNode, context: RunContext) -> tuple[str, ...]:
    return _python_m_brushline(
        "instance",
        "seed-state",
        "--state",
        _path(node, "state", context),
        "--out",
        _path(node, "out", context),
    )


def _build_validate_scenario(node: WorkflowNode, context: RunContext) -> tuple[str, ...]:
    return _python_m_brushline(
        "instance",
        "validate-scenario",
        "--scenario",
        _path(node, "scenario", context),
        "--targets",
        _path(node, "targets", context),
        "--out",
        _path(node, "out", context),
    )


def _build_demo(node: WorkflowNode, context: RunContext) -> tuple[str, ...]:
    return _python_m_brushline(
        "instance",
        "build-demo",
        "--demo",
        _path(node, "demo", context),
        "--out",
        _path(node, "out", context),
    )


def _parameter(node: WorkflowNode, name: str) -> str:
    value = node.parameters.get(name) if isinstance(node.parameters, dict) else None
    if value is None or (isinstance(value, str) and not value.strip()):
        raise ValueError(f"node parameter {name!r} is required")
    return str(value)


def _path(node: WorkflowNode, name: str, context: RunContext) -> str:
    raw = Path(_parameter(node, name))
    resolve = getattr(context, "resolve_path", None)
    if not raw.is_absolute() and callable(resolve):
        return str(resolve(raw))
    return str(raw)


def _resolved_artifacts(node: WorkflowNode, context: RunContext) -> dict[str, Any]:
    artifacts = node.artifacts if isinstance(node.artifacts, dict) else {}
    resolve = getattr(context, "resolve_path", None)
    if not callable(resolve):
        return dict(artifacts)
    resolved: dict[str, Any] = {}
    for key, value in artifacts.items():
        if isinstance(value, (str, Path)):
            resolved[key] = str(resolve(value))
        else:
            resolved[key] = value
    return resolved


def _missing_keys(
    *,
    required: Sequence[str],
    actual: object,
    field_name: str,
    location: str,
) -> list[Diagnostic]:
    present = actual if isinstance(actual, dict) else {}
    diagnostics: list[Diagnostic] = []
    for name in required:
        value = present.get(name)
        if value is None or (isinstance(value, str) and not value.strip()):
            diagnostics.append(
                _diagnostic(
                    f"brushline.validation.{field_name}.missing",
                    f"Node {field_name} is missing {name!r}.",
                    f"{location}.{field_name}",
                )
            )
    return diagnostics


def _diagnostic(code: str, message: str, location: str) -> Diagnostic:
    return Diagnostic(
        severity=DiagnosticSeverity.ERROR,
        code=code,
        message=message,
        location=location,
    )


def _python_m_brushline(*args: str) -> tuple[str, ...]:
    return (sys.executable, "-m", "brushline", *args)


def _default_command_runner(
    command: tuple[str, ...],
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        list(command),
        check=False,
        capture_output=True,
        text=True,
    )


__all__ = [
    "BRUSHLINE_PROVIDER_ID",
    "BRUSHLINE_PROVIDER_VERSION",
    "BrushlineFreshForgeProvider",
    "provider_factory",
]
