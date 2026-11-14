"""Multi-objective archive, scalarization portfolio, diversity, and promotion.

The archive keeps only feasible, non-dominated search results. It deduplicates identical objective
vectors, records crowding distance, evicts the most crowded members deterministically when the size
cap is exceeded, and writes a validated ``brushline.pareto.v1`` document.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, model_validator

from brushline.model.archive import (
    ArchiveMember,
    Objective,
    ParetoArchive,
    Scalarization,
    dominates,
    validate_pareto_archive,
)
from brushline.model.validation import ContractValidation, ensure_relative_path
from brushline.optimization.adapter import (
    SCALARIZATIONS,
    SearchRun,
)

ARCHIVE_SCHEMA_VERSION = "brushline.optimization-archive.v1"
PROMOTION_SCHEMA_VERSION = "brushline.promotion.v1"
ARCHIVE_OBJECTIVES: tuple[Objective, ...] = (
    Objective(name="present_cost", direction="minimize", unit="CAD"),
    Objective(name="service_risk", direction="minimize", unit="index"),
    Objective(name="service_attainment", direction="maximize", unit="fraction"),
    Objective(name="uncertainty", direction="minimize", unit="index"),
)
DEFAULT_EVICTION = "crowding-distance-v1"
BOUNDARY_CROWDING = 1.0e9


class ArchiveError(ValueError):
    """Raised when archive inputs or promotion requests are inconsistent."""


class ArchiveConfig(BaseModel):
    """Archive build settings.

    Parameters
    ----------
    max_size : int
        Maximum archive members.
    eviction : str
        Eviction policy name.
    created_by : str
        Archive creator.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    max_size: int = Field(default=50, ge=1)
    eviction: str = Field(default=DEFAULT_EVICTION, min_length=1)
    created_by: str = Field(default="brushline.optimization.pareto", min_length=1)


class ArchiveResult(BaseModel):
    """The archive and the decisions that produced it.

    Parameters
    ----------
    archive : ParetoArchive
        Validated archive.
    duplicates : list of str
        Plan ids removed as duplicate objective vectors.
    evicted : list of str
        Plan ids removed by the diversity cap.
    rejected_infeasible : list of str
        Plan ids excluded because they were infeasible.
    crowding : dict of str to float
        Crowding distance by plan id.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    archive: ParetoArchive
    duplicates: list[str] = Field(default_factory=list)
    evicted: list[str] = Field(default_factory=list)
    rejected_infeasible: list[str] = Field(default_factory=list)
    crowding: dict[str, float] = Field(default_factory=dict)


class PromotionRecord(BaseModel):
    """One archive member promoted to a plan version.

    Parameters
    ----------
    schema_version : {"brushline.promotion.v1"}
        Schema version.
    promotion_id : str
        Promotion id.
    plan_id : str
        Promoted archive plan.
    parent_plan_id : str or None
        Prior plan version.
    reason : str
        Promotion reason.
    objective : dict of str to float
        Objective vector.
    created_utc : datetime
        Timezone-aware creation time.
    created_by : str
        Promoter.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = PROMOTION_SCHEMA_VERSION
    promotion_id: str = Field(min_length=1)
    plan_id: str = Field(min_length=1)
    parent_plan_id: str | None = None
    reason: str = Field(min_length=1)
    objective: dict[str, float]
    created_utc: datetime
    created_by: str = Field(min_length=1)

    @model_validator(mode="after")
    def _promotion(self) -> PromotionRecord:
        if self.parent_plan_id == self.plan_id:
            raise ValueError("a promotion cannot parent itself")
        if self.created_utc.tzinfo is None:
            raise ValueError("created_utc must be timezone-aware")
        return self


def archive_scalarizations() -> list[Scalarization]:
    """Return the adapter scalarization portfolio in archive form.

    Returns
    -------
    list of Scalarization
        Five scalarizations with weights that sum to one.
    """
    return [
        Scalarization(
            scalarization_id=item.name,
            weights=dict(item.weights),
            description=f"Brushline {item.name} scalarization",
        )
        for item in SCALARIZATIONS
    ]


