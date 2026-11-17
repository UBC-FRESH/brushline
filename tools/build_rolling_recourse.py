# mypy: ignore-errors
"""Compare static, fixed-future recourse, rolling-only, and rolling recourse."""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from brushline.strategic.rolling_recourse import evaluate_rolling_recourse  # noqa: E402
from brushline.strategic.stateful import (  # noqa: E402
    StatefulConfig,
    StatefulMethod,
    StatefulPeriod,
    StatefulPlan,
    StatefulSegment,
)

MODEL = ROOT / "runtime/private/bc-network/model"


def main() -> None:
    """Write rolling-recourse.json."""
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
    result = evaluate_rolling_recourse(
        instance_id="bc-hydro-network-2026",
        plan=plan,
        segments=segments,
        methods=methods,
        periods=periods,
        config=StatefulConfig(risk_weight=1, max_seconds=30),
        episodes=20,
        seed=7,
        lookahead_years=2,
        created_utc=datetime(2026, 11, 17, tzinfo=UTC),
    )
    (MODEL / "rolling-recourse.json").write_text(
        json.dumps(result.model_dump(mode="json"), indent=2) + "\n", encoding="utf-8"
    )
    for case in result.cases:
        print(
            case.name,
            case.budget_violation_probability,
            case.completion_band.p50,
            case.completion_band.mean,
            case.risk_band.mean,
            case.cost_band.p50,
        )


if __name__ == "__main__":
    main()
