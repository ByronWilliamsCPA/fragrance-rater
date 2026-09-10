"""Shared timestamp helpers.

Centralizes the naive-UTC convention used by every timezone-naive ``DateTime``
column in this project (``created_at``, ``updated_at``, ``deleted_at``; see
``models/*.py``), so the fix for Critical finding 3 (PR #66 review) lives in
one place instead of being duplicated at each soft-delete call site.
"""

from __future__ import annotations

from datetime import datetime, timezone


def now_naive_utc() -> datetime:
    """Return the current UTC time as a timezone-naive ``datetime``.

    # #CRITICAL: data-integrity: every soft-delete column in this project
    # (`deleted_at` on Fragrance, Evaluation, Reviewer) is a plain, timezone-
    # naive `DateTime`, not `DateTime(timezone=True)` (confirmed against
    # created_at/updated_at's matching `func.now()` default). Assigning a
    # timezone-aware value directly (`datetime.now(UTC)`) raises `TypeError`
    # under real Postgres/asyncpg: SQLAlchemy's `AsyncpgDateTime` bind path has
    # no processor that strips tzinfo. This is invisible under the test
    # suite's SQLite backend, which accepts aware datetimes silently.
    # #VERIFY: any new naive-column datetime write uses this helper, not
    # `datetime.now(UTC)` or `datetime.now(timezone.utc)` directly.

    Uses `datetime.timezone.utc` rather than the `datetime.UTC` constant
    (Python 3.11+) so this module stays importable on Python 3.10, which
    `pyproject.toml`'s `requires-python = ">=3.10,<3.15"` claims to support.

    Returns:
        datetime: Current UTC time with `tzinfo` stripped, safe to assign to
            a timezone-naive `DateTime` column.
    """
    return datetime.now(timezone.utc).replace(tzinfo=None)
