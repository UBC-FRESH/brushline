"""The pinned FEMIC extension boundary.

Brushline may call only the FEMIC CLI and FreshForge provider surface recorded here. FEMIC is an
alpha dependency, so the pin is exact: a new FEMIC or FreshForge version is a deliberate boundary
review, not a silent upgrade. This module does not import FEMIC; it only records and checks the
surface.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from packaging.specifiers import SpecifierSet
from packaging.version import InvalidVersion, Version

from brushline.model.validation import ContractValidation, check_duplicates

BOUNDARY_SCHEMA_VERSION = "brushline.femic-boundary.v1"
FEMIC_VERSION_PIN = "0.2.0a1"
FEMIC_SPECIFIER = "==0.2.0a1"
FRESHFORGE_VERSION_PIN = "0.1.0a5"
BOUNDARY_PIN_FILENAME = "femic-provider-api.v1.json"

FEMIC_PROVIDER_IDS: tuple[str, ...] = ("femic", "femic.materialization")
FEMIC_NODE_IDS: tuple[str, ...] = (
    "validate_case",
    "geospatial_preflight",
    "compile_upstream",
    "accepted_btc_handoff",
    "btc_post_tipsy",
    "export_patchworks",
    "patchworks_preflight",
    "matrix_build",
    "export_woodstock",
    "ws3_bridge",
    "ws4_quality",
)
FEMIC_MATERIALIZATION_NODE_IDS: tuple[str, ...] = (
    "check_toolchain",
    "check_python_environment",
    "install_packages",
    "init_submodules",
    "init_annex",
    "enable_special_remote",
    "materialize_paths",
    "audit_annex_availability",
    "write_materialization_report",
)
FEMIC_CLI_COMMANDS: tuple[str, ...] = (
    "femic instance init",
    "femic instance rebuild",
    "femic instance validate-spec",
    "femic instance config show",
    "femic freshforge workflows list",
    "femic data bcdc-resolve",
    "femic data bcdc-fetch",
    "femic data bcdc-order",
    "femic prep validate-case",
    "femic prep geospatial-preflight",
)
FRESHFORGE_CLI_COMMANDS: tuple[str, ...] = (
    "freshforge validate",
    "freshforge inspect",
    "freshforge plan",
    "freshforge run",
    "freshforge providers",
)
FEMIC_DATA_CONTRACTS: tuple[str, ...] = (
    "femic.lidar.product.v1",
    "femic.lidar.bundle.v1",
    "femic.inventory.als.v1",
    "femic.inventory.als.model.v1",
    "femic.climate.v1",
    "femic.disturbance.v1",
    "femic.efi.model.v1",
)


@dataclass(frozen=True)
class FemicCompatibility:
    """The result of checking one FEMIC/FreshForge version pair.

    Parameters
    ----------
    femic_version : str
        FEMIC version being checked.
    freshforge_version : str or None
        FreshForge version being checked, or ``None`` when it was not supplied.
    errors : tuple of str
        Named compatibility errors.
    warnings : tuple of str
        Non-fatal findings.
    """

    femic_version: str
    freshforge_version: str | None
    errors: tuple[str, ...]
    warnings: tuple[str, ...]

    @property
    def is_compatible(self) -> bool:
        """Return whether the pair passes every compatibility check.

        Returns
        -------
        bool
            ``True`` when there are no errors.
        """
        return not self.errors

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-ready report.

        Returns
        -------
        dict of str to object
            Versions, compatibility, errors, and warnings.
        """
        return {
            "femic_version": self.femic_version,
            "freshforge_version": self.freshforge_version,
            "is_compatible": self.is_compatible,
            "errors": list(self.errors),
            "warnings": list(self.warnings),
        }


def boundary_manifest() -> dict[str, object]:
    """Return the canonical FEMIC boundary manifest.

    Returns
    -------
    dict of str to object
        The schema version, exact pins, provider ids, node ids, CLI commands, and data contracts.
    """
    return {
        "schema_version": BOUNDARY_SCHEMA_VERSION,
        "femic_version": FEMIC_VERSION_PIN,
        "femic_specifier": FEMIC_SPECIFIER,
        "freshforge_version": FRESHFORGE_VERSION_PIN,
        "provider_ids": list(FEMIC_PROVIDER_IDS),
        "node_ids": list(FEMIC_NODE_IDS),
        "materialization_node_ids": list(FEMIC_MATERIALIZATION_NODE_IDS),
        "femic_cli_commands": list(FEMIC_CLI_COMMANDS),
        "freshforge_cli_commands": list(FRESHFORGE_CLI_COMMANDS),
        "data_contracts": list(FEMIC_DATA_CONTRACTS),
    }


