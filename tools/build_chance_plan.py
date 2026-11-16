# mypy: ignore-errors
"""Build a sampled budget-chance-constrained plan."""

from __future__ import annotations

import json
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
MAX_TRAINING_VIOLATIONS = 2


def main() -> None:
    """Write chance-plan.json."""
    network = json.loads((MODEL / "network.json").read_text(encoding="utf-8"))
    rolling = json.loads((MODEL / "rolling-policy.json").read_text(encoding="utf-8"))
    strategic = json.loads((MODEL / "strategic.json").read_text(encoding="utf-8"))
    robust = json.loads((MODEL / "robust-plan.json").read_text(encoding="utf-8"))
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
    paths = [
        [
            (
                factor["year"],
                factor["cost_factor"],
                factor["hours_factor"],
                factor["capacity_factor"],
            )
            for factor in episode["factors"]
        ]
        for episode in rolling["episodes_detail"]
    ]
    plan = build_stateful_plan(
        instance_id="bc-hydro-network-2026-chance",
        segments=segments,
        methods=methods,
        periods=periods,
        config=StatefulConfig(risk_weight=1, max_seconds=120),
        chance_factors=paths,
        max_budget_violations=MAX_TRAINING_VIOLATIONS,
    )
    nominal = StatefulPlan.model_validate(
        next(item for item in strategic["milp_scenarios"] if "60000" in item["name"])["plan"]
    )
    robust_plan = StatefulPlan.model_validate(robust["plan"])
    test = evaluate_static_plans(
        instance_id="bc-hydro-network-2026",
        plans=[
            StaticPlanCase(name="chance-constrained", nominal_budget=60000, plan=plan),
            StaticPlanCase(name="scenario-robust", nominal_budget=60000, plan=robust_plan),
            StaticPlanCase(name="nominal-balanced", nominal_budget=60000, plan=nominal),
        ],
        periods=periods,
        episodes=100,
        seed=23,
        budget_risk_limit=0.05,
        created_utc=datetime(2026, 11, 16, tzinfo=UTC),
    )
    payload = {
        "schema_version": "brushline.chance-plan.v1",
        "instance_id": "bc-hydro-network-2026",
        "training_paths": len(paths),
        "max_budget_violations": MAX_TRAINING_VIOLATIONS,
        "test_episodes": 100,
        "budget_rows": len(paths) * len(periods),
        "chance_binaries": len(paths) * len(periods),
        "plan": plan.model_dump(mode="json"),
        "test": test.model_dump(mode="json"),
        "caveats": [
            "The chance constraint covers budget only on 20 training paths.",
            "Capacity remains hard across all training paths.",
            "Out-of-sample budget violations are not guaranteed to meet the training threshold.",
            "This is a sampled chance constraint, not a distributional chance-constrained "
            "guarantee.",
        ],
    }
    (MODEL / "chance-plan.json").write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
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
