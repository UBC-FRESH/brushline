"""Strategic scenario archive and reproducibility record."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from brushline.model.validation import ContractValidation, check_duplicates
from brushline.strategic.portfolio import StrategicPortfolio
from brushline.strategic.reports import StrategicReport

SCENARIO_SCHEMA_VERSION: Literal["brushline.strategic-scenario.v1"] = (
    "brushline.strategic-scenario.v1"
)
SCENARIO_ARCHIVE_SCHEMA_VERSION: Literal["brushline.strategic-scenario-archive.v1"] = (
    "brushline.strategic-scenario-archive.v1"
)


class ScenarioError(ValueError):
    """Raised when scenario inputs or replay are inconsistent."""


class ScenarioVersions(BaseModel):
    """Versions that identify a strategic scenario.

    Parameters
    ----------
    dataset_version : str
        Dataset version.
    dataset_digest : str
        Dataset content digest.
    state_model : str
        State model version.
    growth_model : str
        Growth model version.
    treatment_model : str
        Treatment model version.
    adapter : str
        Adapter version.
    brushline_version : str
        Brushline version.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    dataset_version: str = Field(min_length=1)
    dataset_digest: str = Field(min_length=1)
    state_model: str = Field(min_length=1)
    growth_model: str = Field(min_length=1)
    treatment_model: str = Field(min_length=1)
    adapter: str = Field(min_length=1)
    brushline_version: str = Field(min_length=1)


class StrategicScenario(BaseModel):
    """A reproducible strategic scenario record.

    Parameters
    ----------
    schema_version : {"brushline.strategic-scenario.v1"}
        Schema version.
    scenario_id : str
        Scenario id.
    instance_id : str
        Instance id.
    versions : ScenarioVersions
        Data/model/adapter versions.
    configuration : dict
        Scenario configuration.
    config_digest : str
        Canonical configuration digest.
    seed : int
        Seed.
    budget : int
        Search or planning budget.
    horizon_years : int
        Horizon.
    portfolio_id : str
        Portfolio id.
    report_id : str
        Report id.
    portfolio_path : str
        Portfolio artifact path.
    report_path : str
        Report artifact path.
    archive_path : str or None
        Optional P5 archive path.
    portfolio_digest : str
        Canonical portfolio digest.
    report_digest : str
        Canonical report digest.
    created_utc : datetime
        Timezone-aware time.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["brushline.strategic-scenario.v1"] = SCENARIO_SCHEMA_VERSION
    scenario_id: str
    instance_id: str
    versions: ScenarioVersions
    configuration: dict[str, Any]
    config_digest: str
    seed: int
    budget: int = Field(ge=0)
    horizon_years: int = Field(ge=1)
    portfolio_id: str
    report_id: str
    portfolio_path: str
    report_path: str
    archive_path: str | None = None
    portfolio_digest: str
    report_digest: str
    created_utc: datetime

    @model_validator(mode="after")
    def _scenario(self) -> StrategicScenario:
        if self.created_utc.tzinfo is None:
            raise ValueError("created_utc must be timezone-aware")
        if canonical_digest(self.configuration) != self.config_digest:
            raise ValueError("config_digest does not match configuration")
        return self


class ScenarioReplay(BaseModel):
    """A verified scenario replay.

    Parameters
    ----------
    scenario_id : str
        Scenario id.
    ok : bool
        Whether the artifacts match.
    errors : list of str
        Replay errors.
    portfolio_digest : str or None
        Recomputed portfolio digest.
    report_digest : str or None
        Recomputed report digest.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    scenario_id: str
    ok: bool
    errors: list[str] = Field(default_factory=list)
    portfolio_digest: str | None = None
    report_digest: str | None = None


