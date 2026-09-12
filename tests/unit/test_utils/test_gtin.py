"""Tests for GS1 GTIN check-digit validation.

Known-valid values below are real, publicly published GTINs (a UPC-A on
a common retail product; a GTIN-13 read from a Parfumo product page's
`itemprop="gtin13"` meta tag during this project's source-resolution
work) - not invented numbers, since the whole point is validating
against the real GS1 algorithm.
"""

from fragrance_rater.utils.gtin import is_valid_gtin, normalize_gtin


class TestIsValidGtin:
    def test_accepts_a_real_gtin_13(self):
        """Chanel N5 (Parfum)'s gtin13, as published on its Parfumo page."""
        assert is_valid_gtin("3508440005953") is True

    def test_accepts_a_real_upc_a_gtin_12(self):
        assert is_valid_gtin("036000291452") is True

    def test_rejects_wrong_check_digit(self):
        assert is_valid_gtin("3508440005950") is False

    def test_rejects_non_digit_characters(self):
        assert is_valid_gtin("350844000595X") is False
        assert is_valid_gtin("3508-4400-05953") is False

    def test_rejects_unsupported_length(self):
        assert is_valid_gtin("12345") is False
        assert is_valid_gtin("") is False

    def test_accepts_gtin_8(self):
        # 4006381333931 truncated to a real GTIN-8 pattern: compute a
        # valid one directly rather than guessing a real-world example.
        # 9638507 -> check digit 4 (verified against the same algorithm).
        assert is_valid_gtin("96385074") is True

    def test_accepts_gtin_14(self):
        # A GTIN-13 padded with a leading packaging-indicator digit is
        # the common way a GTIN-14 is formed in practice; check digit
        # recomputed for the 14-digit form (not merely copy-pasted from
        # the GTIN-13 above - it differs).
        assert is_valid_gtin("13508440005950") is True

    def test_rejects_none_and_non_string_input(self):
        assert is_valid_gtin(None) is False
        assert is_valid_gtin(3508440005953) is False

    def test_rejects_non_ascii_digit_characters_without_raising(self):
        """str.isdigit() accepts non-ASCII digits (e.g. superscript "²"),
        which int() then rejects; this must return False, not raise, to
        honor the documented "never raises" contract."""
        assert is_valid_gtin("350844000595²") is False
        assert is_valid_gtin("²5084400059530") is False


class TestNormalizeGtin:
    def test_pads_shorter_forms_to_gtin_14(self):
        assert normalize_gtin("96385074") == "00000096385074"
        assert normalize_gtin("036000291452") == "00036000291452"
        assert normalize_gtin("3508440005953") == "03508440005953"

    def test_leaves_a_gtin_14_unchanged(self):
        assert normalize_gtin("13508440005950") == "13508440005950"

    def test_a_gtin_13_and_its_zero_padded_gtin_14_form_normalize_equal(self):
        """This is the exact relationship a UPC-A/EAN-13 recorded as source
        evidence has to the same product's GTIN-14 form: GS1's own
        comparison rule is to left-pad with zeros, so these must compare
        equal despite being different-length strings."""
        gtin13 = "3508440005953"
        gtin14 = normalize_gtin(gtin13)
        assert normalize_gtin(gtin13) == normalize_gtin(gtin14)
