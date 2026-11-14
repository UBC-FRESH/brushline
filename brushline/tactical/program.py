"""Multi-year tactical treatment program."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from brushline.model.state import Season, TreatmentMethod
from brushline.model.validation import ContractValidation, check_duplicates

PROGRAM_SCHEMA_VERSION: Literal["brushline.tactical-program.v1"] = "brushline.tactical-program.v1"


class TacticalError(ValueError):
    """Raised when a tactical program is inconsistent."""


class TreatmentUnit(BaseModel):
    """A tactical treatment unit.

    Parameters
    ----------
    unit_id : str
        Unit id.
    span_id : str
        Span id.
    segment_ids : list of str
        Segments.
    area_ha : float
        Area.
    allowed_methods : list of str
        Allowed methods.
    allowed_seasons : list of str
        Allowed seasons.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    unit_id: str = Field(min_length=1)
    span_id: str = Field(min_length=1)
    segment_ids: list[str] = Field(min_length=1)
    area_ha: float = Field(gt=0)
    allowed_methods: list[TreatmentMethod] = Field(default_factory=list)
    allowed_seasons: list[Season] = Field(default_factory=list)


class TacticalAction(BaseModel):
    """One selected tactical action.

    Parameters
    ----------
    action_id : str
        Action id.
    unit_id : str
        Unit id.
    year : int
        Year.
    season : str
        Season.
    method : str
        Method.
    contractor_id : str
        Contractor id.
    cost : float
        Cost.
    capacity_units : float
        Crew/machine units.
    access_window_id : str or None, optional
        Access window reference.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    action_id: str = Field(min_length=1)
    unit_id: str = Field(min_length=1)
    year: int = Field(ge=1900, le=2200)
    season: Season
    method: TreatmentMethod
    contractor_id: str = Field(min_length=1)
    cost: float = Field(ge=0)
    capacity_units: float = Field(gt=0)
    access_window_id: str | None = None


class TacticalConfig(BaseModel):
    """Tactical program settings.

    Parameters
    ----------
    horizon_years : int
        Horizon from 1 to 5.
    start_year : int
        First year.
    budget_by_year : dict of int to float
        Budget by year.
    currency : str
        Currency.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    horizon_years: int = Field(default=5, ge=1, le=5)
    start_year: int = Field(default=2026, ge=1900, le=2200)
    budget_by_year: dict[int, float] = Field(default_factory=dict)
    currency: str = "CAD"

    @model_validator(mode="after")
    def _budget(self) -> TacticalConfig:
        if any(value < 0 for value in self.budget_by_year.values()):
            raise ValueError("budgets must be non-negative")
        return self


class TacticalViolation(BaseModel):
    """One tactical violation.

    Parameters
    ----------
    code : str
        Code.
    message : str
        Explanation.
    action_id : str or None
        Action.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    code: str
    message: str
    action_id: str | None = None


class TacticalProgram(BaseModel):
    """A multi-year tactical program.

    Parameters
    ----------
    schema_version : {"brushline.tactical-program.v1"}
        Schema version.
    program_id : str
        Program id.
    instance_id : str
        Instance id.
    config : TacticalConfig
        Settings.
    units : list of TreatmentUnit
        Units.
    actions : list of TacticalAction
        Selected actions.
    total_cost : float
        Total cost.
    budget_by_year : dict of int to float
        Budget.
    cost_by_year : dict of int to float
        Cost.
    contractor_allocation : dict of str to int
        Action count by contractor.
    feasible : bool
        Constraints satisfied.
    violations : list of TacticalViolation
        Violations.
    created_utc : datetime
        Timezone-aware time.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["brushline.tactical-program.v1"] = PROGRAM_SCHEMA_VERSION
    program_id: str
    instance_id: str
    config: TacticalConfig
    units: list[TreatmentUnit]
    actions: list[TacticalAction]
    total_cost: float = Field(ge=0)
    budget_by_year: dict[int, float]
    cost_by_year: dict[int, float]
    contractor_allocation: dict[str, int]
    feasible: bool
    violations: list[TacticalViolation] = Field(default_factory=list)
    created_utc: datetime


