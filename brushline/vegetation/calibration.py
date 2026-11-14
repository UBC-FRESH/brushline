"""Calibration of treatment efficacy, resprouting, and regrowth delay.

The calibration uses treatment observations with before/after height, cover, and density. It shrinks
thin evidence toward the P4.3 priors, records intervals and evidence level, and runs deterministic
leave-one-out checks. It does not acquire field data or change the plan schema.
"""

from __future__ import annotations

import math
from datetime import UTC, date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from brushline.model.state import FunctionalGroup, Season, TreatmentMethod
from brushline.model.validation import ContractValidation, check_duplicates
from brushline.vegetation.treatment import (
    DEFAULT_SEASON_FACTORS,
    TREATMENT_PARAMETERS,
    TreatmentParameters,
)

TREATMENT_CALIBRATION_SCHEMA_VERSION: Literal["brushline.treatment-calibration.v1"] = (
    "brushline.treatment-calibration.v1"
)
EVIDENCE_LEVELS: tuple[str, ...] = ("exact", "method_group", "method", "prior")


class TreatmentCalibrationError(ValueError):
    """Raised when treatment calibration evidence is inconsistent."""


class TreatmentObservation(BaseModel):
    """One before/after treatment observation.

    Parameters
    ----------
    observation_id : str
        Stable observation id.
    method : str
        Treatment method.
    season : str
        Treatment season.
    functional_group : str
        Functional group.
    before_height_m : float
        Pre-treatment height.
    after_height_m : float
        Post-treatment height.
    before_cover_pct : float
        Pre-treatment cover.
    after_cover_pct : float
        Post-treatment cover.
    before_density_per_ha : float or None
        Pre-treatment density.
    after_density_per_ha : float or None
        Post-treatment density.
    regrowth_delay_years : int
        Observed delay before regrowth.
    sample_size : int, optional
        Independent samples represented by this record. Defaults to ``1``.
    observed_date : datetime.date or None
        Observation date.
    source : str
        Evidence source.
    source_version : str
        Source version.
    notes : str
        Caveat.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    observation_id: str = Field(min_length=1)
    method: TreatmentMethod
    season: Season
    functional_group: FunctionalGroup
    before_height_m: float = Field(gt=0)
    after_height_m: float = Field(ge=0)
    before_cover_pct: float = Field(gt=0, le=100)
    after_cover_pct: float = Field(ge=0, le=100)
    before_density_per_ha: float | None = Field(default=None, ge=0)
    after_density_per_ha: float | None = Field(default=None, ge=0)
    regrowth_delay_years: int = Field(ge=0, le=20)
    sample_size: int = Field(default=1, ge=1)
    observed_date: date | None = None
    source: str = Field(min_length=1)
    source_version: str = Field(min_length=1)
    notes: str = ""

    @model_validator(mode="after")
    def _transition_consistency(self) -> TreatmentObservation:
        if self.after_height_m > self.before_height_m + 1e-9:
            raise ValueError("after_height_m must not exceed before_height_m")
        if self.after_cover_pct > self.before_cover_pct + 1e-9:
            raise ValueError("after_cover_pct must not exceed before_cover_pct")
        if (self.before_density_per_ha is None) != (self.after_density_per_ha is None):
            raise ValueError("density needs both before and after values")
        return self

    @property
    def height_efficacy(self) -> float:
        """Return the observed height reduction fraction.

        Returns
        -------
        float
            ``1 - after / before``, clamped to 0 to 1.
        """
        return max(0.0, min(1.0, 1.0 - self.after_height_m / self.before_height_m))

    @property
    def cover_efficacy(self) -> float:
        """Return the observed cover reduction fraction.

        Returns
        -------
        float
            ``1 - after / before``, clamped to 0 to 1.
        """
        return max(0.0, min(1.0, 1.0 - self.after_cover_pct / self.before_cover_pct))

    @property
    def resprout_factor(self) -> float | None:
        """Return the observed density increase fraction.

        Returns
        -------
        float or None
            ``after / before - 1`` when density is present, otherwise ``None``.
        """
        if self.before_density_per_ha in (None, 0) or self.after_density_per_ha is None:
            return None
        return max(0.0, self.after_density_per_ha / self.before_density_per_ha - 1.0)


class TreatmentCalibrationConfig(BaseModel):
    """Calibration pooling, interval, and holdout rules.

    Parameters
    ----------
    prior_strength : float, optional
        Pseudo-observation weight for the prior. Defaults to ``4``.
    min_observations : int, optional
        Minimum records for an exact evidence level. Defaults to ``2``.
    holdout_every : int, optional
        Hold out every nth sorted observation. Defaults to ``5``.
    holdout_tolerance : float, optional
        Maximum absolute cover-efficacy error. Defaults to ``0.25``.
    confidence_z : float, optional
        Interval multiplier. Defaults to ``1.96``.
    model_card_id : str, optional
        Model card id.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    prior_strength: float = Field(default=4.0, gt=0)
    min_observations: int = Field(default=2, ge=1)
    holdout_every: int = Field(default=5, ge=2)
    holdout_tolerance: float = Field(default=0.25, ge=0, le=1)
    confidence_z: float = Field(default=1.96, gt=0)
    model_card_id: str = "brushline.treatment-calibration.v1"


