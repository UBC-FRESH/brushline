"""Optimization formulation: variables, options, constraints, and objectives.

The formulation is the stable boundary between Brushline and Fresh Solutions. A variable index maps
to one segment/period or span/period; an option index maps to no action or one treatment/monitoring
option. The evaluator, operators, archive, and adapter all use these indices.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from brushline.model.archive import Objective
from brushline.model.state import Season, Sensor, TreatmentMethod
from brushline.model.validation import ContractValidation, check_duplicates

FORMULATION_SCHEMA_VERSION: Literal["brushline.optimization-formulation.v1"] = (
    "brushline.optimization-formulation.v1"
)
VARIABLE_KINDS: tuple[str, ...] = ("treatment", "monitoring")
CONSTRAINT_KINDS: tuple[str, ...] = (
    "budget",
    "capacity",
    "access",
    "service",
    "monitoring_budget",
    "spatial",
    "temporal",
)
OBJECTIVE_NAMES: tuple[str, ...] = (
    "present_cost",
    "service_risk",
    "service_attainment",
    "uncertainty",
)
DEFAULT_OBJECTIVES: tuple[Objective, ...] = (
    Objective(name="present_cost", direction="minimize", unit="CAD"),
    Objective(name="service_risk", direction="minimize", unit="index"),
    Objective(name="service_attainment", direction="maximize", unit="fraction"),
    Objective(name="uncertainty", direction="minimize", unit="index"),
)


class FormulationError(ValueError):
    """Raised when a formulation is inconsistent."""


class PeriodSpec(BaseModel):
    """One planning period and its resource limits.

    Parameters
    ----------
    period_id : str
        Stable period id.
    start_year : int
        First year.
    end_year : int
        Last year.
    budget : float
        Treatment budget.
    monitoring_budget : float
        Monitoring budget.
    capacity_by_method : dict of str to float
        Capacity by method, in hectares.
    season : str
        Dominant season.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    period_id: str = Field(min_length=1)
    start_year: int = Field(ge=1900, le=2200)
    end_year: int = Field(ge=1900, le=2200)
    budget: float = Field(ge=0)
    monitoring_budget: float = Field(default=0, ge=0)
    capacity_by_method: dict[str, float] = Field(default_factory=dict)
    season: Season = "any"

    @model_validator(mode="after")
    def _period_order(self) -> PeriodSpec:
        if self.end_year < self.start_year:
            raise ValueError("period end_year must not precede start_year")
        if any(capacity < 0 for capacity in self.capacity_by_method.values()):
            raise ValueError("capacity must be non-negative")
        return self


class SegmentSpec(BaseModel):
    """One optimization segment.

    Parameters
    ----------
    segment_id : str
        Segment id.
    corridor_id : str
        Corridor id.
    length_m : float
        Segment length.
    treatment_unit_id : str
        Treatment unit.
    service_standard_id : str
        Service standard.
    max_height_m : float
        Service maximum height.
    min_clearance_m : float
        Service minimum clearance.
    allowed_methods : list of str
        Allowed treatment methods. Empty means all.
    inaccessible_period_ids : list of str, optional
        Periods with no access.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    segment_id: str = Field(min_length=1)
    corridor_id: str = Field(min_length=1)
    length_m: float = Field(gt=0)
    treatment_unit_id: str = Field(min_length=1)
    service_standard_id: str = Field(min_length=1)
    max_height_m: float = Field(gt=0)
    min_clearance_m: float = Field(ge=0)
    allowed_methods: list[TreatmentMethod] = Field(default_factory=list)
    inaccessible_period_ids: list[str] = Field(default_factory=list)


class SpanSpec(BaseModel):
    """One monitoring span.

    Parameters
    ----------
    span_id : str
        Span id.
    corridor_id : str
        Corridor id.
    segment_ids : list of str
        Segments in the span.
    monitoring_allowed : bool
        Whether monitoring is allowed.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    span_id: str = Field(min_length=1)
    corridor_id: str = Field(min_length=1)
    segment_ids: list[str] = Field(min_length=1)
    monitoring_allowed: bool = True


