# mypy: ignore-errors
"""Benchmark the rolling-horizon policy on a replicated 590-segment instance."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from brushline.strategic.rolling_policy import simulate_rolling_policy
from brushline.strategic.stateful import StatefulConfig, build_stateful_plan

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "runtime/private/bc-network/scaling"
FACTOR = 10
EPISODES = 20
LOOKAHEAD = 2
HEURISTIC_ITERATIONS = 100
SEED = 7

import sys  # noqa: E402

sys.path.insert(0, str(ROOT))
from tools.benchmark_stateful_scaling import _methods, _periods, _segments  # noqa: E402


def main() -> None:
    """Solve a nominal fixed plan and run the rolling policy at 590 segments."""
    OUT.mkdir(parents=True, exist_ok=True)
    segments = _segments(FACTOR)
    methods = _methods()
    periods = _periods(FACTOR)
    config = StatefulConfig(risk_weight=1.0, cost_weight=0.0, max_seconds=60)
    started = time.perf_counter()
    fixed = build_stateful_plan(
        instance_id="rolling-scale-590",
        segments=segments,
        methods=methods,
        periods=periods,
        config=config,
    )
    fixed_seconds = time.perf_counter() - started
    started = time.perf_counter()
    rolling = simulate_rolling_policy(
        instance_id="rolling-scale-590",
        segments=segments,
        methods=methods,
        periods=periods,
        fixed=fixed,
        config=config,
        episodes=EPISODES,
        lookahead_years=LOOKAHEAD,
        solver="heuristic",
        heuristic_iterations=HEURISTIC_ITERATIONS,
        seed=SEED,
        created_utc=fixed.created_utc,
    )
    rolling_seconds = time.perf_counter() - started
    payload: dict[str, Any] = {
        "factor": FACTOR,
        "segments": len(segments),
        "episodes": EPISODES,
        "lookahead_years": LOOKAHEAD,
        "solver": "heuristic",
        "fixed_solver": "exact",
        "fixed_seconds": round(fixed_seconds, 2),
        "rolling_seconds": round(rolling_seconds, 2),
        "fixed_status": fixed.status,
        "fixed_cost": fixed.total_cost,
        "fixed_risk": fixed.mean_risk,
        "rolling": rolling.model_dump(mode="json"),
    }
    (OUT / "rolling-590.json").write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "segments": len(segments),
                "fixed_seconds": round(fixed_seconds, 2),
                "rolling_seconds": round(rolling_seconds, 2),
                "fixed_status": fixed.status,
                "fixed_cost": fixed.total_cost,
                "fixed_risk": fixed.mean_risk,
                "rolling_cost_band": rolling.rolling_cost_band.model_dump(),
                "rolling_risk_band": rolling.rolling_risk_band.model_dump(),
                "fixed_budget_violation": rolling.fixed_budget_violation_probability,
                "rolling_budget_violation": rolling.rolling_budget_violation_probability,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
