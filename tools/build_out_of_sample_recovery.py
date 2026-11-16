# mypy: ignore-errors
"""Resample future factors after fixed first-year deferral and reoptimize."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from brushline.strategic.stateful import StatefulMethod, StatefulPeriod  # noqa: E402
from tools.build_bc_network_demo import _out_of_sample_recovery  # noqa: E402

MODEL = ROOT / "runtime/private/bc-network/model"


def main() -> None:
    """Write out-of-sample-recovery.json."""
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
    result = _out_of_sample_recovery(
        rolling,
        network["segments"],
        methods,
        periods,
        paths_per_episode=5,
        seed=11,
    )
    (MODEL / "out-of-sample-recovery.json").write_text(
        json.dumps(result, indent=2) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "paths_total": result["paths_total"],
                "final_loss_band": result["final_loss_band"],
                "recovery_band": result["recovery_band"],
                "mean_recovery": result["mean_recovery"],
                "probability_final_gap_at_most_0_005": result[
                    "probability_final_gap_at_most_0_005"
                ],
                "reopt_cost_band": result["reopt_cost_band"],
                "full_cost_band": result["full_cost_band"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
