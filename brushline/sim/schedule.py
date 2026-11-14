"""Schedule rows and conversion from a plan.

A schedule is the minimal action list the simulator replays: segment, year, method, intensity,
efficacy, and cost. The prototype accepts a CSV or a plan artifact. The calibrated production path
will add the richer plan contract.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
from pydantic import BaseModel, ConfigDict, Field

from brushline.model.plan import Plan
from brushline.model.state import TreatmentMethod

SCHEDULE_SCHEMA_VERSION = "brushline.schedule.v1"
SCHEDULE_COLUMNS: tuple[str, ...] = (
    "segment_id",
    "year",
    "action_id",
    "method",
    "intensity",
    "efficacy",
    "cost",
)


class ScheduleRow(BaseModel):
    """One treatment action in a schedule.

    Parameters
    ----------
    segment_id : str
        Segment identifier.
    year : int
        Treatment year.
    action_id : str
        Action identifier.
    method : {"manual", "mechanical", "chemical", "mowing", "grazing", "prescribed_fire", "other"}
        Treatment method.
    intensity : float
        Intensity from 0 to 1.
    efficacy : float
        Efficacy from 0 to 1.
    cost : float
        Action cost. Must be non-negative.
    """

    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)

    segment_id: str = Field(min_length=1)
    year: int = Field(ge=1900, le=2200)
    action_id: str = Field(min_length=1)
    method: TreatmentMethod
    intensity: float = Field(ge=0, le=1)
    efficacy: float = Field(ge=0, le=1)
    cost: float = Field(ge=0)


def schedule_from_plan(plan: Plan) -> list[ScheduleRow]:
    """Convert a plan's actions into schedule rows.

    Parameters
    ----------
    plan : Plan
        Plan artifact.

    Returns
    -------
    list of ScheduleRow
        One row per plan action, in plan order.
    """
    return [
        ScheduleRow(
            segment_id=action.segment_id,
            year=action.year,
            action_id=action.action_id,
            method=action.method,
            intensity=action.intensity,
            efficacy=action.efficacy,
            cost=action.action_cost,
        )
        for action in plan.actions
    ]


def load_schedule(path: Path) -> list[ScheduleRow]:
    """Load a schedule CSV.

    Parameters
    ----------
    path : Path
        CSV file with the columns ``segment_id``, ``year``, ``action_id``, ``method``,
        ``intensity``, ``efficacy``, and ``cost``.

    Returns
    -------
    list of ScheduleRow
        Validated schedule rows.

    Raises
    ------
    ValueError
        When a required column is missing or a row is invalid.
    """
    frame = pd.read_csv(path)
    missing = [column for column in SCHEDULE_COLUMNS if column not in frame.columns]
    if missing:
        raise ValueError(f"schedule is missing columns: {', '.join(missing)}")
    rows: list[ScheduleRow] = []
    for record in frame[list(SCHEDULE_COLUMNS)].to_dict(orient="records"):
        rows.append(ScheduleRow.model_validate(record))
    return rows


__all__ = [
    "SCHEDULE_COLUMNS",
    "SCHEDULE_SCHEMA_VERSION",
    "ScheduleRow",
    "load_schedule",
    "schedule_from_plan",
]
