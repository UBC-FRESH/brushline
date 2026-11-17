"""Forecast-skill sensitivity for weather/outage-aware annual recourse.

A coarse skill model draws a perfect annual forecast with probability ``forecast_skill`` and an
independent synthetic forecast otherwise. The result is a diagnostic, not a meteorological
forecast product.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from brushline.strategic.stateful import (
    StatefulConfig,
    StatefulMethod,
    StatefulPeriod,
    StatefulPlan,
    StatefulSegment,
)
from brushline.strategic.weather_recourse import (
    WeatherCalendarConfig,
    WeatherCaseSummary,
    WeatherRecourseError,
    _simulate_case,
)
from brushline.tactical.shifts import ShiftCrew, ShiftMachine

FORECAST_SKILL_SCHEMA_VERSION: Literal["brushline.forecast-skill.v1"] = (
    "brushline.forecast-skill.v1"
)


class ForecastSkillCase(BaseModel):
    """One forecast-skill point."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    forecast_skill: float = Field(ge=0, le=1)
    summary: WeatherCaseSummary


class ForecastSkillResult(BaseModel):
    """Forecast-skill sensitivity for the calendar-aware policy."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["brushline.forecast-skill.v1"] = FORECAST_SKILL_SCHEMA_VERSION
    instance_id: str
    episodes: int = Field(ge=1)
    seed: int
    years: list[int]
    solver: Literal["exact", "heuristic"]
    lookahead_years: int = Field(ge=1)
    calendar: WeatherCalendarConfig
    cases: list[ForecastSkillCase]
    created_utc: datetime

    @model_validator(mode="after")
    def _time(self) -> ForecastSkillResult:
        if self.created_utc.tzinfo is None:
            raise ValueError("created_utc must be timezone-aware")
        return self


def evaluate_forecast_skill(
    *,
    instance_id: str,
    plan: StatefulPlan,
    segments: list[StatefulSegment],
    methods: list[StatefulMethod],
    periods: list[StatefulPeriod],
    crews: list[ShiftCrew],
    machines: list[ShiftMachine],
    skills: list[float],
    config: StatefulConfig | None = None,
    episodes: int = 20,
    seed: int = 7,
    solver: Literal["exact", "heuristic"] = "exact",
    heuristic_iterations: int = 100,
    lookahead_years: int = 2,
    calendar: WeatherCalendarConfig | None = None,
    created_utc: datetime | None = None,
) -> ForecastSkillResult:
    """Evaluate forecast-aware execution across a forecast-skill sweep."""
    if not plan.actions or not segments or not periods:
        raise WeatherRecourseError("plan, segments, and periods must be non-empty")
    if not crews or not machines:
        raise WeatherRecourseError("crews and machines must be non-empty")
    if episodes < 1:
        raise WeatherRecourseError("episodes must be positive")
    if not skills or any(skill < 0 or skill > 1 for skill in skills):
        raise WeatherRecourseError("forecast skills must be in [0, 1]")
    rules = config or StatefulConfig(risk_weight=1.0, max_seconds=30)
    calendar_rules = calendar or WeatherCalendarConfig(seed=seed)
    cases = [
        ForecastSkillCase(
            forecast_skill=skill,
            summary=_simulate_case(
                name="forecast-aware",
                plan=plan,
                segments=segments,
                methods=methods,
                periods=periods,
                config=rules,
                episodes=episodes,
                seed=seed,
                solver=solver,
                heuristic_iterations=heuristic_iterations,
                lookahead_years=lookahead_years,
                calendar=calendar_rules,
                crews=crews,
                machines=machines,
                forecast_skill=skill,
            ),
        )
        for skill in sorted(set(skills))
    ]
    return ForecastSkillResult(
        instance_id=instance_id,
        episodes=episodes,
        seed=seed,
        years=[period.year for period in periods],
        solver=solver,
        lookahead_years=lookahead_years,
        calendar=calendar_rules,
        cases=cases,
        created_utc=created_utc or datetime.now(UTC),
    )


__all__ = [
    "FORECAST_SKILL_SCHEMA_VERSION",
    "ForecastSkillCase",
    "ForecastSkillResult",
    "evaluate_forecast_skill",
]
