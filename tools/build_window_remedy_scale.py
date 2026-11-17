# mypy: ignore-errors
"""Build a 590-segment fall-window capacity-remedy artifact."""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from brushline.strategic.capacity_remedy import evaluate_window_remedy  # noqa: E402
from brushline.strategic.stateful import StatefulConfig, build_stateful_plan  # noqa: E402
from brushline.strategic.weather_recourse import WeatherCalendarConfig  # noqa: E402
from tools.benchmark_stateful_scaling import _methods, _periods, _segments  # noqa: E402
from tools.benchmark_weather_recourse_scale import _resources  # noqa: E402

OUT = ROOT / "runtime/private/bc-network/scaling"
FACTOR = 10
WINDOWS = [75, 90, 105]
EPISODES = 20
LOOKAHEAD = 2
HEURISTIC_ITERATIONS = 100
SEED = 7


def main() -> None:
    """Write weather-window-remedy-590.json."""
    OUT.mkdir(parents=True, exist_ok=True)
    segments = _segments(FACTOR)
    methods = _methods()
    periods = _periods(FACTOR)
    crews, machines = _resources()
    started = time.perf_counter()
    plan = build_stateful_plan(
        instance_id="window-remedy-scale-590",
        segments=segments,
        methods=methods,
        periods=periods,
        config=StatefulConfig(risk_weight=1.0, cost_weight=0.0, max_seconds=120),
    )
    fixed_seconds = time.perf_counter() - started
    started = time.perf_counter()
    result = evaluate_window_remedy(
        instance_id="window-remedy-scale-590",
        plan=plan,
        segments=segments,
        methods=methods,
        periods=periods,
        crews=crews,
        machines=machines,
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
        "result": result.model_dump(mode="json"),
    }
    (OUT / "weather-window-remedy-590.json").write_text(
        json.dumps(payload, indent=2) + "\n", encoding="utf-8"
    )
    for case in result.cases:
        summary = case.summary
        print(
            case.window_days,
            summary.completion_band.p50,
            summary.retained_scope_band.p50,
            summary.risk_band.mean,
            summary.cost_band.p50,
            summary.mean_unscheduled_hours,
            summary.mean_calendar_deferred_actions,
        )
    print(
        "fixed",
        plan.status,
        round(fixed_seconds, 2),
        "windows",
        round(seconds, 2),
    )


if __name__ == "__main__":
    main()
