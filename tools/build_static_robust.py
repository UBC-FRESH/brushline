# mypy: ignore-errors
"""Evaluate static frontier plans against the 60,000 CAD annual budget."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from brushline.strategic.stateful import StatefulConfig, StatefulPeriod, StatefulPlan
from brushline.strategic.static_plan import StaticPlanCase, evaluate_static_plans

ROOT = Path(__file__).resolve().parents[1]
MODEL = ROOT / "runtime/private/bc-network/model"


def main() -> None:
    """Write the static-plan stress comparison."""
    strategic = json.loads((MODEL / "strategic.json").read_text(encoding="utf-8"))
    cases = [
        StaticPlanCase(
            name=scenario["name"],
            nominal_budget=float(scenario["annual_budget"]),
            plan=StatefulPlan.model_validate(scenario["plan"]),
        )
        for scenario in strategic["milp_scenarios"]
    ]
    periods = [
        StatefulPeriod(year=2027 + index, budget=60000, capacity_hours=6000) for index in range(5)
    ]
    result = evaluate_static_plans(
        instance_id="bc-hydro-network-2026",
        plans=cases,
        periods=periods,
        config=StatefulConfig(risk_weight=1.0),
        episodes=20,
        seed=7,
        budget_risk_limit=0.05,
        created_utc=datetime(2026, 11, 16, tzinfo=UTC),
    )
    (MODEL / "static-robust.json").write_text(
        json.dumps(result.model_dump(mode="json"), indent=2) + "\n", encoding="utf-8"
    )
    print("recommended", result.recommended)
    for plan in result.plans:
        print(
            plan.name,
            plan.nominal_budget,
            plan.cost_band.p10,
            plan.cost_band.p90,
            plan.risk,
            plan.budget_violation_probability,
        )


if __name__ == "__main__":
    main()
