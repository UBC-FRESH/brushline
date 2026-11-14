"""Low-vegetation model card and applicability-domain contract.

The model card is the inspectable boundary of the P4 model: its predictors, training and
validation evidence, error and interval coverage, applicability domain, licence, citation, caveats,
and decision boundary. The domain check rejects an out-of-domain prediction instead of allowing a
silent extrapolation.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from brushline.model.state import (
    FUNCTIONAL_GROUPS,
    TREATMENT_METHODS,
    FunctionalGroup,
    TreatmentMethod,
)
from brushline.model.validation import ContractValidation, check_duplicates
from brushline.vegetation.validation import (
    CandidateSummary,
    MetricSummary,
)

MODEL_CARD_SCHEMA_VERSION: Literal["brushline.low-vegetation-model-card.v1"] = (
    "brushline.low-vegetation-model-card.v1"
)
MODEL_CARD_STATUSES: tuple[str, ...] = ("prototype", "candidate", "approved", "retired")
MODEL_VARIABLES: tuple[str, ...] = ("height_m", "cover_pct", "density_per_ha")


class ModelCardDomainError(ValueError):
    """Raised when a prediction is outside the model card domain."""


class PredictorSpec(BaseModel):
    """One predictor and its accepted range.

    Parameters
    ----------
    name : str
        Predictor name.
    unit : str
        Unit.
    minimum : float
        Lower accepted value.
    maximum : float
        Upper accepted value.
    required : bool, optional
        Whether the predictor is required. Defaults to ``True``.
    description : str
        Short description.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str = Field(min_length=1)
    unit: str = Field(min_length=1)
    minimum: float
    maximum: float
    required: bool = True
    description: str = ""

    @model_validator(mode="after")
    def _range_order(self) -> PredictorSpec:
        if self.minimum >= self.maximum:
            raise ValueError("predictor minimum must be below maximum")
        return self


class ApplicabilityDomain(BaseModel):
    """The predictor and context domain.

    Parameters
    ----------
    functional_groups : list of str
        Supported functional groups.
    treatment_methods : list of str
        Supported treatment methods.
    site_index_min_m : float
        Minimum site index.
    site_index_max_m : float
        Maximum site index.
    climate_factor_min : float
        Minimum climate factor.
    climate_factor_max : float
        Maximum climate factor.
    max_lag_years : int
        Maximum prediction lag.
    min_coverage_pct : float
        Minimum observation coverage.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    functional_groups: list[FunctionalGroup] = Field(min_length=1)
    treatment_methods: list[TreatmentMethod] = Field(min_length=1)
    site_index_min_m: float = Field(ge=0)
    site_index_max_m: float = Field(gt=0)
    climate_factor_min: float = Field(gt=0)
    climate_factor_max: float = Field(gt=0)
    max_lag_years: int = Field(ge=0)
    min_coverage_pct: float = Field(ge=0, le=100)

    @model_validator(mode="after")
    def _domain_order(self) -> ApplicabilityDomain:
        if self.site_index_min_m >= self.site_index_max_m:
            raise ValueError("site-index domain must increase")
        if self.climate_factor_min >= self.climate_factor_max:
            raise ValueError("climate-factor domain must increase")
        return self


class ModelCardEvidence(BaseModel):
    """Training or validation evidence.

    Parameters
    ----------
    dataset_id : str
        Dataset id.
    source : str
        Source.
    source_version : str
        Source version.
    licence : str
        Data licence.
    n_records : int
        Record count.
    spatial_blocks : list of str
        Spatial blocks.
    period : str
        Observation period.
    provenance : str
        Provenance reference.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    dataset_id: str = Field(min_length=1)
    source: str = Field(min_length=1)
    source_version: str = Field(min_length=1)
    licence: str = Field(min_length=1)
    n_records: int = Field(ge=1)
    spatial_blocks: list[str] = Field(min_length=1)
    period: str = Field(min_length=1)
    provenance: str = Field(min_length=1)