class CalibratedTreatmentParameters(BaseModel):
    """Calibrated parameters for one method, season, and group.

    Parameters
    ----------
    method : str
        Method.
    season : str
        Season.
    functional_group : str
        Functional group.
    efficacy : float
        Effective cover reduction fraction.
    top_kill : float
        Height-reduction share.
    resprout_factor : float
        Density increase share.
    regrowth_delay_years : int
        Delay before regrowth.
    height_efficacy : float
        Observed height reduction.
    cover_efficacy : float
        Observed cover reduction.
    efficacy_interval : tuple of float
        Lower and upper efficacy interval.
    resprout_interval : tuple of float
        Lower and upper resprout interval.
    delay_min_years : int
        Minimum observed delay.
    delay_max_years : int
        Maximum observed delay.
    sample_size : int
        Number of records.
    effective_sample_size : float
        Weighted sample size.
    evidence_level : str
        ``exact``, ``method_group``, ``method``, or ``prior``.
    pooled : bool
        Whether the evidence was pooled.
    source_ids : list of str
        Source observation ids.
    model_card_id : str
        Model card id.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    method: TreatmentMethod
    season: Season
    functional_group: FunctionalGroup
    efficacy: float = Field(ge=0, le=1)
    top_kill: float = Field(ge=0, le=1)
    resprout_factor: float = Field(ge=0, le=1)
    regrowth_delay_years: int = Field(ge=0, le=20)
    height_efficacy: float = Field(ge=0, le=1)
    cover_efficacy: float = Field(ge=0, le=1)
    efficacy_interval: tuple[float, float]
    resprout_interval: tuple[float, float]
    delay_min_years: int = Field(ge=0, le=20)
    delay_max_years: int = Field(ge=0, le=20)
    sample_size: int = Field(ge=0)
    effective_sample_size: float = Field(ge=0)
    evidence_level: str
    pooled: bool
    source_ids: list[str] = Field(default_factory=list)
    model_card_id: str

    @model_validator(mode="after")
    def _interval_order(self) -> CalibratedTreatmentParameters:
        if self.evidence_level not in EVIDENCE_LEVELS:
            raise ValueError(f"unknown evidence level {self.evidence_level!r}")
        if not (0 <= self.efficacy_interval[0] <= self.efficacy_interval[1] <= 1):
            raise ValueError("efficacy interval must be ordered inside 0 to 1")
        if not (0 <= self.resprout_interval[0] <= self.resprout_interval[1]):
            raise ValueError("resprout interval must be ordered")
        if self.delay_min_years > self.delay_max_years:
            raise ValueError("delay range must be ordered")
        return self

    def to_treatment_parameters(self, base: TreatmentParameters) -> TreatmentParameters:
        """Apply the calibrated values to a base treatment parameter set.

        Parameters
        ----------
        base : TreatmentParameters
            Method parameters that supply cost and notes.

        Returns
        -------
        TreatmentParameters
            Calibrated parameters.
        """
        return base.model_copy(
            update={
                "efficacy": self.efficacy,
                "top_kill": self.top_kill,
                "resprout_factor": self.resprout_factor,
                "regrowth_delay_years": self.regrowth_delay_years,
            }
        )


class CalibrationCheck(BaseModel):
    """One deterministic leave-one-out check.

    Parameters
    ----------
    observation_id : str
        Held-out observation.
    method : str
        Method.
    season : str
        Season.
    functional_group : str
        Functional group.
    observed_efficacy : float
        Observed cover efficacy.
    predicted_efficacy : float
        Predicted cover efficacy.
    absolute_error : float
        Absolute error.
    tolerance : float
        Acceptance tolerance.
    passed : bool
        Whether the error is within tolerance.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    observation_id: str
    method: TreatmentMethod
    season: Season
    functional_group: FunctionalGroup
    observed_efficacy: float = Field(ge=0, le=1)
    predicted_efficacy: float = Field(ge=0, le=1)
    absolute_error: float = Field(ge=0)
    tolerance: float = Field(ge=0, le=1)
    passed: bool


