"""Plan-only fetch, materialization, coverage, and gap contracts.

The planner reads the catalogue and writes a plan; it never fetches. The materialization
manifest records pointers and checksums, not payloads. The coverage report preserves observed,
stale, partial, missing, out-of-domain, and excluded states instead of imputing a value. The gap
report turns a non-observed state into a next action and a stop/continue decision.

DataLad, annex, public-mirror, and owner-store pointers are metadata strings. This module does not
call a downloader, a remote service, or a secret store.
"""

from __future__ import annotations

import hashlib
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from brushline.integrations.catalogue import (
    ACCESS_STATUSES,
    PRIVATE_CLASSIFICATIONS,
    PUBLIC_CLASSIFICATIONS,
    DataCatalogue,
    UnknownCatalogueReferenceError,
    resolve_connector,
    resolve_source,
)
from brushline.model.validation import ContractValidation, check_duplicates, ensure_relative_path

FETCH_PLAN_SCHEMA_VERSION: Literal["brushline.fetch-plan.v1"] = "brushline.fetch-plan.v1"
MATERIALIZATION_SCHEMA_VERSION: Literal["brushline.materialization.v1"] = (
    "brushline.materialization.v1"
)
COVERAGE_SCHEMA_VERSION: Literal["brushline.coverage.v1"] = "brushline.coverage.v1"
GAP_REPORT_SCHEMA_VERSION: Literal["brushline.gap-report.v1"] = "brushline.gap-report.v1"

FETCH_KINDS: tuple[str, ...] = ("source", "connector")
FETCH_ACCESS_STATUSES: tuple[str, ...] = (*ACCESS_STATUSES, "blocked")
MATERIALIZATION_TARGETS: tuple[str, ...] = (
    "data_lad",
    "annex",
    "public_mirror",
    "owner_store",
    "not_materialized",
)
MATERIALIZATION_STATUSES: tuple[str, ...] = ("materialized", "missing", "partial", "failed")
COVERAGE_STATES: tuple[str, ...] = (
    "observed",
    "stale",
    "partial",
    "missing",
    "out_of_domain",
    "excluded",
)
GAP_DECISIONS: tuple[str, ...] = ("stop", "continue", "continue_with_caveat")
CLASSIFICATIONS: tuple[str, ...] = (*PUBLIC_CLASSIFICATIONS, *PRIVATE_CLASSIFICATIONS)
SHA256_PATTERN: re.Pattern[str] = re.compile(r"^[0-9a-f]{64}$")

DEFAULT_ESTIMATES: dict[str, tuple[float, float, str]] = {
    "bulk_download": (5000.0, 3600.0, "planning_default"),
    "stac": (200.0, 120.0, "planning_default"),
    "wfs": (50.0, 60.0, "planning_default"),
    "wms": (10.0, 30.0, "planning_default"),
    "api": (50.0, 60.0, "planning_default"),
    "rest": (50.0, 60.0, "planning_default"),
    "manual": (0.0, 0.0, "manual"),
    "unknown": (0.0, 0.0, "unknown"),
}

GAP_ACTIONS: dict[str, str] = {
    "missing": "request or acquire the source, or mark the affected segments unknown",
    "stale": "refresh the source or treat the observation as historical",
    "partial": "fill the gap with another source, or mark the affected segments partial",
    "out_of_domain": "exclude the source or use a local calibration",
    "excluded": "confirm the exclusion and record the decision",
}


class FetchEstimate(BaseModel):
    """A planning estimate for one source or connector.

    Parameters
    ----------
    size_mb : float, optional
        Estimated transfer size in megabytes. Defaults to ``0``.
    seconds : float, optional
        Estimated transfer time in seconds. Defaults to ``0``.
    basis : str, optional
        ``planning_default``, ``user``, ``manual``, ``unknown``, or ``owner_side``.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    size_mb: float = Field(default=0, ge=0)
    seconds: float = Field(default=0, ge=0)
    basis: str = "planning_default"


class FetchApproval(BaseModel):
    """A user approval recorded on a fetch plan.

    Parameters
    ----------
    approved_by : str, optional
        Person or role that approved the fetch.
    approved_utc : datetime
        Timezone-aware approval time.
    scope : str, optional
        ``single`` or ``bulk``.
    record : str, optional
        Reference to the approval record.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    approved_by: str = ""
    approved_utc: datetime
    scope: str = "single"
    record: str = ""


