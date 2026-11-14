"""Tests for the Brushline instance template and the two rebuild specs."""

from __future__ import annotations

import re
from pathlib import Path
from typing import cast

import pytest
import yaml
from brushline.cli import app
from brushline.instance_template import TEMPLATE_ROOT, install_instance_template
from typer.testing import CliRunner

RUNNER = CliRunner()
EXPECTED_PROVIDERS = {
    "brushline.validate_aoi",
    "brushline.segment_corridor",
    "brushline.compile_dataset",
    "brushline.seed_vegetation_state",
    "brushline.validate_scenario",
    "brushline.build_demo",
}


def _yaml(path: Path) -> dict[str, object]:
    value = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} is not a YAML mapping")
    return cast("dict[str, object]", value)


def _stages() -> list[dict[str, object]]:
    payload = _yaml(TEMPLATE_ROOT / "config" / "brushline" / "rebuild.steps.yaml")
    return cast("list[dict[str, object]]", payload["stages"])


def test_template_installs_every_file(tmp_path: Path) -> None:
    """The template writes the expected overlay and skips the package marker."""
    result = install_instance_template(tmp_path / "instance")
    expected = {
        "README.md",
        "QUICKSTART.md",
        "config/rebuild.spec.yaml",
        "config/rebuild.allowlist.yaml",
        "config/brushline/scenario.yaml",
        "config/brushline/targets.yaml",
        "config/brushline/standards.yaml",
        "config/brushline/rebuild.steps.yaml",
        "runbooks/REBUILD_RUNBOOK.md",
        "evidence/README.md",
        "tests/README.md",
    }
    written = {path.relative_to(result.root).as_posix() for path in result.written}
    assert written == expected
    assert not (result.root / "__init__.py").exists()
    assert result.skipped == ()


def test_second_install_skips_and_force_overwrites(tmp_path: Path) -> None:
    """An existing file is skipped without force and overwritten with force."""
    root = tmp_path / "instance"
    install_instance_template(root)
    readme = root / "README.md"
    readme.write_text("custom\n", encoding="utf-8")
    second = install_instance_template(root)
    assert second.written == ()
    assert readme.read_text(encoding="utf-8") == "custom\n"
    forced = install_instance_template(root, force=True)
    assert forced.skipped == ()
    assert readme.read_text(encoding="utf-8").startswith("# Brushline instance template")


def test_install_preserves_other_instance_files(tmp_path: Path) -> None:
    """The overlay leaves files it does not own untouched."""
    root = tmp_path / "instance"
    root.mkdir()
    (root / "config").mkdir()
    (root / "config" / "run_profile.case_template.yaml").write_text(
        "selection: {}\n",
        encoding="utf-8",
    )
    install_instance_template(root, force=True)
    assert (root / "config" / "run_profile.case_template.yaml").is_file()


def test_femic_rebuild_spec_validates() -> None:
    """The FEMIC-compatible rebuild spec passes FEMIC's own validator."""
    module = pytest.importorskip("femic.rebuild_spec")
    spec = _yaml(TEMPLATE_ROOT / "config" / "rebuild.spec.yaml")
    validate = module.validate_rebuild_spec_payload
    errors = validate(spec)
    assert errors == []
    assert spec["schema_version"] == "1.0"
    instance = cast("dict[str, object]", spec["instance"])
    assert instance["case_id"]


def test_brushline_extension_spec_is_complete() -> None:
    """The extension spec declares the six providers with valid dependencies."""
    payload = _yaml(TEMPLATE_ROOT / "config" / "brushline" / "rebuild.steps.yaml")
    assert payload["schema_version"] == "brushline.instance.rebuild.v1"
    stages = _stages()
    providers = {stage["provider"] for stage in stages}
    assert providers == EXPECTED_PROVIDERS
    step_ids = {str(stage["step_id"]) for stage in stages}
    assert len(step_ids) == len(stages)
    external = {"geospatial_preflight"}
    for stage in stages:
        assert isinstance(stage["required"], bool)
        for dependency in cast("list[str]", stage["depends_on"]):
            assert dependency in step_ids | external


def test_config_templates_parse() -> None:
    """The scenario, targets, and standards templates carry their schema version."""
    assert (
        _yaml(TEMPLATE_ROOT / "config" / "brushline" / "scenario.yaml")["schema_version"]
        == "brushline.scenario.v1"
    )
    assert (
        _yaml(TEMPLATE_ROOT / "config" / "brushline" / "targets.yaml")["schema_version"]
        == "brushline.targets.v1"
    )
    assert (
        _yaml(TEMPLATE_ROOT / "config" / "brushline" / "standards.yaml")["schema_version"]
        == "brushline.standards.v1"
    )


def test_template_has_no_private_markers() -> None:
    """The template does not carry a personal path, a secret, or a private key."""
    patterns = (
        re.compile(r"/home/"),
        re.compile(r"/Users/"),
        re.compile(r"BEGIN [A-Z ]*PRIVATE KEY"),
        re.compile(r"password\s*[:=]", re.IGNORECASE),
        re.compile(r"token\s*[:=]", re.IGNORECASE),
    )
    for path in TEMPLATE_ROOT.rglob("*"):
        if path.is_file() and path.name != "__init__.py":
            text = path.read_text(encoding="utf-8")
            for pattern in patterns:
                assert pattern.search(text) is None, path


def test_cli_installs_the_template(tmp_path: Path) -> None:
    """The instance template command installs the overlay."""
    root = tmp_path / "instance"
    result = RUNNER.invoke(
        app,
        ["instance", "template", "--instance-root", str(root)],
    )
    assert result.exit_code == 0
    assert "written:" in result.stdout
    assert (root / "config" / "brushline" / "rebuild.steps.yaml").is_file()


def test_template_contains_the_two_specs() -> None:
    """The template carries the FEMIC spec and the Brushline extension spec."""
    assert (TEMPLATE_ROOT / "config" / "rebuild.spec.yaml").is_file()
    assert (TEMPLATE_ROOT / "config" / "brushline" / "rebuild.steps.yaml").is_file()
    assert (TEMPLATE_ROOT / "runbooks" / "REBUILD_RUNBOOK.md").is_file()