class UncertaintyContract(BaseModel):
    """How uncertainty is represented and propagated.

    Parameters
    ----------
    interval_level : float
        Interval coverage level.
    height_interval : str
        Height interval semantics.
    cover_interval : str
        Cover interval semantics.
    density_interval : str
        Density interval semantics.
    propagation : str
        How uncertainty enters the transition model.
    caveat : str
        Decision-support caveat.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    interval_level: float = Field(default=0.95, gt=0.5, lt=1)
    height_interval: str = Field(min_length=1)
    cover_interval: str = Field(min_length=1)
    density_interval: str = Field(min_length=1)
    propagation: str = Field(min_length=1)
    caveat: str = Field(min_length=1)


class ModelCardRequest(BaseModel):
    """A prediction context for the domain check.

    Parameters
    ----------
    functional_group : str
        Functional group.
    treatment_method : str
        Treatment method.
    site_index_m : float
        Site index.
    climate_factor : float
        Climate factor.
    lag_years : int
        Prediction lag.
    coverage_pct : float
        Observation coverage.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    functional_group: FunctionalGroup
    treatment_method: TreatmentMethod
    site_index_m: float = Field(ge=0)
    climate_factor: float = Field(gt=0)
    lag_years: int = Field(ge=0)
    coverage_pct: float = Field(ge=0, le=100)