class FetchRequest(BaseModel):
    """A request to plan a fetch without executing it.

    Parameters
    ----------
    aoi : str
        Area of interest reference, such as an instance-relative AOI path.
    source_ids : list of str, optional
        Public source ids to plan.
    connector_ids : list of str, optional
        Private connector ids to plan.
    queries : dict of str to str, optional
        Query overrides keyed by source or connector id.
    estimates : dict of str to FetchEstimate, optional
        User estimates keyed by source or connector id.
    optional_ids : list of str, optional
        Ids that may be missing without stopping the build.
    bulk : bool, optional
        Whether the request is a bulk fetch. Defaults to ``False``.
    approvals : dict of str to FetchApproval, optional
        Approvals keyed by source or connector id.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    aoi: str = Field(min_length=1)
    source_ids: list[str] = Field(default_factory=list)
    connector_ids: list[str] = Field(default_factory=list)
    queries: dict[str, str] = Field(default_factory=dict)
    estimates: dict[str, FetchEstimate] = Field(default_factory=dict)
    optional_ids: list[str] = Field(default_factory=list)
    bulk: bool = False
    approvals: dict[str, FetchApproval] = Field(default_factory=dict)


class FetchItem(BaseModel):
    """One source or connector in a fetch plan.

    Parameters
    ----------
    kind : str
        ``source`` or ``connector``.
    reference_id : str
        Source or connector id.
    query : str
        Query or read scope.
    licence : str
        Licence or data-sharing record.
    access_status : str
        Catalogue access status, or ``blocked`` for an unapproved connector.
    classification : str
        Source or connector classification.
    estimated_size_mb : float, optional
        Estimated transfer size in megabytes.
    estimated_seconds : float, optional
        Estimated transfer time in seconds.
    estimate_basis : str, optional
        Where the estimate came from.
    bulk : bool, optional
        Whether the item is part of a bulk request.
    approval : FetchApproval or None, optional
        Recorded approval for the item.
    materialization : str, optional
        ``data_lad``, ``annex``, ``public_mirror``, ``owner_store``, or ``not_materialized``.
    materialization_pointer : str, optional
        Metadata pointer, never a payload path.
    required : bool, optional
        Whether a missing source stops the build. Defaults to ``True``.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    kind: str
    reference_id: str = Field(min_length=1)
    query: str = ""
    licence: str = ""
    access_status: str = "unknown"
    classification: str = "unknown"
    estimated_size_mb: float = Field(default=0, ge=0)
    estimated_seconds: float = Field(default=0, ge=0)
    estimate_basis: str = "unknown"
    bulk: bool = False
    approval: FetchApproval | None = None
    materialization: str = "not_materialized"
    materialization_pointer: str = ""
    required: bool = True


class FetchPlan(BaseModel):
    """A plan-only fetch preview.

    Parameters
    ----------
    schema_version : {"brushline.fetch-plan.v1"}
        Plan schema version.
    plan_id : str
        Stable plan identifier.
    created_utc : datetime
        Timezone-aware creation time.
    aoi : str
        Area-of-interest reference.
    mode : {"plan_only"}
        The planner never downloads.
    items : list of FetchItem
        Sources and connectors in plan order.
    notes : str, optional
        Human notes.
    """

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["brushline.fetch-plan.v1"] = FETCH_PLAN_SCHEMA_VERSION
    plan_id: str = Field(min_length=1)
    created_utc: datetime
    aoi: str = Field(min_length=1)
    mode: Literal["plan_only"] = "plan_only"
    items: list[FetchItem] = Field(default_factory=list)
    notes: str = ""

    @property
    def total_size_mb(self) -> float:
        """Return the estimated total transfer size.

        Returns
        -------
        float
            Sum of item size estimates in megabytes.
        """
        return sum(item.estimated_size_mb for item in self.items)

    @property
    def total_seconds(self) -> float:
        """Return the estimated total transfer time.

        Returns
        -------
        float
            Sum of item time estimates in seconds.
        """
        return sum(item.estimated_seconds for item in self.items)

    @property
    def network_items(self) -> int:
        """Return the number of items with a materialization pointer.

        Returns
        -------
        int
            Count of items that are not ``not_materialized``.
        """
        return sum(1 for item in self.items if item.materialization != "not_materialized")