class TreatmentOption(BaseModel):
    """One selectable treatment option.

    Parameters
    ----------
    option_id : str
        Stable option id.
    method : str
        Treatment method.
    intensity : float
        Intensity from 0 to 1.
    season : str
        Season.
    cost_per_ha : float
        Variable cost.
    fixed_cost : float
        Fixed cost.
    label : str
        Human label.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    option_id: str = Field(min_length=1)
    method: TreatmentMethod
    intensity: float = Field(ge=0, le=1)
    season: Season
    cost_per_ha: float = Field(ge=0)
    fixed_cost: float = Field(default=0, ge=0)
    label: str = ""


class MonitoringOption(BaseModel):
    """One selectable monitoring option.

    Parameters
    ----------
    option_id : str
        Stable option id.
    sensor : str
        Sensor.
    sampling_intensity : float
        Sampling intensity from 0 to 1.
    cost_per_span : float
        Cost per span.
    label : str
        Human label.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    option_id: str = Field(min_length=1)
    sensor: Sensor
    sampling_intensity: float = Field(ge=0, le=1)
    cost_per_span: float = Field(ge=0)
    label: str = ""


class Variable(BaseModel):
    """One stable decision variable.

    Parameters
    ----------
    index : int
        Stable variable index.
    kind : str
        ``treatment`` or ``monitoring``.
    target_id : str
        Segment or span id.
    period_id : str
        Period id.
    option_ids : list of str
        Option ids with ``none`` first.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    index: int = Field(ge=0)
    kind: str
    target_id: str = Field(min_length=1)
    period_id: str = Field(min_length=1)
    option_ids: list[str] = Field(min_length=1)

    @model_validator(mode="after")
    def _none_first(self) -> Variable:
        if self.option_ids[0] != "none":
            raise ValueError("the first option must be 'none'")
        if len(set(self.option_ids)) != len(self.option_ids):
            raise ValueError("option ids must be unique")
        return self


class ConstraintSpec(BaseModel):
    """One hard or soft constraint.

    Parameters
    ----------
    constraint_id : str
        Stable id.
    kind : str
        Constraint kind.
    scope : str
        ``global``, ``period``, ``segment``, or ``span``.
    target_id : str
        Target id.
    period_id : str or None
        Period id, when relevant.
    value : float
        Limit or target value.
    unit : str
        Unit.
    hard : bool
        Whether violation is infeasible.
    description : str
        Human description.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    constraint_id: str = Field(min_length=1)
    kind: str
    scope: str
    target_id: str = Field(min_length=1)
    period_id: str | None = None
    value: float = Field(ge=0)
    unit: str = Field(min_length=1)
    hard: bool = True
    description: str = ""


class Formulation(BaseModel):
    """The complete optimization formulation.

    Parameters
    ----------
    schema_version : {"brushline.optimization-formulation.v1"}
        Schema version.
    formulation_id : str
        Formulation id.
    currency : str
        Currency.
    periods : list of PeriodSpec
        Planning periods.
    segments : list of SegmentSpec
        Segments.
    spans : list of SpanSpec
        Monitoring spans.
    treatment_options : list of TreatmentOption
        Treatment options.
    monitoring_options : list of MonitoringOption
        Monitoring options.
    variables : list of Variable
        Stable variables.
    constraints : list of ConstraintSpec
        Constraints.
    objectives : list of Objective
        Objective vector.
    created_utc : datetime
        Creation time.
    """

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["brushline.optimization-formulation.v1"] = FORMULATION_SCHEMA_VERSION
    formulation_id: str = Field(min_length=1)
    currency: str = Field(min_length=1)
    periods: list[PeriodSpec] = Field(min_length=1)
    segments: list[SegmentSpec] = Field(min_length=1)
    spans: list[SpanSpec] = Field(default_factory=list)
    treatment_options: list[TreatmentOption] = Field(default_factory=list)
    monitoring_options: list[MonitoringOption] = Field(default_factory=list)
    variables: list[Variable] = Field(min_length=1)
    constraints: list[ConstraintSpec] = Field(default_factory=list)
    objectives: list[Objective] = Field(min_length=1)
    created_utc: datetime

    @property
    def variable_count(self) -> int:
        """Return the variable count.

        Returns
        -------
        int
            Number of decision variables.
        """
        return len(self.variables)

    def option_count(self, variable_index: int) -> int:
        """Return the option count for one variable.

        Parameters
        ----------
        variable_index : int
            Variable index.

        Returns
        -------
        int
            Number of options.
        """
        return len(self.variables[variable_index].option_ids)

    def option_at(self, variable_index: int, option_index: int) -> str:
        """Return the option id at an index.

        Parameters
        ----------
        variable_index : int
            Variable index.
        option_index : int
            Option index.

        Returns
        -------
        str
            Option id.
        """
        return self.variables[variable_index].option_ids[option_index]

    def initial_assignment(self) -> dict[int, int]:
        """Return the no-action assignment.

        Returns
        -------
        dict of int to int
            All variables at option 0.
        """
        return {variable.index: 0 for variable in self.variables}


