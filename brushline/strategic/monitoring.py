"""Strategic monitoring policy with an approximate value of information.

Monitoring is selected per span from explicit frequency, route, sensor, sampling-intensity,
cost, and uncertainty/risk-reduction options. The value-of-information proxy is declared, not a
structural sensor simulation.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from brushline.model.state import Sensor
from brushline.model.validation import ContractValidation, check_duplicates

MONITORING_SCHEMA_VERSION: Literal["brushline.strategic-monitoring.v1"] = (
    "brushline.strategic-monitoring.v1"
)


class MonitoringError(ValueError):
    """Raised when monitoring inputs are inconsistent."""


class MonitoringSpan(BaseModel):
    """One monitoring span.

    Parameters
    ----------
    span_id : str
        Span id.
    segment_ids : list of str
        Segments in the span.
    baseline_uncertainty : float
        Current uncertainty from 0 to 1.
    service_risk : float
        Current service risk from 0 to 1.
    route_m : float
        Route length in metres.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    span_id: str = Field(min_length=1)
    segment_ids: list[str] = Field(min_length=1)
    baseline_uncertainty: float = Field(ge=0, le=1)
    service_risk: float = Field(ge=0, le=1)
    route_m: float = Field(gt=0)


class MonitoringOption(BaseModel):
    """One monitoring option for one span.

    Parameters
    ----------
    option_id : str
        Option id.
    span_id : str
        Span id.
    sensor : str
        Sensor.
    route : str
        Route pattern or label.
    interval_years : int
        Nominal monitoring interval.
    sampling_intensity : float
        Sampling intensity from 0 to 1.
    cost_per_event : float
        Cost per monitoring event.
    uncertainty_reduction : float
        Relative uncertainty reduction from 0 to 1.
    risk_reduction : float
        Relative service-risk reduction from 0 to 1.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    option_id: str = Field(min_length=1)
    span_id: str = Field(min_length=1)
    sensor: Sensor
    route: str = Field(min_length=1)
    interval_years: int = Field(ge=1, le=30)
    sampling_intensity: float = Field(ge=0, le=1)
    cost_per_event: float = Field(ge=0)
    uncertainty_reduction: float = Field(ge=0, le=1)
    risk_reduction: float = Field(ge=0, le=1)


class MonitoringConfig(BaseModel):
    """Monitoring policy settings.

    Parameters
    ----------
    horizon_years : int
        Policy horizon.
    start_year : int
        First year.
    budget : float
        Total monitoring budget.
    value_per_unit : float
        Value per unit of uncertainty/risk reduction.
    cost_weight : float
        Cost penalty in the value proxy.
    min_net_value : float
        Minimum net value for a selection.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    horizon_years: int = Field(default=10, ge=1, le=50)
    start_year: int = Field(default=2026, ge=1900, le=2200)
    budget: float = Field(default=0, ge=0)
    value_per_unit: float = Field(default=1000.0, ge=0)
    cost_weight: float = Field(default=1.0, ge=0)
    min_net_value: float = Field(default=0.0, ge=0)


class MonitoringDecision(BaseModel):
    """One selected monitoring policy.

    Parameters
    ----------
    span_id : str
        Span id.
    option_id : str
        Option id.
    sensor : str
        Sensor.
    route : str
        Route.
    interval_years : int
        Interval.
    sampling_intensity : float
        Sampling intensity.
    start_year : int
        First year.
    end_year : int
        Last year.
    event_years : list of int
        Scheduled event years.
    total_cost : float
        Total cost.
    value_of_information : float
        Gross value proxy.
    net_value : float
        Gross value minus cost penalty.
    expected_uncertainty_reduction : float
        Absolute reduction.
    expected_risk_reduction : float
        Absolute reduction.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    span_id: str
    option_id: str
    sensor: str
    route: str
    interval_years: int = Field(ge=1)
    sampling_intensity: float = Field(ge=0, le=1)
    start_year: int
    end_year: int
    event_years: list[int] = Field(min_length=1)
    total_cost: float = Field(ge=0)
    value_of_information: float
    net_value: float
    expected_uncertainty_reduction: float = Field(ge=0, le=1)
    expected_risk_reduction: float = Field(ge=0, le=1)


class MonitoringViolation(BaseModel):
    """One named monitoring violation.

    Parameters
    ----------
    code : str
        Code.
    message : str
        Explanation.
    span_id : str or None
        Span.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    code: str
    message: str
    span_id: str | None = None


