"""One resolver for note and accord labels, used by every writer (R6; X-01, X-03).

Before this module the Kaggle importer and the manual catalog service each looked a
note up by exact name, so ``Oak Moss`` and ``oakmoss`` became two notes and every
note-keyed feature fragmented. Every path that turns a source's label into a ``Note``
or an ``AccordType`` now goes through ``VocabularyResolver``.

Resolution order for a note label:

1. A ``curated`` ``NoteAlias`` for the label's normalized key under the active mapping
   version (a person decided ``vanille`` means ``vanilla``).
2. The ``Note`` whose ``name_key`` equals the label's normalized key (``Oak Moss``,
   ``oakmoss``, and ``Oak-Moss`` are one note).
3. Otherwise a new ``Note`` named exactly as the source wrote it.

If steps 1 and 2 both answer and disagree, the label is ``ambiguous``: the resolver
returns no note and a person must settle it. It never picks one silently.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from fragrance_rater.models.fragrance import AccordType, Note, NoteAlias
from fragrance_rater.utils.labels import (
    NOTE_KEY_MAX_LENGTH,
    normalize_accord_code,
    normalize_note_key,
)
from fragrance_rater.utils.logging import get_logger

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = get_logger(__name__)

NOTE_MAPPING_VERSION = "nm-v1"
"""The active ``NoteAlias.mapping_version``. A changed decision set is a new version."""

ACCORD_CODE_MAX_LENGTH = 50

NoteStatus = Literal["exact", "alias", "created", "ambiguous", "unusable"]


@dataclass(frozen=True)
class NoteResolution:
    """The outcome of resolving one raw note label.

    Attributes:
        note (Note | None): The canonical note, or ``None`` when ``status`` is
            ``ambiguous`` or ``unusable``.
        status (NoteStatus): ``exact`` (found by normalized key), ``alias`` (a curated
            decision applied), ``created`` (a label never seen before), ``ambiguous``
            (a curated alias and the key lookup name different notes), or
            ``unusable`` (no letters or digits).
    """

    note: Note | None
    status: NoteStatus


class VocabularyResolver:
    """Resolve raw labels to canonical notes and accord types.

    Instances cache within one unit of work (an import run, a request); build a new
    one per session.

    Args:
        session (AsyncSession): The session the resolver reads and writes through.
        mapping_version (str): The ``NoteAlias`` decision set to apply.
    """

    def __init__(
        self, session: AsyncSession, mapping_version: str = NOTE_MAPPING_VERSION
    ) -> None:
        self.session = session
        self.mapping_version = mapping_version
        self._notes: dict[str, Note] = {}
        self._recorded: set[str] = set()
        self._accords: dict[str, AccordType] = {}

    async def resolve_note(
        self, raw: str, category: str | None = None
    ) -> NoteResolution:
        """Resolve a note label, creating the note when it is new.

        Args:
            raw (str): The label exactly as the source gave it.
            category (str | None): Olfactory family for a note this call creates.
                Never a pyramid position. Ignored for a note that already exists.

        Returns:
            NoteResolution: The note and how it was found.
        """
        label = raw.strip()[:NOTE_KEY_MAX_LENGTH]
        key = normalize_note_key(label)
        if not key:
            return NoteResolution(None, "unusable")
        cached = self._notes.get(key)
        if cached is not None:
            # Another spelling of a note already resolved in this run: keep it too.
            await self._record_spelling(label, key, cached)
            return NoteResolution(cached, "exact")

        existing = await self._resolve_existing(label, key)
        if existing is not None:
            if existing.note is not None:
                self._notes[key] = existing.note
            return existing

        note, created = await self._create_note(label, key, category)
        self._notes[key] = note
        return NoteResolution(note, "created" if created else "exact")

    async def _resolve_existing(self, label: str, key: str) -> NoteResolution | None:
        """Apply steps 1 and 2; ``None`` when neither knows the label."""
        alias = (
            await self.session.execute(
                select(NoteAlias).where(
                    NoteAlias.alias_key == key,
                    NoteAlias.mapping_version == self.mapping_version,
                    NoteAlias.origin == "curated",
                )
            )
        ).scalar_one_or_none()
        by_key = (
            await self.session.execute(select(Note).where(Note.name_key == key))
        ).scalar_one_or_none()

        if alias is None:
            if by_key is None:
                return None
            await self._record_spelling(label, key, by_key)
            return NoteResolution(by_key, "exact")
        if by_key is not None and alias.canonical_note_id != by_key.id:
            logger.warning(
                "note_label_ambiguous",
                label=label,
                alias_target=alias.canonical_note_id,
                key_match=by_key.id,
            )
            return NoteResolution(None, "ambiguous")
        target = by_key or await self.session.get(Note, alias.canonical_note_id)
        return NoteResolution(target, "alias") if target is not None else None

    async def resolve_accord(self, raw: str) -> AccordType | None:
        """Resolve an accord label to its ``AccordType``, registering a new code.

        Args:
            raw (str): The label exactly as the source gave it.

        Returns:
            AccordType | None: The lookup row, or ``None`` for a blank label.

        Raises:
            IntegrityError: If the code cannot be inserted and no concurrent
                writer's row exists to use instead.
        """
        code = normalize_accord_code(raw)[:ACCORD_CODE_MAX_LENGTH]
        if not code:
            return None
        cached = self._accords.get(code)
        if cached is not None:
            return cached
        found = await self.session.get(AccordType, code)
        if found is None:
            found = AccordType(code=code, label=raw.strip()[:ACCORD_CODE_MAX_LENGTH])
            try:
                async with self.session.begin_nested():
                    self.session.add(found)
                    await self.session.flush()
            except IntegrityError:
                # A concurrent writer registered the same code first.
                found = await self.session.get(AccordType, code)
                if found is None:  # pragma: no cover - the conflicting row vanished
                    raise
        self._accords[code] = found
        return found

    async def _create_note(
        self, label: str, key: str, category: str | None
    ) -> tuple[Note, bool]:
        note = Note(id=str(uuid4()), name=label, name_key=key, category=category)
        try:
            async with self.session.begin_nested():
                self.session.add(note)
                await self.session.flush()
        except IntegrityError:
            # A concurrent writer created the note, or an older note already has
            # this exact name under a different key; use whichever now exists.
            existing = (
                await self.session.execute(select(Note).where(Note.name_key == key))
            ).scalar_one_or_none()
            if existing is None:
                raise
            return existing, False
        return note, True

    async def _record_spelling(self, label: str, key: str, note: Note) -> None:
        """Keep a raw spelling that normalizes to ``note`` but is not its name."""
        if label == note.name or label in self._recorded:
            return
        self._recorded.add(label)
        known = (
            await self.session.execute(
                select(NoteAlias.id).where(
                    NoteAlias.raw_label == label,
                    NoteAlias.mapping_version == self.mapping_version,
                )
            )
        ).scalar_one_or_none()
        if known is not None:
            return
        try:
            async with self.session.begin_nested():
                self.session.add(
                    NoteAlias(
                        raw_label=label,
                        alias_key=key,
                        canonical_note_id=note.id,
                        mapping_version=self.mapping_version,
                        origin="observed",
                    )
                )
                await self.session.flush()
        except IntegrityError:
            logger.debug("note_alias_already_recorded", label=label)
