"""Maintenance cadence, dependency audit, governance register, and pilot evidence."""

from __future__ import annotations

import importlib.metadata
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

OPERATIONS_SCHEMA_VERSION: Literal["brushline.operations.v1"] = "brushline.operations.v1"


class ReviewCadence(BaseModel):
    """Review cadence and triage rules."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    cadence: Literal["weekly", "monthly", "quarterly"]
    owner: str
    next_review: str
    checklist: list[str] = Field(min_length=1)


class ReviewRecord(BaseModel):
    """One held review."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    review_id: str
    date: str
    attendees: list[str]
    issues: list[str]
    decisions: list[str]
    actions: list[str]


class DependencyRecord(BaseModel):
    """One dependency/pin audit row."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    package: str
    pin: str
    installed: str
    status: Literal["current", "missing-optional", "drift", "not-installed"]
    reason: str = ""


class GovernanceRecord(BaseModel):
    """One model or dataset governance row."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    asset_id: str
    kind: Literal["model", "dataset", "boundary"]
    card_path: str
    licence: str
    domain: str
    validation_path: str
    status: Literal["current", "needs-review"]


class PilotEvidence(BaseModel):
    """One pilot evidence record."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    pilot_id: str
    title: str
    data_boundary: str
    metrics: dict[str, float]
    caveats: list[str]
    status: Literal["synthetic", "planned", "active", "complete"]


DEFAULT_CADENCE = ReviewCadence(
    cadence="monthly",
    owner="Brushline maintainers",
    next_review="2026-12-14",
    checklist=[
        "Triage new issues and label phase/task",
        "Review open pull requests and dashboards",
        "Check dependency/security advisories",
        "Review model/data cards and licences",
        "Record decisions, owners, and due dates",
    ],
)

DEFAULT_REVIEWS = (
    ReviewRecord(
        review_id="p14-review-1",
        date="2026-11-14",
        attendees=["Brushline maintainers"],
        issues=["P14 launch"],
        decisions=["Monthly cadence adopted", "0.1.3 released"],
        actions=["Record governance register", "Prepare handover guide", "Record pilot evidence"],
    ),
)

PINS = {
    "fresh-solutions": ">=0.9.3,<0.10",
    "femic": "==0.2.0a1",
    "freshforge": "==0.1.0a5",
}


def audit_dependencies() -> list[DependencyRecord]:
    """Audit optional dependency pins against the local environment."""
    rows: list[DependencyRecord] = []
    for package, pin in PINS.items():
        try:
            installed = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            rows.append(
                DependencyRecord(
                    package=package,
                    pin=pin,
                    installed="not-installed",
                    status="missing-optional",
                    reason="Optional extra; core install remains valid.",
                )
            )
            continue
        lower = pin.replace(">=", "").split(",")[0].replace("==", "")
        status: Literal["current", "drift"] = (
            "current" if installed == lower or installed.startswith(lower) else "drift"
        )
        rows.append(
            DependencyRecord(
                package=package,
                pin=pin,
                installed=installed,
                status=status,
                reason="Pinned optional integration." if status == "current" else "Review pin.",
            )
        )
    return rows


def default_governance(root: Path | None = None) -> list[GovernanceRecord]:
    """Return the model/data governance register."""
    base = root or Path(__file__).resolve().parents[2]
    return [
        GovernanceRecord(
            asset_id="brushline.low-vegetation.prototype.v0",
            kind="model",
            card_path=str(
                (base / "notes/reference/low-vegetation-model-card.v1.json").relative_to(base)
            ),
            licence="Apache-2.0",
            domain="low vegetation; prototype applicability domain",
            validation_path=str(
                (base / "notes/reference/vegetation-validation.v1.json").relative_to(base)
            ),
            status="current",
        ),
        GovernanceRecord(
            asset_id="synthetic-corridor",
            kind="dataset",
            card_path=str((base / "examples/synthetic-corridor/README.md").relative_to(base)),
            licence="CC0-1.0",
            domain="synthetic utility corridor",
            validation_path=str(
                (base / "notes/reference/p12-verification.v1.json").relative_to(base)
            ),
            status="current",
        ),
        GovernanceRecord(
            asset_id="femic.provider.v1",
            kind="boundary",
            card_path=str((base / "notes/reference/femic-provider-api.v1.json").relative_to(base)),
            licence="Apache-2.0",
            domain="FEMIC 0.2.0a1 / FreshForge 0.1.0a5 boundary",
            validation_path=str(
                (base / "notes/reference/femic-provider-api.v1.json").relative_to(base)
            ),
            status="current",
        ),
    ]


def validate_governance(records: list[GovernanceRecord], root: Path | None = None) -> list[str]:
    """Return missing paths or unknown statuses."""
    base = root or Path(__file__).resolve().parents[2]
    problems: list[str] = []
    for record in records:
        for path in (record.card_path, record.validation_path):
            if not (base / path).exists():
                problems.append(f"{record.asset_id}: missing {path}")
        if not record.licence:
            problems.append(f"{record.asset_id}: missing licence")
        if record.status != "current":
            problems.append(f"{record.asset_id}: needs review")
    return problems


def default_pilot_evidence() -> PilotEvidence:
    """Return the current synthetic pilot evidence."""
    return PilotEvidence(
        pilot_id="p14-synthetic-pilot",
        title="Synthetic corridor owner-contractor pilot",
        data_boundary="Synthetic/public data only; no private owner data.",
        metrics={
            "optimized_service": 0.707,
            "bau_service": 0.413,
            "optimized_cost": 920.0,
            "bau_cost": 360.0,
            "monitoring_regret_per_dollar": 5.0,
            "fixed_calendar_regret_per_dollar": 1.3333,
            "plan_cost": 120.0,
        },
        caveats=[
            "Synthetic evidence; not a field pilot.",
            "No private data, uploads, or production dispatch.",
            "Scale and field-calibration gaps remain.",
        ],
        status="synthetic",
    )


def write_operations_json(path: str | Path, root: Path | None = None) -> Path:
    """Write cadence, reviews, dependencies, governance, and pilot evidence."""
    import json

    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": OPERATIONS_SCHEMA_VERSION,
        "cadence": DEFAULT_CADENCE.model_dump(mode="json"),
        "reviews": [item.model_dump(mode="json") for item in DEFAULT_REVIEWS],
        "dependencies": [item.model_dump(mode="json") for item in audit_dependencies()],
        "governance": [item.model_dump(mode="json") for item in default_governance(root)],
        "pilot": default_pilot_evidence().model_dump(mode="json"),
        "created_utc": datetime.now(UTC).isoformat(),
    }
    destination.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return destination


__all__ = [
    "DEFAULT_CADENCE",
    "DEFAULT_REVIEWS",
    "OPERATIONS_SCHEMA_VERSION",
    "PINS",
    "DependencyRecord",
    "GovernanceRecord",
    "PilotEvidence",
    "ReviewCadence",
    "ReviewRecord",
    "audit_dependencies",
    "default_governance",
    "default_pilot_evidence",
    "validate_governance",
    "write_operations_json",
]
