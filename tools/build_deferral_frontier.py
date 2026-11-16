# mypy: ignore-errors
"""Sweep risk-ranked first-year deferral fractions."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from brushline.strategic.stateful import StatefulMethod, StatefulPeriod  # noqa: E402
from tools.build_bc_network_demo import _deferral_frontier, _profiles  # noqa: E402

MODEL = ROOT / "runtime/private/bc-network/model"


def main() -> None:
    """Write deferral-frontier.json."""
    network = json.loads((MODEL / "network.json").read_text(encoding="utf-8"))
    strategic = json.loads((MODEL / "strategic.json").read_text(encoding="utf-8"))
    rolling = json.loads((MODEL / "rolling-policy.json").read_text(encoding="utf-8"))
    selected = next(
        scenario for scenario in strategic["milp_scenarios"] if "60000" in scenario["name"]
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
    periods = [
        StatefulPeriod(year=2027 + index, budget=60000, capacity_hours=6000) for index in range(5)
    ]
    result = _deferral_frontier(
        rolling,
        selected["plan"]["actions"],
        network["segments"],
        network["units"],
        network["towers"],
        _profiles(),
        methods,
        periods,
    )
    (MODEL / "deferral-frontier.json").write_text(
        json.dumps(result, indent=2) + "\n", encoding="utf-8"
    )
    for case in result["cases"]:
        print(
            case["target_fraction"],
            case["mean_deferred_fraction"],
            case["completion_75"],
            case["completion_105"],
            case["fixed_future_final_loss"],
            case["recovery_final_loss"],
            case["reopt_cost_mean"],
            case["first_year_budget_feasibility_rate"],
        )


if __name__ == "__main__":
    main()
