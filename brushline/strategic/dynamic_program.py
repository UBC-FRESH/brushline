"""Single-segment finite-horizon dynamic program for strategic policy.

The dynamic program works on discrete P4 state classes. A state/action transition row carries a
one-period probability, service attainment, risk, and uncertainty. The scalar reward is explicit:
service and cost weights are declared, and the policy value is the discounted expected reward. The
result also keeps the separate expected cost, service, risk, and uncertainty so a report never
hides the vector behind the scalar.
"""

from __future__ import annotations

import math
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from brushline.model.state import Season, StateClass, TreatmentMethod
from brushline.model.validation import ContractValidation, check_duplicates

DP_SCHEMA_VERSION: Literal["brushline.strategic-dp.v1"] = "brushline.strategic-dp.v1"


class DynamicProgramError(ValueError):
    """Raised when a dynamic program is inconsistent."""


class DPState(BaseModel):
    """One strategic state.

    Parameters
    ----------
    state_id : str
        Stable state id.
    state_class : str
        P4 state class.
    age_years : int or None, optional
        Age in years.
    label : str, optional
        Human label.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    state_id: str = Field(min_length=1)
    state_class: StateClass
    age_years: int | None = Field(default=None, ge=0)
    label: str = ""


class StrategicAction(BaseModel):
    """One strategic action.

    Parameters
    ----------
    action_id : str
        Stable action id.
    label : str
        Human label.
    method : str or None
        Treatment method; None means no treatment.
    intensity : float
        Treatment intensity from 0 to 1.
    season : str
        Season.
    cost : float
        Cost per application.
    currency : str
        Currency.
    available_states : list of str
        States where the action is available. Empty means all states.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    action_id: str = Field(min_length=1)
    label: str = ""
    method: TreatmentMethod | None = None
    intensity: float = Field(default=0.0, ge=0, le=1)
    season: Season = "any"
    cost: float = Field(default=0.0, ge=0)
    currency: str = "CAD"
    available_states: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _action(self) -> StrategicAction:
        if self.method is None and self.cost != 0:
            raise ValueError("a no-treatment action must have zero cost")
        return self


class Transition(BaseModel):
    """One state/action/outcome transition.

    Parameters
    ----------
    from_state : str
        Source state id.
    action_id : str
        Action id.
    to_state : str
        Destination state id.
    probability : float
        Probability from 0 to 1.
    service_attainment : float
        Service attainment from 0 to 1.
    risk : float
        Risk index from 0 to 1.
    uncertainty : float
        Uncertainty index from 0 to 1.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    from_state: str = Field(min_length=1)
    action_id: str = Field(min_length=1)
    to_state: str = Field(min_length=1)
    probability: float = Field(gt=0, le=1)
    service_attainment: float = Field(ge=0, le=1)
    risk: float = Field(ge=0, le=1)
    uncertainty: float = Field(ge=0, le=1)


class DynamicProgram(BaseModel):
    """A single-segment finite-horizon dynamic program.

    Parameters
    ----------
    schema_version : {"brushline.strategic-dp.v1"}
        Schema version.
    program_id : str
        Program id.
    segment_id : str
        Segment id.
    states : list of DPState
        States.
    actions : list of StrategicAction
        Actions.
    transitions : list of Transition
        Transition rows.
    horizon : int
        Number of periods.
    discount_rate : float
        Annual discount rate from 0 to 1.
    initial_state : str
        Initial state id.
    terminal_values : dict of str to float
        Terminal value by state.
    service_weight : float
        Reward weight for service attainment.
    risk_weight : float
        Reward penalty for risk.
    uncertainty_weight : float
        Reward penalty for uncertainty.
    cost_weight : float
        Reward penalty per cost unit.
    created_utc : datetime
        Timezone-aware creation time.
    """

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["brushline.strategic-dp.v1"] = DP_SCHEMA_VERSION
    program_id: str = Field(min_length=1)
    segment_id: str = Field(min_length=1)
    states: list[DPState] = Field(min_length=1)
    actions: list[StrategicAction] = Field(min_length=1)
    transitions: list[Transition] = Field(min_length=1)
    horizon: int = Field(ge=1, le=100)
    discount_rate: float = Field(default=0.0, ge=0, le=1)
    initial_state: str = Field(min_length=1)
    terminal_values: dict[str, float] = Field(default_factory=dict)
    service_weight: float = Field(default=1.0, ge=0)
    risk_weight: float = Field(default=1.0, ge=0)
    uncertainty_weight: float = Field(default=1.0, ge=0)
    cost_weight: float = Field(default=0.001, ge=0)
    created_utc: datetime

    @model_validator(mode="after")
    def _timezone(self) -> DynamicProgram:
        if self.created_utc.tzinfo is None:
            raise ValueError("created_utc must be timezone-aware")
        if any(not math.isfinite(value) for value in self.terminal_values.values()):
            raise ValueError("terminal values must be finite")
        return self


class PolicyDecision(BaseModel):
    """One action in the optimal policy.

    Parameters
    ----------
    period : int
        Period from zero.
    state_id : str
        State id.
    action_id : str
        Action id.
    value : float
        State value under the policy.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    period: int = Field(ge=0)
    state_id: str
    action_id: str
    value: float


