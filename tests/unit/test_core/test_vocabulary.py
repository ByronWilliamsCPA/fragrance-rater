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

    def test_training_ineligible_codes_excludes_none(self):
        """Regression tripwire: `None` (the implicit "eligible" state for
        every fragrance with no override) must never be added to this
        frozenset, or every explicitly-eligible fragrance would silently
        stop training affinities.
        """
        assert None not in vocabulary.TRAINING_INELIGIBLE_CODES

    def test_training_ineligible_codes_is_frozenset(self):
        assert isinstance(vocabulary.TRAINING_INELIGIBLE_CODES, frozenset)


class TestHouseIntakeAlignment:
    """The house form and the catalog share one vocabulary per fact."""

    def test_every_house_concentration_code_has_a_catalog_form(self):
        from typing import get_args

        from fragrance_rater.schemas.house_intake import Concentration

        codes = set(get_args(Concentration)) - {"OTHER"}
        assert codes == set(vocabulary.CATALOG_CONCENTRATIONS)

    def test_house_marketed_for_is_the_catalog_gender_vocabulary(self):
        from fragrance_rater.schemas.house_intake import HouseSubmissionPayload

        for gender in vocabulary.GENDER_TARGETS:
            payload = HouseSubmissionPayload(fragrance_name="X", marketed_for=gender)
            assert payload.marketed_for == gender

    def test_house_availability_is_the_catalog_market_status_vocabulary(self):
        from fragrance_rater.schemas.fragrance import FragranceUpdate
        from fragrance_rater.schemas.house_intake import HouseSubmissionPayload

        for market_status in vocabulary.MARKET_STATUSES:
            house = HouseSubmissionPayload(
                fragrance_name="X", availability=market_status
            )
            catalog = FragranceUpdate(market_status=market_status)
            assert house.availability == catalog.market_status == market_status

    def test_catalog_accepts_the_earliest_house_launch_year(self):
        from fragrance_rater.schemas.fragrance import FragranceUpdate

        earliest = vocabulary.EARLIEST_LAUNCH_YEAR
        assert FragranceUpdate(launch_year=earliest).launch_year == earliest

    def test_concentration_synonyms_compare_equal(self):
        key = vocabulary.concentration_key
        assert key("Eau de  Parfum") == key("EDP") == key("edp")
        assert key("Extrait de Parfum") == key("Extrait")
        assert key("EDT") != key("EDP")
