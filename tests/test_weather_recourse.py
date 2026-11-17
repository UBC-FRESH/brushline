"""Tests for weather/outage-aware annual recourse."""

from __future__ import annotations

from datetime import UTC, datetime

from brushline.strategic.stateful import (
    StatefulConfig,
    StatefulMethod,
    StatefulPeriod,
    StatefulPlan,
    StatefulSegment,
    build_stateful_plan,
)
from brushline.strategic.weather_recourse import (
    WeatherCalendarConfig,
    evaluate_weather_recourse,
)
from brushline.tactical.shifts import ShiftCrew, ShiftMachine

CREATED = datetime(2026, 11, 17, tzinfo=UTC)


def _problem() -> tuple[
    StatefulPlan, list[StatefulSegment], list[StatefulMethod], list[StatefulPeriod]
]:
    segments = [
        StatefulSegment(
            segment_id=f"s{index}",
            span_id=f"u{index}",
            length_m=500,
            area_ha=3.5,
            initial_risk=0.2 + index * 0.03,
        )
        for index in range(3)
    ]
    methods = [
        StatefulMethod(method="mowing", cost_per_ha=420, hours_per_ha=7, risk_reduction=0.3),
        StatefulMethod(method="manual", cost_per_ha=1450, hours_per_ha=32, risk_reduction=0.55),
    ]
    periods = [
        StatefulPeriod(year=2027, budget=20000, capacity_hours=100),
        StatefulPeriod(year=2028, budget=20000, capacity_hours=100),
    ]
    plan = build_stateful_plan(
        instance_id="tiny",
        segments=segments,
        methods=methods,
        periods=periods,
        config=StatefulConfig(risk_weight=1.0, max_seconds=30),
        created_utc=CREATED,
    )
    return plan, segments, methods, periods


def test_weather_recourse_cases() -> None:
    plan, segments, methods, periods = _problem()
    crews = [ShiftCrew(crew_id="crew-a", methods=["mowing", "manual"], shift_hours=8)]
    machines = [ShiftMachine(machine_id="machine-a", methods=["mowing"], shift_hours=8)]
    result = evaluate_weather_recourse(
        instance_id="weather",
        plan=plan,
        segments=segments,
        methods=methods,
        periods=periods,
        crews=crews,
        machines=machines,
        config=StatefulConfig(risk_weight=1.0, max_seconds=30),
        episodes=2,
        seed=7,
        calendar=WeatherCalendarConfig(window_days=30, outage_days=[5], seed=7),
        created_utc=CREATED,
    )
    assert [case.name for case in result.cases] == [
        "calendar-naive",
        "forecast-aware",
        "calendar-aware",
    ]
    assert result.years == [2027, 2028]
    naive, forecast, aware = result.cases
    assert naive.budget_violation_probability == 0
    assert aware.budget_violation_probability == 0
    assert aware.mean_unscheduled_hours == 0
    assert forecast.mean_calendar_deferred_actions >= 0
    assert aware.mean_calendar_deferred_actions >= 0
    assert aware.mean_resource_deferred_actions >= 0
    assert aware.completion_band.p50 <= naive.completion_band.p50 + 1e-9
    assert aware.retained_scope_band.p50 <= 1.0
    assert result.calendar.window_days == 30