class TreatmentCalibrationReport(BaseModel):
    """The calibrated treatment parameters and held-out checks.

    Parameters
    ----------
    schema_version : {"brushline.treatment-calibration.v1"}
        Report schema version.
    created_utc : datetime
        Timezone-aware creation time.
    config : TreatmentCalibrationConfig
        Calibration rules.
    parameters : list of CalibratedTreatmentParameters
        Calibrated cells.
    holdout_checks : list of CalibrationCheck
        Leave-one-out checks.
    open_questions : list of str
        Reviewer questions.
    """

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["brushline.treatment-calibration.v1"] = (
        TREATMENT_CALIBRATION_SCHEMA_VERSION
    )
    created_utc: datetime
    config: TreatmentCalibrationConfig
    parameters: list[CalibratedTreatmentParameters] = Field(min_length=1)
    holdout_checks: list[CalibrationCheck] = Field(default_factory=list)
    open_questions: list[str] = Field(default_factory=list)


def calibrate_treatment(
    observations: list[TreatmentObservation],
    config: TreatmentCalibrationConfig | None = None,
    *,
    created_utc: datetime | None = None,
) -> TreatmentCalibrationReport:
    """Calibrate treatment efficacy, resprouting, and delay.

    Parameters
    ----------
    observations : list of TreatmentObservation
        Evidence records.
    config : TreatmentCalibrationConfig, optional
        Pooling, interval, and holdout rules.
    created_utc : datetime, optional
        Report time.

    Returns
    -------
    TreatmentCalibrationReport
        Calibrated cells and held-out checks.

    Raises
    ------
    TreatmentCalibrationError
        When the evidence is empty or has duplicate observation ids.
    """
    if not observations:
        raise TreatmentCalibrationError("at least one treatment observation is required")
    ids = [observation.observation_id for observation in observations]
    if len(set(ids)) != len(ids):
        raise TreatmentCalibrationError("treatment observation ids must be unique")
    rules = config or TreatmentCalibrationConfig()
    parameters = _calibrate_cells(observations, rules)
    checks: list[CalibrationCheck] = []
    ordered = sorted(observations, key=lambda item: item.observation_id)
    for index, held in enumerate(ordered, start=1):
        if index % rules.holdout_every != 0:
            continue
        remaining = [
            observation
            for observation in observations
            if observation.observation_id != held.observation_id
        ]
        calibrated = _calibrate_cells(remaining, rules)
        prediction = next(
            (
                item
                for item in calibrated
                if item.method == held.method
                and item.season == held.season
                and item.functional_group == held.functional_group
            ),
            None,
        )
        predicted = prediction.efficacy if prediction is not None else _prior(held).efficacy
        error = abs(predicted - held.cover_efficacy)
        checks.append(
            CalibrationCheck(
                observation_id=held.observation_id,
                method=held.method,
                season=held.season,
                functional_group=held.functional_group,
                observed_efficacy=held.cover_efficacy,
                predicted_efficacy=predicted,
                absolute_error=error,
                tolerance=rules.holdout_tolerance,
                passed=error <= rules.holdout_tolerance,
            )
        )
    open_questions: list[str] = []
    pooled = [item for item in parameters if item.pooled]
    if pooled:
        open_questions.append(
            f"{len(pooled)} cells use pooled or prior evidence; review the evidence level."
        )
    failed = [check for check in checks if not check.passed]
    if failed:
        open_questions.append(f"{len(failed)} held-out checks exceed the tolerance.")
    if not checks:
        open_questions.append("No leave-one-out checks were available.")
    return TreatmentCalibrationReport(
        created_utc=created_utc or datetime.now(UTC),
        config=rules,
        parameters=parameters,
        holdout_checks=checks,
        open_questions=open_questions,
    )


