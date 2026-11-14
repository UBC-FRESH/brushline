"""Demo manifest contract for the public portal.

A demo manifest describes one public example: the partner question, the data sources and licences,
the scenarios, the artifact paths, the headline metrics, the caveats, and the pilot link. The public
portal is public-data-only and read-only.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from brushline.model.validation import (
    ContractValidation,
    ensure_relative_path,
)

DEMO_SCHEMA_VERSION: Literal["brushline.demo.v1"] = "brushline.demo.v1"
DEMO_STATUSES: tuple[str, ...] = ("draft", "published", "retired")

DemoStatus = Literal["draft", "published", "retired"]


class DemoSource(BaseModel):
    """One data source used by a demo.

    Parameters
    ----------
    name : str
        Source name.
    licence : str
        Licence identifier.
    version : str
        Source version or vintage.
    url : str, optional
        Public source URL.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str = Field(min_length=1)
    licence: str = Field(min_length=1)
    version: str = Field(min_length=1)
    url: str = ""


class DemoMetric(BaseModel):
    """One headline metric for a demo.

    Parameters
    ----------
    name : str
        Metric name.
    value : float
        Metric value.
    unit : str
        Unit or index label.
    """

    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)

    name: str = Field(min_length=1)
    value: float
    unit: str = Field(min_length=1)


class DemoArtifacts(BaseModel):
    """The artifact paths for a demo.

    Parameters
    ----------
    run : str
        Run directory or manifest path.
    plan : str
        Plan path.
    reports : str
        Reports directory or index path.
    pareto : str or None, optional
        Pareto archive path.
    timeline : str or None, optional
        Operations timeline path.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    run: str = Field(min_length=1)
    plan: str = Field(min_length=1)
    reports: str = Field(min_length=1)
    pareto: str | None = None
    timeline: str | None = None

    @field_validator("run", "plan", "reports", "pareto", "timeline")
    @classmethod
    def _relative_path(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return ensure_relative_path(value, "demo artifact path")


class DemoManifest(BaseModel):
    """The manifest of one public demo.

    Parameters
    ----------
    id : str
        Lowercase demo identifier.
    title : str
        Human title.
    sector : str
        Partner sector, such as utility, pipeline, rail, or road.
    region : str
        Region label.
    aoi : str
        Demo-relative AOI path.
    question : str
        The partner question the demo answers.
    data_sources : list of DemoSource
        Data sources and licences. At least one is required.
    scenarios : list of str
        Scenario names. At least one is required.
    artifacts : DemoArtifacts
        Artifact paths.
    headline_metrics : list of DemoMetric
        Headline metrics. At least one is required.
    caveats : list of str
        Caveats. At least one is required.
    pilot : str
        Demo-relative pilot brief path.
    status : {"draft", "published", "retired"}
        Demo status.
    created_utc : datetime
        Timezone-aware creation time.
    contact : str, optional
        Contact or pilot-request link.
    """

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["brushline.demo.v1"] = DEMO_SCHEMA_VERSION
    id: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{1,62}$")
    title: str = Field(min_length=1)
    sector: str = Field(min_length=1)
    region: str = Field(min_length=1)
    aoi: str = Field(min_length=1)
    question: str = Field(min_length=1)
    data_sources: list[DemoSource] = Field(min_length=1)
    scenarios: list[str] = Field(min_length=1)
    artifacts: DemoArtifacts
    headline_metrics: list[DemoMetric] = Field(min_length=1)
    caveats: list[str] = Field(min_length=1)
    pilot: str = Field(min_length=1)
    status: DemoStatus
    created_utc: datetime
    contact: str = ""

    @field_validator("aoi", "pilot")
    @classmethod
    def _relative_path(cls, value: str) -> str:
        return ensure_relative_path(value, "demo path")

    @field_validator("created_utc")
    @classmethod
    def _timezone_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("created_utc must be timezone-aware")
        return value


def validate_demo_manifest(manifest: DemoManifest) -> ContractValidation:
    """Validate demo sources, caveats, artifact paths, and publication status.

    Parameters
    ----------
    manifest : DemoManifest
        Demo manifest to validate.

    Returns
    -------
    ContractValidation
        Errors, warnings, and counts.
    """
    errors: list[str] = []
    warnings: list[str] = []
    for source in manifest.data_sources:
        if not source.licence:
            errors.append(f"DEMO-LICENCE: source {source.name} has no licence")
    if manifest.status == "published":
        if not manifest.artifacts.run or not manifest.artifacts.plan:
            errors.append("DEMO-ARTIFACT: a published demo needs a run and a plan")
        if not manifest.artifacts.reports:
            errors.append("DEMO-ARTIFACT: a published demo needs reports")
    if manifest.status != "published":
        warnings.append(f"DEMO-STATUS: demo {manifest.id} is {manifest.status}")
    if manifest.artifacts.pareto is None:
        warnings.append(f"DEMO-ARTIFACT: demo {manifest.id} has no Pareto archive")
    if manifest.artifacts.timeline is None:
        warnings.append(f"DEMO-ARTIFACT: demo {manifest.id} has no operations timeline")
    counts: dict[str, int | float] = {
        "sources": len(manifest.data_sources),
        "scenarios": len(manifest.scenarios),
        "metrics": len(manifest.headline_metrics),
        "caveats": len(manifest.caveats),
    }
    return ContractValidation(tuple(errors), tuple(warnings), counts)


__all__ = [
    "DEMO_SCHEMA_VERSION",
    "DEMO_STATUSES",
    "DemoArtifacts",
    "DemoManifest",
    "DemoMetric",
    "DemoSource",
    "validate_demo_manifest",
]