class MaterializedItem(BaseModel):
    """One materialized or missing source.

    Parameters
    ----------
    id : str
        Stable item identifier.
    source_id : str
        Source or connector id.
    status : str, optional
        ``materialized``, ``missing``, ``partial``, or ``failed``.
    path : str, optional
        Instance-relative path. Empty for a missing item.
    sha256 : str, optional
        Expected SHA-256 of the file.
    size_bytes : int, optional
        Expected file size in bytes.
    retrieved_utc : datetime or None, optional
        Timezone-aware retrieval time.
    licence : str, optional
        Licence or data-sharing record.
    pointer : str, optional
        ``data_lad:``, ``annex:``, ``public_mirror:``, or ``owner_store:`` pointer.
    reason : str, optional
        Why the item is missing, partial, or failed.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str = Field(min_length=1)
    source_id: str = Field(min_length=1)
    status: str = "materialized"
    path: str = ""
    sha256: str = ""
    size_bytes: int = Field(default=0, ge=0)
    retrieved_utc: datetime | None = None
    licence: str = ""
    pointer: str = ""
    reason: str = ""


class MaterializationManifest(BaseModel):
    """The materialization record for one fetch plan.

    Parameters
    ----------
    schema_version : {"brushline.materialization.v1"}
        Manifest schema version.
    plan_id : str
        Fetch plan identifier.
    created_utc : datetime
        Timezone-aware creation time.
    items : list of MaterializedItem
        Materialized and missing items.
    notes : str, optional
        Human notes.
    """

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["brushline.materialization.v1"] = MATERIALIZATION_SCHEMA_VERSION
    plan_id: str = Field(min_length=1)
    created_utc: datetime
    items: list[MaterializedItem] = Field(default_factory=list)
    notes: str = ""


class CoverageEntry(BaseModel):
    """One source coverage state for one target.

    Parameters
    ----------
    source_id : str
        Source or connector id.
    target_id : str, optional
        Segment, span, or ``aoi`` target. Defaults to ``aoi``.
    state : str, optional
        ``observed``, ``stale``, ``partial``, ``missing``, ``out_of_domain``, or ``excluded``.
    coverage_pct : float, optional
        Coverage percentage from 0 to 100.
    vintage : str, optional
        Source vintage for the observation.
    evidence : str, optional
        Evidence reference supporting the state.
    reason : str, optional
        Reason for a non-observed state.
    required : bool, optional
        Whether the gap stops the build. Defaults to ``True``.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    source_id: str = Field(min_length=1)
    target_id: str = Field(default="aoi", min_length=1)
    state: str = "missing"
    coverage_pct: float = Field(default=0, ge=0, le=100)
    vintage: str = ""
    evidence: str = ""
    reason: str = ""
    required: bool = True


class CoverageReport(BaseModel):
    """The coverage states for one fetch plan.

    Parameters
    ----------
    schema_version : {"brushline.coverage.v1"}
        Report schema version.
    plan_id : str
        Fetch plan identifier.
    created_utc : datetime
        Timezone-aware creation time.
    aoi : str
        Area-of-interest reference.
    entries : list of CoverageEntry
        Coverage entries.
    notes : str, optional
        Human notes.
    """

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["brushline.coverage.v1"] = COVERAGE_SCHEMA_VERSION
    plan_id: str = Field(min_length=1)
    created_utc: datetime
    aoi: str = Field(min_length=1)
    entries: list[CoverageEntry] = Field(default_factory=list)
    notes: str = ""