class MonitoringPolicy(BaseModel):
    """A strategic monitoring policy.

    Parameters
    ----------
    schema_version : {"brushline.strategic-monitoring.v1"}
        Schema version.
    policy_id : str
        Policy id.
    instance_id : str
        Instance id.
    config : MonitoringConfig
        Settings.
    decisions : list of MonitoringDecision
        Selected monitoring decisions.
    total_cost : float
        Total cost.
    budget : float
        Budget.
    expected_uncertainty_reduction : float
        Aggregate reduction.
    expected_risk_reduction : float
        Aggregate reduction.
    total_net_value : float
        Sum of net values.
    feasible : bool
        Constraints satisfied.
    violations : list of MonitoringViolation
        Violations.
    caveats : list of str
        Approximation caveats.
    created_utc : datetime
        Timezone-aware time.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["brushline.strategic-monitoring.v1"] = MONITORING_SCHEMA_VERSION
    policy_id: str
    instance_id: str
    config: MonitoringConfig
    decisions: list[MonitoringDecision]
    total_cost: float = Field(ge=0)
    budget: float = Field(ge=0)
    expected_uncertainty_reduction: float = Field(ge=0, le=1)
    expected_risk_reduction: float = Field(ge=0, le=1)
    total_net_value: float
    feasible: bool
    violations: list[MonitoringViolation] = Field(default_factory=list)
    caveats: list[str] = Field(default_factory=list)
    created_utc: datetime

    @model_validator(mode="after")
    def _time(self) -> MonitoringPolicy:
        if self.created_utc.tzinfo is None:
            raise ValueError("created_utc must be timezone-aware")
        return self


def validate_monitoring_inputs(
    spans: list[MonitoringSpan], options: list[MonitoringOption]
) -> ContractValidation:
    """Validate span and option references and duplicate ids.

    Parameters
    ----------
    spans : list of MonitoringSpan
        Spans.
    options : list of MonitoringOption
        Options.

    Returns
    -------
    ContractValidation
        Errors and counts.
    """
    errors: list[str] = []
    warnings: list[str] = []
    check_duplicates("MONITORING", "span", [item.span_id for item in spans], errors)
    check_duplicates("MONITORING", "option", [item.option_id for item in options], errors)
    span_ids = {item.span_id for item in spans}
    for option in options:
        if option.span_id not in span_ids:
            errors.append(f"MONITORING-SPAN: option {option.option_id} has unknown span")
    if not options:
        warnings.append("MONITORING-EMPTY: no monitoring options")
    return ContractValidation(
        tuple(errors), tuple(warnings), {"spans": len(spans), "options": len(options)}
    )


def build_monitoring_policy(
    *,
    policy_id: str,
    instance_id: str,
    spans: list[MonitoringSpan],
    options: list[MonitoringOption],
    config: MonitoringConfig | None = None,
    created_utc: datetime | None = None,
) -> MonitoringPolicy:
    """Select monitoring by net value of information under a total budget.

    Parameters
    ----------
    policy_id : str
        Policy id.
    instance_id : str
        Instance id.
    spans : list of MonitoringSpan
        Spans.
    options : list of MonitoringOption
        Options.
    config : MonitoringConfig, optional
        Settings.
    created_utc : datetime, optional
        Creation time.

    Returns
    -------
    MonitoringPolicy
        Policy and value-of-information evidence.
    """
    validation = validate_monitoring_inputs(spans, options)
    if not validation.is_valid:
        raise MonitoringError("; ".join(validation.errors))
    rules = config or MonitoringConfig()
    span_map = {span.span_id: span for span in spans}
    candidates: list[tuple[float, MonitoringDecision]] = []
    for option in options:
        span = span_map[option.span_id]
        events = _event_years(rules.start_year, rules.horizon_years, option.interval_years)
        total_cost = option.cost_per_event * len(events)
        gross = rules.value_per_unit * (
            span.baseline_uncertainty * option.uncertainty_reduction
            + span.service_risk * option.risk_reduction
        )
        net = gross - rules.cost_weight * total_cost
        if net <= rules.min_net_value:
            continue
        candidates.append(
            (
                net,
                MonitoringDecision(
                    span_id=option.span_id,
                    option_id=option.option_id,
                    sensor=option.sensor,
                    route=option.route,
                    interval_years=option.interval_years,
                    sampling_intensity=option.sampling_intensity,
                    start_year=rules.start_year,
                    end_year=rules.start_year + rules.horizon_years - 1,
                    event_years=events,
                    total_cost=total_cost,
                    value_of_information=gross,
                    net_value=net,
                    expected_uncertainty_reduction=(
                        span.baseline_uncertainty * option.uncertainty_reduction
                    ),
                    expected_risk_reduction=(span.service_risk * option.risk_reduction),
                ),
            )
        )
    candidates.sort(key=lambda item: (-item[0], item[1].option_id))
    selected: list[MonitoringDecision] = []
    selected_spans: set[str] = set()
    total = 0.0
    violations: list[MonitoringViolation] = []
    for _, decision in candidates:
        if decision.span_id in selected_spans:
            continue
        if total + decision.total_cost <= rules.budget + 1e-9:
            selected.append(decision)
            selected_spans.add(decision.span_id)
            total += decision.total_cost
    if total > rules.budget + 1e-9:
        violations.append(
            MonitoringViolation(
                code="MONITORING-BUDGET",
                message=f"cost {total:.2f} exceeds budget {rules.budget:.2f}",
            )
        )
    selected.sort(key=lambda item: item.span_id)
    return MonitoringPolicy(
        policy_id=policy_id,
        instance_id=instance_id,
        config=rules,
        decisions=selected,
        total_cost=total,
        budget=rules.budget,
        expected_uncertainty_reduction=sum(item.expected_uncertainty_reduction for item in selected)
        / max(len(spans), 1),
        expected_risk_reduction=sum(item.expected_risk_reduction for item in selected)
        / max(len(spans), 1),
        total_net_value=sum(item.net_value for item in selected),
        feasible=not violations,
        violations=violations,
        caveats=[
            "Value of information is a declared proxy, not a structural sensor simulation.",
            "Uncertainty and risk reductions are option-level assumptions.",
            "The monitoring interval is a policy choice; event dates remain subject to "
            "route and weather feasibility.",
        ],
        created_utc=created_utc or datetime.now(UTC),
    )


def _event_years(start_year: int, horizon: int, interval: int) -> list[int]:
    years: list[int] = []
    for offset in range(0, horizon, interval):
        years.append(start_year + offset)
    return years or [start_year]


__all__ = [
    "MONITORING_SCHEMA_VERSION",
    "MonitoringConfig",
    "MonitoringDecision",
    "MonitoringError",
    "MonitoringOption",
    "MonitoringPolicy",
    "MonitoringSpan",
    "MonitoringViolation",
    "build_monitoring_policy",
    "validate_monitoring_inputs",
]
