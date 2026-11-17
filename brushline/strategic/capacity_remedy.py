"""Calendar-window capacity remedy for weather/outage-aware recourse.

The remedy extends the fall work window while keeping the crew and machine mix fixed. It is an
operational what-if, not a field schedule or a costed workforce plan.
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

WINDOW_REMEDY_SCHEMA_VERSION: Literal["brushline.window-remedy.v1"] = "brushline.window-remedy.v1"


class WindowRemedyCase(BaseModel):
    """One fall-window length."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    window_days: int = Field(ge=1, le=366)
    summary: WeatherCaseSummary


class WindowRemedyResult(BaseModel):
    """Observed-calendar awareness across fall-window lengths."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["brushline.window-remedy.v1"] = WINDOW_REMEDY_SCHEMA_VERSION
    instance_id: str
    episodes: int = Field(ge=1)
    seed: int
    years: list[int]
    solver: Literal["exact", "heuristic"]
    lookahead_years: int = Field(ge=1)
    cases: list[WindowRemedyCase]
    created_utc: datetime

    @model_validator(mode="after")
    def _time(self) -> WindowRemedyResult:
        if self.created_utc.tzinfo is None:
            raise ValueError("created_utc must be timezone-aware")
        return self


def evaluate_window_remedy(
    *,
    instance_id: str,
    plan: StatefulPlan,
    segments: list[StatefulSegment],
    methods: list[StatefulMethod],
    periods: list[StatefulPeriod],
    crews: list[ShiftCrew],
    machines: list[ShiftMachine],
    windows: list[int],
    config: StatefulConfig | None = None,
    episodes: int = 20,
    seed: int = 7,
    solver: Literal["exact", "heuristic"] = "exact",
    heuristic_iterations: int = 100,
    lookahead_years: int = 2,
    calendar: WeatherCalendarConfig | None = None,
    created_utc: datetime | None = None,
) -> WindowRemedyResult:
    """Evaluate observed-calendar awareness across fall-window lengths."""
    if not plan.actions or not segments or not periods:
        raise WeatherRecourseError("plan, segments, and periods must be non-empty")
    if not crews or not machines:
        raise WeatherRecourseError("crews and machines must be non-empty")
    if episodes < 1:
        raise WeatherRecourseError("episodes must be positive")
    if not windows or any(window < 1 or window > 366 for window in windows):
        raise WeatherRecourseError("window days must be in [1, 366]")
    rules = config or StatefulConfig(risk_weight=1.0, max_seconds=30)
    base = calendar or WeatherCalendarConfig(seed=seed)
    cases = []
    for window in sorted(set(windows)):
        calendar_rules = base.model_copy(update={"window_days": window})
        cases.append(
            WindowRemedyCase(
                window_days=window,
                summary=_simulate_case(
                    name="calendar-aware",
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
                ),
            )
        )
    return WindowRemedyResult(
        instance_id=instance_id,
        episodes=episodes,
        seed=seed,
        years=[period.year for period in periods],
        solver=solver,
        lookahead_years=lookahead_years,
        cases=cases,
        created_utc=created_utc or datetime.now(UTC),
    )


__all__ = [
    "WINDOW_REMEDY_SCHEMA_VERSION",
    "WindowRemedyCase",
    "WindowRemedyResult",
    "evaluate_window_remedy",
]