class DomainCheck(BaseModel):
    """The result of a model-card domain check.

    Parameters
    ----------
    in_domain : bool
        Whether the request is inside the domain.
    reasons : list of str
        Named domain failures.
    model_id : str
        Model id.
    version : str
        Model version.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    in_domain: bool
    reasons: list[str] = Field(default_factory=list)
    model_id: str
    version: str


class LowVegetationModelCard(BaseModel):
    """The versioned low-vegetation model card.

    Parameters
    ----------
    schema_version : {"brushline.low-vegetation-model-card.v1"}
        Card schema version.
    model_id : str
        Model id.
    name : str
        Human name.
    version : str
        Model version.
    status : str
        ``prototype``, ``candidate``, ``approved``, or ``retired``.
    created_utc : datetime
        Timezone-aware creation time.
    licence : str
        Model licence.
    citation : str
        Citation.
    description : str
        Short description.
    predictors : list of PredictorSpec
        Predictor specs.
    functional_groups : list of str
        Supported groups.
    domain : ApplicabilityDomain
        Applicability domain.
    training : ModelCardEvidence
        Training evidence.
    validation : ModelCardEvidence
        Validation evidence.
    metrics : list of MetricSummary
        Validation metrics.
    candidates : list of CandidateSummary
        Candidate benchmark.
    uncertainty : UncertaintyContract
        Uncertainty contract.
    caveats : list of str
        Caveats.
    decision_boundary : str
        Decision-support boundary.
    """

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["brushline.low-vegetation-model-card.v1"] = MODEL_CARD_SCHEMA_VERSION
    model_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    version: str = Field(min_length=1)
    status: str
    created_utc: datetime
    licence: str = Field(min_length=1)
    citation: str = Field(min_length=1)
    description: str = Field(min_length=1)
    predictors: list[PredictorSpec] = Field(min_length=1)
    functional_groups: list[FunctionalGroup] = Field(min_length=1)
    domain: ApplicabilityDomain
    training: ModelCardEvidence
    validation: ModelCardEvidence
    metrics: list[MetricSummary] = Field(min_length=1)
    candidates: list[CandidateSummary] = Field(default_factory=list)
    uncertainty: UncertaintyContract
    caveats: list[str] = Field(min_length=1)
    decision_boundary: str = Field(min_length=1)


def check_domain(
    card: LowVegetationModelCard,
    request: ModelCardRequest,
) -> DomainCheck:
    """Check a prediction request against the card's applicability domain.

    Parameters
    ----------
    card : LowVegetationModelCard
        Model card.
    request : ModelCardRequest
        Prediction context.

    Returns
    -------
    DomainCheck
        In-domain flag and named reasons.
    """
    reasons: list[str] = []
    if request.functional_group not in card.domain.functional_groups:
        reasons.append(f"functional group {request.functional_group!r} is not supported")
    if request.treatment_method not in card.domain.treatment_methods:
        reasons.append(f"treatment method {request.treatment_method!r} is not supported")
    if not (card.domain.site_index_min_m <= request.site_index_m <= card.domain.site_index_max_m):
        reasons.append("site index is outside the applicability domain")
    if not (
        card.domain.climate_factor_min <= request.climate_factor <= card.domain.climate_factor_max
    ):
        reasons.append("climate factor is outside the applicability domain")
    if request.lag_years > card.domain.max_lag_years:
        reasons.append("prediction lag is outside the applicability domain")
    if request.coverage_pct < card.domain.min_coverage_pct:
        reasons.append("observation coverage is below the applicability domain")
    return DomainCheck(
        in_domain=not reasons,
        reasons=reasons,
        model_id=card.model_id,
        version=card.version,
    )


def require_in_domain(
    card: LowVegetationModelCard,
    request: ModelCardRequest,
) -> DomainCheck:
    """Return a passing domain check or raise.

    Parameters
    ----------
    card : LowVegetationModelCard
        Model card.
    request : ModelCardRequest
        Prediction context.

    Returns
    -------
    DomainCheck
        The passing check.

    Raises
    ------
    ModelCardDomainError
        When the request is outside the domain.
    """
    check = check_domain(card, request)
    if not check.in_domain:
        raise ModelCardDomainError("; ".join(check.reasons))
    return check


def validate_model_card(card: LowVegetationModelCard) -> ContractValidation:
    """Validate the model card and its evidence.

    Parameters
    ----------
    card : LowVegetationModelCard
        Card to validate.

    Returns
    -------
    ContractValidation
        Errors, warnings, and counts.
    """
    errors: list[str] = []
    warnings: list[str] = []
    check_duplicates(
        "MODEL-CARD",
        "predictor",
        [predictor.name for predictor in card.predictors],
        errors,
    )
    check_duplicates(
        "MODEL-CARD",
        "group",
        list(card.functional_groups),
        errors,
    )
    check_duplicates(
        "MODEL-CARD",
        "metric",
        [f"{metric.group}:{metric.variable}" for metric in card.metrics],
        errors,
    )
    check_duplicates(
        "MODEL-CARD",
        "candidate",
        [candidate.name for candidate in card.candidates],
        errors,
    )
    if card.created_utc.tzinfo is None:
        errors.append("MODEL-CARD-TIME: created_utc is not timezone-aware")
    if card.status not in MODEL_CARD_STATUSES:
        errors.append(f"MODEL-CARD-STATUS: unknown status {card.status!r}")
    if not card.licence.strip() or not card.citation.strip():
        errors.append("MODEL-CARD-LICENCE: licence and citation are required")
    if not card.decision_boundary.strip():
        errors.append("MODEL-CARD-BOUNDARY: decision boundary is required")
    if any(predictor.minimum >= predictor.maximum for predictor in card.predictors):
        errors.append("MODEL-CARD-PREDICTOR: predictor range is not ordered")
    if not set(card.functional_groups).issubset(set(FUNCTIONAL_GROUPS)):
        errors.append("MODEL-CARD-GROUP: unknown functional group")
    if not set(card.domain.functional_groups).issubset(set(card.functional_groups)):
        errors.append("MODEL-CARD-DOMAIN: domain names a group outside the card")
    if not set(card.domain.treatment_methods).issubset(set(TREATMENT_METHODS)):
        errors.append("MODEL-CARD-DOMAIN: domain names an unknown treatment method")
    if card.training.n_records <= 0 or card.validation.n_records <= 0:
        errors.append("MODEL-CARD-EVIDENCE: training and validation need records")
    metric_groups = {metric.group for metric in card.metrics}
    if not metric_groups.issubset(set(card.functional_groups)):
        errors.append("MODEL-CARD-METRIC: metric names a group outside the card")
    for metric in card.metrics:
        if metric.variable not in MODEL_VARIABLES:
            errors.append(f"MODEL-CARD-METRIC: unknown variable {metric.variable!r}")
        if metric.n == 0:
            errors.append("MODEL-CARD-METRIC: metric has no records")
        if metric.interval_coverage is None:
            warnings.append(
                f"MODEL-CARD-INTERVAL: {metric.group}/{metric.variable} has no interval coverage"
            )
    for candidate in card.candidates:
        if candidate.n == 0:
            errors.append(f"MODEL-CARD-CANDIDATE: {candidate.name} has no records")
    if not card.uncertainty.propagation.strip():
        errors.append("MODEL-CARD-UNCERTAINTY: propagation is required")
    if not card.caveats:
        errors.append("MODEL-CARD-CAVEAT: at least one caveat is required")
    if not card.candidates:
        warnings.append("MODEL-CARD-CANDIDATE: no candidate benchmark is recorded")
    counts: dict[str, int | float] = {
        "predictors": len(card.predictors),
        "groups": len(card.functional_groups),
        "metrics": len(card.metrics),
        "candidates": len(card.candidates),
        "training_records": card.training.n_records,
        "validation_records": card.validation.n_records,
    }
    return ContractValidation(tuple(errors), tuple(warnings), counts)


__all__ = [
    "MODEL_CARD_SCHEMA_VERSION",
    "MODEL_CARD_STATUSES",
    "MODEL_VARIABLES",
    "ApplicabilityDomain",
    "DomainCheck",
    "LowVegetationModelCard",
    "ModelCardDomainError",
    "ModelCardEvidence",
    "ModelCardRequest",
    "PredictorSpec",
    "UncertaintyContract",
    "check_domain",
    "require_in_domain",
    "validate_model_card",
]
