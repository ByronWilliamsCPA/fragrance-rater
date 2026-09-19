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
