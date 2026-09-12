"""GS1 GTIN (barcode) validation.

A GTIN read off a physical bottle is the strongest identity signal this
project has: unlike a text-based match against a scraped page, it is
assigned per exact SKU by the manufacturer and does not depend on any
external source being reachable or well-formed. This module exists so
the offline manifest validator (`scripts/validate_calibration_manifest.py`)
and the live calibration API (`MembershipInput`/`CalibrationService`)
enforce the identical check-digit rule rather than drifting apart.
"""

from __future__ import annotations

#: GTIN-8, GTIN-12 (UPC-A), GTIN-13 (EAN-13), and GTIN-14 are the lengths
#: GS1 defines; anything else is not a GTIN, not just an unusual one.
VALID_GTIN_LENGTHS = (8, 12, 13, 14)


def _gs1_check_digit(digits: str) -> int:
    """Compute the GS1 mod-10 check digit for `digits`.

    Args:
        digits (str): The GTIN with its own check digit removed.

    Returns:
        int: The check digit `digits` should be followed by.
    """
    # #ASSUME: data-integrity: GS1's rule weights the digit immediately
    # left of the check digit as x3, alternating x1/x3 leftward from
    # there - equivalently, weight 3 on every digit at an even distance
    # (0, 2, 4, ...) from the rightmost end of `digits` when read in
    # reverse. This is length-independent, which is what lets one
    # function cover GTIN-8/12/13/14 uniformly.
    total = sum(
        (3 if position % 2 == 0 else 1) * int(digit)
        for position, digit in enumerate(reversed(digits))
    )
    return (10 - total % 10) % 10


def is_valid_gtin(value: object) -> bool:
    """Check whether `value` is a well-formed, check-digit-valid GTIN.

    # #ASSUME: data-integrity: `value` is typed `object`, not `str`,
    # because every current caller sits at a boundary where the value's
    # real type is not statically guaranteed - manifest JSON, a request
    # payload, or scraped HTML text. Narrowing this to `str` would push
    # the isinstance check out to each caller (or drop it, letting a
    # non-string slip through) instead of keeping this one shared
    # validator responsible for its own input.

    Args:
        value (object): Candidate GTIN, digits only (no spaces/hyphens).

    Returns:
        bool: True if `value` is a string of all digits, a valid GTIN
            length, and its final digit matches the GS1 check digit
            computed from the rest; False otherwise (never raises on
            malformed input).
    """
    # #ASSUME: data-integrity: str.isdigit() accepts non-ASCII digit
    # characters (e.g. superscript "²"), which int() then rejects,
    # so isascii() must gate isdigit() to keep the "never raises"
    # contract this function documents.
    if not isinstance(value, str) or not value.isascii() or not value.isdigit():
        return False
    if len(value) not in VALID_GTIN_LENGTHS:
        return False
    body, check_digit = value[:-1], int(value[-1])
    return _gs1_check_digit(body) == check_digit


def normalize_gtin(value: str) -> str:
    """Normalize a GTIN-8/12/13/14 to its canonical GTIN-14 form.

    # #ASSUME: data-integrity: GS1's own guidance for comparing GTINs of
    # different declared lengths is to left-pad with zeros to 14 digits,
    # so a UPC-A (GTIN-12) and the EAN-13/GTIN-14 encoding of the exact
    # same product compare equal instead of as a false mismatch. Callers
    # should validate with `is_valid_gtin` first; this does not validate
    # `value` itself.

    Args:
        value (str): An all-digit GTIN-8/12/13/14.

    Returns:
        str: `value` left-padded with zeros to 14 digits.
    """
    return value.zfill(14)
