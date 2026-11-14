"""Deterministic prototype simulator.

The prototype uses a linear growth rule and a fractional treatment transition. It is not the
calibrated P4 model. Its job is to exercise the compiled dataset, the plan or schedule, the run
writer, and the studio artifact contract end to end.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import cast

import pandas as pd

from brushline.model.plan import Plan, validate_plan
from brushline.model.run import RunManifest
from brushline.model.schema import validate_dataset
from brushline.run import RunArtifactSpec, write_run_manifest
from brushline.sim.schedule import SCHEDULE_COLUMNS, ScheduleRow, load_schedule, schedule_from_plan

GROWTH_PER_YEAR_M: float = 0.25
COVER_GROWTH_PER_YEAR_PCT: float = 2.0
DENSITY_GROWTH_PER_YEAR: float = 1.05
MAX_HEIGHT_M: float = 10.0


@dataclass(frozen=True)
class SimulationResult:
    """The output of one prototype simulation.

    Parameters
    ----------
    run_dir : Path
        Run directory.
    accounts : pandas.DataFrame
        Long account values, one row per year and account.
    schedule : pandas.DataFrame
        Replayed schedule with status.
    state_values : pandas.DataFrame
        Per-segment, per-year state values.
    summary : dict of str to object
        Run summary.
    """

    run_dir: Path
    accounts: pd.DataFrame
    schedule: pd.DataFrame
    state_values: pd.DataFrame
    summary: dict[str, object]


def simulate_dataset(
    dataset: Path,
    out: Path,
    *,
    plan: Path | None = None,
    schedule: Path | None = None,
    years: int = 5,
    start_year: int = 2026,
    force: bool = False,
) -> SimulationResult:
    """Replay a plan or schedule against a compiled dataset.

    Parameters
    ----------
    dataset : Path
        Compiled dataset directory.
    out : Path
        Run directory.
    plan : Path or None, optional
        Plan artifact. Exactly one of ``plan`` and ``schedule`` is required.
    schedule : Path or None, optional
        Schedule CSV. Exactly one of ``plan`` and ``schedule`` is required.
    years : int, optional
        Number of simulation years. Defaults to ``5``.
    start_year : int, optional
        First simulation year. Defaults to ``2026``.
    force : bool, optional
        Overwrite a non-empty run directory. Defaults to ``False``.

    Returns
    -------
    SimulationResult
        The run directory, accounts, schedule, state values, and summary.

    Raises
    ------
    ValueError
        When the input selection is invalid, the dataset is invalid, or a schedule references an
        unknown segment.
    FileExistsError
        When the output directory is not empty and ``force`` is false.
    """
    if (plan is None) == (schedule is None):
        raise ValueError("provide exactly one of --plan or --schedule")
    if years < 1:
        raise ValueError("years must be at least 1")
    dataset = Path(dataset).expanduser().resolve()
    report = validate_dataset(dataset)
    if not report.is_valid:
        raise ValueError("; ".join(report.errors))
    dataset_manifest = json.loads((dataset / "manifest.json").read_text(encoding="utf-8"))
    segments = pd.read_parquet(dataset / "segments.parquet")
    states = pd.read_parquet(dataset / "states.parquet")
    segment_ids = {str(value) for value in segments["segment_id"].tolist()}
    schedule_rows = _load_rows(plan, schedule, segment_ids)
    segment_map = _segment_map(segments)
    state_map = _state_map(states)
    missing = sorted(segment_ids - set(state_map))
    if missing:
        raise ValueError(f"segments without a state: {', '.join(missing)}")

    start_actions: dict[int, dict[str, list[ScheduleRow]]] = {}
    for row in schedule_rows:
        start_actions.setdefault(row.year, {}).setdefault(row.segment_id, []).append(row)
    end_year = start_year + years - 1
    schedule_records: list[dict[str, object]] = []
    for row in schedule_rows:
        status = "applied" if start_year <= row.year <= end_year else "outside_horizon"
        schedule_records.append({**row.model_dump(), "status": status})
    schedule_frame = pd.DataFrame(schedule_records)
    if schedule_frame.empty:
        schedule_frame = pd.DataFrame(columns=[*SCHEDULE_COLUMNS, "status"])

    state_runtime = {segment_id: dict(values) for segment_id, values in state_map.items()}
    state_records: list[dict[str, object]] = []
    account_records: list[dict[str, object]] = []
    total_cost = 0.0
    actions_applied = 0
    for year in range(start_year, end_year + 1):
        year_actions = start_actions.get(year, {})
        year_cost = 0.0
        year_treated = 0
        for segment_id in sorted(segment_ids):
            values = state_runtime[segment_id]
            actions = year_actions.get(segment_id, [])
            action_cost = 0.0
            if actions:
                for action in actions:
                    values["height_m"] = _number(values["height_m"]) * (1.0 - action.efficacy)
                    values["cover_pct"] = _number(values["cover_pct"]) * (1.0 - action.efficacy)
                    density = values["density_per_ha"]
                    if isinstance(density, float) and not math.isnan(density):
                        values["density_per_ha"] = density * (1.0 - 0.5 * action.efficacy)
                    action_cost += action.cost
                year_cost += action_cost
                year_treated += len(actions)
                total_cost += action_cost
                actions_applied += len(actions)
            elif values["state_class"] != "unknown":
                values["height_m"] = min(
                    _number(values["height_m"]) + GROWTH_PER_YEAR_M,
                    MAX_HEIGHT_M,
                )
                values["cover_pct"] = min(
                    _number(values["cover_pct"]) + COVER_GROWTH_PER_YEAR_PCT,
                    100.0,
                )
                density = values["density_per_ha"]
                if isinstance(density, float) and not math.isnan(density):
                    values["density_per_ha"] = density * DENSITY_GROWTH_PER_YEAR
            state_records.append(
                {
                    "year": year,
                    "segment_id": segment_id,
                    "functional_group": values["functional_group"],
                    "state_class": values["state_class"],
                    "height_m": round(_number(values["height_m"]), 6),
                    "cover_pct": round(_number(values["cover_pct"]), 6),
                    "density_per_ha": values["density_per_ha"],
                    "action_cost": round(action_cost, 2),
                }
            )
        known = [values for values in state_runtime.values() if values["state_class"] != "unknown"]
        mean_height = (
            sum(_number(values["height_m"]) for values in known) / len(known) if known else 0.0
        )
        mean_cover = (
            sum(_number(values["cover_pct"]) for values in known) / len(known) if known else 0.0
        )
        max_height = max((_number(values["height_m"]) for values in known), default=0.0)
        violations = 0
        for segment_id, values in state_runtime.items():
            if values["state_class"] == "unknown":
                continue
            max_height = float(cast("float", segment_map[segment_id]["max_height_m"]))
            if _number(values["height_m"]) > max_height:
                violations += 1
        unknown = sum(1 for values in state_runtime.values() if values["state_class"] == "unknown")
        account_records.extend(
            [
                _account(year, "vegetation.mean_height_m", round(mean_height, 6), "m"),
                _account(year, "vegetation.mean_cover_pct", round(mean_cover, 6), "%"),
                _account(year, "vegetation.max_height_m", round(max_height, 6), "m"),
                _account(year, "vegetation.unknown_segments", unknown, "count"),
                _account(year, "vegetation.clearing_violations", violations, "count"),
                _account(year, "treatment.cost", round(year_cost, 2), "CAD"),
                _account(year, "treatment.segments", year_treated, "count"),
            ]
        )
    accounts = pd.DataFrame(account_records)
    state_values = pd.DataFrame(state_records)
    target = Path(out).expanduser().resolve()
    if target.exists() and any(target.iterdir()) and not force:
        raise FileExistsError(f"{target} is not empty; pass force=True to overwrite")
    target.mkdir(parents=True, exist_ok=True)
    schedule_frame.to_csv(target / "schedule.csv", index=False)
    accounts.to_csv(target / "account_values.csv", index=False)
    state_values.to_csv(target / "state_values.csv", index=False)
    _write_summary(target / "reports" / "summary.md", dataset, schedule_rows, start_year, end_year)
    final = accounts[accounts["year"] == end_year].set_index("account")["value"].to_dict()
    summary: dict[str, object] = {
        "start_year": start_year,
        "end_year": end_year,
        "years": years,
        "actions_applied": actions_applied,
        "actions_outside_horizon": len(
            [row for row in schedule_rows if not start_year <= row.year <= end_year]
        ),
        "total_cost": round(total_cost, 2),
        "final_mean_height_m": float(final["vegetation.mean_height_m"]),
        "final_mean_cover_pct": float(final["vegetation.mean_cover_pct"]),
        "final_max_height_m": float(final["vegetation.max_height_m"]),
        "unknown_segments": int(final["vegetation.unknown_segments"]),
        "clearing_violations": int(final["vegetation.clearing_violations"]),
    }
    data_version = str(dataset_manifest.get("content_digest", ""))
    write_run_manifest(
        target,
        run_id=f"sim-{start_year}-{years}",
        run_type="simulate",
        status="complete",
        data_version=data_version,
        model_versions={"growth": "prototype-linear-v1", "treatment": "prototype-fraction-v1"},
        configuration={
            "dataset": str(dataset),
            "plan": str(plan) if plan is not None else None,
            "schedule": str(schedule) if schedule is not None else None,
            "start_year": start_year,
            "years": years,
        },
        summary=summary,
        artifacts=[
            RunArtifactSpec("schedule", "schedule.csv", "brushline.schedule.v1", "text/csv"),
            RunArtifactSpec("accounts", "account_values.csv", "brushline.accounts.v1", "text/csv"),
            RunArtifactSpec(
                "state_values",
                "state_values.csv",
                "brushline.state-values.v1",
                "text/csv",
            ),
            RunArtifactSpec("report", "reports/summary.md", "text/markdown", "text/markdown"),
        ],
    )
    return SimulationResult(target, accounts, schedule_frame, state_values, summary)


def _load_rows(
    plan: Path | None,
    schedule: Path | None,
    segment_ids: set[str],
) -> list[ScheduleRow]:
    if plan is not None:
        plan_path = Path(plan).expanduser().resolve()
        artifact = Plan.model_validate_json(plan_path.read_text(encoding="utf-8"))
        report = validate_plan(artifact, known_segment_ids=segment_ids)
        if not report.is_valid:
            raise ValueError("; ".join(report.errors))
        rows = schedule_from_plan(artifact)
    else:
        if schedule is None:
            raise ValueError("a plan or a schedule is required")
        rows = load_schedule(Path(schedule).expanduser().resolve())
    unknown = sorted({row.segment_id for row in rows} - segment_ids)
    if unknown:
        raise ValueError(f"schedule references unknown segments: {', '.join(unknown)}")
    return rows


def _segment_map(segments: pd.DataFrame) -> dict[str, dict[str, object]]:
    records = cast("list[dict[str, object]]", segments.to_dict(orient="records"))
    return {
        str(record["segment_id"]): {
            "max_height_m": float(cast("float", record["max_height_m"])),
            "span_id": str(record["span_id"]),
        }
        for record in records
    }


def _state_map(states: pd.DataFrame) -> dict[str, dict[str, object]]:
    ordered = states.sort_values(["segment_id", "cover_pct"], ascending=[True, False])
    records = cast("list[dict[str, object]]", ordered.to_dict(orient="records"))
    result: dict[str, dict[str, object]] = {}
    for record in records:
        segment_id = str(record["segment_id"])
        if segment_id in result:
            continue
        density = record["density_per_ha"]
        density_value: float | None = None
        if isinstance(density, (int, float)) and not (
            isinstance(density, float) and math.isnan(density)
        ):
            density_value = float(density)
        result[segment_id] = {
            "functional_group": str(record["functional_group"]),
            "state_class": str(record["state_class"]),
            "height_m": float(cast("float", record["height_m"])),
            "cover_pct": float(cast("float", record["cover_pct"])),
            "density_per_ha": density_value if density_value is not None else float("nan"),
        }
    return result


def _account(year: int, name: str, value: float | int, unit: str) -> dict[str, object]:
    return {"year": year, "account": name, "value": value, "unit": unit}


def _number(value: object) -> float:
    return float(cast("float", value))


def _write_summary(
    path: Path,
    dataset: Path,
    schedule_rows: list[ScheduleRow],
    start_year: int,
    end_year: int,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        (
            "# Prototype simulation report\n\n"
            f"- Dataset: {dataset}\n"
            f"- Horizon: {start_year} to {end_year}\n"
            f"- Scheduled actions: {len(schedule_rows)}\n"
            "- Model: prototype linear growth and fractional treatment; not the calibrated P4\n"
            "  model.\n"
        ),
        encoding="utf-8",
    )


def read_run_summary(run_dir: Path) -> RunManifest:
    """Read a run manifest.

    Parameters
    ----------
    run_dir : Path
        Run directory.

    Returns
    -------
    RunManifest
        The parsed run manifest.
    """
    return RunManifest.model_validate_json((Path(run_dir) / "run.json").read_text(encoding="utf-8"))


__all__ = ["SimulationResult", "read_run_summary", "simulate_dataset"]