class GapRecord(BaseModel):
    """One non-observed coverage gap and its next action.

    Parameters
    ----------
    gap_id : str
        Stable gap identifier.
    source_id : str
        Source or connector id.
    target_id : str
        Segment, span, or ``aoi`` target.
    state : str
        Coverage state that created the gap.
    decision : str
        ``stop`` or ``continue_with_caveat``.
    recommended_action : str
        Next action.
    reason : str
        Why the gap exists.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    gap_id: str = Field(min_length=1)
    source_id: str = Field(min_length=1)
    target_id: str = Field(min_length=1)
    state: str
    decision: str
    recommended_action: str = Field(min_length=1)
    reason: str = ""


class GapReport(BaseModel):
    """The gap summary and stop/continue decision.

    Parameters
    ----------
    schema_version : {"brushline.gap-report.v1"}
        Report schema version.
    plan_id : str
        Fetch plan identifier.
    created_utc : datetime
        Timezone-aware creation time.
    decision : str
        ``stop``, ``continue``, or ``continue_with_caveat``.
    next_action : str
        The first recommended action, or ``none``.
    gaps : list of GapRecord
        Non-observed coverage entries.
    """

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["brushline.gap-report.v1"] = GAP_REPORT_SCHEMA_VERSION
    plan_id: str = Field(min_length=1)
    created_utc: datetime
    decision: str = "continue"
    next_action: str = "none"
    gaps: list[GapRecord] = Field(default_factory=list)


def default_estimate(access_method: str) -> FetchEstimate:
    """Return the deterministic planning estimate for an access method.

    These are planning placeholders, not measurements. A user estimate overrides them in a
    ``FetchRequest``.

    Parameters
    ----------
    access_method : str
        Catalogue access method.

    Returns
    -------
    FetchEstimate
        Size, time, and basis.
    """
    size, seconds, basis = DEFAULT_ESTIMATES.get(access_method, (0.0, 0.0, "unknown"))
    return FetchEstimate(size_mb=size, seconds=seconds, basis=basis)


def plan_fetch(
    catalogue: DataCatalogue,
    request: FetchRequest,
    *,
    plan_id: str = "fetch-plan",
    created_utc: datetime | None = None,
) -> FetchPlan:
    """Build a plan-only fetch preview from the catalogue.

    The function resolves source and connector metadata and copies it into the plan. It does not
    fetch, test a connection, or read a secret. Unknown ids raise
    :class:`brushline.integrations.catalogue.UnknownCatalogueReferenceError`.

    Parameters
    ----------
    catalogue : DataCatalogue
        Catalogue and connector registry.
    request : FetchRequest
        Requested sources, connectors, estimates, and approvals.
    plan_id : str, optional
        Plan identifier. Defaults to ``fetch-plan``.
    created_utc : datetime, optional
        Creation time. Defaults to the current UTC time.

    Returns
    -------
    FetchPlan
        Plan-only preview with size and time estimates.

    Raises
    ------
    UnknownCatalogueReferenceError
        When a requested source or connector is not registered.
    """
    items: list[FetchItem] = [
        _source_item(catalogue, source_id, request) for source_id in request.source_ids
    ]
    items.extend(
        _connector_item(catalogue, connector_id, request) for connector_id in request.connector_ids
    )
    return FetchPlan(
        plan_id=plan_id,
        created_utc=created_utc or datetime.now(UTC),
        aoi=request.aoi,
        items=items,
    )


def validate_fetch_plan(
    plan: FetchPlan,
    catalogue: DataCatalogue | None = None,
) -> ContractValidation:
    """Validate a fetch plan without fetching.

    Parameters
    ----------
    plan : FetchPlan
        Plan to validate.
    catalogue : DataCatalogue, optional
        Catalogue used to check source, connector, and approval references.

    Returns
    -------
    ContractValidation
        Errors, warnings, and counts.
    """
    errors: list[str] = []
    warnings: list[str] = []
    check_duplicates(
        "FETCH",
        "item",
        [f"{item.kind}:{item.reference_id}" for item in plan.items],
        errors,
    )
    if plan.created_utc.tzinfo is None:
        errors.append("FETCH-TIME: created_utc is not timezone-aware")
    for item in plan.items:
        if item.kind not in FETCH_KINDS:
            errors.append(f"FETCH-KIND: item {item.reference_id} has unknown kind {item.kind!r}")
        if not item.licence.strip():
            errors.append(f"FETCH-LICENCE: item {item.reference_id} has no licence")
        if item.classification not in CLASSIFICATIONS:
            errors.append(
                f"FETCH-CLASSIFICATION: item {item.reference_id} has unknown classification "
                f"{item.classification!r}"
            )
        if item.access_status not in FETCH_ACCESS_STATUSES:
            errors.append(
                f"FETCH-ACCESS: item {item.reference_id} has unknown access status "
                f"{item.access_status!r}"
            )
        if item.estimated_size_mb < 0 or item.estimated_seconds < 0:
            errors.append(f"FETCH-ESTIMATE: item {item.reference_id} has a negative estimate")
        if item.materialization not in MATERIALIZATION_TARGETS:
            errors.append(
                f"FETCH-MATERIALIZATION: item {item.reference_id} has unknown target "
                f"{item.materialization!r}"
            )
        elif not _pointer_matches(item.materialization, item.materialization_pointer):
            errors.append(
                f"FETCH-MATERIALIZATION: item {item.reference_id} pointer does not match "
                f"{item.materialization}"
            )
        if item.bulk:
            if item.approval is None:
                errors.append(f"FETCH-APPROVAL: bulk item {item.reference_id} has no approval")
            elif item.approval.scope != "bulk":
                errors.append(
                    f"FETCH-APPROVAL: bulk item {item.reference_id} approval scope is "
                    f"{item.approval.scope!r}, expected bulk"
                )
        if item.approval is not None:
            errors.extend(_approval_errors(item.reference_id, item.approval))
        if (
            item.approval is None
            and not item.bulk
            and item.materialization not in ("not_materialized", "owner_store")
        ):
            warnings.append(
                f"FETCH-APPROVAL: item {item.reference_id} is plan-only without an approval"
            )
        if item.access_status in ("request", "unknown", "unavailable", "blocked"):
            warnings.append(f"FETCH-ACCESS: item {item.reference_id} is {item.access_status}")
        if catalogue is not None:
            errors.extend(_catalogue_errors(item, catalogue))
    if not plan.items:
        warnings.append("FETCH-EMPTY: the plan has no items")
    counts: dict[str, int | float] = {
        "items": len(plan.items),
        "sources": sum(1 for item in plan.items if item.kind == "source"),
        "connectors": sum(1 for item in plan.items if item.kind == "connector"),
        "bulk_items": sum(1 for item in plan.items if item.bulk),
        "estimated_size_mb": plan.total_size_mb,
        "estimated_seconds": plan.total_seconds,
    }
    return ContractValidation(tuple(errors), tuple(warnings), counts)


def file_sha256(path: Path) -> str:
    """Return the SHA-256 digest of a file.

    Parameters
    ----------
    path : Path
        File to hash.

    Returns
    -------
    str
        Lowercase hexadecimal SHA-256 digest.
    """
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_materialization(
    manifest: MaterializationManifest,
    root: Path | None = None,
) -> ContractValidation:
    """Validate checksums, sizes, licences, pointers, and path containment.

    A materialized item with a checksum, size, or containment mismatch fails. The caller should
    stop materialization when ``is_valid`` is false.

    Parameters
    ----------
    manifest : MaterializationManifest
        Manifest to validate.
    root : Path, optional
        Workspace root used to resolve relative paths and verify files.

    Returns
    -------
    ContractValidation
        Errors, warnings, and counts.
    """
    errors: list[str] = []
    warnings: list[str] = []
    check_duplicates("MATERIALIZATION", "item", [item.id for item in manifest.items], errors)
    if manifest.created_utc.tzinfo is None:
        errors.append("MATERIALIZATION-TIME: created_utc is not timezone-aware")
    root_resolved = root.resolve() if root is not None else None
    for item in manifest.items:
        if item.status not in MATERIALIZATION_STATUSES:
            errors.append(
                f"MATERIALIZATION-STATUS: item {item.id} has unknown status {item.status!r}"
            )
        if item.pointer and not any(
            item.pointer.startswith(f"{target}:")
            for target in MATERIALIZATION_TARGETS
            if target != "not_materialized"
        ):
            errors.append(f"MATERIALIZATION-POINTER: item {item.id} has an unknown pointer")
        if item.sha256 and not SHA256_PATTERN.fullmatch(item.sha256):
            errors.append(f"MATERIALIZATION-CHECKSUM: item {item.id} has an invalid sha256")
        if item.retrieved_utc is not None and item.retrieved_utc.tzinfo is None:
            errors.append(
                f"MATERIALIZATION-TIME: item {item.id} retrieval time is not timezone-aware"
            )
        if item.status == "materialized":
            if not item.path:
                errors.append(f"MATERIALIZATION-PATH: item {item.id} has no path")
            if not item.sha256:
                errors.append(f"MATERIALIZATION-CHECKSUM: item {item.id} has no checksum")
            if not item.licence.strip():
                errors.append(f"MATERIALIZATION-LICENCE: item {item.id} has no licence")
            if item.retrieved_utc is None:
                errors.append(f"MATERIALIZATION-TIME: item {item.id} has no retrieval time")
            if not item.pointer:
                errors.append(f"MATERIALIZATION-POINTER: item {item.id} has no pointer")
        elif not item.reason.strip():
            errors.append(f"MATERIALIZATION-REASON: item {item.id} has no reason")
        if not item.path:
            continue
        try:
            ensure_relative_path(item.path, "materialization path")
        except ValueError as exc:
            errors.append(f"MATERIALIZATION-PATH: item {item.id}: {exc}")
            continue
        if root_resolved is None:
            continue
        candidate = (root_resolved / item.path).resolve()
        if not candidate.is_relative_to(root_resolved):
            errors.append(
                f"MATERIALIZATION-PATH: item {item.id} resolves outside the workspace root"
            )
            continue
        if item.status != "materialized":
            continue
        if not candidate.is_file():
            errors.append(f"MATERIALIZATION-PATH: item {item.id} file does not exist")
            continue
        actual_size = candidate.stat().st_size
        if actual_size != item.size_bytes:
            errors.append(
                f"MATERIALIZATION-SIZE: item {item.id} size is {actual_size}, "
                f"expected {item.size_bytes}"
            )
        if file_sha256(candidate) != item.sha256:
            errors.append(f"MATERIALIZATION-CHECKSUM: item {item.id} checksum does not match")
    if not manifest.items:
        warnings.append("MATERIALIZATION-EMPTY: the manifest has no items")
    counts: dict[str, int | float] = {
        "items": len(manifest.items),
        "materialized": sum(1 for item in manifest.items if item.status == "materialized"),
        "missing": sum(1 for item in manifest.items if item.status == "missing"),
    }
    return ContractValidation(tuple(errors), tuple(warnings), counts)


def materialization_decision(
    manifest: MaterializationManifest,
    root: Path | None = None,
) -> str:
    """Return the materialization decision.

    Parameters
    ----------
    manifest : MaterializationManifest
        Manifest to validate.
    root : Path, optional
        Workspace root used for file checks.

    Returns
    -------
    str
        ``continue`` when the manifest is valid, otherwise ``stop``.
    """
    return "continue" if validate_materialization(manifest, root).is_valid else "stop"


def validate_coverage(report: CoverageReport) -> ContractValidation:
    """Validate coverage states and their evidence.

    Parameters
    ----------
    report : CoverageReport
        Coverage report to validate.

    Returns
    -------
    ContractValidation
        Errors, warnings, and counts.
    """
    errors: list[str] = []
    warnings: list[str] = []
    check_duplicates(
        "COVERAGE",
        "entry",
        [f"{entry.source_id}:{entry.target_id}" for entry in report.entries],
        errors,
    )
    if report.created_utc.tzinfo is None:
        errors.append("COVERAGE-TIME: created_utc is not timezone-aware")
    for entry in report.entries:
        if entry.state not in COVERAGE_STATES:
            errors.append(
                f"COVERAGE-STATE: {entry.source_id}:{entry.target_id} has unknown state "
                f"{entry.state!r}"
            )
            continue
        if entry.state == "observed":
            if entry.coverage_pct <= 0:
                errors.append(
                    f"COVERAGE-STATE: {entry.source_id}:{entry.target_id} is observed with "
                    "zero coverage"
                )
            if not entry.evidence.strip():
                errors.append(
                    f"COVERAGE-EVIDENCE: {entry.source_id}:{entry.target_id} is observed "
                    "without evidence"
                )
        elif entry.state == "partial":
            if not 0 < entry.coverage_pct < 100:
                errors.append(
                    f"COVERAGE-PARTIAL: {entry.source_id}:{entry.target_id} must be between "
                    "0 and 100 percent"
                )
            if not entry.evidence.strip():
                errors.append(
                    f"COVERAGE-EVIDENCE: {entry.source_id}:{entry.target_id} is partial "
                    "without evidence"
                )
        elif entry.state == "stale":
            if not entry.evidence.strip() or not entry.vintage.strip():
                errors.append(
                    f"COVERAGE-STALE: {entry.source_id}:{entry.target_id} needs evidence "
                    "and a vintage"
                )
        elif entry.state == "missing":
            if entry.coverage_pct != 0:
                errors.append(
                    f"COVERAGE-MISSING: {entry.source_id}:{entry.target_id} must have zero coverage"
                )
            if not entry.reason.strip():
                errors.append(f"COVERAGE-REASON: {entry.source_id}:{entry.target_id} has no reason")
        elif not entry.reason.strip():
            errors.append(f"COVERAGE-REASON: {entry.source_id}:{entry.target_id} has no reason")
    if not report.entries:
        warnings.append("COVERAGE-EMPTY: the report has no entries")
    counts = coverage_counts(report)
    return ContractValidation(tuple(errors), tuple(warnings), counts)


def coverage_counts(report: CoverageReport) -> dict[str, int | float]:
    """Count coverage states in a report.

    Parameters
    ----------
    report : CoverageReport
        Coverage report.

    Returns
    -------
    dict of str to int or float
        Counts for each state plus ``total``.
    """
    counts: dict[str, int | float] = dict.fromkeys(COVERAGE_STATES, 0)
    for entry in report.entries:
        if entry.state in counts:
            counts[entry.state] += 1
    counts["total"] = len(report.entries)
    return counts


def build_gap_report(coverage: CoverageReport) -> GapReport:
    """Turn non-observed coverage entries into gaps and a decision.

    A required missing or out-of-domain source stops the build. A stale, partial, excluded, or
    optional gap continues with a caveat. The gap report never imputes coverage.

    Parameters
    ----------
    coverage : CoverageReport
        Coverage report.

    Returns
    -------
    GapReport
        Gaps, the overall decision, and the next action.
    """
    gaps: list[GapRecord] = []
    for entry in coverage.entries:
        if entry.state == "observed":
            continue
        if entry.state in ("missing", "out_of_domain") and entry.required:
            decision = "stop"
        else:
            decision = "continue_with_caveat"
        gaps.append(
            GapRecord(
                gap_id=f"{entry.source_id}:{entry.target_id}",
                source_id=entry.source_id,
                target_id=entry.target_id,
                state=entry.state,
                decision=decision,
                recommended_action=GAP_ACTIONS.get(
                    entry.state,
                    "review the coverage state",
                ),
                reason=entry.reason,
            )
        )
    if any(gap.decision == "stop" for gap in gaps):
        decision = "stop"
    elif gaps:
        decision = "continue_with_caveat"
    else:
        decision = "continue"
    return GapReport(
        plan_id=coverage.plan_id,
        created_utc=coverage.created_utc,
        decision=decision,
        next_action=gaps[0].recommended_action if gaps else "none",
        gaps=gaps,
    )


def validate_gap_report(report: GapReport) -> ContractValidation:
    """Validate gap records, the stop/continue decision, and the next action.

    Parameters
    ----------
    report : GapReport
        Gap report to validate.

    Returns
    -------
    ContractValidation
        Errors, warnings, and counts.
    """
    errors: list[str] = []
    warnings: list[str] = []
    check_duplicates("GAP", "gap", [gap.gap_id for gap in report.gaps], errors)
    if report.created_utc.tzinfo is None:
        errors.append("GAP-TIME: created_utc is not timezone-aware")
    if report.decision not in GAP_DECISIONS:
        errors.append(f"GAP-DECISION: unknown decision {report.decision!r}")
    if not report.next_action.strip():
        errors.append("GAP-ACTION: next_action is empty")
    for gap in report.gaps:
        if gap.decision not in ("stop", "continue_with_caveat"):
            errors.append(f"GAP-DECISION: {gap.gap_id} has unknown decision {gap.decision!r}")
        if gap.state not in COVERAGE_STATES:
            errors.append(f"GAP-STATE: {gap.gap_id} has unknown state {gap.state!r}")
    if report.decision == "stop" and not any(gap.decision == "stop" for gap in report.gaps):
        errors.append("GAP-DECISION: stop has no stopping gap")
    if report.decision == "continue" and report.gaps:
        errors.append("GAP-DECISION: continue has gaps")
    if report.decision == "continue_with_caveat" and any(
        gap.decision == "stop" for gap in report.gaps
    ):
        errors.append("GAP-DECISION: continue_with_caveat has a stopping gap")
    if any(gap.decision == "continue_with_caveat" for gap in report.gaps):
        warnings.append("GAP-CAVEAT: the build continues with an unresolved gap")
    counts: dict[str, int | float] = {
        "gaps": len(report.gaps),
        "stop": sum(1 for gap in report.gaps if gap.decision == "stop"),
        "continue_with_caveat": sum(
            1 for gap in report.gaps if gap.decision == "continue_with_caveat"
        ),
    }
    return ContractValidation(tuple(errors), tuple(warnings), counts)


def _source_item(
    catalogue: DataCatalogue,
    source_id: str,
    request: FetchRequest,
) -> FetchItem:
    source = resolve_source(catalogue, source_id)
    estimate = request.estimates.get(source.id) or default_estimate(source.access_method)
    materialization = _materialization_for(source.access_method)
    return FetchItem(
        kind="source",
        reference_id=source.id,
        query=request.queries.get(source.id, source.query),
        licence=source.licence,
        access_status=source.access_status,
        classification=source.classification,
        estimated_size_mb=estimate.size_mb,
        estimated_seconds=estimate.seconds,
        estimate_basis=estimate.basis,
        bulk=request.bulk,
        approval=request.approvals.get(source.id),
        materialization=materialization,
        materialization_pointer=_pointer(materialization, source.id),
        required=source.id not in request.optional_ids,
    )


def _connector_item(
    catalogue: DataCatalogue,
    connector_id: str,
    request: FetchRequest,
) -> FetchItem:
    connector = resolve_connector(catalogue, connector_id)
    estimate = request.estimates.get(connector.id) or FetchEstimate(
        size_mb=0,
        seconds=0,
        basis="owner_side",
    )
    return FetchItem(
        kind="connector",
        reference_id=connector.id,
        query=request.queries.get(
            connector.id,
            f"read scope: {', '.join(connector.read_scope.tables)}",
        ),
        licence=(
            connector.approval.data_sharing_record
            if connector.approval is not None
            else "owner data-sharing record"
        ),
        access_status="available" if connector.approved else "blocked",
        classification=connector.classification,
        estimated_size_mb=estimate.size_mb,
        estimated_seconds=estimate.seconds,
        estimate_basis=estimate.basis,
        bulk=request.bulk,
        approval=request.approvals.get(connector.id),
        materialization="owner_store",
        materialization_pointer=f"owner_store:{connector.id}",
        required=connector.id not in request.optional_ids,
    )


def _materialization_for(access_method: str) -> str:
    if access_method in ("bulk_download", "stac"):
        return "data_lad"
    if access_method in ("wms", "wfs", "api", "rest"):
        return "public_mirror"
    return "not_materialized"


def _pointer(materialization: str, reference_id: str) -> str:
    if materialization == "not_materialized":
        return ""
    return f"{materialization}:inputs/{reference_id}"


def _pointer_matches(materialization: str, pointer: str) -> bool:
    if materialization == "not_materialized":
        return pointer == ""
    return pointer.startswith(f"{materialization}:")


def _approval_errors(reference_id: str, approval: FetchApproval) -> list[str]:
    errors: list[str] = []
    if not approval.approved_by.strip():
        errors.append(f"FETCH-APPROVAL: item {reference_id} approval has no approver")
    if not approval.record.strip():
        errors.append(f"FETCH-APPROVAL: item {reference_id} approval has no record")
    if approval.approved_utc.tzinfo is None:
        errors.append(f"FETCH-APPROVAL: item {reference_id} approval time is not timezone-aware")
    if approval.scope not in ("single", "bulk"):
        errors.append(
            f"FETCH-APPROVAL: item {reference_id} has unknown approval scope {approval.scope!r}"
        )
    return errors


def _catalogue_errors(item: FetchItem, catalogue: DataCatalogue) -> list[str]:
    errors: list[str] = []
    if item.kind == "source":
        try:
            source = resolve_source(catalogue, item.reference_id)
        except UnknownCatalogueReferenceError:
            return [f"FETCH-SOURCE: item {item.reference_id} is not registered"]
        if source.licence != item.licence:
            errors.append(f"FETCH-DRIFT: source {item.reference_id} licence changed since planning")
    elif item.kind == "connector":
        try:
            connector = resolve_connector(catalogue, item.reference_id)
        except UnknownCatalogueReferenceError:
            return [f"FETCH-CONNECTOR: item {item.reference_id} is not registered"]
        if not connector.approved:
            errors.append(
                f"FETCH-CONNECTOR: connector {item.reference_id} is not approved by its owner"
            )
        if connector.classification != item.classification:
            errors.append(
                f"FETCH-DRIFT: connector {item.reference_id} classification changed since planning"
            )
    return errors


__all__ = [
    "COVERAGE_SCHEMA_VERSION",
    "COVERAGE_STATES",
    "FETCH_ACCESS_STATUSES",
    "FETCH_KINDS",
    "FETCH_PLAN_SCHEMA_VERSION",
    "GAP_DECISIONS",
    "GAP_REPORT_SCHEMA_VERSION",
    "MATERIALIZATION_SCHEMA_VERSION",
    "MATERIALIZATION_STATUSES",
    "MATERIALIZATION_TARGETS",
    "CoverageEntry",
    "CoverageReport",
    "FetchApproval",
    "FetchEstimate",
    "FetchItem",
    "FetchPlan",
    "FetchRequest",
    "GapRecord",
    "GapReport",
    "MaterializationManifest",
    "MaterializedItem",
    "build_gap_report",
    "coverage_counts",
    "default_estimate",
    "file_sha256",
    "materialization_decision",
    "plan_fetch",
    "validate_coverage",
    "validate_fetch_plan",
    "validate_gap_report",
    "validate_materialization",
]
