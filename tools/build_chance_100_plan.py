# mypy: ignore-errors
"""Build a 100-path sampled budget chance-constrained plan."""

from __future__ import annotations

import json
import math
import random
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from brushline.strategic.stateful import (  # noqa: E402
    StatefulConfig,
    StatefulMethod,
    StatefulPeriod,
    StatefulPlan,
    StatefulSegment,
    build_stateful_plan,
)
from brushline.strategic.static_plan import StaticPlanCase, evaluate_static_plans  # noqa: E402

MODEL = ROOT / "runtime/private/bc-network/model"
TRAINING_PATHS = 100
MAX_BUDGET_VIOLATIONS = 10


def main() -> None:
    """Write chance-100-plan.json."""
    network = json.loads((MODEL / "network.json").read_text(encoding="utf-8"))
    strategic = json.loads((MODEL / "strategic.json").read_text(encoding="utf-8"))
    chance20 = json.loads((MODEL / "chance-plan.json").read_text(encoding="utf-8"))
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
    rng = random.Random(31)
    paths = [
        [
            (
                period.year,
                math.exp(rng.gauss(-0.5 * 0.18**2, 0.18)),
                math.exp(rng.gauss(-0.5 * 0.15**2, 0.15)),
                math.exp(rng.gauss(-0.5 * 0.15**2, 0.15)),
            )
            for period in periods
        ]
        for _ in range(TRAINING_PATHS)
    ]
    plan = build_stateful_plan(
        instance_id="bc-hydro-network-2026-chance-100",
        segments=segments,
        methods=methods,
        periods=periods,
        config=StatefulConfig(risk_weight=1, max_seconds=180),
        chance_factors=paths,
        max_budget_violations=MAX_BUDGET_VIOLATIONS,
    )
    nominal = StatefulPlan.model_validate(
        next(item for item in strategic["milp_scenarios"] if "60000" in item["name"])["plan"]
    )
    chance20_plan = StatefulPlan.model_validate(chance20["plan"])
    test = evaluate_static_plans(
        instance_id="bc-hydro-network-2026",
        plans=[
            StaticPlanCase(name="chance 100 paths", nominal_budget=60000, plan=plan),
            StaticPlanCase(name="chance 20 paths", nominal_budget=60000, plan=chance20_plan),
            StaticPlanCase(name="nominal-balanced", nominal_budget=60000, plan=nominal),
        ],
        periods=periods,
        episodes=100,
        seed=23,
        budget_risk_limit=0.05,
        created_utc=datetime(2026, 11, 17, tzinfo=UTC),
    )
    payload = {
        "schema_version": "brushline.chance-100-plan.v1",
        "instance_id": "bc-hydro-network-2026",
        "training_paths": TRAINING_PATHS,
        "max_budget_violations": MAX_BUDGET_VIOLATIONS,
        "test_episodes": 100,
        "plan": plan.model_dump(mode="json"),
        "test": test.model_dump(mode="json"),
        "caveats": [
            "Budget chance is sampled on 100 training paths; capacity remains hard.",
            "Out-of-sample violations are not guaranteed to meet the training threshold.",
            "This is a sampled chance constraint, not a distributional guarantee.",
            "No risk, weather, outage, safety, or asset-owner priority model is included.",
        ],
    }
    (MODEL / "chance-100-plan.json").write_text(
        json.dumps(payload, indent=2) + "\n", encoding="utf-8"
    )
    print(
        "status",
        plan.status,
        "risk",
        plan.mean_risk,
        "cost",
        plan.total_cost,
        "actions",
        len(plan.actions),
    )
    for summary in test.plans:
        print(summary.name, summary.risk, summary.cost_band, summary.budget_violation_probability)


if __name__ == "__main__":
    main()
