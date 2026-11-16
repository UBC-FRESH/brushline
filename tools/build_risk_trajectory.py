# mypy: ignore-errors
"""Replay multi-year risk trajectories for first-year scope deferral."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.build_bc_network_demo import _risk_trajectory  # noqa: E402

MODEL = ROOT / "runtime/private/bc-network/model"


def main() -> None:
    """Write risk-trajectory.json."""
    network = json.loads((MODEL / "network.json").read_text(encoding="utf-8"))
    rolling = json.loads((MODEL / "rolling-policy.json").read_text(encoding="utf-8"))
    result = _risk_trajectory(rolling, network["segments"])
    (MODEL / "risk-trajectory.json").write_text(
        json.dumps(result, indent=2) + "\n", encoding="utf-8"
    )
    print("years", result["years"], "deferred", result["mean_deferred_fraction"])
    for case in result["cases"]:
        print(
            case["name"],
            case["annual_risk"],
            case["mean_risk_loss"],
            case["final_risk_loss"],
        )


if __name__ == "__main__":
    main()
