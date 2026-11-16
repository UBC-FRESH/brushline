# mypy: ignore-errors
"""Validate deferral-frontier candidates with resampled future factors."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from brushline.strategic.stateful import StatefulMethod, StatefulPeriod  # noqa: E402
from tools.build_bc_network_demo import _out_of_sample_recovery  # noqa: E402

MODEL = ROOT / "runtime/private/bc-network/model"
TARGETS = (0.0, 0.05, 0.10, 0.15, 0.20, 0.25)


def _case(target: float, result: dict, paths_total: int) -> dict:
    return {
        "target_fraction": target,
        "paths_total": paths_total,
        "final_loss_band": result["final_loss_band"],
        "recovery_band": result["recovery_band"],
        "probability_final_gap_at_most_0_005": result["probability_final_gap_at_most_0_005"],
        "reopt_cost_band": result["reopt_cost_band"],
        "no_reopt_cost_band": result["no_reopt_cost_band"],
        "full_cost_band": result["full_cost_band"],
        "mean_recovery": result["mean_recovery"],
    }


def main() -> None:
    """Write frontier-validation.json."""
    network = json.loads((MODEL / "network.json").read_text(encoding="utf-8"))
    rolling = json.loads((MODEL / "rolling-policy.json").read_text(encoding="utf-8"))
    existing = json.loads((MODEL / "out-of-sample-recovery.json").read_text(encoding="utf-8"))
    frontier = json.loads((MODEL / "deferral-frontier.json").read_text(encoding="utf-8"))
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
    cases = []
    for target in TARGETS:
        if target == 0.0:
            zero = {
                "final_loss_band": {"p10": 0.0, "p50": 0.0, "p90": 0.0, "mean": 0.0},
                "recovery_band": {"p10": 0.0, "p50": 0.0, "p90": 0.0, "mean": 0.0},
                "probability_final_gap_at_most_0_005": 1.0,
                "reopt_cost_band": existing["full_cost_band"],
                "no_reopt_cost_band": existing["full_cost_band"],
                "full_cost_band": existing["full_cost_band"],
                "mean_recovery": 0.0,
            }
            cases.append(_case(target, zero, existing["paths_total"]))
        elif target == 0.20:
            cases.append(
                _case(
                    target,
                    {
                        "final_loss_band": existing["final_loss_band"],
                        "recovery_band": existing["recovery_band"],
                        "probability_final_gap_at_most_0_005": existing[
                            "probability_final_gap_at_most_0_005"
                        ],
                        "reopt_cost_band": existing["reopt_cost_band"],
                        "no_reopt_cost_band": existing["no_reopt_cost_band"],
                        "full_cost_band": existing["full_cost_band"],
                        "mean_recovery": existing["mean_recovery"],
                    },
                    existing["paths_total"],
                )
            )
        else:
            result = _out_of_sample_recovery(
                rolling,
                network["segments"],
                methods,
                periods,
                target_fraction=target,
                paths_per_episode=2,
                seed=31 + int(target * 100),
            )
            cases.append(_case(target, result, result["paths_total"]))
    fixed_by_target = {case["target_fraction"]: case for case in frontier["cases"]}
    for case in cases:
        fixed = fixed_by_target.get(case["target_fraction"], {})
        case["completion_75"] = fixed.get("completion_75")
        case["completion_105"] = fixed.get("completion_105")
        case["fixed_final_loss"] = fixed.get("fixed_future_final_loss")
        case["first_year_budget_feasibility_rate"] = fixed.get("first_year_budget_feasibility_rate")
    (MODEL / "frontier-validation.json").write_text(
        json.dumps(
            {
                "schema_version": "brushline.frontier-validation.v1",
                "instance_id": "bc-hydro-network-2026",
                "episodes": len(rolling["episodes_detail"]),
                "targets": list(TARGETS),
                "cases": cases,
                "caveats": [
                    "Out-of-sample paths are 100 for 0% and 20%, and 40 for 5%, 10%, 15%, and 25%.",
                    "First-year deferral is fixed; future factors are independent path draws.",
                    "Completion is from the fixed-factor frontier; out-of-sample validation "
                    "covers risk and cost.",
                    "No stochastic dynamic program or multi-year safety/asset-owner model is "
                    "included.",
                ],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    for case in cases:
        print(
            case["target_fraction"],
            case["paths_total"],
            case["final_loss_band"],
            case["recovery_band"],
            case["probability_final_gap_at_most_0_005"],
            case["reopt_cost_band"]["p50"],
        )


if __name__ == "__main__":
    main()
