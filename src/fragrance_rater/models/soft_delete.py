"""One definition of "live" for soft-deletable rows (architecture review D-21).

``Fragrance``, ``Evaluation`` and ``Reviewer`` are soft-deleted: a DELETE route
sets ``deleted_at`` instead of removing the row. Every read used to spell the
filter out by hand (``Model.deleted_at.is_(None)`` in a query,
``obj.deleted_at is not None`` on a loaded row), dozens of times, which is how
three read paths came to omit it. These two helpers are the shared spelling;
they change no behaviour.

The relationship-level alternative (``with_loader_criteria`` on every query)
was not taken: it would also filter rows that deliberately read deleted
history (the reveal payload's catalog lookup, an outcome link to an evaluation
deleted afterwards), and an implicit filter is exactly what made the omissions
invisible.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, TypeGuard

if TYPE_CHECKING:
    from datetime import datetime

    from sqlalchemy import ColumnElement
    from sqlalchemy.orm import Mapped


class SoftDeletable(Protocol):
    """A mapped class with a nullable ``deleted_at`` soft-delete column."""

    deleted_at: Mapped[datetime | None]


def live(model: type[SoftDeletable]) -> ColumnElement[bool]:
    """Return the SQL predicate "this row is not soft-deleted".

    Args:
        model (type[SoftDeletable]): ``Fragrance``, ``Evaluation`` or
            ``Reviewer`` (any mapped class with ``deleted_at``).

    Returns:
        ColumnElement[bool]: ``model.deleted_at IS NULL``.
    """
    return model.deleted_at.is_(None)


def is_live[Row: SoftDeletable](row: Row | None) -> TypeGuard[Row]:
    """Whether a loaded row exists and is not soft-deleted.

    A ``TypeGuard`` (not ``TypeIs``): ``True`` narrows away ``None``, but
    ``False`` says nothing about the type, since a soft-deleted row is still a
    row.

    Args:
        row (Row | None): A loaded row, or ``None`` when a lookup found
            nothing.

    Returns:
        TypeGuard[Row]: ``False`` for ``None`` and for a soft-deleted row.
    """
    return row is not None and row.deleted_at is None