def validate_treatment_calibration(
    report: TreatmentCalibrationReport,
) -> ContractValidation:
    """Validate calibrated cells, intervals, and held-out checks.

    Parameters
    ----------
    report : TreatmentCalibrationReport
        Report to validate.

    Returns
    -------
    ContractValidation
        Errors, warnings, and counts.
    """
    errors: list[str] = []
    warnings: list[str] = []
    check_duplicates(
        "CALIBRATION",
        "cell",
        [f"{item.method}:{item.season}:{item.functional_group}" for item in report.parameters],
        errors,
    )
    if report.created_utc.tzinfo is None:
        errors.append("CALIBRATION-TIME: created_utc is not timezone-aware")
    for item in report.parameters:
        if item.evidence_level not in EVIDENCE_LEVELS:
            errors.append(
                f"CALIBRATION-EVIDENCE: {item.method}/{item.season} has unknown "
                f"evidence level {item.evidence_level!r}"
            )
        if item.sample_size == 0 and item.evidence_level != "prior":
            errors.append(f"CALIBRATION-EVIDENCE: {item.method}/{item.season} has no samples")
        if item.evidence_level == "prior" and not item.pooled:
            errors.append(f"CALIBRATION-EVIDENCE: {item.method}/{item.season} prior is not pooled")
        if item.evidence_level != "prior" and not item.source_ids:
            errors.append(f"CALIBRATION-SOURCE: {item.method}/{item.season} has no source ids")
        if item.effective_sample_size > 0 and item.sample_size == 0:
            errors.append(
                f"CALIBRATION-SAMPLE: {item.method}/{item.season} has weight without samples"
            )
    for check in report.holdout_checks:
        if not check.passed:
            errors.append(
                f"CALIBRATION-HOLDOUT: {check.observation_id} error "
                f"{check.absolute_error:.4f} exceeds {check.tolerance:.4f}"
            )
    if not report.holdout_checks:
        warnings.append("CALIBRATION-EMPTY: no held-out checks")
    counts: dict[str, int | float] = {
        "cells": len(report.parameters),
        "exact": sum(1 for item in report.parameters if item.evidence_level == "exact"),
        "pooled": sum(1 for item in report.parameters if item.pooled),
        "holdout": len(report.holdout_checks),
        "holdout_failed": sum(1 for check in report.holdout_checks if not check.passed),
    }
    return ContractValidation(tuple(errors), tuple(warnings), counts)


def _calibrate_cells(
    observations: list[TreatmentObservation],
    config: TreatmentCalibrationConfig,
) -> list[CalibratedTreatmentParameters]:
    keys = sorted({(item.method, item.season, item.functional_group) for item in observations})
    return [
        _calibrate_cell(observations, method, season, group, config)
        for method, season, group in keys
    ]


def _calibrate_cell(
    observations: list[TreatmentObservation],
    method: TreatmentMethod,
    season: Season,
    group: FunctionalGroup,
    config: TreatmentCalibrationConfig,
) -> CalibratedTreatmentParameters:
    exact = [
        item
        for item in observations
        if item.method == method and item.season == season and item.functional_group == group
    ]
    method_group = [
        item for item in observations if item.method == method and item.functional_group == group
    ]
    method_only = [item for item in observations if item.method == method]
    if len(exact) >= config.min_observations:
        selected = exact
        level = "exact"
    elif len(method_group) >= config.min_observations:
        selected = method_group
        level = "method_group"
    elif len(method_only) >= config.min_observations:
        selected = method_only
        level = "method"
    else:
        selected = []
        level = "prior"
    base = _base_parameters(method)
    prior = _prior(_synthetic_observation(method, season, group))
    if not selected:
        return _from_prior(base, method, season, group, config)
    weights = [item.sample_size for item in selected]
    effective_n = float(sum(weights))
    height_mean = _weighted_mean([(item.height_efficacy, item.sample_size) for item in selected])
    cover_mean = _weighted_mean([(item.cover_efficacy, item.sample_size) for item in selected])
    resprouts = [
        (item.resprout_factor, item.sample_size)
        for item in selected
        if item.resprout_factor is not None
    ]
    resprout_mean = _weighted_mean(resprouts) if resprouts else base.resprout_factor
    delays = [item.regrowth_delay_years for item in selected]
    efficacy = _shrink(cover_mean, effective_n, prior.efficacy, config.prior_strength)
    top_kill = max(0.0, min(1.0, height_mean / efficacy)) if efficacy > 1e-9 else base.top_kill
    resprout = max(
        0.0,
        min(
            1.0,
            _shrink(
                resprout_mean,
                effective_n,
                prior.resprout_factor,
                config.prior_strength,
            ),
        ),
    )
    delay = round(
        _shrink(
            sum(delays) / len(delays),
            effective_n,
            float(prior.regrowth_delay_years),
            config.prior_strength,
        )
    )
    cover_sd = _weighted_sd(
        [(item.cover_efficacy, item.sample_size) for item in selected],
        cover_mean,
    )
    resprout_sd = _weighted_sd(resprouts, resprout_mean) if resprouts else 0.2
    efficacy_interval = _interval(
        efficacy,
        max(0.05, cover_sd / math.sqrt(max(effective_n, 1))),
        config.confidence_z,
    )
    resprout_interval = _interval(
        resprout,
        max(0.05, resprout_sd / math.sqrt(max(effective_n, 1))),
        config.confidence_z,
    )
    return CalibratedTreatmentParameters(
        method=method,
        season=season,
        functional_group=group,
        efficacy=efficacy,
        top_kill=top_kill,
        resprout_factor=resprout,
        regrowth_delay_years=max(0, min(20, delay)),
        height_efficacy=height_mean,
        cover_efficacy=cover_mean,
        efficacy_interval=efficacy_interval,
        resprout_interval=resprout_interval,
        delay_min_years=min(delays),
        delay_max_years=max(delays),
        sample_size=len(selected),
        effective_sample_size=effective_n,
        evidence_level=level,
        pooled=level != "exact",
        source_ids=[item.observation_id for item in selected],
        model_card_id=config.model_card_id,
    )


