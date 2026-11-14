"""LiDAR coverage, applicability, and observation-gap reporting.

The adapter maps point-cloud, DEM, CHM, field-plot, and model-card evidence into the P2.5 coverage
states and gap report. It does not read a payload, download a product, or impute a missing value. A
required missing, stale, or out-of-domain evidence item is explicit and can stop the state build.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from brushline.integrations.fetch import (
    CoverageEntry,
    CoverageReport,
    GapReport,
    build_gap_report,
    validate_coverage,
    validate_gap_report,
)
from brushline.model.validation import ContractValidation, check_duplicates

LIDAR_COVERAGE_SCHEMA_VERSION: Literal["brushline.lidar-coverage.v1"] = (
    "brushline.lidar-coverage.v1"
)
LIDAR_EVIDENCE_KINDS: tuple[str, ...] = (
    "point_cloud",
    "dem",
    "chm",
    "field_plot",
    "inventory",
    "climate",
    "site_index",
)
DEFAULT_REQUIRED_KINDS: tuple[str, ...] = ("point_cloud", "dem", "chm")
DEFAULT_OPTIONAL_KINDS: tuple[str, ...] = ("field_plot",)
COVERAGE_ACTIONS: dict[str, str] = {
    "missing": "request or acquire the missing evidence, or mark the affected state unknown",
    "stale": "refresh the evidence or treat the observation as historical",
    "partial": "fill the coverage gap or mark the affected state partial",
    "out_of_domain": "exclude the model output or use a locally validated model",
    "excluded": "confirm the exclusion and record the decision",
}


class LidarCoverageError(ValueError):
    """Raised when the LiDAR coverage request is inconsistent."""


class Applicability(BaseModel):
    """The model-card applicability of one evidence item.

    Parameters
    ----------
    model_card_id : str or None
        Model card id.
    in_domain : bool, optional
        Whether the evidence is inside the model domain. Defaults to ``True``.
    reason : str, optional
        Why the evidence is out of domain.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    model_card_id: str | None = None
    in_domain: bool = True
    reason: str = ""

    @model_validator(mode="after")
    def _out_of_domain_reason(self) -> Applicability:
        if not self.in_domain and not self.reason.strip():
            raise ValueError("out-of-domain applicability needs a reason")
        return self


class LidarEvidence(BaseModel):
    """One acquisition or observation for a segment.

    Parameters
    ----------
    segment_id : str
        Segment id.
    kind : str
        Evidence kind.
    acquisition_date : datetime.date
        Acquisition date.
    coverage_pct : float
        Source coverage percentage.
    valid_pixel_pct : float or None
        Valid-pixel percentage, when the producer records it.
    applicability : Applicability, optional
        Model-card applicability.
    evidence : str
        Evidence reference, such as a bundle or product id.
    excluded : bool, optional
        Whether the evidence is deliberately excluded.
    reason : str, optional
        Exclusion or caveat reason.
    source : str
        Source name.
    source_version : str
        Source version.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    segment_id: str = Field(min_length=1)
    kind: str
    acquisition_date: date
    coverage_pct: float = Field(ge=0, le=100)
    valid_pixel_pct: float | None = Field(default=None, ge=0, le=100)
    applicability: Applicability = Field(default_factory=Applicability)
    evidence: str = Field(min_length=1)
    excluded: bool = False
    reason: str = ""
    source: str = Field(min_length=1)
    source_version: str = Field(min_length=1)

    @model_validator(mode="after")
    def _exclusion_reason(self) -> LidarEvidence:
        if self.excluded and not self.reason.strip():
            raise ValueError("excluded evidence needs a reason")
        return self


class LidarCoverageConfig(BaseModel):
    """Coverage and recency rules.

    Parameters
    ----------
    state_year : int, optional
        Target state year. Defaults to ``2026``.
    max_age_years : int, optional
        Maximum acquisition age for a contemporary observation. Defaults to ``10``.
    min_coverage_pct : float, optional
        Minimum usable coverage. Defaults to ``50``.
    min_valid_pixel_pct : float, optional
        Minimum valid-pixel percentage. Defaults to ``80``.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    state_year: int = Field(default=2026, ge=1900, le=2200)
    max_age_years: int = Field(default=10, ge=0)
    min_coverage_pct: float = Field(default=50.0, ge=0, le=100)
    min_valid_pixel_pct: float = Field(default=80.0, ge=0, le=100)


