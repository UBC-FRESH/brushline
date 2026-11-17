# mypy: ignore-errors
"""Evaluate first-year operational recourse on the nominal balanced plan."""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from brushline.strategic.stateful import StatefulPlan, StatefulSegment  # noqa: E402
from brushline.strategic.two_stage import evaluate_two_stage  # noqa: E402

MODEL = ROOT / "runtime/private/bc-network/model"


def main() -> None:
    """Write two-stage-policy.json."""
    network = json.loads((MODEL / "network.json").read_text(encoding="utf-8"))
    strategic = json.loads((MODEL / "strategic.json").read_text(encoding="utf-8"))
    plan = StatefulPlan.model_validate(
        next(item for item in strategic["milp_scenarios"] if "60000" in item["name"])["plan"]
    )
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
    result = evaluate_two_stage(
        instance_id="bc-hydro-network-2026",
        plan=plan,
        segments=segments,
        budget=60000,
        capacity_hours=6000,
        episodes=100,
        seed=23,
        created_utc=datetime(2026, 11, 17, tzinfo=UTC),
    )
    (MODEL / "two-stage-policy.json").write_text(
        json.dumps(result.model_dump(mode="json"), indent=2) + "\n", encoding="utf-8"
    )
    print("year", result.year, "actions", result.first_stage_actions)
    print("static", result.static_cost_band, result.static_budget_violation_probability)
    print("recourse", result.recourse_cost_band, result.recourse_budget_violation_probability)
    print("risk", result.static_risk_band, result.recourse_risk_band)
    print("completion", result.static_completion_band, result.recourse_completion_band)
    print(
        "deferred", result.mean_deferred_actions, result.mean_deferred_hours, result.mean_risk_loss
    )


if __name__ == "__main__":
    main()