def _from_prior(
    base: TreatmentParameters,
    method: TreatmentMethod,
    season: Season,
    group: FunctionalGroup,
    config: TreatmentCalibrationConfig,
) -> CalibratedTreatmentParameters:
    prior = _prior(_synthetic_observation(method, season, group))
    return CalibratedTreatmentParameters(
        method=method,
        season=season,
        functional_group=group,
        efficacy=prior.efficacy,
        top_kill=prior.top_kill,
        resprout_factor=prior.resprout_factor,
        regrowth_delay_years=prior.regrowth_delay_years,
        height_efficacy=prior.efficacy * prior.top_kill,
        cover_efficacy=prior.efficacy,
        efficacy_interval=_interval(prior.efficacy, 0.2, config.confidence_z),
        resprout_interval=_interval(prior.resprout_factor, 0.2, config.confidence_z),
        delay_min_years=prior.regrowth_delay_years,
        delay_max_years=prior.regrowth_delay_years,
        sample_size=0,
        effective_sample_size=0.0,
        evidence_level="prior",
        pooled=True,
        source_ids=[],
        model_card_id=config.model_card_id,
    )


def _base_parameters(method: TreatmentMethod) -> TreatmentParameters:
    for parameters in TREATMENT_PARAMETERS:
        if parameters.method == method:
            return parameters
    raise TreatmentCalibrationError(f"no treatment parameters for {method!r}")


def _synthetic_observation(
    method: TreatmentMethod,
    season: Season,
    group: FunctionalGroup,
) -> TreatmentObservation:
    base = _base_parameters(method)
    factor = DEFAULT_SEASON_FACTORS.get(season, 1.0)
    efficacy = base.efficacy * factor
    before_h = 2.0
    before_c = 30.0
    return TreatmentObservation(
        observation_id=f"prior:{method}:{season}:{group}",
        method=method,
        season=season,
        functional_group=group,
        before_height_m=before_h,
        after_height_m=max(0.05, before_h * (1 - efficacy * base.top_kill)),
        before_cover_pct=before_c,
        after_cover_pct=max(1.0, before_c * (1 - efficacy)),
        before_density_per_ha=1000.0,
        after_density_per_ha=1000.0 * (1 + base.resprout_factor * efficacy),
        regrowth_delay_years=base.regrowth_delay_years,
        source="prior",
        source_version="p4.3",
    )


def _prior(observation: TreatmentObservation) -> TreatmentParameters:
    base = _base_parameters(observation.method)
    factor = DEFAULT_SEASON_FACTORS.get(observation.season, 1.0)
    return base.model_copy(
        update={
            "efficacy": min(1.0, base.efficacy * factor),
            "regrowth_delay_years": base.regrowth_delay_years,
        }
    )


def _weighted_mean(values: list[tuple[float, int]]) -> float:
    total = sum(weight for _, weight in values)
    return sum(value * weight for value, weight in values) / total


def _weighted_sd(values: list[tuple[float, int]], mean: float) -> float:
    total = sum(weight for _, weight in values)
    if total <= 1:
        return 0.2
    variance = sum(weight * (value - mean) ** 2 for value, weight in values) / total
    return math.sqrt(variance)


def _shrink(mean: float, n: float, prior: float, strength: float) -> float:
    return (mean * n + prior * strength) / (n + strength)


def _interval(value: float, half_width: float, z: float) -> tuple[float, float]:
    delta = z * half_width
    return (max(0.0, value - delta), min(1.0, value + delta))


__all__ = [
    "EVIDENCE_LEVELS",
    "TREATMENT_CALIBRATION_SCHEMA_VERSION",
    "CalibratedTreatmentParameters",
    "CalibrationCheck",
    "TreatmentCalibrationConfig",
    "TreatmentCalibrationError",
    "TreatmentCalibrationReport",
    "TreatmentObservation",
    "calibrate_treatment",
    "validate_treatment_calibration",
]