class LidarCoverageRequest(BaseModel):
    """A request to assess LiDAR coverage and applicability.

    Parameters
    ----------
    aoi : str
        AOI reference.
    plan_id : str, optional
        Report plan id.
    segment_ids : list of str
        Segment ids.
    observations : list of LidarEvidence
        Available evidence.
    required_kinds : list of str, optional
        Evidence kinds whose absence stops the build.
    optional_kinds : list of str, optional
        Evidence kinds whose absence is a caveat.
    config : LidarCoverageConfig, optional
        Coverage and recency rules.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    aoi: str = Field(min_length=1)
    plan_id: str = "lidar-coverage"
    segment_ids: list[str] = Field(min_length=1)
    observations: list[LidarEvidence] = Field(default_factory=list)
    required_kinds: list[str] = Field(default_factory=lambda: list(DEFAULT_REQUIRED_KINDS))
    optional_kinds: list[str] = Field(default_factory=lambda: list(DEFAULT_OPTIONAL_KINDS))
    config: LidarCoverageConfig = Field(default_factory=LidarCoverageConfig)

    @model_validator(mode="after")
    def _request_consistency(self) -> LidarCoverageRequest:
        if len(set(self.segment_ids)) != len(self.segment_ids):
            raise ValueError("segment_ids must be unique")
        expected = [*self.required_kinds, *self.optional_kinds]
        if len(set(expected)) != len(expected):
            raise ValueError("required_kinds and optional_kinds must not overlap")
        unknown = sorted(set(expected) - set(LIDAR_EVIDENCE_KINDS))
        if unknown:
            raise ValueError(f"unknown evidence kinds: {', '.join(unknown)}")
        if not expected:
            raise ValueError("at least one evidence kind is required")
        known_segments = set(self.segment_ids)
        for observation in self.observations:
            if observation.segment_id not in known_segments:
                raise ValueError(f"observation segment {observation.segment_id!r} is not requested")
        return self


class LidarCoverageEntry(BaseModel):
    """One segment/evidence coverage decision.

    Parameters
    ----------
    segment_id : str
        Segment id.
    kind : str
        Evidence kind.
    state : str
        One of the six coverage states.
    required : bool
        Whether a gap stops the build.
    coverage_pct : float
        Usable coverage after the valid-pixel rule.
    source_coverage_pct : float
        Source coverage before the valid-pixel rule.
    valid_pixel_pct : float or None
        Valid-pixel percentage.
    acquisition_date : datetime.date or None
        Acquisition date.
    vintage : str
        Acquisition year or empty.
    evidence : str
        Evidence reference.
    reason : str
        Missing or non-observed reason.
    model_card_id : str or None
        Model card id.
    applicability : Applicability
        Model-card applicability.
    recommended_action : str
        Next action.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    segment_id: str = Field(min_length=1)
    kind: str
    state: str
    required: bool
    coverage_pct: float = Field(ge=0, le=100)
    source_coverage_pct: float = Field(ge=0, le=100)
    valid_pixel_pct: float | None = Field(default=None, ge=0, le=100)
    acquisition_date: date | None = None
    vintage: str = ""
    evidence: str = ""
    reason: str = ""
    model_card_id: str | None = None
    applicability: Applicability = Field(default_factory=Applicability)
    recommended_action: str = ""


class LidarCoverageReport(BaseModel):
    """The LiDAR coverage report and its P2.5 gap view.

    Parameters
    ----------
    schema_version : {"brushline.lidar-coverage.v1"}
        Report schema version.
    created_utc : datetime
        Timezone-aware creation time.
    request : LidarCoverageRequest
        Request and evidence.
    entries : list of LidarCoverageEntry
        Segment/evidence decisions.
    coverage : CoverageReport
        P2.5 coverage view.
    gaps : GapReport
        P2.5 gap and stop/continue decision.
    """

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["brushline.lidar-coverage.v1"] = LIDAR_COVERAGE_SCHEMA_VERSION
    created_utc: datetime
    request: LidarCoverageRequest
    entries: list[LidarCoverageEntry] = Field(default_factory=list)
    coverage: CoverageReport
    gaps: GapReport


