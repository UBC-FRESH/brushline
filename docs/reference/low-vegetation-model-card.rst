Low-vegetation model card
==========================

The model card is the inspectable boundary of the P4 low-vegetation model. It names the predictors,
training and validation evidence, error, interval coverage, functional groups, treatment methods,
applicability domain, licence, citation, caveats, and decision boundary.

The committed card is ``notes/reference/low-vegetation-model-card.v1.json``.

Card
----

A ``LowVegetationModelCard`` carries:

- model id, name, version, status, creation time, licence, citation, and description;
- predictor specs with units, ranges, and required flags;
- supported functional groups;
- an ``ApplicabilityDomain`` with site-index, climate, lag, coverage, group, and treatment bounds;
- training and validation evidence with source, version, licence, record count, spatial blocks, period,
  and provenance;
- validation metrics and candidate benchmark;
- an uncertainty contract;
- caveats and a decision boundary.

The committed card is a prototype. Its evidence is synthetic until a field calibration replaces it.

Domain check
------------

``check_domain(card, request)`` rejects a request when:

- the functional group is not supported;
- the treatment method is not supported;
- site index is outside its range;
- climate factor is outside its range;
- prediction lag exceeds the card maximum;
- observation coverage is below the card minimum.

The check returns ``DomainCheck`` with named reasons. ``require_in_domain`` raises
``ModelCardDomainError`` instead of allowing a silent extrapolation.

.. code-block:: python

   from pathlib import Path
   from brushline.vegetation.model_card import (
       LowVegetationModelCard,
       ModelCardRequest,
       check_domain,
       require_in_domain,
       validate_model_card,
   )

   card = LowVegetationModelCard.model_validate_json(
       Path("notes/reference/low-vegetation-model-card.v1.json").read_text()
   )
   assert validate_model_card(card).is_valid
   check = check_domain(
       card,
       ModelCardRequest(
           functional_group="shrub",
           treatment_method="mowing",
           site_index_m=20,
           climate_factor=1.0,
           lag_years=1,
           coverage_pct=100,
       ),
   )
   assert check.in_domain
   require_in_domain(card, check_request)

Uncertainty contract
--------------------

The card declares a 95 percent interval level and the semantics for height, cover, and density:

- each prediction is a mean with a standard deviation;
- the state distribution and intervals enter growth, treatment, and planning;
- the interval is decision-support evidence, not a guarantee.

The card does not replace the state distribution with a point estimate.

Evidence and benchmark
----------------------

The card names the training and validation datasets, record counts, spatial blocks, period, licence,
and provenance. It includes validation metrics by functional group and variable and candidate benchmark
summaries with RMSE differences.

The P4.6 candidate disagreement is recorded in the card. It is not hidden or treated as a model failure
by itself.

Named errors
------------

.. list-table::
   :header-rows: 1
   :widths: 32 68

   * - Prefix
     - Meaning
   * - ``MODEL-CARD-TIME``
     - Creation time is not timezone-aware.
   * - ``MODEL-CARD-STATUS``
     - Unknown card status.
   * - ``MODEL-CARD-LICENCE``
     - Missing licence or citation.
   * - ``MODEL-CARD-BOUNDARY``
     - Missing decision boundary.
   * - ``MODEL-CARD-PREDICTOR``
     - Predictor range is not ordered.
   * - ``MODEL-CARD-GROUP``, ``MODEL-CARD-DOMAIN``
     - Unknown group, or a domain group/method outside the card.
   * - ``MODEL-CARD-EVIDENCE``
     - Training or validation has no records.
   * - ``MODEL-CARD-METRIC``
     - Unknown variable, no records, or a group outside the card.
   * - ``MODEL-CARD-CANDIDATE``
     - Candidate has no records (warning when the benchmark is absent).
   * - ``MODEL-CARD-INTERVAL``
     - A metric has no interval coverage (warning).
   * - ``MODEL-CARD-UNCERTAINTY``
     - Missing uncertainty propagation.
   * - ``MODEL-CARD-CAVEAT``
     - The card has no caveat.
   * - ``MODEL-CARD-ID``
     - Duplicate predictor, group, metric, or candidate key.

Limits
------

- The committed card is a prototype backed by synthetic evidence.
- A card field is not a guarantee of field accuracy.
- The domain check is a boundary, not an approval to treat.
- The card does not replace a field inspection, a qualified reviewer, or the owner's work-control rules.
