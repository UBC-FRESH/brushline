"""Contract tests for the pinned FEMIC provider boundary."""

from __future__ import annotations

import json
from pathlib import Path
from typing import cast

import pytest
from brushline.integrations.femic import (
    BOUNDARY_PIN_FILENAME,
    FEMIC_CLI_COMMANDS,
    FEMIC_DATA_CONTRACTS,
    FEMIC_MATERIALIZATION_NODE_IDS,
    FEMIC_NODE_IDS,
    FEMIC_PROVIDER_IDS,
    FEMIC_VERSION_PIN,
    FRESHFORGE_VERSION_PIN,
    boundary_manifest,
    check_femic_compatibility,
    load_boundary_pin,
    validate_boundary_pin,
    write_boundary_pin,
)

ROOT = Path(__file__).resolve().parents[1]
PIN = ROOT / "notes" / "reference" / BOUNDARY_PIN_FILENAME


def _pin_copy() -> dict[str, object]:
    # The pin is JSON at the test boundary, so a round-trip copy is untyped.
    return cast("dict[str, object]", json.loads(json.dumps(boundary_manifest())))


def test_pin_matches_the_canonical_manifest() -> None:
    """The committed pin is the canonical boundary manifest and validates."""
    pin = load_boundary_pin(PIN)
    assert pin == boundary_manifest()
    report = validate_boundary_pin(pin)
    assert report.is_valid
    assert report.counts["providers"] == 2
    assert report.counts["nodes"] == 11
    assert report.counts["materialization_nodes"] == 9
    assert report.counts["contracts"] == 7


def test_compatible_versions_pass() -> None:
    """The exact FEMIC and FreshForge pins are compatible."""
    report = check_femic_compatibility(FEMIC_VERSION_PIN, FRESHFORGE_VERSION_PIN)
    assert report.is_compatible
    assert report.errors == ()
    assert report.to_dict()["femic_version"] == FEMIC_VERSION_PIN


def test_wrong_femic_version_is_rejected() -> None:
    """A FEMIC version other than the exact pin is rejected."""
    for version in ("0.1.0", "0.2.0a2", "0.3.0"):
        report = check_femic_compatibility(version, FRESHFORGE_VERSION_PIN)
        assert any(message.startswith("FEMIC-VERSION") for message in report.errors)


def test_wrong_freshforge_version_is_rejected() -> None:
    """A FreshForge version other than the exact pin is rejected."""
    report = check_femic_compatibility(FEMIC_VERSION_PIN, "0.1.0a6")
    assert any(message.startswith("FEMIC-FRESHFORGE") for message in report.errors)


def test_missing_freshforge_is_a_warning() -> None:
    """A missing FreshForge version is a warning, not a compatibility pass."""
    report = check_femic_compatibility(FEMIC_VERSION_PIN)
    assert report.is_compatible
    assert any(message.startswith("FEMIC-FRESHFORGE") for message in report.warnings)


def test_invalid_versions_are_rejected() -> None:
    """An invalid version string fails with a named error."""
    report = check_femic_compatibility("not-a-version", "also-not-a-version")
    assert any(message.startswith("FEMIC-VERSION") for message in report.errors)
    assert any(message.startswith("FEMIC-FRESHFORGE") for message in report.errors)


def test_missing_node_fails_the_pin() -> None:
    """A pin that drops a provider node fails validation."""
    payload = _pin_copy()
    nodes = cast("list[str]", payload["node_ids"])
    nodes.remove("matrix_build")
    report = validate_boundary_pin(payload)
    assert any(message.startswith("FEMIC-PIN") for message in report.errors)


def test_extra_node_fails_the_pin() -> None:
    """A pin that adds an undeclared node fails validation."""
    payload = _pin_copy()
    nodes = cast("list[str]", payload["node_ids"])
    nodes.append("brushline.undeclared")
    report = validate_boundary_pin(payload)
    assert any(message.startswith("FEMIC-PIN") for message in report.errors)


def test_wrong_contract_fails_the_pin() -> None:
    """A pin with a changed data contract fails validation."""
    payload = _pin_copy()
    contracts = cast("list[str]", payload["data_contracts"])
    contracts[0] = "femic.lidar.product.v2"
    report = validate_boundary_pin(payload)
    assert any(message.startswith("FEMIC-PIN") for message in report.errors)


def test_pin_round_trips(tmp_path: Path) -> None:
    """The boundary pin writes and loads without a semantic change."""
    target = write_boundary_pin(tmp_path / BOUNDARY_PIN_FILENAME)
    assert load_boundary_pin(target) == boundary_manifest()


def test_load_rejects_a_non_object(tmp_path: Path) -> None:
    """A pin that is not a JSON object is rejected."""
    target = tmp_path / BOUNDARY_PIN_FILENAME
    target.write_text("[]", encoding="utf-8")
    with pytest.raises(ValueError, match="JSON object"):
        load_boundary_pin(target)


def test_boundary_lists_the_expected_surface() -> None:
    """The boundary names the two providers, the commands, and the contracts."""
    assert FEMIC_PROVIDER_IDS == ("femic", "femic.materialization")
    assert "femic instance rebuild" in FEMIC_CLI_COMMANDS
    assert "femic data bcdc-fetch" in FEMIC_CLI_COMMANDS
    assert "femic.prep" not in FEMIC_DATA_CONTRACTS
    assert len(FEMIC_NODE_IDS) == 11
    assert len(FEMIC_MATERIALIZATION_NODE_IDS) == 9
    assert len(FEMIC_DATA_CONTRACTS) == 7
