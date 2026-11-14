"""Tests for the P6.6 strategic scenario archive and replay."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from brushline.strategic.monitoring import (
    MonitoringConfig,
    build_monitoring_policy,
)
from brushline.strategic.portfolio import (
    PortfolioConfig,
    PortfolioOption,
    PortfolioPeriod,
    PortfolioSegment,
    StrategicPortfolio,
    build_strategic_portfolio,
)
from brushline.strategic.reports import StrategicReport, build_strategic_report
from brushline.strategic.scenario import (
    ScenarioArchive,
    ScenarioError,
    ScenarioVersions,
    StrategicScenario,
    build_scenario,
    canonical_digest,
    load_scenario,
    load_scenario_archive,
    replay_scenario,
    validate_scenario_archive,
    write_scenario,
    write_scenario_archive,
)
from pydantic import ValidationError

NOW = datetime(2026, 11, 14, tzinfo=UTC)
VERSIONS = ScenarioVersions(
    dataset_version="synthetic.v1",
    dataset_digest="abc123",
    state_model="state.v1",
    growth_model="growth.v1",
    treatment_model="treatment.v1",
    adapter="adapter.v1",
    brushline_version="0.1.0",
)
CONFIG = {"horizon": 2, "service_target": 0.7, "currency": "CAD", "weights": [1, 2]}


def _segments() -> list[PortfolioSegment]:
    return [
        PortfolioSegment(
            segment_id="s1",
            span_id="sp",
            sequence=0,
            length_m=100,
            base_service=0.2,
            base_risk=0.8,
            base_uncertainty=0.5,
        )
    ]


def _periods() -> list[PortfolioPeriod]:
    return [
        PortfolioPeriod(
            period_id="p1", start_year=2026, budget=100, capacity_by_method={"mowing": 1}
        ),
        PortfolioPeriod(
            period_id="p2", start_year=2027, budget=100, capacity_by_method={"mowing": 1}
        ),
    ]


def _options() -> list[PortfolioOption]:
    return [
        PortfolioOption(
            option_id=f"s1-{period}-mow",
            segment_id="s1",
            period_id=period,
            action_id="mow",
            method="mowing",
            cost=40,
            capacity_units=1,
            service_attainment=0.8,
            risk=0.2,
            uncertainty=0.3,
        )
        for period in ("p1", "p2")
    ]


def _artifacts() -> tuple[StrategicPortfolio, StrategicReport]:
    portfolio = build_strategic_portfolio(
        portfolio_id="opt",
        instance_id="tiny",
        segments=_segments(),
        periods=_periods(),
        options=_options(),
        config=PortfolioConfig(service_target=0.7),
        created_utc=NOW,
    )
    monitoring = build_monitoring_policy(
        policy_id="mon",
        instance_id="tiny",
        spans=[],
        options=[],
        config=MonitoringConfig(horizon_years=2),
        created_utc=NOW,
    )
    report = build_strategic_report(
        report_id="report",
        instance_id="tiny",
        portfolio=portfolio,
        monitoring=monitoring,
        periods=_periods(),
        created_utc=NOW,
    )
    return portfolio, report


def _scenario(
    portfolio: StrategicPortfolio | None = None,
    report: StrategicReport | None = None,
) -> StrategicScenario:
    if portfolio is None or report is None:
        portfolio, report = _artifacts()
    return build_scenario(
        scenario_id="scenario-1",
        instance_id="tiny",
        versions=VERSIONS,
        configuration=CONFIG,
        portfolio=portfolio,
        report=report,
        seed=7,
        budget=100,
        horizon_years=2,
        portfolio_path="runs/portfolio.json",
        report_path="runs/report.json",
        archive_path="runs/pareto.json",
        created_utc=NOW,
    )


def test_scenario_replays_artifact_digests() -> None:
    """The scenario records canonical digests and replays both artifacts."""
    portfolio, report = _artifacts()
    scenario = _scenario(portfolio, report)
    assert scenario.config_digest == canonical_digest(CONFIG)
    assert scenario.portfolio_digest == canonical_digest(portfolio.model_dump(mode="json"))
    replay = replay_scenario(scenario, portfolio=portfolio, report=report)
    assert replay.ok
    assert replay.portfolio_digest == scenario.portfolio_digest
    assert replay.report_digest == scenario.report_digest
    assert canonical_digest({"b": 1, "a": 2}) == canonical_digest({"a": 2, "b": 1})
    assert scenario.created_utc == NOW


def test_missing_and_tampered_artifacts_are_explicit() -> None:
    """Missing artifacts, id mismatches, and digest mismatches are errors."""
    portfolio, report = _artifacts()
    scenario = _scenario(portfolio, report)
    missing = replay_scenario(scenario, portfolio=None, report=None)
    assert not missing.ok
    assert len(missing.errors) == 2
    wrong_id = portfolio.model_copy(update={"portfolio_id": "other"})
    replay = replay_scenario(scenario, portfolio=wrong_id, report=report)
    assert not replay.ok
    assert any("portfolio id" in error for error in replay.errors)
    tampered = scenario.model_copy(update={"report_digest": "0" * 64})
    replay = replay_scenario(tampered, portfolio=portfolio, report=report)
    assert not replay.ok
    assert any("report digest" in error for error in replay.errors)
    wrong_report = report.model_copy(update={"report_id": "other"})
    replay = replay_scenario(scenario, portfolio=portfolio, report=wrong_report)
    assert not replay.ok
    with pytest.raises(ScenarioError):
        build_scenario(
            scenario_id="x",
            instance_id="other",
            versions=VERSIONS,
            configuration=CONFIG,
            portfolio=portfolio,
            report=report,
            seed=1,
            budget=1,
            horizon_years=1,
            portfolio_path="a",
            report_path="b",
            created_utc=NOW,
        )


def test_scenario_and_archive_round_trip(tmp_path: Path) -> None:
    """Scenario and archive writers/loaders preserve the records."""
    portfolio, report = _artifacts()
    scenario = _scenario(portfolio, report)
    path = tmp_path / "scenario.json"
    assert write_scenario(scenario, path) == path
    assert load_scenario(path) == scenario
    archive = ScenarioArchive(scenarios=[scenario], created_utc=NOW, created_by="test")
    assert validate_scenario_archive(archive).is_valid
    archive_path = tmp_path / "archive.json"
    assert write_scenario_archive(archive, archive_path) == archive_path
    assert load_scenario_archive(archive_path) == archive
    duplicate = ScenarioArchive(scenarios=[scenario, scenario], created_utc=NOW, created_by="test")
    assert not validate_scenario_archive(duplicate).is_valid
    empty = ScenarioArchive(scenarios=[], created_utc=NOW, created_by="test")
    assert not validate_scenario_archive(empty).is_valid
    with pytest.raises(ScenarioError):
        write_scenario_archive(duplicate, tmp_path / "bad.json")
    with pytest.raises(ScenarioError):
        load_scenario_archive(tmp_path / "bad.json")


def test_scenario_model_guards() -> None:
    """Configuration digests, times, and versions are validated."""
    portfolio, report = _artifacts()
    scenario = _scenario(portfolio, report)
    with pytest.raises(ValidationError, match="config_digest"):
        StrategicScenario(
            **{
                **scenario.model_dump(),
                "config_digest": "0" * 64,
            }
        )
    with pytest.raises(ValidationError):
        StrategicScenario(
            **{
                **scenario.model_dump(),
                "created_utc": datetime(2026, 11, 14),
            }
        )
    with pytest.raises(ValidationError):
        ScenarioVersions(
            dataset_version="",
            dataset_digest="x",
            state_model="x",
            growth_model="x",
            treatment_model="x",
            adapter="x",
            brushline_version="x",
        )
    with pytest.raises(ValidationError):
        ScenarioArchive(scenarios=[], created_utc=datetime(2026, 11, 14), created_by="x")


def test_committed_scenario_fixture_loads() -> None:
    """The committed scenario example has a valid canonical configuration digest."""
    path = Path(__file__).resolve().parents[1] / "notes" / "reference" / "p6-scenario.v1.json"
    scenario = load_scenario(path)
    assert scenario.scenario_id == "p6-scenario-v1"
    assert scenario.instance_id == "tiny"
    assert scenario.config_digest == canonical_digest(scenario.configuration)
    assert scenario.portfolio_path == "runs/tiny/portfolio.json"
    assert scenario.report_path == "runs/tiny/report.json"