def build_archive(
    runs: list[SearchRun],
    *,
    instance_id: str | None = None,
    run_id: str | None = None,
    config: ArchiveConfig | None = None,
    created_utc: datetime | None = None,
    scalarizations: list[Scalarization] | None = None,
) -> ArchiveResult:
    """Build a non-dominated archive from exact search runs.

    Parameters
    ----------
    runs : list of SearchRun
        Replayable search results.
    instance_id : str or None, optional
        Instance id. Defaults to the first run's instance.
    run_id : str or None, optional
        Run id. Defaults to the instance id.
    config : ArchiveConfig, optional
        Archive settings.
    created_utc : datetime, optional
        Creation time. Defaults to now.
    scalarizations : list of Scalarization, optional
        Archive scalarizations. Defaults to the five adapter scalarizations.

    Returns
    -------
    ArchiveResult
        Validated archive and build decisions.

    Raises
    ------
    ArchiveError
        When runs are empty or span multiple instances.
    """
    if not runs:
        raise ArchiveError("at least one search run is required")
    rules = config or ArchiveConfig()
    names = {run.instance_id for run in runs}
    if instance_id is not None:
        names.add(instance_id)
    if len(names) != 1:
        raise ArchiveError("all search runs must use one instance id")
    resolved_instance = instance_id or runs[0].instance_id
    resolved_run = run_id or resolved_instance
    created = created_utc or datetime.now(UTC)
    duplicates: list[str] = []
    rejected: list[str] = []
    selected: list[ArchiveMember] = []
    seen: set[tuple[float, ...]] = set()
    for index, run in enumerate(runs):
        plan_id = _plan_id(run, index)
        if not run.feasible:
            rejected.append(plan_id)
            continue
        vector = tuple(run.objective_vector[name] for name in _objective_names())
        if vector in seen:
            duplicates.append(plan_id)
            continue
        seen.add(vector)
        selected.append(
            ArchiveMember(
                plan_id=plan_id,
                plan_path=ensure_relative_path(f"plans/{plan_id}.json", "plan path"),
                objective=dict(run.objective_vector),
                feasible=True,
                seed=run.seed,
                evidence_path=ensure_relative_path(f"evidence/{plan_id}.json", "evidence path"),
                budget=run.budget,
                metadata={
                    "mode": run.mode,
                    "adapter": run.adapter,
                    "scalarization": _scalarization_name(run),
                    "source_run": run.instance_id,
                },
            )
        )
    non_dominated = _non_dominated(selected)
    crowding = _crowding(non_dominated)
    evicted: list[str] = []
    if len(non_dominated) > rules.max_size:
        keep = sorted(
            non_dominated,
            key=lambda item: (-crowding[item.plan_id], item.plan_id),
        )[: rules.max_size]
        keep_ids = {item.plan_id for item in keep}
        evicted = sorted(item.plan_id for item in non_dominated if item.plan_id not in keep_ids)
        non_dominated = sorted(keep, key=lambda item: item.plan_id)
    members = [
        member.model_copy(
            update={
                "metadata": {
                    **member.metadata,
                    "crowding_distance": crowding[member.plan_id],
                }
            }
        )
        for member in non_dominated
    ]
    archive = ParetoArchive(
        instance_id=resolved_instance,
        run_id=resolved_run,
        objectives=list(ARCHIVE_OBJECTIVES),
        scalarizations=scalarizations or archive_scalarizations(),
        members=members,
        eviction=rules.eviction,
        created_utc=created,
        created_by=rules.created_by,
    )
    validation = validate_pareto_archive(archive)
    if not validation.is_valid:
        raise ArchiveError("; ".join(validation.errors))
    return ArchiveResult(
        archive=archive,
        duplicates=duplicates,
        evicted=evicted,
        rejected_infeasible=rejected,
        crowding={member.plan_id: crowding[member.plan_id] for member in members},
    )


def _objective_names() -> tuple[str, ...]:
    return tuple(objective.name for objective in ARCHIVE_OBJECTIVES)


def _scalarization_name(run: SearchRun) -> str:
    metadata = run.evidence.get("metadata", {})
    if isinstance(metadata, dict):
        return str(metadata.get("scalarization", "unknown"))
    return "unknown"


def _plan_id(run: SearchRun, index: int) -> str:
    return f"{run.mode}-{_scalarization_name(run)}-{run.seed}-{index:03d}"


def _non_dominated(members: list[ArchiveMember]) -> list[ArchiveMember]:
    candidates = sorted(members, key=lambda item: item.plan_id)
    kept: list[ArchiveMember] = []
    for candidate in candidates:
        if any(dominates(existing, candidate, list(ARCHIVE_OBJECTIVES)) for existing in kept):
            continue
        kept = [
            existing
            for existing in kept
            if not dominates(candidate, existing, list(ARCHIVE_OBJECTIVES))
        ]
        kept.append(candidate)
    return sorted(kept, key=lambda item: item.plan_id)


