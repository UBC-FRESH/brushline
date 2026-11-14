"""Tests for the Brushline FreshForge provider: metadata, validation, and command execution."""

from __future__ import annotations

import subprocess
from collections.abc import Callable
from importlib import metadata
from pathlib import Path

import pytest

pytest.importorskip("freshforge")

from brushline.integrations.freshforge import (
    BRUSHLINE_PROVIDER_ID,
    BrushlineFreshForgeProvider,
    provider_factory,
)
from freshforge.execution import RunContext
from freshforge.providers import NodeTypeMetadata
from freshforge.records import RunStatus, WorkflowNode


def _provider() -> BrushlineFreshForgeProvider:
    return BrushlineFreshForgeProvider()


def _node_type(provider: BrushlineFreshForgeProvider, node_id: str) -> NodeTypeMetadata:
    return next(item for item in provider.metadata().node_types if item.id == node_id)


def _node(
    provider: BrushlineFreshForgeProvider,
    node_id: str,
    *,
    parameters: dict[str, object],
    artifacts: dict[str, object] | None = None,
) -> WorkflowNode:
    node_type = _node_type(provider, node_id)
    return WorkflowNode(
        id=f"node-{node_id}",
        provider=f"{BRUSHLINE_PROVIDER_ID}.{node_id}",
        inputs=dict.fromkeys(node_type.inputs, True),
        outputs=dict.fromkeys(node_type.outputs, True),
        parameters=parameters,
        artifacts=artifacts
        if artifacts is not None
        else {name: f"{name}.json" for name in node_type.artifacts},
    )


def _runner(
    commands: list[tuple[str, ...]],
    returncode: int = 0,
) -> Callable[[tuple[str, ...]], subprocess.CompletedProcess[str]]:
    def run(command: tuple[str, ...]) -> subprocess.CompletedProcess[str]:
        commands.append(command)
        return subprocess.CompletedProcess(command, returncode, "ok", "")

    return run


def test_metadata_declares_the_six_nodes() -> None:
    """The provider exposes the six Brushline nodes."""
    metadata_value = _provider().metadata()
    assert metadata_value.id == BRUSHLINE_PROVIDER_ID
    ids = {node.id for node in metadata_value.node_types}
    assert ids == {
        "validate_aoi",
        "segment_corridor",
        "compile_dataset",
        "seed_vegetation_state",
        "validate_scenario",
        "build_demo",
    }
    for node in metadata_value.node_types:
        assert node.inputs
        assert node.outputs
        assert node.parameters
        assert node.artifacts


def test_validate_node_passes_with_every_key() -> None:
    """A node with every required key has no diagnostics."""
    provider = _provider()
    node = _node(provider, "validate_aoi", parameters={"aoi": "aoi.geojson", "out": "out"})
    diagnostics = provider.validate_node(
        node,
        _node_type(provider, "validate_aoi"),
        location="nodes.validate_aoi",
    )
    assert diagnostics == ()


def test_validate_node_names_missing_keys() -> None:
    """A missing input, parameter, or artifact gets a named diagnostic."""
    provider = _provider()
    node = WorkflowNode(
        id="n1",
        provider="brushline.validate_aoi",
        inputs={},
        outputs={"aoi_validation": True},
        parameters={},
        artifacts={},
    )
    diagnostics = provider.validate_node(
        node,
        _node_type(provider, "validate_aoi"),
        location="nodes.n1",
    )
    codes = {item.code for item in diagnostics}
    assert "brushline.validation.inputs.missing" in codes
    assert "brushline.validation.parameters.missing" in codes
    assert "brushline.validation.artifacts.missing" in codes


def test_run_validate_aoi_success(tmp_path: Path) -> None:
    """The validate_aoi node runs the Brushline CLI and succeeds."""
    provider = _provider()
    commands: list[tuple[str, ...]] = []
    provider = BrushlineFreshForgeProvider(_runner(commands))
    node = _node(
        provider,
        "validate_aoi",
        parameters={"aoi": "aoi.geojson", "out": "out"},
        artifacts={"aoi_validation": "out/aoi_validation.json"},
    )
    result = provider.run_node(
        node,
        _node_type(provider, "validate_aoi"),
        context=RunContext(workflow_id="wf", workdir=tmp_path),
    )
    assert result.ok
    assert result.status is RunStatus.SUCCESS
    assert commands[0][1:3] == ("-m", "brushline")
    assert "validate-aoi" in commands[0]
    assert str(tmp_path / "aoi.geojson") in commands[0]
    assert result.artifacts["aoi_validation"] == str(tmp_path / "out/aoi_validation.json")


