"""Plan contract: the shared owner-contractor plan artifact.

A plan has a versioned header, a list of actions with a line-item cost build-up, and a list of
named assumptions. The plan is the exchange object between the owner and the contractor; every
number in it is traceable to a cost line, a rate, or a stated assumption.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from brushline.model.state import Season, TreatmentMethod
from brushline.model.validation import (
    ContractValidation,
    check_duplicates,
)

PLAN_SCHEMA_VERSION: Literal["brushline.plan.v1"] = "brushline.plan.v1"
COST_CATEGORIES: tuple[str, ...] = (
    "labour",
    "equipment",
    "materials",
    "travel",
    "access",
    "supervision",
    "overhead",
    "risk",
    "other",
)
PLAN_STATUSES: tuple[str, ...] = ("draft", "proposed", "approved", "superseded")

CostCategory = Literal[
    "labour",
    "equipment",
    "materials",
    "travel",
    "access",
    "supervision",
    "overhead",
    "risk",
    "other",
]
PlanStatus = Literal["draft", "proposed", "approved", "superseded"]


class CostLine(BaseModel):
    """One line in a plan's cost build-up.

    Parameters
    ----------
    category : {"labour", "equipment", "materials", "travel", "access", "supervision",
        "overhead", "risk", "other"}
        Cost category.
    amount : float
        Line amount. Must be non-negative.
    description : str, optional
        Human description.
    quantity : float or None, optional
        Quantity, when the line is rate-based.
    rate : float or None, optional
        Rate per unit, when the line is rate-based.
    currency : str, optional
        Currency code. Defaults to ``CAD``.
    source : str, optional
        Rate or cost source.
    """

    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)

    category: CostCategory
    amount: float = Field(ge=0)
    description: str = ""
    quantity: float | None = Field(default=None, ge=0)
    rate: float | None = Field(default=None, ge=0)
    currency: str = Field(default="CAD", min_length=1)
    source: str = ""

    @model_validator(mode="after")
    def _amount_matches_rate(self) -> CostLine:
        if self.quantity is not None and self.rate is not None:
            expected = self.quantity * self.rate
            if abs(self.amount - expected) > 0.01:
                raise ValueError(
                    f"amount {self.amount} does not match quantity {self.quantity} "
                    f"times rate {self.rate}"
                )
        return self


class PlanAction(BaseModel):
    """One treatment or monitoring action in a plan.

    Parameters
    ----------
    action_id : str
        Stable action identifier.
    segment_id : str
        Segment identifier.
    year : int
        Action year.
    season : {"spring", "summer", "fall", "winter", "any"}
        Action season.
    method : {"manual", "mechanical", "chemical", "mowing", "grazing", "prescribed_fire", "other"}
        Treatment method.
    intensity : float
        Intensity from 0 to 1.
    efficacy : float, optional
        Expected efficacy from 0 to 1. Defaults to ``0.5``.
    cost_lines : list of CostLine
        Line-item cost build-up. At least one line is required.
    treatment_unit_id : str or None, optional
        Owning treatment unit.
    quantity_ha : float, optional
        Treated area in hectares. Defaults to ``0``.
    quantity_km : float, optional
        Treated corridor length in kilometres. Defaults to ``0``.
    assumptions : list of str, optional
        Assumptions specific to this action.
    risk_notes : str, optional
        Risk notes.
    """

    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)

    action_id: str = Field(min_length=1)
    segment_id: str = Field(min_length=1)
    year: int = Field(ge=1900, le=2200)
    season: Season
    method: TreatmentMethod
    intensity: float = Field(ge=0, le=1)
    efficacy: float = Field(default=0.5, ge=0, le=1)
    cost_lines: list[CostLine] = Field(min_length=1)
    treatment_unit_id: str | None = None
    quantity_ha: float = Field(default=0.0, ge=0)
    quantity_km: float = Field(default=0.0, ge=0)
    assumptions: list[str] = Field(default_factory=list)
    risk_notes: str = ""

    @property
    def action_cost(self) -> float:
        """Return the sum of the action's cost lines.

        Returns
        -------
        float
            Total action cost in the plan currency.
        """
        return sum(line.amount for line in self.cost_lines)


class PlanAssumption(BaseModel):
    """A named assumption in a plan.

    Parameters
    ----------
    assumption_id : str
        Stable assumption identifier.
    statement : str
        The assumption.
    source : str
        Source or owner of the assumption.
    impact : str, optional
        What the assumption affects.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    assumption_id: str = Field(min_length=1)
    statement: str = Field(min_length=1)
    source: str = Field(min_length=1)
    impact: str = ""


