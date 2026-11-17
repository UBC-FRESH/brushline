# mypy: ignore-errors
"""Benchmark weather/outage-aware recourse at 590 replicated segments."""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from brushline.strategic.stateful import StatefulConfig, build_stateful_plan  # noqa: E402
from brushline.strategic.weather_recourse import (  # noqa: E402
    WeatherCalendarConfig,
    evaluate_weather_recourse,
)
from brushline.tactical.shifts import ShiftCrew, ShiftMachine  # noqa: E402
from tools.benchmark_stateful_scaling import _methods, _periods, _segments  # noqa: E402
from tools.build_bc_network_demo import _profiles  # noqa: E402

OUT = ROOT / "runtime/private/bc-network/scaling"
FACTOR = 10
EPISODES = 20
LOOKAHEAD = 2
HEURISTIC_ITERATIONS = 100
SEED = 7


def _resources() -> tuple[list[ShiftCrew], list[ShiftMachine]]:
    profiles = _profiles()
    crews: list[ShiftCrew] = []
    machines: list[ShiftMachine] = []
    for copy in range(FACTOR):
        for profile in profiles:
            crews.append(
                ShiftCrew(
                    crew_id=f"{profile.contractor_id}-{copy}",
                    methods=list(profile.methods),
                    shift_hours=8.0,
                    contractor_id=f"{profile.contractor_id}-{copy}",
                )
            )
            if any(method in {"mowing", "mechanical"} for method in profile.methods):
                machines.append(
                    ShiftMachine(
                        machine_id=f"{profile.contractor_id}-{copy}-machine",
                        methods=[
                            method
                            for method in profile.methods
                            if method in {"mowing", "mechanical"}
                        ],
                        shift_hours=8.0,
                        contractor_id=f"{profile.contractor_id}-{copy}",
                    )
                )
    return crews, machines


def main() -> None:
    """Write weather-recourse-590.json."""
    OUT.mkdir(parents=True, exist_ok=True)
    segments = _segments(FACTOR)
    methods = _methods()
    periods = _periods(FACTOR)
    crews, machines = _resources()
    fixed_started = time.perf_counter()
    plan = build_stateful_plan(
        instance_id="weather-recourse-scale-590",
        segments=segments,
        methods=methods,
        periods=periods,
        config=StatefulConfig(risk_weight=1.0, cost_weight=0.0, max_seconds=120),
    )
    fixed_seconds = time.perf_counter() - fixed_started
    started = time.perf_counter()
    result = evaluate_weather_recourse(
        instance_id="weather-recourse-scale-590",
        plan=plan,
        segments=segments,
        methods=methods,
        periods=periods,
        crews=crews,
        machines=machines,
        config=StatefulConfig(risk_weight=1.0, cost_weight=0.0, max_seconds=60),
        episodes=EPISODES,
        seed=SEED,
        solver="heuristic",
        heuristic_iterations=HEURISTIC_ITERATIONS,
        lookahead_years=LOOKAHEAD,
        calendar=WeatherCalendarConfig(
            window_days=75,
            outage_days=[11, 12, 13, 14, 15],
            weather_probability=0.20,
            travel_hours=0.5,
            seed=SEED,
        ),
    )
    rolling_seconds = time.perf_counter() - started
    payload: dict[str, Any] = {
        "factor": FACTOR,
        "segments": len(segments),
        "episodes": EPISODES,
        "lookahead_years": LOOKAHEAD,
        "solver": "heuristic",
        "fixed_solver": "exact",
        "fixed_seconds": round(fixed_seconds, 2),
        "rolling_seconds": round(rolling_seconds, 2),
        "fixed_status": plan.status,
        "crews": len(crews),
        "machines": len(machines),
        "result": result.model_dump(mode="json"),
    }
    (OUT / "weather-recourse-590.json").write_text(
        json.dumps(payload, indent=2) + "\n", encoding="utf-8"
    )
    for case in result.cases:
        print(
            case.name,
            case.budget_violation_probability,
            case.completion_band.p50,
            case.completion_band.mean,
            case.retained_scope_band.mean,
            case.risk_band.mean,
            case.cost_band.p50,
            case.mean_unscheduled_hours,
            case.mean_calendar_deferred_actions,
        )
    print(
        "fixed",
        plan.status,
        round(fixed_seconds, 2),
        "weather",
        round(rolling_seconds, 2),
    )


if __name__ == "__main__":
    main()
