# mypy: ignore-errors
"""Re-optimize future years after first-year risk-ranked deferral."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from brushline.strategic.stateful import StatefulMethod, StatefulPeriod  # noqa: E402
from tools.build_bc_network_demo import _rolling_recovery  # noqa: E402

MODEL = ROOT / "runtime/private/bc-network/model"


def main() -> None:
    """Write rolling-recovery.json."""
    network = json.loads((MODEL / "network.json").read_text(encoding="utf-8"))
    rolling = json.loads((MODEL / "rolling-policy.json").read_text(encoding="utf-8"))
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
    result = _rolling_recovery(rolling, network["segments"], methods, periods)
    (MODEL / "rolling-recovery.json").write_text(
        json.dumps(result, indent=2) + "\n", encoding="utf-8"
    )
    print("years", result["years"], "deferred", result["mean_deferred_fraction"])
    print("recovery", result["mean_recovery"], result["final_recovery"])
    for case in result["cases"]:
        print(case["name"], case["annual_risk"], case["mean_risk_loss"], case["final_risk_loss"])


if __name__ == "__main__":
    main()
