"""Coverage and approximate value of information."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

VALUE_SCHEMA_VERSION: Literal["brushline.monitoring-value.v1"] = "brushline.monitoring-value.v1"


class MonitoringCandidate(BaseModel):
    """One monitoring candidate.

    Parameters
    ----------
    candidate_id : str
        Candidate id.
    span_id : str
        Span.
    cost : float
        Cost.
    coverage : float
        Coverage from 0 to 1.
    uncertainty : float
        Current uncertainty.
    expected_loss_reduction : float
        Expected decision-loss reduction.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    candidate_id: str = Field(min_length=1)
    span_id: str = Field(min_length=1)
    cost: float = Field(ge=0)
    coverage: float = Field(ge=0, le=1)
    uncertainty: float = Field(ge=0, le=1)
    expected_loss_reduction: float = Field(ge=0)


class MonitoringChoice(BaseModel):
    """One selected candidate."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    candidate_id: str
    span_id: str
    cost: float = Field(ge=0)
    coverage: float = Field(ge=0, le=1)
    expected_loss_reduction: float
    value_of_information: float


class MonitoringValue(BaseModel):
    """A value-of-information report.

    Parameters
    ----------
    schema_version : {"brushline.monitoring-value.v1"}
        Schema version.
    report_id : str
        Report id.
    choices : list of MonitoringChoice
        Selected choices.
    total_cost : float
        Total cost.
    expected_loss_reduction : float
        Sum of reductions.
    value_of_information : float
        Reduction minus cost.
    regret_per_dollar : float
        Reduction divided by cost.
    feasible : bool
        Budget satisfied.
    created_utc : datetime
        Timezone-aware time.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["brushline.monitoring-value.v1"] = VALUE_SCHEMA_VERSION
    report_id: str
    choices: list[MonitoringChoice]
    total_cost: float = Field(ge=0)
    expected_loss_reduction: float
    value_of_information: float
    regret_per_dollar: float
    feasible: bool
    created_utc: datetime


def select_monitoring(
    candidates: list[MonitoringCandidate],
    *,
    report_id: str,
    budget: float,
    value_per_loss: float = 1.0,
    created_utc: datetime | None = None,
) -> MonitoringValue:
    """Select candidates greedily by net value and budget.

    Parameters
    ----------
    candidates : list of MonitoringCandidate
        Candidates.
    report_id : str
        Report id.
    budget : float
        Budget.
    value_per_loss : float, optional
        Value per loss unit.
    created_utc : datetime, optional
        Creation time.

    Returns
    -------
    MonitoringValue
        Selection and regret-per-dollar evidence.
    """
    if budget < 0 or value_per_loss < 0:
        raise ValueError("budget and value_per_loss must be non-negative")
    ranked = sorted(
        candidates,
        key=lambda item: (
            -(item.expected_loss_reduction * value_per_loss - item.cost),
            item.candidate_id,
        ),
    )
    choices: list[MonitoringChoice] = []
    total = 0.0
    selected_spans: set[str] = set()
    for item in ranked:
        if item.span_id in selected_spans:
            continue
        net = item.expected_loss_reduction * value_per_loss - item.cost
        if net <= 0 or total + item.cost > budget + 1e-9:
            continue
        choices.append(
            MonitoringChoice(
                candidate_id=item.candidate_id,
                span_id=item.span_id,
                cost=item.cost,
                coverage=item.coverage,
                expected_loss_reduction=item.expected_loss_reduction,
                value_of_information=net,
            )
        )
        selected_spans.add(item.span_id)
        total += item.cost
    reduction = sum(item.expected_loss_reduction for item in choices)
    return MonitoringValue(
        report_id=report_id,
        choices=choices,
        total_cost=total,
        expected_loss_reduction=reduction,
        value_of_information=reduction * value_per_loss - total,
        regret_per_dollar=reduction / total if total else 0.0,
        feasible=total <= budget + 1e-9,
        created_utc=created_utc or datetime.now(UTC),
    )


def fixed_calendar(
    candidates: list[MonitoringCandidate],
    *,
    report_id: str,
    budget: float,
    created_utc: datetime | None = None,
) -> MonitoringValue:
    """Select a deterministic fixed-calendar baseline.

    Parameters
    ----------
    candidates : list of MonitoringCandidate
        Candidates.
    report_id : str
        Report id.
    budget : float
        Budget.
    created_utc : datetime, optional
        Creation time.

    Returns
    -------
    MonitoringValue
        Fixed-calendar selection.
    """
    choices: list[MonitoringChoice] = []
    total = 0.0
    for item in sorted(candidates, key=lambda candidate: candidate.candidate_id):
        if total + item.cost > budget + 1e-9:
            break
        choices.append(
            MonitoringChoice(
                candidate_id=item.candidate_id,
                span_id=item.span_id,
                cost=item.cost,
                coverage=item.coverage,
                expected_loss_reduction=item.expected_loss_reduction,
                value_of_information=item.expected_loss_reduction - item.cost,
            )
        )
        total += item.cost
    reduction = sum(item.expected_loss_reduction for item in choices)
    return MonitoringValue(
        report_id=report_id,
        choices=choices,
        total_cost=total,
        expected_loss_reduction=reduction,
        value_of_information=reduction - total,
        regret_per_dollar=reduction / total if total else 0.0,
        feasible=total <= budget + 1e-9,
        created_utc=created_utc or datetime.now(UTC),
    )


__all__ = [
    "VALUE_SCHEMA_VERSION",
    "MonitoringCandidate",
    "MonitoringChoice",
    "MonitoringValue",
    "fixed_calendar",
    "select_monitoring",
]