def assess_lidar_coverage(
    request: LidarCoverageRequest,
    *,
    created_utc: datetime | None = None,
) -> LidarCoverageReport:
    """Assess LiDAR evidence, coverage, applicability, and gaps.

    Parameters
    ----------
    request : LidarCoverageRequest
        Segment ids, observations, expected kinds, and rules.
    created_utc : datetime, optional
        Report time. Defaults to the current UTC time.

    Returns
    -------
    LidarCoverageReport
        Per-evidence decisions, the P2.5 coverage view, and the gap report.
    """
    created = created_utc or datetime.now(UTC)
    by_key: dict[tuple[str, str], LidarEvidence] = {}
    for observation in request.observations:
        key = (observation.segment_id, observation.kind)
        if key in by_key:
            raise LidarCoverageError(
                f"duplicate evidence for {observation.segment_id}/{observation.kind}"
            )
        by_key[key] = observation
    entries: list[LidarCoverageEntry] = []
    for segment_id in request.segment_ids:
        for kind in [*request.required_kinds, *request.optional_kinds]:
            required = kind in request.required_kinds
            evidence = by_key.get((segment_id, kind))
            entries.append(
                _entry(
                    segment_id,
                    kind,
                    required,
                    evidence,
                    request.config,
                )
            )
    coverage_entries = [
        CoverageEntry(
            source_id=entry.kind,
            target_id=entry.segment_id,
            state=entry.state,
            coverage_pct=entry.coverage_pct,
            vintage=entry.vintage,
            evidence=entry.evidence,
            reason=entry.reason,
            required=entry.required,
        )
        for entry in entries
    ]
    coverage = CoverageReport(
        plan_id=request.plan_id,
        created_utc=created,
        aoi=request.aoi,
        entries=coverage_entries,
    )
    gaps = build_gap_report(coverage)
    return LidarCoverageReport(
        created_utc=created,
        request=request,
        entries=entries,
        coverage=coverage,
        gaps=gaps,
    )


def validate_lidar_coverage(report: LidarCoverageReport) -> ContractValidation:
    """Validate the LiDAR coverage entries and their P2.5 reports.

    Parameters
    ----------
    report : LidarCoverageReport
        Report to validate.

    Returns
    -------
    ContractValidation
        Errors, warnings, and counts.
    """
    errors: list[str] = []
    warnings: list[str] = []
    check_duplicates(
        "LIDAR-COVERAGE",
        "entry",
        [f"{entry.segment_id}:{entry.kind}" for entry in report.entries],
        errors,
    )
    if report.created_utc.tzinfo is None:
        errors.append("LIDAR-COVERAGE-TIME: created_utc is not timezone-aware")
    coverage_report = validate_coverage(report.coverage)
    gap_report = validate_gap_report(report.gaps)
    errors.extend(coverage_report.errors)
    errors.extend(gap_report.errors)
    warnings.extend(coverage_report.warnings)
    warnings.extend(gap_report.warnings)
    coverage_entries = {
        (entry.target_id, entry.source_id): entry for entry in report.coverage.entries
    }
    for entry in report.entries:
        if entry.state not in COVERAGE_ACTIONS and entry.state != "observed":
            errors.append(
                f"LIDAR-COVERAGE-STATE: {entry.segment_id}/{entry.kind} has unknown "
                f"state {entry.state!r}"
            )
        if entry.valid_pixel_pct is not None and entry.valid_pixel_pct > 100:
            errors.append(
                f"LIDAR-COVERAGE-VALID: {entry.segment_id}/{entry.kind} valid pixels exceed 100"
            )
        if entry.coverage_pct > entry.source_coverage_pct:
            errors.append(
                f"LIDAR-COVERAGE-COVERAGE: {entry.segment_id}/{entry.kind} usable coverage "
                "exceeds source coverage"
            )
        if entry.state != "observed" and not entry.recommended_action.strip():
            errors.append(f"LIDAR-COVERAGE-ACTION: {entry.segment_id}/{entry.kind} has no action")
        if entry.state == "stale" and entry.acquisition_date is None:
            errors.append(f"LIDAR-COVERAGE-STALE: {entry.segment_id}/{entry.kind} has no date")
        if entry.state == "out_of_domain" and entry.applicability.in_domain:
            errors.append(
                f"LIDAR-COVERAGE-DOMAIN: {entry.segment_id}/{entry.kind} is not marked "
                "out of domain"
            )
        if entry.state == "excluded" and not entry.reason.strip():
            errors.append(f"LIDAR-COVERAGE-EXCLUDED: {entry.segment_id}/{entry.kind} has no reason")
        other = coverage_entries.get((entry.segment_id, entry.kind))
        if other is None:
            errors.append(
                f"LIDAR-COVERAGE-REF: {entry.segment_id}/{entry.kind} is missing from "
                "the coverage view"
            )
        elif other.state != entry.state:
            errors.append(f"LIDAR-COVERAGE-REF: {entry.segment_id}/{entry.kind} state mismatch")
    if not report.entries:
        warnings.append("LIDAR-COVERAGE-EMPTY: the report has no entries")
    counts: dict[str, int | float] = {
        "entries": len(report.entries),
        "observed": sum(1 for entry in report.entries if entry.state == "observed"),
        "stale": sum(1 for entry in report.entries if entry.state == "stale"),
        "partial": sum(1 for entry in report.entries if entry.state == "partial"),
        "missing": sum(1 for entry in report.entries if entry.state == "missing"),
        "out_of_domain": sum(1 for entry in report.entries if entry.state == "out_of_domain"),
        "excluded": sum(1 for entry in report.entries if entry.state == "excluded"),
        "stop": report.gaps.decision == "stop",
    }
    return ContractValidation(tuple(errors), tuple(warnings), counts)


