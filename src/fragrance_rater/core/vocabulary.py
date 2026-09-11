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
