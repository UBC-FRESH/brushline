# mypy: ignore-errors
"""Compare added-crew and window remedies at 590 replicated segments."""

from __future__ import annotations

import json
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from brushline.strategic.capacity_remedy import evaluate_capacity_remedy  # noqa: E402
from brushline.strategic.stateful import StatefulConfig, build_stateful_plan  # noqa: E402
from brushline.strategic.weather_recourse import WeatherCalendarConfig  # noqa: E402
from brushline.tactical.shifts import ShiftCrew, ShiftMachine  # noqa: E402
from tools.benchmark_stateful_scaling import _methods, _periods, _segments  # noqa: E402
from tools.benchmark_weather_recourse_scale import _resources  # noqa: E402

OUT = ROOT / "runtime/private/bc-network/scaling"
FACTOR = 10
WINDOWS = [90, 105]
EPISODES = 20
LOOKAHEAD = 2
HEURISTIC_ITERATIONS = 100
SEED = 7


def _extra_resources(factor: int) -> tuple[list[ShiftCrew], list[ShiftMachine]]:
    crews = []
    machines = []
    for copy in range(factor):
        crews.append(
            ShiftCrew(
                crew_id=f"relief-mowing-{copy}",
                methods=["mowing", "manual"],
                shift_hours=8.0,
            )
        )
        machines.append(
            ShiftMachine(
                machine_id=f"relief-mower-{copy}",
                methods=["mowing"],
                shift_hours=8.0,
            )
        )
    return crews, machines


def main() -> None:
    """Write capacity-remedy-590.json."""
    OUT.mkdir(parents=True, exist_ok=True)
    segments = _segments(FACTOR)
    methods = _methods()
    periods = _periods(FACTOR)
    crews, machines = _resources()
    extra_crews, extra_machines = _extra_resources(FACTOR)
    started = time.perf_counter()
    plan = build_stateful_plan(
        instance_id="capacity-remedy-scale-590",
        segments=segments,
        methods=methods,
        periods=periods,
        config=StatefulConfig(risk_weight=1.0, cost_weight=0.0, max_seconds=120),
    )
    fixed_seconds = time.perf_counter() - started
    started = time.perf_counter()
    result = evaluate_capacity_remedy(
        instance_id="capacity-remedy-scale-590",
        plan=plan,
        segments=segments,
        methods=methods,
        periods=periods,
        crews=crews,
        machines=machines,
        extra_crews=extra_crews,
        extra_machines=extra_machines,
        windows=WINDOWS,
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
        crew_day_cost=1200.0,
        machine_day_cost=900.0,
        supervision_fraction=0.08,
        overhead_fraction=0.10,
        seasonal_overhead_per_crew=2500.0,
        created_utc=datetime(2026, 11, 17, tzinfo=UTC),
    )
    seconds = time.perf_counter() - started
    payload: dict[str, Any] = {
        "factor": FACTOR,
        "segments": len(segments),
        "episodes": EPISODES,
        "lookahead_years": LOOKAHEAD,
        "solver": "heuristic",
        "fixed_solver": "exact",
        "fixed_seconds": round(fixed_seconds, 2),
        "seconds": round(seconds, 2),
        "fixed_status": plan.status,
        "crews": len(crews),
        "machines": len(machines),
        "extra_crews": len(extra_crews),
        "extra_machines": len(extra_machines),
        "assumptions": {
            "crew_day_cost": 1200.0,
            "machine_day_cost": 900.0,
            "supervision_fraction": 0.08,
            "overhead_fraction": 0.10,
            "seasonal_overhead_per_crew": 2500.0,
        },
        "result": result.model_dump(mode="json"),
    }
    (OUT / "capacity-remedy-590.json").write_text(
        json.dumps(payload, indent=2) + "\n", encoding="utf-8"
    )
    for case in result.cases:
        summary = case.summary
        print(
            case.name,
            summary.completion_band.p50,
            summary.risk_band.mean,
            summary.cost_band.p50,
            summary.mean_resource_cost,
            summary.total_cost_band.p50 if summary.total_cost_band else None,
            summary.mean_calendar_deferred_actions,
        )
    print(
        "fixed",
        plan.status,
        round(fixed_seconds, 2),
        "remedy",
        round(seconds, 2),
    )


if __name__ == "__main__":
    main()
