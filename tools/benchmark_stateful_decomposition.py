# mypy: ignore-errors
"""Benchmark heuristic seed versus budget-preserving cluster repair."""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Any

from brushline.strategic.decomposition import repair_stateful_clusters
from brushline.strategic.heuristic import build_stateful_heuristic
from brushline.strategic.stateful import StatefulConfig, StatefulMethod

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.benchmark_stateful_scaling import METHODS, _periods, _segments  # noqa: E402

OUT = ROOT / "runtime/private/bc-network/scaling"
MAX_SEGMENTS = 150
HEURISTIC_ITERATIONS = 100
CLUSTER_SECONDS = 30.0


def main() -> None:
    """Run cluster repair at 590, 2,950, and 10,030 segments."""
    methods = [
        StatefulMethod(
            method=method,
            cost_per_ha=params["cost_ha"],
            hours_per_ha=params["hours_ha"],
            risk_reduction=params["risk_reduction"],
        )
        for method, params in METHODS.items()
    ]
    results: list[dict[str, Any]] = []
    for factor in (10, 50, 170):
        segments = _segments(factor)
        periods = _periods(factor)
        config = StatefulConfig(risk_weight=1.0, cost_weight=0.0, max_seconds=CLUSTER_SECONDS)
        started = time.perf_counter()
        baseline = build_stateful_heuristic(
            instance_id=f"decomp-{factor}",
            segments=segments,
            methods=methods,
            periods=periods,
            config=config,
            iterations=HEURISTIC_ITERATIONS,
            seed=7,
        )
        heuristic_seconds = time.perf_counter() - started
        started = time.perf_counter()
        repaired = repair_stateful_clusters(
            instance_id=f"decomp-{factor}",
            segments=segments,
            methods=methods,
            periods=periods,
            baseline=baseline,
            config=config,
            max_segments_per_cluster=MAX_SEGMENTS,
        )
        repair_seconds = time.perf_counter() - started
        item = {
            "factor": factor,
            "segments": len(segments),
            "clusters": repaired.cluster_count,
            "heuristic_iterations": HEURISTIC_ITERATIONS,
            "heuristic_seconds": round(heuristic_seconds, 2),
            "heuristic_objective": baseline.objective,
            "repair_seconds": round(repair_seconds, 2),
            "repaired_objective": repaired.plan.objective,
            "relative_gap": repaired.gap_to_baseline,
            "cluster_statuses": {
                status: sum(1 for cluster in repaired.clusters if cluster.status == status)
                for status in ("optimal", "feasible", "infeasible")
            },
            "all_clusters_optimal": all(
                cluster.status == "optimal" for cluster in repaired.clusters
            ),
            "replay_ok": repaired.plan.replay_ok,
        }
        print(item, flush=True)
        results.append(item)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "decomposition.json").write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {OUT / 'decomposition.json'}")


if __name__ == "__main__":
    main()