def validate_tactical_inputs(
    units: list[TreatmentUnit], actions: list[TacticalAction]
) -> ContractValidation:
    """Validate unit/action references, methods, seasons, and duplicate ids.

    Parameters
    ----------
    units : list of TreatmentUnit
        Units.
    actions : list of TacticalAction
        Actions.

    Returns
    -------
    ContractValidation
        Errors and counts.
    """
    errors: list[str] = []
    warnings: list[str] = []
    check_duplicates("TACTICAL", "unit", [item.unit_id for item in units], errors)
    check_duplicates("TACTICAL", "action", [item.action_id for item in actions], errors)
    unit_ids = {item.unit_id for item in units}
    for action in actions:
        if action.unit_id not in unit_ids:
            errors.append(f"TACTICAL-UNIT: action {action.action_id} has unknown unit")
    if not actions:
        warnings.append("TACTICAL-EMPTY: no actions are selected")
    return ContractValidation(
        tuple(errors), tuple(warnings), {"units": len(units), "actions": len(actions)}
    )


def build_tactical_program(
    *,
    program_id: str,
    instance_id: str,
    units: list[TreatmentUnit],
    actions: list[TacticalAction],
    config: TacticalConfig | None = None,
    created_utc: datetime | None = None,
) -> TacticalProgram:
    """Validate and assemble a tactical program.

    Parameters
    ----------
    program_id : str
        Program id.
    instance_id : str
        Instance id.
    units : list of TreatmentUnit
        Units.
    actions : list of TacticalAction
        Actions.
    config : TacticalConfig, optional
        Settings.
    created_utc : datetime, optional
        Creation time.

    Returns
    -------
    TacticalProgram
        Program and named violations.
    """
    validation = validate_tactical_inputs(units, actions)
    if not validation.is_valid:
        raise TacticalError("; ".join(validation.errors))
    rules = config or TacticalConfig()
    unit_map = {unit.unit_id: unit for unit in units}
    start, end = rules.start_year, rules.start_year + rules.horizon_years - 1
    violations: list[TacticalViolation] = []
    cost_by_year: dict[int, float] = {}
    allocations: dict[str, int] = {}
    ordered = sorted(actions, key=lambda item: (item.year, item.action_id))
    for action in ordered:
        if action.year < start or action.year > end:
            violations.append(
                TacticalViolation(
                    code="TACTICAL-YEAR",
                    message=f"action {action.action_id} is outside the horizon",
                    action_id=action.action_id,
                )
            )
        unit = unit_map[action.unit_id]
        if unit.allowed_methods and action.method not in unit.allowed_methods:
            violations.append(
                TacticalViolation(
                    code="TACTICAL-METHOD",
                    message=f"action {action.action_id} uses a disallowed method",
                    action_id=action.action_id,
                )
            )
        if unit.allowed_seasons and action.season not in unit.allowed_seasons:
            violations.append(
                TacticalViolation(
                    code="TACTICAL-SEASON",
                    message=f"action {action.action_id} uses a disallowed season",
                    action_id=action.action_id,
                )
            )
        cost_by_year[action.year] = cost_by_year.get(action.year, 0.0) + action.cost
        allocations[action.contractor_id] = allocations.get(action.contractor_id, 0) + 1
    budget = {year: rules.budget_by_year.get(year, 0.0) for year in range(start, end + 1)}
    for year, spent in cost_by_year.items():
        if spent > budget.get(year, 0.0) + 1e-9:
            violations.append(
                TacticalViolation(
                    code="TACTICAL-BUDGET",
                    message=f"cost {spent:.2f} exceeds budget {budget.get(year, 0.0):.2f}",
                )
            )
    total = sum(action.cost for action in ordered)
    return TacticalProgram(
        program_id=program_id,
        instance_id=instance_id,
        config=rules,
        units=units,
        actions=ordered,
        total_cost=total,
        budget_by_year=budget,
        cost_by_year=cost_by_year,
        contractor_allocation=allocations,
        feasible=not violations,
        violations=violations,
        created_utc=created_utc or datetime.now(UTC),
    )


__all__ = [
    "PROGRAM_SCHEMA_VERSION",
    "TacticalAction",
    "TacticalConfig",
    "TacticalError",
    "TacticalProgram",
    "TacticalViolation",
    "TreatmentUnit",
    "build_tactical_program",
    "validate_tactical_inputs",
]
