# mypy: ignore-errors
"""Compare added-crew and longer-window remedies for calendar-aware recourse."""

from __future__ import annotations

import json
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from brushline.strategic.capacity_remedy import evaluate_capacity_remedy  # noqa: E402
from brushline.strategic.stateful import (  # noqa: E402
    StatefulConfig,
    StatefulMethod,
    StatefulPeriod,
    StatefulPlan,
    StatefulSegment,
)
from brushline.strategic.weather_recourse import WeatherCalendarConfig  # noqa: E402
from brushline.tactical.shifts import ShiftCrew, ShiftMachine  # noqa: E402
from tools.build_bc_network_demo import _profiles  # noqa: E402

MODEL = ROOT / "runtime/private/bc-network/model"
WINDOWS = [90, 105]
EPISODES = 20


def main() -> None:
    """Write capacity-remedy.json."""
    network = json.loads((MODEL / "network.json").read_text(encoding="utf-8"))
    strategic = json.loads((MODEL / "strategic.json").read_text(encoding="utf-8"))
    plan = StatefulPlan.model_validate(
        next(item for item in strategic["milp_scenarios"] if "60000" in item["name"])["plan"]
    )
    methods = [
        StatefulMethod(
            method=method,
            cost_per_ha=params["cost_ha"],
            hours_per_ha=params["hours_ha"],
            risk_reduction=params["risk_reduction"],
        )
        for method, params in network["assumptions"]["method_costs"].items()
    ]
    segments = [
        StatefulSegment(
            segment_id=segment["segment_id"],
            span_id=segment["unit_id"],
            length_m=segment["length_m"],
            area_ha=segment["length_m"] * segment["width_m"] / 10000,
            initial_risk=segment["base_risk"],
        )
        for segment in network["segments"]
    ]
    periods = [
        StatefulPeriod(year=2027 + index, budget=60000, capacity_hours=6000) for index in range(5)
    ]
    profiles = _profiles()
    crews = [
        ShiftCrew(
            crew_id=profile.contractor_id,
            methods=list(profile.methods),
            shift_hours=8.0,
            contractor_id=profile.contractor_id,
        )
        for profile in profiles
    ]
    machines = [
        ShiftMachine(
            machine_id=f"{profile.contractor_id}-machine",
            methods=[method for method in profile.methods if method in {"mowing", "mechanical"}],
            shift_hours=8.0,
            contractor_id=profile.contractor_id,
        )
        for profile in profiles
        if any(method in {"mowing", "mechanical"} for method in profile.methods)
    ]
    extra_crews = [
        ShiftCrew(
            crew_id="relief-mowing-crew",
            methods=["mowing", "manual"],
            shift_hours=8.0,
        )
    ]
    extra_machines = [
        ShiftMachine(
            machine_id="relief-mower",
            methods=["mowing"],
            shift_hours=8.0,
        )
    ]
    started = time.perf_counter()
    result = evaluate_capacity_remedy(
        instance_id="bc-hydro-network-2026",
        plan=plan,
        segments=segments,
        methods=methods,
        periods=periods,
        crews=crews,
        machines=machines,
        extra_crews=extra_crews,
        extra_machines=extra_machines,
        windows=WINDOWS,
        config=StatefulConfig(risk_weight=1.0, max_seconds=30),
        episodes=EPISODES,
        seed=7,
        solver="exact",
        lookahead_years=2,
        calendar=WeatherCalendarConfig(
            window_days=75,
            outage_days=[11, 12, 13, 14, 15],
            weather_probability=0.20,
            travel_hours=0.5,
            seed=7,
        ),
        crew_day_cost=1200.0,
        machine_day_cost=900.0,
        supervision_fraction=0.08,
        overhead_fraction=0.10,
        seasonal_overhead_per_crew=2500.0,
        created_utc=datetime(2026, 11, 17, tzinfo=UTC),
    )
    seconds = time.perf_counter() - started
    payload = {
        "windows": WINDOWS,
        "episodes": EPISODES,
        "seconds": round(seconds, 2),
        "assumptions": {
            "crew_day_cost": 1200.0,
            "machine_day_cost": 900.0,
            "supervision_fraction": 0.08,
            "overhead_fraction": 0.10,
            "seasonal_overhead_per_crew": 2500.0,
        },
        "result": result.model_dump(mode="json"),
    }
    (MODEL / "capacity-remedy.json").write_text(
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
    print("seconds", round(seconds, 2))


if __name__ == "__main__":
    main()
