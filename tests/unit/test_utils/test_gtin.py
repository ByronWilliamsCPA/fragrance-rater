"""Tests for GS1 GTIN check-digit validation.

Known-valid values below are real, publicly published GTINs (a UPC-A on
a common retail product; a GTIN-13 read from a Parfumo product page's
`itemprop="gtin13"` meta tag during this project's source-resolution
work) - not invented numbers, since the whole point is validating
against the real GS1 algorithm.
"""

from fragrance_rater.utils.gtin import is_valid_gtin


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
