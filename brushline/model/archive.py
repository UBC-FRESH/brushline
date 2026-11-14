"""Pareto archive contract for multi-objective searches.

The archive keeps the non-dominated plans found by a search portfolio. Each member carries its
objective vector, its plan path, its evidence record, and the seed that produced it. The validator
checks the objective definitions, the scalarization weights, the member keys, and the non-dominance
invariant.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from brushline.model.validation import (
    ContractValidation,
    check_duplicates,
    ensure_relative_path,
)

PARETO_SCHEMA_VERSION: Literal["brushline.pareto.v1"] = "brushline.pareto.v1"
OBJECTIVE_DIRECTIONS: tuple[str, ...] = ("minimize", "maximize")

ObjectiveDirection = Literal["minimize", "maximize"]


class Objective(BaseModel):
    """One objective dimension.

    Parameters
    ----------
    name : str
        Objective name.
    direction : {"minimize", "maximize"}
        Whether lower or higher is better.
    unit : str
        Unit or index label.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str = Field(min_length=1)
    direction: ObjectiveDirection
    unit: str = Field(min_length=1)


class Scalarization(BaseModel):
    """One weighted scalarization used to seed the archive.

    Parameters
    ----------
    scalarization_id : str
        Stable identifier.
    weights : dict of str to float
        Objective weights. They must be non-negative and sum to 1.
    description : str, optional
        Human description.
    """

    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)

    scalarization_id: str = Field(min_length=1)
    weights: dict[str, float] = Field(min_length=1)
    description: str = ""

    @model_validator(mode="after")
    def _weights_are_valid(self) -> Scalarization:
        if any(weight < 0 for weight in self.weights.values()):
            raise ValueError("scalarization weights must be non-negative")
        total = sum(self.weights.values())
        if abs(total - 1.0) > 1e-6:
            raise ValueError(f"scalarization weights sum to {total}, expected 1")
        return self


class ArchiveMember(BaseModel):
    """One non-dominated plan in a Pareto archive.

    Parameters
    ----------
    plan_id : str
        Plan identifier.
    plan_path : str
        Archive-relative plan path.
    objective : dict of str to float
        Objective vector. Keys must match the archive objectives.
    feasible : bool
        Whether the plan satisfies the hard constraints.
    seed : int
        Seed that produced the plan.
    evidence_path : str
        Archive-relative evidence record.
    budget : int or None, optional
        Search budget used to produce the plan.
    metadata : dict of str to object, optional
        Additional member metadata.
    """

    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)

    plan_id: str = Field(min_length=1)
    plan_path: str = Field(min_length=1)
    objective: dict[str, float] = Field(min_length=1)
    feasible: bool
    seed: int
    evidence_path: str = Field(min_length=1)
    budget: int | None = Field(default=None, ge=0)
    metadata: dict[str, object] = Field(default_factory=dict)

    @field_validator("plan_path", "evidence_path")
    @classmethod
    def _relative_path(cls, value: str) -> str:
        return ensure_relative_path(value, "archive member path")


class ParetoArchive(BaseModel):
    """The archive of non-dominated solutions from one run.

    Parameters
    ----------
    instance_id : str
        Instance identifier.
    run_id : str
        Run identifier.
    objectives : list of Objective
        Objective definitions. At least one is required.
    scalarizations : list of Scalarization
        Scalarizations used by the search portfolio.
    members : list of ArchiveMember
        Archive members.
    eviction : str
        Eviction policy, such as ``crowding-distance``.
    created_utc : datetime
        Timezone-aware creation time.
    created_by : str
        Person, process, or agent that created the archive.
    """

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["brushline.pareto.v1"] = PARETO_SCHEMA_VERSION
    instance_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    objectives: list[Objective] = Field(min_length=1)
    scalarizations: list[Scalarization] = Field(default_factory=list)
    members: list[ArchiveMember] = Field(default_factory=list)
    eviction: str = Field(min_length=1)
    created_utc: datetime
    created_by: str = Field(min_length=1)

    @field_validator("created_utc")
    @classmethod
    def _timezone_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("created_utc must be timezone-aware")
        return value


def dominates(
    left: ArchiveMember,
    right: ArchiveMember,
    objectives: list[Objective],
) -> bool:
    """Return whether one member dominates another.

    Parameters
    ----------
    left : ArchiveMember
        Candidate dominator.
    right : ArchiveMember
        Candidate dominated member.
    objectives : list of Objective
        Objective definitions.

    Returns
    -------
    bool
        ``True`` when ``left`` is at least as good on every objective and strictly better on one.
        Returns ``False`` when an objective is missing from either member.
    """
    strict = False
    for objective in objectives:
        if objective.name not in left.objective or objective.name not in right.objective:
            return False
        left_value = left.objective[objective.name]
        right_value = right.objective[objective.name]
        if objective.direction == "minimize":
            if left_value > right_value:
                return False
            if left_value < right_value:
                strict = True
        else:
            if left_value < right_value:
                return False
            if left_value > right_value:
                strict = True
    return strict


def validate_pareto_archive(archive: ParetoArchive) -> ContractValidation:
    """Validate objective definitions, scalarizations, member keys, and non-dominance.

    Parameters
    ----------
    archive : ParetoArchive
        Archive to validate.

    Returns
    -------
    ContractValidation
        Errors, warnings, and counts.
    """
    errors: list[str] = []
    warnings: list[str] = []
    check_duplicates("PARETO", "objective", [item.name for item in archive.objectives], errors)
    check_duplicates(
        "PARETO",
        "scalarization",
        [item.scalarization_id for item in archive.scalarizations],
        errors,
    )
    check_duplicates("PARETO", "member", [item.plan_id for item in archive.members], errors)
    names = {item.name for item in archive.objectives}
    for scalarization in archive.scalarizations:
        unknown = sorted(set(scalarization.weights) - names)
        for name in unknown:
            errors.append(
                f"PARETO-SCALARIZATION: {scalarization.scalarization_id} weights unknown "
                f"objective {name}"
            )
    for member in archive.members:
        missing = sorted(names - set(member.objective))
        extra = sorted(set(member.objective) - names)
        for name in missing:
            errors.append(f"PARETO-OBJECTIVE: member {member.plan_id} is missing objective {name}")
        for name in extra:
            errors.append(f"PARETO-OBJECTIVE: member {member.plan_id} has unknown objective {name}")
    for index, left in enumerate(archive.members):
        for right in archive.members[index + 1 :]:
            if dominates(left, right, archive.objectives):
                errors.append(f"PARETO-DOMINANCE: member {left.plan_id} dominates {right.plan_id}")
            elif dominates(right, left, archive.objectives):
                errors.append(f"PARETO-DOMINANCE: member {right.plan_id} dominates {left.plan_id}")
    if not archive.members:
        warnings.append("PARETO-EMPTY: the archive has no members")
    counts: dict[str, int | float] = {
        "objectives": len(archive.objectives),
        "scalarizations": len(archive.scalarizations),
        "members": len(archive.members),
    }
    return ContractValidation(tuple(errors), tuple(warnings), counts)


__all__ = [
    "OBJECTIVE_DIRECTIONS",
    "PARETO_SCHEMA_VERSION",
    "ArchiveMember",
    "Objective",
    "ParetoArchive",
    "Scalarization",
    "dominates",
    "validate_pareto_archive",
]
