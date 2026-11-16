# mypy: ignore-errors
"""Compare added crew/machine capacity with first-year scope reduction."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.build_bc_network_demo import _operational_remedies, _profiles  # noqa: E402

MODEL = ROOT / "runtime/private/bc-network/model"


def main() -> None:
    """Write operational-remedies.json."""
    network = json.loads((MODEL / "network.json").read_text(encoding="utf-8"))
    strategic = json.loads((MODEL / "strategic.json").read_text(encoding="utf-8"))
    rolling = json.loads((MODEL / "rolling-policy.json").read_text(encoding="utf-8"))
    selected = next(
        scenario for scenario in strategic["milp_scenarios"] if "60000" in scenario["name"]
    )
    remedies = _operational_remedies(
        rolling,
        selected["plan"]["actions"],
        network["segments"],
        network["units"],
        network["towers"],
        _profiles(),
    )
    (MODEL / "operational-remedies.json").write_text(
        json.dumps(remedies, indent=2) + "\n", encoding="utf-8"
    )
    for case in remedies["cases"]:
        print(
            case["name"],
            case["scenario_completion_rate"],
            case["mean_completion_rate"],
            case["unscheduled_hours_band"]["p50"],
        )


if __name__ == "__main__":
    main()
