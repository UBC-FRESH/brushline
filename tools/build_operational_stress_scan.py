# mypy: ignore-errors
"""Stress first-year weather/outage calendars across all rolling episodes."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.build_bc_network_demo import _operational_stress_scan, _profiles  # noqa: E402

MODEL = ROOT / "runtime/private/bc-network/model"


def main() -> None:
    """Write operational-stress-scan.json."""
    network = json.loads((MODEL / "network.json").read_text(encoding="utf-8"))
    strategic = json.loads((MODEL / "strategic.json").read_text(encoding="utf-8"))
    rolling = json.loads((MODEL / "rolling-policy.json").read_text(encoding="utf-8"))
    selected = next(
        scenario for scenario in strategic["milp_scenarios"] if "60000" in scenario["name"]
    )
    scan = _operational_stress_scan(
        rolling,
        selected["plan"]["actions"],
        network["segments"],
        network["units"],
        network["towers"],
        _profiles(),
    )
    (MODEL / "operational-stress-scan.json").write_text(
        json.dumps(scan, indent=2) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "episodes": scan["episodes"],
                "scenario_completion_rate": scan["scenario_completion_rate"],
                "baseline_feasibility_rate": scan["baseline_feasibility_rate"],
                "mean_completion_rate": scan["mean_completion_rate"],
                "episodes_with_full_completion": scan["episodes_with_full_completion"],
                "unscheduled_hours_band": scan["unscheduled_hours_band"],
                "failure_sources": scan["failure_sources"],
                "window_sensitivity": scan["window_sensitivity"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
