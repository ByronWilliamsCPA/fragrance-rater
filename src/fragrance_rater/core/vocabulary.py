"""Canonical value vocabularies shared across ingestion paths and the API.

Major finding 5: the Parfumo scraper, the Kaggle importer, and the API's
request/filter schemas each independently decided what values a
``gender_target`` may take. They drifted (the scraper wrote lowercase
"masculine"/"feminine"/"unisex" straight to the database while the Kaggle
importer and the API schema both use the capitalized "Masculine"/
"Feminine"/"Unisex" form), which silently broke gender_target filtering
for any fragrance imported via the scraper. This module is the single
source of truth both ingestion paths and the API schemas must agree on.
"""

from __future__ import annotations

from typing import Final, Literal

# #ASSUME: data-integrity: this Literal is duplicated (not imported) into
# GENDER_TARGETS below because `typing.Literal` values must be literal at
# type-check time; keeping them adjacent in one module is what makes them
# "canonical" rather than a strict single definition.
# #VERIFY: any new caller needing the gender_target vocabulary imports
# GenderTarget/GENDER_TARGETS from here rather than redefining the Literal.
GenderTarget = Literal["Masculine", "Feminine", "Unisex"]

GENDER_TARGETS: Final[tuple[GenderTarget, ...]] = ("Masculine", "Feminine", "Unisex")

# #ASSUME: data-integrity: ADR-014. `Fragrance.primary_family`/`subfamily`
# are hardcoded, unversioned Michael Edwards Wheel strings (NOT NULL,
# min_length=1); there is no schema-level way to add a fragrance from a
# tradition the Wheel doesn't cover (e.g. Gulf attar/oud, South Asian ittar)
# without coercing it into a fake Edwards family. UNCLASSIFIED_FAMILY is the
# sentinel value for that case until ADR-010's ClassificationSystem exists.
# #VERIFY: any caller writing a Fragrance whose tradition has no real Edwards
# family should use this constant rather than inventing another ad hoc
# string; RecommendationService still buckets it as its own family in
# family_affinities today (see ADR-014 Consequences: a known, deliberately
# deferred limitation, not a silent bug).
UNCLASSIFIED_FAMILY: Final[str] = "Unclassified"

# #ASSUME: data-integrity: ADR-014. This is the single source of truth both
# the training_eligibilities migration seed data (alembic/versions/
# 7daf681ed339_training_eligibility_lookup.py) and
# RecommendationService.build_preference_profile's eligibility check must
# agree on, exactly the kind of drift this module's own docstring already
# describes for gender_target (the scraper and the API/importer disagreeing
# on case). A code absent from both this set and the migration's seed rows
# is a modeling bug, not a valid third state.
# #VERIFY: any new caller checking whether a fragrance may train affinities
# imports TRAINING_INELIGIBLE_CODES from here rather than re-listing the
# excluded codes.
TRAINING_INELIGIBLE_CODES: Final[frozenset[str]] = frozenset(
    {"excluded_pending_classification", "excluded_manual"}
)

# R8 (architecture review X-05; data-model-gap-analysis row XL): a per-row
# training-eligibility code on both evidence tables, `evaluations` and
# `calibration_observations`. Distinct from the fragrance-level
# `training_eligibility_code` above: ADR-014 gates a fragrance for every
# reviewer, this gates one encounter (a contaminated sample, a
# mis-administered trial). Only `eligible` rows reach `v_training_rows`.
# #CRITICAL: data-integrity: ADR-014 deliberately does not build this
# per-evidence gate and so says nothing about its default. The gap analysis
# suggested defaulting to ELIGIBLE; R8 instead defaults every existing and
# new row to `unreviewed` (ineligible) until the owner decides, so that no
# row trains a model without a deliberate decision. Reversing that is one
# UPDATE plus a server-default change, and `unreviewed` stays distinct from a
# deliberate `withheld` so the reversal cannot release withheld rows.
# #VERIFY: tests/unit/test_models/test_training_eligibility.py pins this
# tuple against the model CHECKs, the migration, and the view.
EvidenceTrainingEligibility = Literal[
    "unreviewed", "eligible", "withheld", "invalidated", "questionable"
]

EVIDENCE_TRAINING_ELIGIBILITIES: Final[tuple[EvidenceTrainingEligibility, ...]] = (
    "unreviewed",
    "eligible",
    "withheld",
    "invalidated",
    "questionable",
)

#: The code every evidence row starts with (see the #CRITICAL note above).
DEFAULT_EVIDENCE_TRAINING_ELIGIBILITY: Final[EvidenceTrainingEligibility] = "unreviewed"

#: The only code `v_training_rows` admits.
TRAINABLE_EVIDENCE_ELIGIBILITY: Final[EvidenceTrainingEligibility] = "eligible"

# House intake alignment (docs/superpowers/specs/2026-10-02-house-intake-design.md).
# #ASSUME: data-integrity: the house form, the catalog schemas, and the
# manager review compare these values directly, so each is defined once here
# rather than once per layer, the drift this module exists to prevent.
# #VERIFY: tests/unit/test_core/test_vocabulary.py asserts the house payload
# and catalog schemas accept exactly these values.

#: Earliest launch year either layer accepts. Houses such as Farina (1709) and
#: Floris (1730) still sell eighteenth-century fragrances.
EARLIEST_LAUNCH_YEAR: Final[int] = 1700

MarketStatus = Literal["in_production", "limited_edition", "upcoming", "discontinued"]

MARKET_STATUSES: Final[tuple[MarketStatus, ...]] = (
    "in_production",
    "limited_edition",
    "upcoming",
    "discontinued",
)

#: House concentration codes in the short form the catalog already stores.
CATALOG_CONCENTRATIONS: Final[dict[str, str]] = {
    "EDC": "EDC",
    "EDT": "EDT",
    "EDP": "EDP",
    "PARFUM": "Parfum",
    "EXTRAIT": "Extrait",
    "OIL": "Oil",
    "SOLID": "Solid",
}

# Spellings that name the same concentration, so a catalog row written as
# "Eau de Parfum" compares equal to a house's EDP instead of reading as a
# different version.
_CONCENTRATION_SYNONYMS: Final[dict[str, str]] = {
    "eau de cologne": "edc",
    "cologne": "edc",
    "eau de toilette": "edt",
    "eau de parfum": "edp",
    "extrait de parfum": "extrait",
    "perfume oil": "oil",
    "attar": "oil",
    "solid perfume": "solid",
}


def concentration_key(value: str) -> str:
    """Comparison key for a concentration, treating known spellings as equal.

    Args:
        value (str): A concentration as stored or declared.

    Returns:
        str: A case- and spacing-insensitive key; synonyms share one key.
    """
    key = " ".join(value.casefold().split())
    return _CONCENTRATION_SYNONYMS.get(key, key)
