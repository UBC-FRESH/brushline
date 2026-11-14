"""Write a run manifest and its artifact index."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from brushline.model.run import RunArtifact, RunManifest, RunStatus, RunType, validate_run_manifest
from brushline.model.schema import file_sha256


@dataclass(frozen=True)
class RunArtifactSpec:
    """One artifact to include in a run manifest.

    Parameters
    ----------
    name : str
        Artifact name.
    path : str
        Run-relative path.
    schema_version : str
        Artifact schema version.
    media_type : str
        Media type.
    """

    name: str
    path: str
    schema_version: str
    media_type: str


def write_run_manifest(
    run_dir: Path,
    *,
    run_id: str,
    run_type: RunType,
    status: RunStatus,
    data_version: str,
    model_versions: dict[str, str],
    configuration: dict[str, object],
    summary: dict[str, object],
    artifacts: list[RunArtifactSpec],
    created_utc: datetime | None = None,
    seed: int | None = None,
) -> Path:
    """Write a run's ``run.json``.

    Parameters
    ----------
    run_dir : Path
        Run directory. It must already contain the artifacts.
    run_id : str
        Run identifier.
    run_type : {"build", "simulate", "plan", "monitor", "compare", "demo"}
        Run type.
    status : {"running", "complete", "failed"}
        Run status.
    data_version : str
        Dataset version or digest.
    model_versions : dict of str to str
        Model ids and versions.
    configuration : dict of str to object
        Run configuration.
    summary : dict of str to object
        Run summary.
    artifacts : list of RunArtifactSpec
        Artifacts to index.
    created_utc : datetime or None, optional
        Timezone-aware creation time. Defaults to the current UTC time.
    seed : int or None, optional
        Random seed.

    Returns
    -------
    Path
        The written ``run.json``.

    Raises
    ------
    FileNotFoundError
        When an indexed artifact is missing.
    RuntimeError
        When the manifest fails its own validator.
    """
    root = Path(run_dir).expanduser().resolve()
    records: list[RunArtifact] = []
    for spec in artifacts:
        path = root / spec.path
        if not path.is_file():
            raise FileNotFoundError(path)
        records.append(
            RunArtifact(
                name=spec.name,
                path=spec.path,
                schema_version=spec.schema_version,
                media_type=spec.media_type,
                sha256=file_sha256(path),
            )
        )
    manifest = RunManifest(
        run_id=run_id,
        run_type=run_type,
        status=status,
        created_utc=created_utc or datetime.now(UTC),
        data_version=data_version,
        model_versions=model_versions,
        configuration=configuration,
        artifacts=records,
        created_by="brushline",
        seed=seed,
        summary=summary,
    )
    report = validate_run_manifest(manifest)
    if not report.is_valid:
        raise RuntimeError("; ".join(report.errors))
    path = root / "run.json"
    path.write_text(
        json.dumps(manifest.model_dump(mode="json"), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return path


__all__ = ["RunArtifactSpec", "write_run_manifest"]
