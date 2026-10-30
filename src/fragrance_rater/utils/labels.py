"""Normalization of raw note and accord labels (R6; X-01, X-03).

Sources spell the same thing differently: ``Oak Moss``, ``oak moss``, ``oakmoss``,
``Ylang-Ylang``, ``Néroli``. Identity is decided on a normalized key; the raw
spelling is always kept beside it (on ``Note.name`` and ``NoteAlias.raw_label``) so
a decision can be audited and reversed.

Normalization removes only presentation differences: case, Latin accents, and word
separators. It never merges different words. ``vanille`` and ``vanilla`` are
different keys, so joining them is an explicit, versioned ``NoteAlias`` decision
and not a side effect of string handling.
"""

from __future__ import annotations

import re
import unicodedata

NOTE_KEY_MAX_LENGTH = 100
"""Width of ``notes.name_key`` and ``note_aliases.alias_key``; equal to ``notes.name``."""

_NON_ALPHANUMERIC = re.compile(r"[\W_]+")
_WHITESPACE = re.compile(r"\s+")


def _fold(raw: str) -> str:
    """Return ``raw`` compatibility-normalized, Latin accents stripped, casefolded.

    Only marks that follow a Latin letter are removed (``Néroli`` and ``neroli``
    agree). Marks in other scripts carry meaning and stay: stripping the voiced
    mark from ``が`` would make it ``か``, a different word.
    """
    decomposed = unicodedata.normalize("NFKD", raw)
    kept: list[str] = []
    after_latin = False
    for ch in decomposed:
        if unicodedata.combining(ch) and after_latin:
            continue
        kept.append(ch)
        after_latin = unicodedata.name(ch, "").startswith("LATIN")
    return unicodedata.normalize("NFC", "".join(kept)).casefold()


def normalize_note_key(raw: str) -> str:
    """Return the identity key for a note label.

    Lowercases, strips Latin accents, and drops every character that is not a letter
    or digit in any script, so word separators (spaces, hyphens, apostrophes,
    ampersands) do not split one note into several.

    Args:
        raw (str): The label exactly as the source gave it.

    Returns:
        str: The key, truncated to ``NOTE_KEY_MAX_LENGTH``. Empty when ``raw`` has
            no letters or digits in any script; callers must treat an empty key as unusable.
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
