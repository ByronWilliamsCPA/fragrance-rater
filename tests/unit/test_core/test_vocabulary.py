"""Tests for canonical value vocabularies in core/vocabulary.py."""

from fragrance_rater.core import vocabulary


class TestGenderTargets:
    """Pre-existing vocabulary; smoke-tested for regression only."""

    def test_gender_targets_values(self):
        assert vocabulary.GENDER_TARGETS == ("Masculine", "Feminine", "Unisex")


class TestUnclassifiedFamily:
    """ADR-014: sentinel primary_family/subfamily value outside the Michael
    Edwards Wheel taxonomy, until ADR-010's ClassificationSystem exists.
    """

    def test_unclassified_family_value(self):
        assert vocabulary.UNCLASSIFIED_FAMILY == "Unclassified"

    def test_unclassified_family_is_a_string(self):
        assert isinstance(vocabulary.UNCLASSIFIED_FAMILY, str)


class TestTrainingIneligibleCodes:
    """ADR-014: single source of truth the migration seed data and
    RecommendationService's eligibility check must agree on.
    """

    def test_training_ineligible_codes_values(self):
        assert (
            frozenset({"excluded_pending_classification", "excluded_manual"})
            == vocabulary.TRAINING_INELIGIBLE_CODES
        )

    def test_training_ineligible_codes_excludes_eligible(self):
        assert "eligible" not in vocabulary.TRAINING_INELIGIBLE_CODES

    def test_training_ineligible_codes_is_frozenset(self):
        assert isinstance(vocabulary.TRAINING_INELIGIBLE_CODES, frozenset)