def _coverage_reason(observation: LidarEvidence, state: str) -> str:
    """Return the reason for a non-observed coverage state.

    Parameters
    ----------
    observation : LidarEvidence
        Source evidence.
    state : str
        Coverage state.

    Returns
    -------
    str
        Observation reason or a state-specific fallback.
    """
    if observation.reason.strip():
        return observation.reason
    if state == "partial":
        return "usable coverage is below the threshold"
    if state == "stale":
        return "acquisition is older than the contemporary window"
    if state == "out_of_domain":
        return observation.applicability.reason
    if state == "missing":
        return "usable coverage is zero"
    return ""


def _entry(
    segment_id: str,
    kind: str,
    required: bool,
    observation: LidarEvidence | None,
    config: LidarCoverageConfig,
) -> LidarCoverageEntry:
    if observation is None:
        return LidarCoverageEntry(
            segment_id=segment_id,
            kind=kind,
            state="missing",
            required=required,
            coverage_pct=0,
            source_coverage_pct=0,
            evidence="",
            reason=f"no {kind} evidence for the segment",
            recommended_action=COVERAGE_ACTIONS["missing"],
        )
    usable = observation.coverage_pct
    if observation.valid_pixel_pct is not None:
        usable = min(usable, observation.valid_pixel_pct)
    if observation.excluded:
        state = "excluded"
    elif usable == 0:
        state = "missing"
    elif usable < config.min_coverage_pct or (
        observation.valid_pixel_pct is not None
        and observation.valid_pixel_pct < config.min_valid_pixel_pct
    ):
        state = "partial"
    elif observation.acquisition_date.year < config.state_year - config.max_age_years:
        state = "stale"
    elif not observation.applicability.in_domain:
        state = "out_of_domain"
    else:
        state = "observed"
    vintage = str(observation.acquisition_date.year)
    return LidarCoverageEntry(
        segment_id=segment_id,
        kind=kind,
        state=state,
        required=required,
        coverage_pct=usable,
        source_coverage_pct=observation.coverage_pct,
        valid_pixel_pct=observation.valid_pixel_pct,
        acquisition_date=observation.acquisition_date,
        vintage=vintage,
        evidence=observation.evidence,
        reason=_coverage_reason(observation, state),
        model_card_id=observation.applicability.model_card_id,
        applicability=observation.applicability,
        recommended_action=COVERAGE_ACTIONS.get(state, ""),
    )


__all__ = [
    "DEFAULT_OPTIONAL_KINDS",
    "DEFAULT_REQUIRED_KINDS",
    "LIDAR_COVERAGE_SCHEMA_VERSION",
    "LIDAR_EVIDENCE_KINDS",
    "Applicability",
    "LidarCoverageConfig",
    "LidarCoverageEntry",
    "LidarCoverageError",
    "LidarCoverageReport",
    "LidarCoverageRequest",
    "LidarEvidence",
    "assess_lidar_coverage",
    "validate_lidar_coverage",
]
