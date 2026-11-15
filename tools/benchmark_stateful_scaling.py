# mypy: ignore-errors
"""Benchmark exact stateful MILP scaling and Fresh Solutions convergence.

Run from the Brushline repository after the BC network model has been generated.
The benchmark uses replicated, slightly perturbed segments from that model.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from brushline.strategic.heuristic import StatefulHeuristicAdapter
from brushline.strategic.stateful import (
    StatefulConfig,
    StatefulMethod,
    StatefulPeriod,
    StatefulSegment,
    _build_problem,
    replay_stateful_choices,
)
from fresh_solutions import ConvergenceConfig, PopulationConfig, SearchConfig, run_to_convergence
from scipy.optimize import LinearConstraint, milp

ROOT = Path(__file__).resolve().parents[1]
MODEL = ROOT / "runtime/private/bc-network/model"
OUT = ROOT / "runtime/private/bc-network/scaling"
START_YEAR = 2027
HORIZON = 5
BUDGET = 60000.0
CAPACITY = 6000.0
EXACT_SECONDS = 120.0
HEURISTIC_EVALS = 100_000

METHODS = {
    "mowing": {"cost_ha": 420, "hours_ha": 7, "risk_reduction": 0.30},
    "mechanical": {"cost_ha": 900, "hours_ha": 14, "risk_reduction": 0.42},
    "manual": {"cost_ha": 1450, "hours_ha": 32, "risk_reduction": 0.55},
}


def _segments(factor: int) -> list[StatefulSegment]:
    network = json.loads((MODEL / "network.json").read_text(encoding="utf-8"))
    base = network["segments"]
    result = []
    for copy in range(factor):
        for index, segment in enumerate(base):
            risk = min(0.90, max(0.0, segment["base_risk"] + ((copy + index) % 7 - 3) * 0.005))
            result.append(
                StatefulSegment(
                    segment_id=f"{segment['segment_id']}-{copy}",
                    span_id=f"{segment['unit_id']}-{copy}",
                    length_m=segment["length_m"],
                    area_ha=segment["length_m"] * segment["width_m"] / 10000.0,
                    initial_risk=risk,
                )
            )
    return result


def _methods() -> list[StatefulMethod]:
    return [
        StatefulMethod(
            method=method,
            cost_per_ha=params["cost_ha"],
            hours_per_ha=params["hours_ha"],
            risk_reduction=params["risk_reduction"],
        )
        for method, params in METHODS.items()
    ]


def _periods(factor: int) -> list[StatefulPeriod]:
    return [
        StatefulPeriod(
            year=START_YEAR + offset,
            budget=BUDGET * factor,
            capacity_hours=CAPACITY * factor,
        )
        for offset in range(HORIZON)
    ]


def _exact(
    segments: list[StatefulSegment], methods: list[StatefulMethod], periods: list[StatefulPeriod]
) -> dict[str, Any]:
    config = StatefulConfig(risk_weight=1.0, cost_weight=0.0, max_seconds=EXACT_SECONDS)
    started = time.perf_counter()
    c, integrality, bounds, matrix, lower, upper, x_index = _build_problem(
        segments, methods, periods, config
    )
    formulated = time.perf_counter()
    result = milp(
        c,
        integrality=integrality,
        bounds=bounds,
        constraints=LinearConstraint(matrix, lower, upper),
        options={"time_limit": EXACT_SECONDS, "mip_rel_gap": 0.0},
    )
    solved = time.perf_counter()
    selected = (
        {key: bool(result.x[index] > 0.5) for index, key in enumerate(x_index)}
        if result.x is not None
        else {}
    )
    actions, _years, cost, hours, risk = replay_stateful_choices(
        segments, methods, periods, config, selected
    )
    objective = risk if result.x is not None else None
    return {
        "status": int(result.status),
        "success": bool(result.success),
        "formulate_seconds": round(formulated - started, 4),
        "solve_seconds": round(solved - formulated, 4),
        "objective": objective,
        "mip_gap": getattr(result, "mip_gap", None),
        "dual_bound": getattr(result, "mip_dual_bound", None),
        "node_count": getattr(result, "mip_node_count", None),
        "actions": len(actions),
        "cost": round(cost, 2),
        "risk": round(risk, 4),
        "hours": round(hours, 2),
    }


def _heuristic(
    segments: list[StatefulSegment], methods: list[StatefulMethod], periods: list[StatefulPeriod]
) -> dict[str, Any]:
    adapter = StatefulHeuristicAdapter(
        segments, methods, periods, StatefulConfig(risk_weight=1.0, cost_weight=0.0)
    )
    started = time.perf_counter()
    result = run_to_convergence(
        adapter,
        PopulationConfig(population=16, generations=4, seed=7, mutation_rate=0.10),
        SearchConfig(iterations=1000, seed=7, temperature=2.0, cooling=0.999),
        ConvergenceConfig(
            local_iterations_per_round=500,
            patience_rounds=5,
            min_relative_improvement=1e-4,
            max_rounds=20,
            max_evaluations=HEURISTIC_EVALS,
        ),
    )
    elapsed = time.perf_counter() - started
    selected = adapter._selected(result.assignment)
    actions, _years, cost, hours, risk = replay_stateful_choices(
        segments, methods, periods, StatefulConfig(risk_weight=1.0, cost_weight=0.0), selected
    )
    return {
        "status": "converged" if result.converged else "not_converged",
        "converged": result.converged,
        "stop_reason": result.stop_reason,
        "seconds": round(elapsed, 2),
        "evaluations": result.evaluations,
        "rounds": result.rounds,
        "objective": risk,
        "risk": risk,
        "cost": cost,
        "hours": hours,
        "actions": len(actions),
    }


def main() -> None:
    """Run exact and heuristic scaling benchmarks."""
    OUT.mkdir(parents=True, exist_ok=True)
    results = []
    methods = _methods()
    for factor in (1, 2, 4, 8, 16):
        segments = _segments(factor)
        periods = _periods(factor)
        print(f"factor={factor} segments={len(segments)}", flush=True)
        exact = _exact(segments, methods, periods)
        print(" exact", exact, flush=True)
        heuristic = _heuristic(segments, methods, periods)
        print(" heuristic", heuristic, flush=True)
        gap = None
        if exact["success"] and exact["status"] == 0 and exact["objective"] not in (None, 0):
            gap = (heuristic["objective"] - exact["objective"]) / abs(exact["objective"])
        bound_gap = None
        if exact["dual_bound"] not in (None, 0):
            bound_gap = (heuristic["objective"] - exact["dual_bound"]) / abs(exact["dual_bound"])
        item = {
            "factor": factor,
            "segments": len(segments),
            "variables": len(segments) * HORIZON * (len(methods) + 1),
            "binaries": len(segments) * HORIZON * len(methods),
            "exact": exact,
            "heuristic": heuristic,
            "relative_gap": gap,
            "heuristic_gap_to_dual_bound": bound_gap,
        }
        results.append(item)
        (OUT / "scaling.json").write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
        if not exact["success"] or exact["status"] != 0:
            print(" exact solve did not reach optimality; stopping", flush=True)
            break
    optimal = [
        item for item in results if item["exact"]["success"] and item["exact"]["status"] == 0
    ]
    fit = {}
    if len(optimal) >= 2:
        import numpy as np

        sizes = np.asarray([item["segments"] for item in optimal], dtype=float)
        exact_times = np.asarray([item["exact"]["solve_seconds"] for item in optimal], dtype=float)
        heuristic_times = np.asarray(
            [item["heuristic"]["seconds"] for item in optimal], dtype=float
        )
        exact_fit = np.polyfit(np.log(sizes), np.log(exact_times), 1)
        heuristic_fit = np.polyfit(sizes, heuristic_times, 1)
        fit = {
            "exact_loglog_slope": round(float(exact_fit[0]), 4),
            "exact_loglog_intercept": round(float(exact_fit[1]), 4),
            "heuristic_seconds_per_segment": round(float(heuristic_fit[0]), 6),
            "heuristic_seconds_intercept": round(float(heuristic_fit[1]), 4),
            "optimal_points": len(optimal),
        }
    payload = {"results": results, "fit": fit}
    (OUT / "scaling.json").write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(f"fit {fit}")
    print(f"wrote {OUT / 'scaling.json'}")


if __name__ == "__main__":
    main()