def build_formulation(
    *,
    formulation_id: str,
    periods: list[PeriodSpec],
    segments: list[SegmentSpec],
    spans: list[SpanSpec],
    treatment_options: list[TreatmentOption],
    monitoring_options: list[MonitoringOption],
    currency: str = "CAD",
    created_utc: datetime | None = None,
) -> Formulation:
    """Build a stable formulation with variables and constraints.

    Parameters
    ----------
    formulation_id : str
        Formulation id.
    periods : list of PeriodSpec
        Periods.
    segments : list of SegmentSpec
        Segments.
    spans : list of SpanSpec
        Spans.
    treatment_options : list of TreatmentOption
        Treatment options.
    monitoring_options : list of MonitoringOption
        Monitoring options.
    currency : str, optional
        Currency. Defaults to ``CAD``.
    created_utc : datetime, optional
        Creation time.

    Returns
    -------
    Formulation
        Stable variables, constraints, and objectives.

    Raises
    ------
    FormulationError
        When the generated formulation is invalid.
    """
    variables: list[Variable] = []
    index = 0
    treatment_by_method = {option.method: option for option in treatment_options}
    for segment in segments:
        for period in periods:
            allowed = [
                option
                for option in treatment_options
                if (not segment.allowed_methods or option.method in segment.allowed_methods)
            ]
            variables.append(
                Variable(
                    index=index,
                    kind="treatment",
                    target_id=segment.segment_id,
                    period_id=period.period_id,
                    option_ids=["none", *[option.option_id for option in allowed]],
                )
            )
            index += 1
    for span in spans:
        for period in periods:
            allowed_monitoring = monitoring_options if span.monitoring_allowed else []
            variables.append(
                Variable(
                    index=index,
                    kind="monitoring",
                    target_id=span.span_id,
                    period_id=period.period_id,
                    option_ids=["none", *[option.option_id for option in allowed_monitoring]],
                )
            )
            index += 1
    constraints: list[ConstraintSpec] = []
    for period in periods:
        constraints.append(
            ConstraintSpec(
                constraint_id=f"budget:{period.period_id}",
                kind="budget",
                scope="period",
                target_id=period.period_id,
                period_id=period.period_id,
                value=period.budget,
                unit=currency,
                description="Treatment budget for the period.",
            )
        )
        constraints.append(
            ConstraintSpec(
                constraint_id=f"monitoring-budget:{period.period_id}",
                kind="monitoring_budget",
                scope="period",
                target_id=period.period_id,
                period_id=period.period_id,
                value=period.monitoring_budget,
                unit=currency,
                description="Monitoring budget for the period.",
            )
        )
        for method in treatment_by_method:
            capacity = period.capacity_by_method.get(method, 0.0)
            constraints.append(
                ConstraintSpec(
                    constraint_id=f"capacity:{period.period_id}:{method}",
                    kind="capacity",
                    scope="period",
                    target_id=method,
                    period_id=period.period_id,
                    value=capacity,
                    unit="ha",
                    description=f"Capacity for {method} in the period.",
                )
            )
    for segment in segments:
        for period_id in segment.inaccessible_period_ids:
            constraints.append(
                ConstraintSpec(
                    constraint_id=f"access:{segment.segment_id}:{period_id}",
                    kind="access",
                    scope="segment",
                    target_id=segment.segment_id,
                    period_id=period_id,
                    value=0.0,
                    unit="boolean",
                    description="Segment has no access in the period.",
                )
            )
        constraints.append(
            ConstraintSpec(
                constraint_id=f"service:{segment.segment_id}",
                kind="service",
                scope="segment",
                target_id=segment.segment_id,
                value=segment.max_height_m,
                unit="m",
                description="Service maximum height.",
            )
        )
    formulation = Formulation(
        formulation_id=formulation_id,
        currency=currency,
        periods=periods,
        segments=segments,
        spans=spans,
        treatment_options=treatment_options,
        monitoring_options=monitoring_options,
        variables=variables,
        constraints=constraints,
        objectives=list(DEFAULT_OBJECTIVES),
        created_utc=created_utc or datetime.now(UTC),
    )
    validation = validate_formulation(formulation)
    if not validation.is_valid:
        raise FormulationError("; ".join(validation.errors))
    return formulation


