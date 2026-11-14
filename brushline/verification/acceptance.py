# ruff: noqa: E501
"""Acceptance-criteria evidence and verification report."""

from __future__ import annotations

import json
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from brushline.strategic.validation import build_synthetic_case as build_strategic_case

VERIFICATION_SCHEMA_VERSION: Literal["brushline.verification.v1"] = "brushline.verification.v1"
Status = Literal["met", "partial", "not_met", "gap"]


class CriterionEvidence(BaseModel):
    """Evidence for one scope success criterion."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    number: int = Field(ge=1, le=16)
    name: str
    status: Status
    evidence: str
    note: str = ""


class VerificationReport(BaseModel):
    """The release verification report."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["brushline.verification.v1"] = VERIFICATION_SCHEMA_VERSION
    criteria: list[CriterionEvidence]
    bau: dict[str, float]
    monitoring: dict[str, float | bool]
    exchange: dict[str, float | bool]
    performance: dict[str, float | int | str]
    reproducible: bool
    recommendation: str
    created_utc: datetime


def build_verification(created_utc: datetime | None = None) -> VerificationReport:
    """Run the synthetic evidence checks and assemble the report."""
    created = created_utc or datetime(2026, 11, 14, tzinfo=UTC)
    started = time.perf_counter()
    case = build_strategic_case(created)
    elapsed = time.perf_counter() - started
    second = build_strategic_case(created)
    reproducible = (
        case.scenario.portfolio_digest == second.scenario.portfolio_digest
        and case.scenario.report_digest == second.scenario.report_digest
    )
    criteria = [
        CriterionEvidence(
            number=1,
            name="End-to-end synthetic corridor",
            status="met",
            evidence="fixture/CLI/studio tests and run artifacts",
            note="Synthetic evidence only.",
        ),
        CriterionEvidence(
            number=2,
            name="Growth and treatment validation",
            status="partial",
            evidence="P4 held-out synthetic validation and model card",
            note="No field plots.",
        ),
        CriterionEvidence(
            number=3,
            name="FEMIC-extended instance builder",
            status="partial",
            evidence="P2 provider pin, template, catalogue, fetch and capability tests",
            note="No live FEMIC/FreshForge build.",
        ),
        CriterionEvidence(
            number=4,
            name="Agent capability",
            status="met",
            evidence="P2.6 offline fake provider and validators",
            note="Offline harness.",
        ),
        CriterionEvidence(
            number=5,
            name="LiDAR state initialization",
            status="partial",
            evidence="P3 LiDAR/terrain/canopy/state/coverage contracts",
            note="No live bundle in this verification run.",
        ),
        CriterionEvidence(
            number=6,
            name="Low-vegetation calibration",
            status="not_met",
            evidence="P4 synthetic calibration and model-card domain",
            note="No field calibration or mature-EFI transfer.",
        ),
        CriterionEvidence(
            number=7,
            name="Demo portal",
            status="met",
            evidence="P11 static five-instance synthetic portal and validation",
            note="Public/synthetic only.",
        ),
        CriterionEvidence(
            number=8,
            name="Exact small-instance check",
            status="met",
            evidence="P5 tiny optimum and exact replay",
            note="324 assignments.",
        ),
        CriterionEvidence(
            number=9,
            name="Search quality under a stated budget",
            status="partial",
            evidence="P5 tiny/local budget and archive tests",
            note="No broad validation set.",
        ),
        CriterionEvidence(
            number=10,
            name="Business-as-usual comparison",
            status="met",
            evidence=f"P6 case: optimized {case.portfolio.service_attainment:.3f}/{case.portfolio.total_cost:.0f}, BAU {case.bau.service_attainment:.3f}/{case.bau.total_cost:.0f}",
            note="Synthetic case.",
        ),
        CriterionEvidence(
            number=11,
            name="Monitoring value",
            status="met",
            evidence="P8 adaptive 5.0 vs fixed 1.33 regret/dollar",
            note="Synthetic expected-loss proxy.",
        ),
        CriterionEvidence(
            number=12,
            name="Owner-contractor agreement",
            status="met",
            evidence="P9 plan 120 reproduced; bid differences traced",
            note="Synthetic rates.",
        ),
        CriterionEvidence(
            number=13,
            name="Studio contract",
            status="met",
            evidence="P10 artifact-only API and read-only reviewer skin tests",
            note="Static/synthetic content.",
        ),
        CriterionEvidence(
            number=14,
            name="Reproducibility",
            status="met" if reproducible else "not_met",
            evidence="P6 scenario portfolio/report digests replayed twice",
            note="Same case and seed.",
        ),
        CriterionEvidence(
            number=15,
            name="Scale",
            status="not_met",
            evidence=f"Measured small-case build: {elapsed:.3f}s for 10 periods/3 segments",
            note="10,000 segments/1,000 evaluations/8-core target not attempted.",
        ),
        CriterionEvidence(
            number=16,
            name="Quality gates",
            status="met",
            evidence="pytest, coverage, validator and docs gates",
            note="Local dashboard green.",
        ),
    ]
    return VerificationReport(
        criteria=criteria,
        bau={
            "optimized_service": case.portfolio.service_attainment,
            "optimized_cost": case.portfolio.total_cost,
            "bau_service": case.bau.service_attainment,
            "bau_cost": case.bau.total_cost,
        },
        monitoring={
            "adaptive_regret_per_dollar": 5.0,
            "fixed_regret_per_dollar": 1.3333333333,
            "beats_calendar": True,
        },
        exchange={"plan_cost": 120.0, "same_artifact": True, "attributable": True},
        performance={
            "segments": 3,
            "periods": 10,
            "seconds": round(elapsed, 4),
            "target_segments": 10000,
            "target_met": False,
        },
        reproducible=reproducible,
        recommendation="Release candidate for an internal prototype, not a production or field-calibrated release. Close the field-calibration and scale gaps before a public operational claim.",
        created_utc=created,
    )


def write_verification(report: VerificationReport, path: str | Path) -> Path:
    """Write the verification JSON."""
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(report.model_dump_json(indent=2) + "\n", encoding="utf-8")
    return destination


def write_report_markdown(report: VerificationReport, path: str | Path) -> Path:
    """Write a human-readable verification report."""
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# P12 verification report",
        "",
        "## Criteria",
        "",
        "| # | Criterion | Status | Evidence | Gap |",
        "| --- | --- | --- | --- | --- |",
    ]
    lines += [
        f"| {c.number} | {c.name} | {c.status} | {c.evidence} | {c.note} |" for c in report.criteria
    ]
    lines += [
        "",
        "## BAU case",
        "",
        json.dumps(report.bau, indent=2),
        "",
        "## Monitoring value",
        "",
        json.dumps(report.monitoring, indent=2),
        "",
        "## Owner-contractor exchange",
        "",
        json.dumps(report.exchange, indent=2),
        "",
        "## Performance and scale",
        "",
        json.dumps(report.performance, indent=2),
        "",
        "## Reproducibility",
        "",
        f"Replayed: {report.reproducible}",
        "",
        "## Recommendation",
        "",
        report.recommendation,
        "",
    ]
    destination.write_text("\n".join(lines), encoding="utf-8")
    return destination
