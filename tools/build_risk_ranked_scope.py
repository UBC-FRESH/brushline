# mypy: ignore-errors
"""Evaluate first-year scope deferral ranked by risk reduction per hour."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.build_bc_network_demo import _profiles, _risk_ranked_scope  # noqa: E402

MODEL = ROOT / "runtime/private/bc-network/model"


def main() -> None:
    """Write risk-ranked-scope.json."""
    network = json.loads((MODEL / "network.json").read_text(encoding="utf-8"))
    strategic = json.loads((MODEL / "strategic.json").read_text(encoding="utf-8"))
    rolling = json.loads((MODEL / "rolling-policy.json").read_text(encoding="utf-8"))
    selected = next(
        scenario for scenario in strategic["milp_scenarios"] if "60000" in scenario["name"]
    )
    result = _risk_ranked_scope(
        rolling,
        selected["plan"]["actions"],
        network["segments"],
        network["units"],
        network["towers"],
        _profiles(),
    )
    (MODEL / "risk-ranked-scope.json").write_text(
        json.dumps(result, indent=2) + "\n", encoding="utf-8"
    )
    for case in result["cases"]:
        print(
            case["name"],
            case["scenario_completion_rate"],
            case["mean_completion_rate"],
            case["mean_risk_loss"],
            case["mean_residual_risk"],
            case["total_cost_band"]["p50"],
            case["budget_feasibility_rate"],
        )


if __name__ == "__main__":
    main()
