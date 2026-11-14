"""Shared validation report and helpers for the Brushline artifact contracts."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ContractValidation:
    """The outcome of validating one artifact contract.

    Parameters
    ----------
    errors : tuple of str
        Named errors. An empty tuple means the artifact is valid.
    warnings : tuple of str
        Non-fatal findings.
    counts : dict of str to int or float
        Object counts or summary values.
    """

    errors: tuple[str, ...]
    warnings: tuple[str, ...]
    counts: dict[str, int | float]

    @property
    def is_valid(self) -> bool:
        """Return whether the artifact passed every check.

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
            Validity, errors, warnings, and counts.
        """
        return {
            "is_valid": self.is_valid,
            "errors": list(self.errors),
            "warnings": list(self.warnings),
            "counts": dict(sorted(self.counts.items())),
        }


def check_duplicates(prefix: str, label: str, values: list[str], errors: list[str]) -> None:
    """Append one error for each duplicated value.

    Parameters
    ----------
    prefix : str
        Error-code prefix, such as ``PLAN``.
    label : str
        Human label for the collection.
    values : list of str
        Identifiers in the collection.
    errors : list of str
        Error accumulator.
    """
    seen: set[str] = set()
    duplicates: set[str] = set()
    for value in values:
        if value in seen:
            duplicates.add(value)
        seen.add(value)
    for value in sorted(duplicates):
        errors.append(f"{prefix}-ID: duplicate {label} id {value}")


def ensure_relative_path(value: str, label: str) -> str:
    """Reject an absolute path or a path that escapes the artifact directory.

    Parameters
    ----------
    value : str
        Path to check.
    label : str
        Human label for the path.

    Returns
    -------
    str
        The original path when it is relative and contained.

    Raises
    ------
    ValueError
        When the path is absolute or contains ``..``.
    """
    candidate = Path(value)
    if candidate.is_absolute() or ".." in candidate.parts:
        raise ValueError(f"{label} must be relative and stay inside the artifact directory")
    return value