def validate_formulation(formulation: Formulation) -> ContractValidation:
    """Validate variable indices, references, options, constraints, and objectives.

    Parameters
    ----------
    formulation : Formulation
        Formulation to validate.

    Returns
    -------
    ContractValidation
        Errors, warnings, and counts.
    """
    errors: list[str] = []
    warnings: list[str] = []
    check_duplicates(
        "FORMULATION",
        "period",
        [period.period_id for period in formulation.periods],
        errors,
    )
    check_duplicates(
        "FORMULATION",
        "segment",
        [segment.segment_id for segment in formulation.segments],
        errors,
    )
    check_duplicates(
        "FORMULATION",
        "span",
        [span.span_id for span in formulation.spans],
        errors,
    )
    check_duplicates(
        "FORMULATION",
        "treatment option",
        [option.option_id for option in formulation.treatment_options],
        errors,
    )
    check_duplicates(
        "FORMULATION",
        "monitoring option",
        [option.option_id for option in formulation.monitoring_options],
        errors,
    )
    check_duplicates(
        "FORMULATION",
        "variable",
        [str(variable.index) for variable in formulation.variables],
        errors,
    )
    check_duplicates(
        "FORMULATION",
        "constraint",
        [constraint.constraint_id for constraint in formulation.constraints],
        errors,
    )
    check_duplicates(
        "FORMULATION",
        "objective",
        [objective.name for objective in formulation.objectives],
        errors,
    )
    if formulation.created_utc.tzinfo is None:
        errors.append("FORMULATION-TIME: created_utc is not timezone-aware")
    if [variable.index for variable in formulation.variables] != list(
        range(len(formulation.variables))
    ):
        errors.append("FORMULATION-INDEX: variable indices must be consecutive from zero")
    if {objective.name for objective in formulation.objectives} != set(OBJECTIVE_NAMES):
        errors.append("FORMULATION-OBJECTIVE: the four core objectives are required")
    period_ids = {period.period_id for period in formulation.periods}
    segment_ids = {segment.segment_id for segment in formulation.segments}
    span_ids = {span.span_id for span in formulation.spans}
    treatment_ids = {option.option_id for option in formulation.treatment_options}
    monitoring_ids = {option.option_id for option in formulation.monitoring_options}
    for variable in formulation.variables:
        if variable.kind not in VARIABLE_KINDS:
            errors.append(f"FORMULATION-KIND: variable {variable.index} has unknown kind")
        if variable.period_id not in period_ids:
            errors.append(f"FORMULATION-REF: variable {variable.index} has unknown period")
        if variable.kind == "treatment" and variable.target_id not in segment_ids:
            errors.append(f"FORMULATION-REF: variable {variable.index} has unknown segment")
        if variable.kind == "monitoring" and variable.target_id not in span_ids:
            errors.append(f"FORMULATION-REF: variable {variable.index} has unknown span")
        allowed = treatment_ids if variable.kind == "treatment" else monitoring_ids
        for option_id in variable.option_ids[1:]:
            if option_id not in allowed:
                errors.append(
                    f"FORMULATION-OPTION: variable {variable.index} has unknown "
                    f"option {option_id!r}"
                )
    for constraint in formulation.constraints:
        if constraint.kind not in CONSTRAINT_KINDS:
            errors.append(f"FORMULATION-CONSTRAINT: unknown kind {constraint.kind!r}")
        if constraint.period_id is not None and constraint.period_id not in period_ids:
            errors.append(f"FORMULATION-CONSTRAINT: {constraint.constraint_id} has unknown period")
        if (
            constraint.kind == "access"
            and constraint.scope == "segment"
            and constraint.target_id not in segment_ids
        ):
            errors.append(f"FORMULATION-CONSTRAINT: {constraint.constraint_id} has unknown segment")
    for option in treatment_ids:
        if (
            not any(option in variable.option_ids for variable in formulation.variables)
            and formulation.treatment_options
        ):
            warnings.append(f"FORMULATION-OPTION: treatment option {option} is unused")
    if not formulation.treatment_options:
        warnings.append("FORMULATION-EMPTY: no treatment options")
    if not formulation.monitoring_options:
        warnings.append("FORMULATION-EMPTY: no monitoring options")
    counts: dict[str, int | float] = {
        "periods": len(formulation.periods),
        "segments": len(formulation.segments),
        "spans": len(formulation.spans),
        "variables": len(formulation.variables),
        "constraints": len(formulation.constraints),
        "objectives": len(formulation.objectives),
    }
    return ContractValidation(tuple(errors), tuple(warnings), counts)


__all__ = [
    "CONSTRAINT_KINDS",
    "DEFAULT_OBJECTIVES",
    "FORMULATION_SCHEMA_VERSION",
    "OBJECTIVE_NAMES",
    "VARIABLE_KINDS",
    "ConstraintSpec",
    "Formulation",
    "FormulationError",
    "MonitoringOption",
    "PeriodSpec",
    "SegmentSpec",
    "SpanSpec",
    "TreatmentOption",
    "Variable",
    "build_formulation",
    "validate_formulation",
]