class PlanHeader(BaseModel):
    """The versioned header of a plan.

    Parameters
    ----------
    plan_id : str
        Stable plan identifier.
    version : int
        Plan version, starting at 1.
    status : {"draft", "proposed", "approved", "superseded"}
        Plan status.
    scenario_id : str
        Scenario identifier.
    dataset_id : str
        Compiled dataset identifier.
    data_version : str
        Data version or digest.
    model_versions : dict of str to str
        Model ids and versions used by the plan.
    configuration : dict of str to object
        Plan configuration.
    currency : str
        Plan currency.
    created_utc : datetime
        Timezone-aware creation time.
    created_by : str
        Person, process, or agent that created the plan.
    parent_plan_id : str or None, optional
        Previous plan version, when this is a refinement.
    seed : int or None, optional
        Random seed, when a search produced the plan.
    service_standard_ids : list of str, optional
        Service standards used by the plan.
    notes : str, optional
        Free notes.
    """

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["brushline.plan.v1"] = PLAN_SCHEMA_VERSION
    plan_id: str = Field(min_length=1)
    version: int = Field(ge=1)
    status: PlanStatus
    scenario_id: str = Field(min_length=1)
    dataset_id: str = Field(min_length=1)
    data_version: str = Field(min_length=1)
    model_versions: dict[str, str] = Field(min_length=1)
    configuration: dict[str, object] = Field(default_factory=dict)
    currency: str = Field(min_length=1)
    created_utc: datetime
    created_by: str = Field(min_length=1)
    parent_plan_id: str | None = None
    seed: int | None = None
    service_standard_ids: list[str] = Field(default_factory=list)
    notes: str = ""

    @field_validator("created_utc")
    @classmethod
    def _timezone_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("created_utc must be timezone-aware")
        return value


class Plan(BaseModel):
    """A complete plan artifact.

    Parameters
    ----------
    header : PlanHeader
        Plan header.
    actions : list of PlanAction
        Plan actions. At least one is required.
    assumptions : list of PlanAssumption, optional
        Plan-level assumptions.
    """

    model_config = ConfigDict(extra="forbid")

    header: PlanHeader
    actions: list[PlanAction] = Field(min_length=1)
    assumptions: list[PlanAssumption] = Field(default_factory=list)

    @property
    def total_cost(self) -> float:
        """Return the sum of every action's cost.

        Returns
        -------
        float
            Total plan cost in the plan currency.
        """
        return sum(action.action_cost for action in self.actions)


def validate_plan(plan: Plan, *, known_segment_ids: set[str] | None = None) -> ContractValidation:
    """Validate plan ids, references, currencies, and assumptions.

    Parameters
    ----------
    plan : Plan
        Plan to validate.
    known_segment_ids : set of str or None, optional
        Segment ids that the plan may reference. When ``None``, the check is skipped.

    Returns
    -------
    ContractValidation
        Errors, warnings, and counts.
    """
    errors: list[str] = []
    warnings: list[str] = []
    check_duplicates("PLAN", "action", [item.action_id for item in plan.actions], errors)
    check_duplicates(
        "PLAN",
        "assumption",
        [item.assumption_id for item in plan.assumptions],
        errors,
    )
    if plan.header.parent_plan_id == plan.header.plan_id:
        errors.append("PLAN-VERSION: a plan cannot be its own parent")
    for action in plan.actions:
        if known_segment_ids is not None and action.segment_id not in known_segment_ids:
            errors.append(
                f"PLAN-REF: action {action.action_id} references unknown segment "
                f"{action.segment_id}"
            )
        for line in action.cost_lines:
            if line.currency != plan.header.currency:
                errors.append(
                    f"PLAN-CURRENCY: action {action.action_id} line {line.category} uses "
                    f"{line.currency}, expected {plan.header.currency}"
                )
        if not action.assumptions:
            warnings.append(
                f"PLAN-ASSUMPTION: action {action.action_id} has no explicit assumption"
            )
    if "data_version" not in plan.header.model_versions:
        warnings.append(
            "PLAN-VERSION: model_versions does not name a data_version entry; the header field "
            "is still authoritative"
        )
    counts: dict[str, int | float] = {
        "actions": len(plan.actions),
        "assumptions": len(plan.assumptions),
        "total_cost": round(plan.total_cost, 2),
    }
    return ContractValidation(tuple(errors), tuple(warnings), counts)


__all__ = [
    "COST_CATEGORIES",
    "PLAN_SCHEMA_VERSION",
    "PLAN_STATUSES",
    "CostLine",
    "Plan",
    "PlanAction",
    "PlanAssumption",
    "PlanHeader",
    "validate_plan",
]