class DynamicProgramResult(BaseModel):
    """The solved policy and its expected outcomes.

    Parameters
    ----------
    schema_version : {"brushline.strategic-dp-result.v1"}
        Schema version.
    program_id : str
        Program id.
    segment_id : str
        Segment id.
    policy : list of PolicyDecision
        One decision per state and period.
    values : list of dict of str to float
        State value by period, including the terminal period.
    initial_state : str
        Initial state.
    policy_value : float
        Value at the initial state and period zero.
    expected_cost : float
        Discounted expected cost.
    expected_service_attainment : float
        Discounted average service attainment.
    expected_risk : float
        Discounted average risk.
    expected_uncertainty : float
        Discounted average uncertainty.
    discount_rate : float
        Discount rate.
    horizon : int
        Horizon.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = "brushline.strategic-dp-result.v1"
    program_id: str
    segment_id: str
    policy: list[PolicyDecision]
    values: list[dict[str, float]]
    initial_state: str
    policy_value: float
    expected_cost: float = Field(ge=0)
    expected_service_attainment: float = Field(ge=0, le=1)
    expected_risk: float = Field(ge=0, le=1)
    expected_uncertainty: float = Field(ge=0, le=1)
    discount_rate: float
    horizon: int

    def action_for(self, period: int, state_id: str) -> str:
        """Return the policy action for a period and state.

        Parameters
        ----------
        period : int
            Period.
        state_id : str
            State id.

        Returns
        -------
        str
            Action id.

        Raises
        ------
        KeyError
            When the period/state is not in the policy.
        """
        for decision in self.policy:
            if decision.period == period and decision.state_id == state_id:
                return decision.action_id
        raise KeyError(f"no policy decision for period {period}, state {state_id!r}")


def validate_dynamic_program(program: DynamicProgram) -> ContractValidation:
    """Validate references, availability, and transition probabilities.

    Parameters
    ----------
    program : DynamicProgram
        Program.

    Returns
    -------
    ContractValidation
        Errors and counts.
    """
    errors: list[str] = []
    warnings: list[str] = []
    state_ids = [state.state_id for state in program.states]
    action_ids = [action.action_id for action in program.actions]
    check_duplicates("DP", "state", state_ids, errors)
    check_duplicates("DP", "action", action_ids, errors)
    check_duplicates(
        "DP",
        "transition",
        [f"{row.from_state}:{row.action_id}:{row.to_state}" for row in program.transitions],
        errors,
    )
    known_states = set(state_ids)
    known_actions = {action.action_id: action for action in program.actions}
    if program.initial_state not in known_states:
        errors.append("DP-STATE: initial_state is unknown")
    for state in program.terminal_values:
        if state not in known_states:
            errors.append(f"DP-TERMINAL: unknown state {state}")
    for action in program.actions:
        for state in action.available_states:
            if state not in known_states:
                errors.append(f"DP-AVAILABILITY: {action.action_id} names unknown state {state}")
    rows: dict[tuple[str, str], list[Transition]] = {}
    for transition in program.transitions:
        if transition.from_state not in known_states:
            errors.append(f"DP-STATE: transition from unknown state {transition.from_state}")
        if transition.to_state not in known_states:
            errors.append(f"DP-STATE: transition to unknown state {transition.to_state}")
        if transition.action_id not in known_actions:
            errors.append(f"DP-ACTION: transition names unknown action {transition.action_id}")
        rows.setdefault((transition.from_state, transition.action_id), []).append(transition)
    for dp_state in program.states:
        for action in program.actions:
            available = not action.available_states or dp_state.state_id in action.available_states
            if not available:
                continue
            key = (dp_state.state_id, action.action_id)
            outcomes = rows.get(key, [])
            if not outcomes:
                errors.append(
                    f"DP-TRANSITION: {dp_state.state_id}/{action.action_id} has no outcomes"
                )
                continue
            total = sum(item.probability for item in outcomes)
            if abs(total - 1.0) > 1e-6:
                errors.append(
                    f"DP-PROBABILITY: {dp_state.state_id}/{action.action_id} sums to {total}"
                )
    if not any(action.available_states for action in program.actions):
        warnings.append("DP-AVAILABILITY: every action is available in every state")
    counts: dict[str, int | float] = {
        "states": len(program.states),
        "actions": len(program.actions),
        "transitions": len(program.transitions),
        "horizon": program.horizon,
    }
    return ContractValidation(tuple(errors), tuple(warnings), counts)


def solve_dynamic_program(program: DynamicProgram) -> DynamicProgramResult:
    """Solve the dynamic program by backward induction and replay its policy.

    Parameters
    ----------
    program : DynamicProgram
        Program.

    Returns
    -------
    DynamicProgramResult
        Policy, values, and expected outcomes.

    Raises
    ------
    DynamicProgramError
        When the program is invalid.
    """
    validation = validate_dynamic_program(program)
    if not validation.is_valid:
        raise DynamicProgramError("; ".join(validation.errors))
    states = [state.state_id for state in program.states]
    rows: dict[tuple[str, str], list[Transition]] = {}
    for row in program.transitions:
        rows.setdefault((row.from_state, row.action_id), []).append(row)
    discount = 1.0 / (1.0 + program.discount_rate)
    values: list[dict[str, float]] = [
        {state: program.terminal_values.get(state, 0.0) for state in states}
        for _ in range(program.horizon + 1)
    ]
    policy: list[PolicyDecision] = []
    for period in range(program.horizon - 1, -1, -1):
        for state in states:
            best_action: str | None = None
            best_value = -math.inf
            for action in program.actions:
                if action.available_states and state not in action.available_states:
                    continue
                q = 0.0
                for outcome in rows[(state, action.action_id)]:
                    reward = _reward(program, action, outcome)
                    q += outcome.probability * (
                        reward + discount * values[period + 1][outcome.to_state]
                    )
                if q > best_value + 1e-12 or (
                    abs(q - best_value) <= 1e-12
                    and (best_action is None or action.action_id < best_action)
                ):
                    best_value = q
                    best_action = action.action_id
            if best_action is None:
                raise DynamicProgramError(f"no available action for state {state}")
            values[period][state] = best_value
            policy.append(
                PolicyDecision(
                    period=period,
                    state_id=state,
                    action_id=best_action,
                    value=best_value,
                )
            )
    policy.sort(key=lambda item: (item.period, item.state_id))
    expected_cost, service, risk, uncertainty = _replay(program, policy, rows, discount)
    return DynamicProgramResult(
        program_id=program.program_id,
        segment_id=program.segment_id,
        policy=policy,
        values=values,
        initial_state=program.initial_state,
        policy_value=values[0][program.initial_state],
        expected_cost=expected_cost,
        expected_service_attainment=service,
        expected_risk=risk,
        expected_uncertainty=uncertainty,
        discount_rate=program.discount_rate,
        horizon=program.horizon,
    )


def _reward(program: DynamicProgram, action: StrategicAction, outcome: Transition) -> float:
    return (
        program.service_weight * outcome.service_attainment
        - program.risk_weight * outcome.risk
        - program.uncertainty_weight * outcome.uncertainty
        - program.cost_weight * action.cost
    )


def _replay(
    program: DynamicProgram,
    policy: list[PolicyDecision],
    rows: dict[tuple[str, str], list[Transition]],
    discount: float,
) -> tuple[float, float, float, float]:
    decisions = {(item.period, item.state_id): item for item in policy}
    distribution = {program.initial_state: 1.0}
    cost = 0.0
    service = 0.0
    risk = 0.0
    uncertainty = 0.0
    weight_sum = 0.0
    for period in range(program.horizon):
        factor = discount**period
        next_distribution: dict[str, float] = {}
        for state, probability in distribution.items():
            decision = decisions[(period, state)]
            action = next(item for item in program.actions if item.action_id == decision.action_id)
            for outcome in rows[(state, action.action_id)]:
                mass = probability * outcome.probability
                cost += factor * mass * action.cost
                service += factor * mass * outcome.service_attainment
                risk += factor * mass * outcome.risk
                uncertainty += factor * mass * outcome.uncertainty
                next_distribution[outcome.to_state] = (
                    next_distribution.get(outcome.to_state, 0.0) + mass
                )
        weight_sum += factor
        distribution = next_distribution
    denominator = max(weight_sum, 1e-12)
    return cost, service / denominator, risk / denominator, uncertainty / denominator


__all__ = [
    "DP_SCHEMA_VERSION",
    "DPState",
    "DynamicProgram",
    "DynamicProgramError",
    "DynamicProgramResult",
    "PolicyDecision",
    "StrategicAction",
    "Transition",
    "solve_dynamic_program",
    "validate_dynamic_program",
]
