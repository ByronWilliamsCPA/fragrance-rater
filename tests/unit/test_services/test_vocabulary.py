"""Tests for the shared note and accord resolver (R6; X-01, X-03).

The fixtures are the ones the D1 plan names: ``oak moss``/``oakmoss``,
``vanille``/``vanilla``, an ambiguous label, and an unknown one.
"""

from __future__ import annotations

import pytest
from sqlalchemy import func, select

from fragrance_rater.models.fragrance import AccordType, Note, NoteAlias
from fragrance_rater.services.vocabulary import (
    NOTE_MAPPING_VERSION,
    VocabularyResolver,
)

pytestmark = pytest.mark.asyncio


async def _count(session, model) -> int:
    return (await session.execute(select(func.count()).select_from(model))).scalar_one()


async def test_spelling_variants_resolve_to_one_note(async_session) -> None:
    resolver = VocabularyResolver(async_session)

    first = await resolver.resolve_note("Oak Moss")
    second = await resolver.resolve_note("oakmoss")
    third = await VocabularyResolver(async_session).resolve_note("OAK-MOSS")

    assert first.status == "created"
    assert first.note is not None
    assert second.note is first.note
    assert third.note is first.note
    assert third.status == "exact"
    assert await _count(async_session, Note) == 1
    # The first spelling is the note's name; later spellings are kept verbatim.
    assert first.note.name == "Oak Moss"
    assert first.note.name_key == "oakmoss"
    recorded = (
        (await async_session.execute(select(NoteAlias.raw_label, NoteAlias.origin)))
        .tuples()
        .all()
    )
    assert sorted(recorded) == [("OAK-MOSS", "observed"), ("oakmoss", "observed")]


async def test_a_curated_alias_joins_a_synonym(async_session) -> None:
    vanilla = Note(id="n-vanilla", name="Vanilla")
    async_session.add(vanilla)
    async_session.add(
        NoteAlias(
            raw_label="vanille",
            alias_key="vanille",
            canonical_note_id="n-vanilla",
            mapping_version=NOTE_MAPPING_VERSION,
            origin="curated",
        )
    )
    await async_session.flush()

    result = await VocabularyResolver(async_session).resolve_note("Vanille")

    assert result.status == "alias"
    assert result.note is vanilla
    assert await _count(async_session, Note) == 1


async def test_an_alias_from_another_mapping_version_is_not_applied(
    async_session,
) -> None:
    async_session.add(Note(id="n-vanilla", name="Vanilla"))
    async_session.add(
        NoteAlias(
            raw_label="vanille",
            alias_key="vanille",
            canonical_note_id="n-vanilla",
            mapping_version="nm-old",
            origin="curated",
        )
    )
    await async_session.flush()

    result = await VocabularyResolver(async_session).resolve_note("vanille")

    assert result.status == "created"
    assert result.note is not None
    assert result.note.id != "n-vanilla"


async def test_a_label_the_alias_and_the_key_disagree_on_is_ambiguous(
    async_session,
) -> None:
    async_session.add_all(
        [Note(id="n-a", name="Musk"), Note(id="n-b", name="White Musk")]
    )
    async_session.add(
        NoteAlias(
            raw_label="Musk",
            alias_key="musk",
            canonical_note_id="n-b",
            mapping_version=NOTE_MAPPING_VERSION,
            origin="curated",
        )
    )
    await async_session.flush()

    result = await VocabularyResolver(async_session).resolve_note("musk")

    assert result.status == "ambiguous"
    assert result.note is None
    assert await _count(async_session, Note) == 2  # nothing was created or merged


async def test_an_unknown_label_creates_a_note_with_the_given_category(
    async_session,
) -> None:
    result = await VocabularyResolver(async_session).resolve_note(
        "Hedione", category="Floral"
    )

    assert result.status == "created"
    assert result.note is not None
    assert (result.note.name, result.note.category) == ("Hedione", "Floral")


async def test_a_category_does_not_overwrite_an_existing_note(async_session) -> None:
    resolver = VocabularyResolver(async_session)
    first = await resolver.resolve_note("Rose", category="Floral")
    again = await VocabularyResolver(async_session).resolve_note(
        "rose", category="Wood"
    )

    assert again.note is first.note
    assert again.note is not None
    assert again.note.category == "Floral"


async def test_a_label_without_letters_or_digits_is_unusable(async_session) -> None:
    result = await VocabularyResolver(async_session).resolve_note(" - ")

    assert (result.note, result.status) == (None, "unusable")
    assert await _count(async_session, Note) == 0


async def test_accord_labels_share_one_code(async_session) -> None:
    resolver = VocabularyResolver(async_session)

    first = await resolver.resolve_accord("Fresh Spicy")
    second = await VocabularyResolver(async_session).resolve_accord("fresh  spicy")

    assert first is not None
    assert second is first
    assert (first.code, first.label) == ("fresh spicy", "Fresh Spicy")
    assert await _count(async_session, AccordType) == 1
    assert await resolver.resolve_accord("   ") is None
