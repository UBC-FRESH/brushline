# mypy: ignore-errors
"""Generate the first-year execution package for the median rolling-policy episode."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.build_bc_network_demo import _policy_execution, _profiles  # noqa: E402

MODEL = ROOT / "runtime/private/bc-network/model"


def main() -> None:
    """Read the current artifacts and write policy-execution.json."""
    network = json.loads((MODEL / "network.json").read_text(encoding="utf-8"))
    strategic = json.loads((MODEL / "strategic.json").read_text(encoding="utf-8"))
    rolling = json.loads((MODEL / "rolling-policy.json").read_text(encoding="utf-8"))
    selected = next(
        scenario for scenario in strategic["milp_scenarios"] if "60000" in scenario["name"]
    )
    execution = _policy_execution(
        rolling,
        selected["plan"]["actions"],
        network["segments"],
        network["units"],
        network["towers"],
        _profiles(),
    )
    (MODEL / "policy-execution.json").write_text(
        json.dumps(execution, indent=2) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "episode": execution["selection"]["episode_index"],
                "year": execution["selection"]["year"],
                "policy_actions": execution["policy"]["actions"],
                "policy_cost": execution["policy"]["cost"],
                "policy_hours": execution["policy"]["hours"],
                "tactical_actions": execution["policy"]["tactical_actions"],
                "work_orders": execution["policy"]["work_orders"],
                "shift_assignments": execution["policy"]["shift_assignments"],
                "resource_feasible": execution["policy"]["resource_feasible"],
                "shift_feasible": execution["policy"]["shift_feasible"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