class ScenarioArchive(BaseModel):
    """A versioned set of strategic scenarios.

    Parameters
    ----------
    schema_version : {"brushline.strategic-scenario-archive.v1"}
        Schema version.
    scenarios : list of StrategicScenario
        Scenarios.
    created_utc : datetime
        Timezone-aware time.
    created_by : str
        Creator.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["brushline.strategic-scenario-archive.v1"] = (
        SCENARIO_ARCHIVE_SCHEMA_VERSION
    )
    scenarios: list[StrategicScenario] = Field(default_factory=list)
    created_utc: datetime
    created_by: str = Field(min_length=1)

    @model_validator(mode="after")
    def _archive(self) -> ScenarioArchive:
        if self.created_utc.tzinfo is None:
            raise ValueError("created_utc must be timezone-aware")
        return self


def canonical_digest(value: object) -> str:
    """Return a canonical SHA-256 digest of a JSON-like value.

    Parameters
    ----------
    value : object
        JSON-like value.

    Returns
    -------
    str
        Hex digest.
    """
    payload = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        default=str,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def build_scenario(
    *,
    scenario_id: str,
    instance_id: str,
    versions: ScenarioVersions,
    configuration: dict[str, Any],
    portfolio: StrategicPortfolio,
    report: StrategicReport,
    seed: int,
    budget: int,
    horizon_years: int,
    portfolio_path: str,
    report_path: str,
    archive_path: str | None = None,
    created_utc: datetime | None = None,
) -> StrategicScenario:
    """Build a scenario with canonical configuration, portfolio, and report digests.

    Parameters
    ----------
    scenario_id : str
        Scenario id.
    instance_id : str
        Instance id.
    versions : ScenarioVersions
        Versions.
    configuration : dict
        Configuration.
    portfolio : StrategicPortfolio
        Portfolio.
    report : StrategicReport
        Report.
    seed : int
        Seed.
    budget : int
        Budget.
    horizon_years : int
        Horizon.
    portfolio_path : str
        Portfolio path.
    report_path : str
        Report path.
    archive_path : str or None, optional
        P5 archive path.
    created_utc : datetime, optional
        Creation time.

    Returns
    -------
    StrategicScenario
        Scenario record.
    """
    if portfolio.instance_id != instance_id or report.instance_id != instance_id:
        raise ScenarioError("portfolio and report must use the scenario instance")
    return StrategicScenario(
        scenario_id=scenario_id,
        instance_id=instance_id,
        versions=versions,
        configuration=configuration,
        config_digest=canonical_digest(configuration),
        seed=seed,
        budget=budget,
        horizon_years=horizon_years,
        portfolio_id=portfolio.portfolio_id,
        report_id=report.report_id,
        portfolio_path=portfolio_path,
        report_path=report_path,
        archive_path=archive_path,
        portfolio_digest=canonical_digest(portfolio.model_dump(mode="json")),
        report_digest=canonical_digest(report.model_dump(mode="json")),
        created_utc=created_utc or datetime.now(UTC),
    )


def replay_scenario(
    scenario: StrategicScenario,
    *,
    portfolio: StrategicPortfolio | None,
    report: StrategicReport | None,
) -> ScenarioReplay:
    """Verify that reconstructed artifacts match the scenario record.

    Parameters
    ----------
    scenario : StrategicScenario
        Scenario record.
    portfolio : StrategicPortfolio or None
        Reconstructed portfolio.
    report : StrategicReport or None
        Reconstructed report.

    Returns
    -------
    ScenarioReplay
        Match evidence. Missing artifacts are errors.
    """
    errors: list[str] = []
    portfolio_digest: str | None = None
    report_digest: str | None = None
    if portfolio is None:
        errors.append("SCENARIO-ARTIFACT: portfolio is missing")
    else:
        if portfolio.portfolio_id != scenario.portfolio_id:
            errors.append("SCENARIO-PORTFOLIO: portfolio id differs")
        portfolio_digest = canonical_digest(portfolio.model_dump(mode="json"))
        if portfolio_digest != scenario.portfolio_digest:
            errors.append("SCENARIO-PORTFOLIO: portfolio digest differs")
    if report is None:
        errors.append("SCENARIO-ARTIFACT: report is missing")
    else:
        if report.report_id != scenario.report_id:
            errors.append("SCENARIO-REPORT: report id differs")
        report_digest = canonical_digest(report.model_dump(mode="json"))
        if report_digest != scenario.report_digest:
            errors.append("SCENARIO-REPORT: report digest differs")
    return ScenarioReplay(
        scenario_id=scenario.scenario_id,
        ok=not errors,
        errors=errors,
        portfolio_digest=portfolio_digest,
        report_digest=report_digest,
    )


def validate_scenario_archive(archive: ScenarioArchive) -> ContractValidation:
    """Validate duplicate scenario ids and record references.

    Parameters
    ----------
    archive : ScenarioArchive
        Archive.

    Returns
    -------
    ContractValidation
        Errors and counts.
    """
    errors: list[str] = []
    check_duplicates(
        "SCENARIO", "scenario", [scenario.scenario_id for scenario in archive.scenarios], errors
    )
    if not archive.scenarios:
        errors.append("SCENARIO-EMPTY: the archive has no scenarios")
    return ContractValidation(tuple(errors), (), {"scenarios": len(archive.scenarios)})


def write_scenario(scenario: StrategicScenario, path: str | Path) -> Path:
    """Write a scenario record as JSON.

    Parameters
    ----------
    scenario : StrategicScenario
        Scenario.
    path : str or Path
        Destination.

    Returns
    -------
    Path
        Written path.
    """
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(scenario.model_dump_json(indent=2) + "\n", encoding="utf-8")
    return destination


def load_scenario(path: str | Path) -> StrategicScenario:
    """Load a scenario record.

    Parameters
    ----------
    path : str or Path
        Source.

    Returns
    -------
    StrategicScenario
        Scenario.
    """
    return StrategicScenario.model_validate_json(Path(path).read_text(encoding="utf-8"))


def write_scenario_archive(archive: ScenarioArchive, path: str | Path) -> Path:
    """Validate and write a scenario archive.

    Parameters
    ----------
    archive : ScenarioArchive
        Archive.
    path : str or Path
        Destination.

    Returns
    -------
    Path
        Written path.

    Raises
    ------
    ScenarioError
        When the archive is invalid.
    """
    validation = validate_scenario_archive(archive)
    if not validation.is_valid:
        raise ScenarioError("; ".join(validation.errors))
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(archive.model_dump_json(indent=2) + "\n", encoding="utf-8")
    return destination


def load_scenario_archive(path: str | Path) -> ScenarioArchive:
    """Load and validate a scenario archive.

    Parameters
    ----------
    path : str or Path
        Source.

    Returns
    -------
    ScenarioArchive
        Archive.
    """
    try:
        archive = ScenarioArchive.model_validate_json(Path(path).read_text(encoding="utf-8"))
    except OSError as exc:
        raise ScenarioError(f"cannot read scenario archive: {exc}") from exc
    validation = validate_scenario_archive(archive)
    if not validation.is_valid:
        raise ScenarioError("; ".join(validation.errors))
    return archive


__all__ = [
    "SCENARIO_ARCHIVE_SCHEMA_VERSION",
    "SCENARIO_SCHEMA_VERSION",
    "ScenarioArchive",
    "ScenarioError",
    "ScenarioReplay",
    "ScenarioVersions",
    "StrategicScenario",
    "build_scenario",
    "canonical_digest",
    "load_scenario",
    "load_scenario_archive",
    "replay_scenario",
    "validate_scenario_archive",
    "write_scenario",
    "write_scenario_archive",
]
