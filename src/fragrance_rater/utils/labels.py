"""Normalization of raw note and accord labels (R6; X-01, X-03).

Sources spell the same thing differently: ``Oak Moss``, ``oak moss``, ``oakmoss``,
``Ylang-Ylang``, ``Néroli``. Identity is decided on a normalized key; the raw
spelling is always kept beside it (on ``Note.name`` and ``NoteAlias.raw_label``) so
a decision can be audited and reversed.

Normalization removes only presentation differences: case, accents, and word
separators. It never merges different words. ``vanille`` and ``vanilla`` are
different keys, so joining them is an explicit, versioned ``NoteAlias`` decision
and not a side effect of string handling.
"""

from __future__ import annotations

import re
import unicodedata

NOTE_KEY_MAX_LENGTH = 100
"""Width of ``notes.name_key`` and ``note_aliases.alias_key``; equal to ``notes.name``."""

_NON_ALPHANUMERIC = re.compile(r"[^0-9a-z]+")
_WHITESPACE = re.compile(r"\s+")


def _fold(raw: str) -> str:
    """Return ``raw`` compatibility-normalized, accent-stripped, and casefolded."""
    decomposed = unicodedata.normalize("NFKD", raw)
    stripped = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    return stripped.casefold()


def normalize_note_key(raw: str) -> str:
    """Return the identity key for a note label.

    Lowercases, strips accents, and drops every character that is not a letter or
    digit, so word separators (spaces, hyphens, apostrophes, ampersands) do not
    split one note into several.

    Args:
        raw (str): The label exactly as the source gave it.

    Returns:
        str: The key, truncated to ``NOTE_KEY_MAX_LENGTH``. Empty when ``raw`` has
            no letters or digits; callers must treat an empty key as unusable.
    """
    return _NON_ALPHANUMERIC.sub("", _fold(raw))[:NOTE_KEY_MAX_LENGTH]


def normalize_accord_code(raw: str) -> str:
    """Return the ``accord_types.code`` for an accord label.

    Accords read as phrases (``fresh spicy``, ``white floral``), so word breaks are
    kept: lowercases, strips accents, and collapses runs of whitespace.

    Args:
        raw (str): The label exactly as the source gave it.

    Returns:
        str: The code. Empty when ``raw`` is blank.
    """
    return _WHITESPACE.sub(" ", _fold(raw)).strip()