def check_femic_compatibility(
    femic_version: str,
    freshforge_version: str | None = None,
) -> FemicCompatibility:
    """Check a FEMIC/FreshForge version pair against the exact pins.

    Parameters
    ----------
    femic_version : str
        FEMIC version.
    freshforge_version : str or None, optional
        FreshForge version. When ``None``, the FreshForge check is reported as not run.

    Returns
    -------
    FemicCompatibility
        The compatibility report.
    """
    errors: list[str] = []
    warnings: list[str] = []
    try:
        parsed_femic = Version(femic_version)
    except InvalidVersion:
        errors.append(f"FEMIC-VERSION: {femic_version!r} is not a valid version")
        parsed_femic = None
    if parsed_femic is not None and parsed_femic not in SpecifierSet(FEMIC_SPECIFIER):
        errors.append(f"FEMIC-VERSION: {femic_version!r} does not satisfy {FEMIC_SPECIFIER}")
    if freshforge_version is None:
        warnings.append("FEMIC-FRESHFORGE: FreshForge version was not supplied")
    else:
        try:
            parsed_freshforge = Version(freshforge_version)
        except InvalidVersion:
            errors.append(f"FEMIC-FRESHFORGE: {freshforge_version!r} is not a valid version")
            parsed_freshforge = None
        if parsed_freshforge is not None and freshforge_version != FRESHFORGE_VERSION_PIN:
            errors.append(
                f"FEMIC-FRESHFORGE: {freshforge_version!r} is not the pinned "
                f"{FRESHFORGE_VERSION_PIN!r}"
            )
    return FemicCompatibility(
        femic_version=femic_version,
        freshforge_version=freshforge_version,
        errors=tuple(errors),
        warnings=tuple(warnings),
    )


def validate_boundary_pin(payload: dict[str, object]) -> ContractValidation:
    """Validate a boundary pin against the canonical manifest.

    Parameters
    ----------
    payload : dict of str to object
        Parsed boundary pin.

    Returns
    -------
    ContractValidation
        Errors, warnings, and counts.
    """
    canonical = boundary_manifest()
    errors: list[str] = []
    warnings: list[str] = []
    for key in (
        "schema_version",
        "femic_version",
        "femic_specifier",
        "freshforge_version",
    ):
        if payload.get(key) != canonical[key]:
            errors.append(f"FEMIC-PIN: {key} is {payload.get(key)!r}, expected {canonical[key]!r}")
    list_keys = {
        "provider_ids": FEMIC_PROVIDER_IDS,
        "node_ids": FEMIC_NODE_IDS,
        "materialization_node_ids": FEMIC_MATERIALIZATION_NODE_IDS,
        "femic_cli_commands": FEMIC_CLI_COMMANDS,
        "freshforge_cli_commands": FRESHFORGE_CLI_COMMANDS,
        "data_contracts": FEMIC_DATA_CONTRACTS,
    }
    for key, expected_values in list_keys.items():
        value = payload.get(key)
        if not isinstance(value, list):
            errors.append(f"FEMIC-PIN: {key} is missing or is not a list")
            continue
        actual = sorted(str(item) for item in value)
        expected = sorted(expected_values)
        if actual != expected:
            errors.append(f"FEMIC-PIN: {key} does not match the canonical list")
    check_duplicates("FEMIC-PIN", "provider", list(FEMIC_PROVIDER_IDS), errors)
    check_duplicates("FEMIC-PIN", "node", list(FEMIC_NODE_IDS), errors)
    counts: dict[str, int | float] = {
        "providers": len(FEMIC_PROVIDER_IDS),
        "nodes": len(FEMIC_NODE_IDS),
        "materialization_nodes": len(FEMIC_MATERIALIZATION_NODE_IDS),
        "commands": len(FEMIC_CLI_COMMANDS) + len(FRESHFORGE_CLI_COMMANDS),
        "contracts": len(FEMIC_DATA_CONTRACTS),
    }
    return ContractValidation(tuple(errors), tuple(warnings), counts)


def load_boundary_pin(path: Path) -> dict[str, object]:
    """Load a boundary pin from JSON.

    Parameters
    ----------
    path : Path
        JSON file.

    Returns
    -------
    dict of str to object
        The parsed pin.

    Raises
    ------
    ValueError
        When the file does not contain a JSON object.
    """
    value: object = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} does not contain a JSON object")
    return cast("dict[str, object]", value)


def write_boundary_pin(path: Path) -> Path:
    """Write the canonical boundary pin.

    Parameters
    ----------
    path : Path
        Destination JSON file.

    Returns
    -------
    Path
        The written path.
    """
    target = Path(path).expanduser().resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(boundary_manifest(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return target


__all__ = [
    "BOUNDARY_PIN_FILENAME",
    "BOUNDARY_SCHEMA_VERSION",
    "FEMIC_CLI_COMMANDS",
    "FEMIC_DATA_CONTRACTS",
    "FEMIC_MATERIALIZATION_NODE_IDS",
    "FEMIC_NODE_IDS",
    "FEMIC_PROVIDER_IDS",
    "FEMIC_SPECIFIER",
    "FEMIC_VERSION_PIN",
    "FRESHFORGE_CLI_COMMANDS",
    "FRESHFORGE_VERSION_PIN",
    "FemicCompatibility",
    "boundary_manifest",
    "check_femic_compatibility",
    "load_boundary_pin",
    "validate_boundary_pin",
    "write_boundary_pin",
]