def test_run_compile_dataset_with_force(tmp_path: Path) -> None:
    """The compile_dataset node passes --force when the parameter is true."""
    commands: list[tuple[str, ...]] = []
    provider = BrushlineFreshForgeProvider(_runner(commands))
    node = _node(
        provider,
        "compile_dataset",
        parameters={"fixture": "fixture", "out": "dataset", "force": True},
    )
    result = provider.run_node(
        node,
        _node_type(provider, "compile_dataset"),
        context=RunContext(workflow_id="wf", workdir=tmp_path),
    )
    assert result.ok
    assert "--force" in commands[0]
    assert "compile-dataset" in commands[0]


def test_run_failure_names_the_command(tmp_path: Path) -> None:
    """A non-zero command result is a failed node with a named diagnostic."""
    commands: list[tuple[str, ...]] = []
    provider = BrushlineFreshForgeProvider(_runner(commands, returncode=2))
    node = _node(
        provider,
        "segment_corridor",
        parameters={"corridor": "corridor.json", "out": "out"},
    )
    result = provider.run_node(
        node,
        _node_type(provider, "segment_corridor"),
        context=RunContext(workflow_id="wf", workdir=tmp_path),
    )
    assert not result.ok
    assert result.status is RunStatus.FAILED
    assert result.diagnostics[0].code == "brushline.execution.command.failed"
    assert result.data["returncode"] == 2


def test_unknown_node_type_is_unsupported(tmp_path: Path) -> None:
    """A node type without a builder returns a failed result, not an exception."""
    provider = _provider()
    node = WorkflowNode(id="n1", provider="brushline.unknown")
    result = provider.run_node(
        node,
        NodeTypeMetadata(id="unknown"),
        context=RunContext(workflow_id="wf", workdir=tmp_path),
    )
    assert result.status is RunStatus.FAILED
    assert result.diagnostics[0].code == "brushline.execution.unsupported"


def test_missing_parameter_is_a_failed_result(tmp_path: Path) -> None:
    """A missing node parameter returns a named failed result."""
    provider = _provider()
    node = WorkflowNode(
        id="n1",
        provider="brushline.validate_aoi",
        inputs={"aoi": True},
        outputs={"aoi_validation": True},
        parameters={},
        artifacts={"aoi_validation": "out/aoi_validation.json"},
    )
    result = provider.run_node(
        node,
        _node_type(provider, "validate_aoi"),
        context=RunContext(workflow_id="wf", workdir=tmp_path),
    )
    assert result.status is RunStatus.FAILED
    assert result.diagnostics[0].code == "brushline.execution.parameters.invalid"


def test_provider_factory_and_entry_point() -> None:
    """The factory returns the provider and the entry point is discoverable."""
    assert provider_factory().metadata().id == BRUSHLINE_PROVIDER_ID
    entries = metadata.entry_points(group="freshforge.providers")
    matching = [entry for entry in entries if entry.name == "brushline"]
    assert matching
    loaded = matching[0].load()()
    assert loaded.metadata().id == BRUSHLINE_PROVIDER_ID


def test_run_node_captures_stdout_and_stderr(tmp_path: Path) -> None:
    """The provider records command output and omits --force when it is false."""
    commands: list[tuple[str, ...]] = []

    def run(command: tuple[str, ...]) -> subprocess.CompletedProcess[str]:
        commands.append(command)
        return subprocess.CompletedProcess(command, 0, "out", "err")

    provider = BrushlineFreshForgeProvider(run)
    node = _node(
        provider,
        "compile_dataset",
        parameters={"fixture": "fixture", "out": "dataset", "force": False},
    )
    result = provider.run_node(
        node,
        _node_type(provider, "compile_dataset"),
        context=RunContext(workflow_id="wf", workdir=tmp_path),
    )
    assert result.ok
    assert result.data["stdout"] == "out"
    assert result.data["stderr"] == "err"
    assert "--force" not in commands[0]
