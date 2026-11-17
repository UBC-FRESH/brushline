# mypy: ignore-errors
"""Benchmark rolling recourse at 590 replicated segments."""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from brushline.strategic.rolling_recourse import evaluate_rolling_recourse  # noqa: E402
from brushline.strategic.stateful import StatefulConfig, build_stateful_plan  # noqa: E402
from tools.benchmark_stateful_scaling import _methods, _periods, _segments  # noqa: E402

OUT = ROOT / "runtime/private/bc-network/scaling"
FACTOR = 10
EPISODES = 20
LOOKAHEAD = 2
HEURISTIC_ITERATIONS = 100
SEED = 7


def main() -> None:
    """Write rolling-recourse-590.json."""
    OUT.mkdir(parents=True, exist_ok=True)
    segments = _segments(FACTOR)
    methods = _methods()
    periods = _periods(FACTOR)
    config = StatefulConfig(risk_weight=1.0, cost_weight=0.0, max_seconds=120)
    started = time.perf_counter()
    plan = build_stateful_plan(
        instance_id="rolling-recourse-scale-590",
        segments=segments,
        methods=methods,
        periods=periods,
        config=config,
    )
    fixed_seconds = time.perf_counter() - started
    started = time.perf_counter()
    result = evaluate_rolling_recourse(
        instance_id="rolling-recourse-scale-590",
        plan=plan,
        segments=segments,
        methods=methods,
        periods=periods,
        config=StatefulConfig(risk_weight=1.0, cost_weight=0.0, max_seconds=60),
        episodes=EPISODES,
        seed=SEED,
        solver="heuristic",
        heuristic_iterations=HEURISTIC_ITERATIONS,
        lookahead_years=LOOKAHEAD,
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
        "fixed_status": plan.status,
        "fixed_cost": plan.total_cost,
        "fixed_risk": plan.mean_risk,
        "result": result.model_dump(mode="json"),
    }
    (OUT / "rolling-recourse-590.json").write_text(
        json.dumps(payload, indent=2) + "\n", encoding="utf-8"
    )
    for case in result.cases:
        print(
            case.name,
            case.budget_violation_probability,
            case.completion_band.p50,
            case.completion_band.mean,
            case.risk_band.mean,
            case.cost_band.p50,
        )
    print("fixed", plan.status, round(fixed_seconds, 2), "rolling", round(rolling_seconds, 2))


if __name__ == "__main__":
    main()