def _crowding(members: list[ArchiveMember]) -> dict[str, float]:
    if not members:
        return {}
    if len(members) == 1:
        return {members[0].plan_id: 0.0}
    distances = {member.plan_id: 0.0 for member in members}
    for objective in ARCHIVE_OBJECTIVES:
        ordered = sorted(
            members,
            key=lambda item: (
                -item.objective[objective.name]
                if objective.direction == "maximize"
                else item.objective[objective.name],
                item.plan_id,
            ),
        )
        values = [member.objective[objective.name] for member in ordered]
        low = min(values)
        high = max(values)
        distances[ordered[0].plan_id] = BOUNDARY_CROWDING
        distances[ordered[-1].plan_id] = BOUNDARY_CROWDING
        span = high - low
        if span <= 0:
            continue
        for index in range(1, len(ordered) - 1):
            distances[ordered[index].plan_id] += (
                abs(
                    ordered[index + 1].objective[objective.name]
                    - ordered[index - 1].objective[objective.name]
                )
                / span
            )
    return distances


def _validate_promotion(record: PromotionRecord) -> ContractValidation:
    from brushline.model.validation import ContractValidation

    errors: list[str] = []
    if set(record.objective) != set(_objective_names()):
        errors.append("PROMOTION-OBJECTIVE: promotion must carry the four objectives")
    return ContractValidation(tuple(errors), (), {"objectives": len(record.objective)})


def promote_member(
    archive: ParetoArchive,
    plan_id: str,
    reason: str,
    *,
    parent_plan_id: str | None = None,
    created_by: str = "brushline.optimization.pareto",
    created_utc: datetime | None = None,
) -> PromotionRecord:
    """Promote one archive member to a plan version.

    Parameters
    ----------
    archive : ParetoArchive
        Source archive.
    plan_id : str
        Member plan id.
    reason : str
        Promotion reason.
    parent_plan_id : str or None, optional
        Prior plan version.
    created_by : str, optional
        Promoter.
    created_utc : datetime, optional
        Creation time.

    Returns
    -------
    PromotionRecord
        Promotion record.

    Raises
    ------
    ArchiveError
        When the plan is not in the archive.
    """
    member = next((item for item in archive.members if item.plan_id == plan_id), None)
    if member is None:
        raise ArchiveError(f"plan {plan_id!r} is not in the archive")
    record = PromotionRecord(
        promotion_id=f"promote-{plan_id}",
        plan_id=plan_id,
        parent_plan_id=parent_plan_id,
        reason=reason,
        objective=dict(member.objective),
        created_utc=created_utc or datetime.now(UTC),
        created_by=created_by,
    )
    validation = _validate_promotion(record)
    if not validation.is_valid:
        raise ArchiveError("; ".join(validation.errors))
    return record


def write_pareto_archive(archive: ParetoArchive, path: str | Path) -> Path:
    """Write and validate a Pareto archive as ``pareto.json``.

    Parameters
    ----------
    archive : ParetoArchive
        Archive.
    path : str or Path
        Destination.

    Returns
    -------
    Path
        Written path.

    Raises
    ------
    ArchiveError
        When the archive is invalid.
    """
    validation = validate_pareto_archive(archive)
    if not validation.is_valid:
        raise ArchiveError("; ".join(validation.errors))
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(archive.model_dump_json(indent=2) + "\n", encoding="utf-8")
    return destination


def load_pareto_archive(path: str | Path) -> ParetoArchive:
    """Load and validate a Pareto archive.

    Parameters
    ----------
    path : str or Path
        Source.

    Returns
    -------
    ParetoArchive
        Archive.

    Raises
    ------
    ArchiveError
        When the archive is invalid.
    """
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    archive = ParetoArchive.model_validate(payload)
    validation = validate_pareto_archive(archive)
    if not validation.is_valid:
        raise ArchiveError("; ".join(validation.errors))
    return archive


def write_promotion(record: PromotionRecord, path: str | Path) -> Path:
    """Write a promotion record.

    Parameters
    ----------
    record : PromotionRecord
        Promotion record.
    path : str or Path
        Destination.

    Returns
    -------
    Path
        Written path.
    """
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(record.model_dump_json(indent=2) + "\n", encoding="utf-8")
    return destination


def load_promotion(path: str | Path) -> PromotionRecord:
    """Load a promotion record.

    Parameters
    ----------
    path : str or Path
        Source.

    Returns
    -------
    PromotionRecord
        Promotion record.
    """
    return PromotionRecord.model_validate_json(Path(path).read_text(encoding="utf-8"))


__all__ = [
    "ARCHIVE_OBJECTIVES",
    "ARCHIVE_SCHEMA_VERSION",
    "DEFAULT_EVICTION",
    "PROMOTION_SCHEMA_VERSION",
    "ArchiveConfig",
    "ArchiveError",
    "ArchiveResult",
    "PromotionRecord",
    "archive_scalarizations",
    "build_archive",
    "load_pareto_archive",
    "load_promotion",
    "promote_member",
    "write_pareto_archive",
    "write_promotion",
]
