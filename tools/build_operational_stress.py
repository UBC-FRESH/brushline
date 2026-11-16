# mypy: ignore-errors
"""Generate the assumed weather/outage stress for the median policy execution."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.build_bc_network_demo import _operational_stress, _profiles  # noqa: E402

MODEL = ROOT / "runtime/private/bc-network/model"


def main() -> None:
    """Write operational-stress.json."""
    execution = json.loads((MODEL / "policy-execution.json").read_text(encoding="utf-8"))
    stress = _operational_stress(execution, _profiles())
    (MODEL / "operational-stress.json").write_text(
        json.dumps(stress, indent=2) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "baseline": stress["baseline"],
                "scenarios": stress["scenarios"],
                "completion_probability": stress["completion_probability"],
                "mean_completion_rate": stress["mean_completion_rate"],
                "unscheduled_hours_band": stress["unscheduled_hours_band"],
                "blocked_days_band": stress["blocked_days_band"],
                "failed_scenarios": len(stress["failed_scenarios"]),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
