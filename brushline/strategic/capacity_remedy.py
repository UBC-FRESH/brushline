"""Capacity remedies for weather/outage-aware recourse.

The window remedy extends the fall work window while keeping the crew and machine mix fixed. The
added-crew comparison buys one or more relief crews and machines and charges explicit resource
costs. Both are operational what-ifs, not field schedules.
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
CAPACITY_REMEDY_SCHEMA_VERSION: Literal["brushline.capacity-remedy.v1"] = (
    "brushline.capacity-remedy.v1"
)


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
    "CAPACITY_REMEDY_SCHEMA_VERSION",
    "WINDOW_REMEDY_SCHEMA_VERSION",
    "CapacityRemedyCase",
    "CapacityRemedyResult",
    "WindowRemedyCase",
    "WindowRemedyResult",
    "evaluate_capacity_remedy",
    "evaluate_window_remedy",
]


class CapacityRemedyCase(BaseModel):
    """One capacity-remedy case."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str
    window_days: int = Field(ge=1, le=366)
    extra_crews: int = Field(ge=0)
    extra_machines: int = Field(ge=0)
    summary: WeatherCaseSummary


class CapacityRemedyResult(BaseModel):
    """Added crew and longer-window remedies on a common comparison."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["brushline.capacity-remedy.v1"] = CAPACITY_REMEDY_SCHEMA_VERSION
    instance_id: str
    episodes: int = Field(ge=1)
    seed: int
    years: list[int]
    solver: Literal["exact", "heuristic"]
    lookahead_years: int = Field(ge=1)
    cases: list[CapacityRemedyCase]
    created_utc: datetime

    @model_validator(mode="after")
    def _time(self) -> CapacityRemedyResult:
        if self.created_utc.tzinfo is None:
            raise ValueError("created_utc must be timezone-aware")
        return self


def evaluate_capacity_remedy(
    *,
    instance_id: str,
    plan: StatefulPlan,
    segments: list[StatefulSegment],
    methods: list[StatefulMethod],
    periods: list[StatefulPeriod],
    crews: list[ShiftCrew],
    machines: list[ShiftMachine],
    extra_crews: list[ShiftCrew],
    extra_machines: list[ShiftMachine],
    windows: list[int],
    config: StatefulConfig | None = None,
    episodes: int = 20,
    seed: int = 7,
    solver: Literal["exact", "heuristic"] = "exact",
    heuristic_iterations: int = 100,
    lookahead_years: int = 2,
    calendar: WeatherCalendarConfig | None = None,
    crew_day_cost: float = 1200.0,
    machine_day_cost: float = 900.0,
    supervision_fraction: float = 0.08,
    overhead_fraction: float = 0.10,
    seasonal_overhead_per_crew: float = 2500.0,
    created_utc: datetime | None = None,
) -> CapacityRemedyResult:
    """Compare baseline, added crew, and longer-window remedies."""
    if not extra_crews or not extra_machines:
        raise WeatherRecourseError("extra crews and machines must be non-empty")
    if not windows or any(window < 1 or window > 366 for window in windows):
        raise WeatherRecourseError("window days must be in [1, 366]")
    rules = config or StatefulConfig(risk_weight=1.0, max_seconds=30)
    base = calendar or WeatherCalendarConfig(seed=seed)
    base_window = base.window_days
    extra_crew_ids = {crew.crew_id for crew in extra_crews}
    extra_machine_ids = {machine.machine_id for machine in extra_machines}
    cases: list[CapacityRemedyCase] = []

    def add_case(
        *,
        name: str,
        window_days: int,
        use_extra: bool,
    ) -> None:
        all_crews = [*crews, *extra_crews] if use_extra else list(crews)
        all_machines = [*machines, *extra_machines] if use_extra else list(machines)
        calendar_rules = base.model_copy(update={"window_days": window_days})
        summary = _simulate_case(
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
            crews=all_crews,
            machines=all_machines,
            extra_crew_ids=extra_crew_ids if use_extra else None,
            extra_machine_ids=extra_machine_ids if use_extra else None,
            crew_day_cost=crew_day_cost if use_extra else 0.0,
            machine_day_cost=machine_day_cost if use_extra else 0.0,
            supervision_fraction=supervision_fraction if use_extra else 0.0,
            overhead_fraction=overhead_fraction if use_extra else 0.0,
            seasonal_overhead_per_crew=(seasonal_overhead_per_crew if use_extra else 0.0),
        )
        cases.append(
            CapacityRemedyCase(
                name=name,
                window_days=window_days,
                extra_crews=len(extra_crews) if use_extra else 0,
                extra_machines=len(extra_machines) if use_extra else 0,
                summary=summary,
            )
        )

    add_case(name="baseline", window_days=base_window, use_extra=False)
    add_case(name="extra-crew", window_days=base_window, use_extra=True)
    for window in sorted(set(windows)):
        if window == base_window:
            continue
        add_case(name=f"window-{window}", window_days=window, use_extra=False)
    return CapacityRemedyResult(
        instance_id=instance_id,
        episodes=episodes,
        seed=seed,
        years=[period.year for period in periods],
        solver=solver,
        lookahead_years=lookahead_years,
        cases=cases,
        created_utc=created_utc or datetime.now(UTC),
    )
