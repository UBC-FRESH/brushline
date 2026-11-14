"""Run contract: the manifest of one build, simulation, plan, or demo run.

A run directory contains ``run.json`` and the artifacts it names. The manifest records the run
type, the data and model versions, the configuration, the seed, the status, and the artifact index.
An artifact that is not available must say why.
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

RUN_SCHEMA_VERSION: Literal["brushline.run.v1"] = "brushline.run.v1"
RUN_TYPES: tuple[str, ...] = ("build", "simulate", "plan", "monitor", "compare", "demo")
RUN_STATUSES: tuple[str, ...] = ("running", "complete", "failed")

RunType = Literal["build", "simulate", "plan", "monitor", "compare", "demo"]
RunStatus = Literal["running", "complete", "failed"]


class RunArtifact(BaseModel):
    """One artifact in a run directory.

    Parameters
    ----------
    name : str
        Stable artifact name, such as ``plan`` or ``pareto``.
    path : str
        Run-relative path.
    schema_version : str
        Artifact schema version.
    media_type : str
        Media type, such as ``application/json`` or ``text/csv``.
    available : bool
        Whether the artifact exists and is usable.
    sha256 : str or None, optional
        SHA-256 of the artifact file. Required when ``available`` is true.
    reason : str or None, optional
        Why the artifact is unavailable. Required when ``available`` is false.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str = Field(min_length=1)
    path: str = Field(min_length=1)
    schema_version: str = Field(min_length=1)
    media_type: str = Field(min_length=1)
    available: bool = True
    sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    reason: str | None = None

    @field_validator("path")
    @classmethod
    def _relative_path(cls, value: str) -> str:
        return ensure_relative_path(value, "artifact path")

    @model_validator(mode="after")
    def _availability_is_explained(self) -> RunArtifact:
        if self.available and self.sha256 is None:
            raise ValueError("an available artifact needs a sha256")
        if not self.available and not self.reason:
            raise ValueError("an unavailable artifact needs a reason")
        return self


class RunManifest(BaseModel):
    """The manifest of one run.

    Parameters
    ----------
    run_id : str
        Stable run identifier.
    run_type : {"build", "simulate", "plan", "monitor", "compare", "demo"}
        Run type.
    status : {"running", "complete", "failed"}
        Run status.
    created_utc : datetime
        Timezone-aware creation time.
    data_version : str
        Dataset version or digest.
    model_versions : dict of str to str
        Model ids and versions.
    configuration : dict of str to object
        Run configuration.
    artifacts : list of RunArtifact
        Artifact index. At least one is required.
    created_by : str
        Person, process, or agent that created the run.
    seed : int or None, optional
        Random seed.
    summary : dict of str to object, optional
        Run summary.
    """

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["brushline.run.v1"] = RUN_SCHEMA_VERSION
    run_id: str = Field(min_length=1)
    run_type: RunType
    status: RunStatus
    created_utc: datetime
    data_version: str = Field(min_length=1)
    model_versions: dict[str, str] = Field(min_length=1)
    configuration: dict[str, object] = Field(default_factory=dict)
    artifacts: list[RunArtifact] = Field(min_length=1)
    created_by: str = Field(min_length=1)
    seed: int | None = None
    summary: dict[str, object] = Field(default_factory=dict)

    @field_validator("created_utc")
    @classmethod
    def _timezone_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("created_utc must be timezone-aware")
        return value


def validate_run_manifest(manifest: RunManifest) -> ContractValidation:
    """Validate run artifact names, status, and availability.

    Parameters
    ----------
    manifest : RunManifest
        Run manifest to validate.

    Returns
    -------
    ContractValidation
        Errors, warnings, and counts.
    """
    errors: list[str] = []
    warnings: list[str] = []
    check_duplicates("RUN", "artifact", [item.name for item in manifest.artifacts], errors)
    available = [item for item in manifest.artifacts if item.available]
    if manifest.status == "complete" and not available:
        warnings.append("RUN-ARTIFACT: a complete run has no available artifact")
    if manifest.status == "failed" and available:
        warnings.append("RUN-ARTIFACT: a failed run still has an available artifact")
    for artifact in manifest.artifacts:
        if not artifact.available and artifact.reason is None:
            errors.append(f"RUN-ARTIFACT: artifact {artifact.name} has no reason")
    counts: dict[str, int | float] = {
        "artifacts": len(manifest.artifacts),
        "available_artifacts": len(available),
    }
    return ContractValidation(tuple(errors), tuple(warnings), counts)


__all__ = [
    "RUN_SCHEMA_VERSION",
    "RUN_STATUSES",
    "RUN_TYPES",
    "RunArtifact",
    "RunManifest",
    "validate_run_manifest",
]
