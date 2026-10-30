"""Curated note-alias decisions: a reviewable file, a validator, and a loader (R6 PR 2).

``NoteAlias`` rows with ``origin='curated'`` are decisions a person made: ``vanille``
means ``vanilla``. They change which note a label resolves to, so they are kept as a
versioned file under review, not typed into a database. This module is the path from
that file to the table:

- ``parse_alias_file`` reads and validates the file. It reports every violation, not
  just the first, and never touches the database.
- ``load_aliases`` compares the file with the database and reports what loading would
  do. It writes only on request, only when nothing blocks, and in one transaction.
- ``find_ambiguities`` lists the labels the resolver already refuses to guess at.

A decision never merges notes by itself. If a label already names a different note
(``collides_with_note``) the load is refused: a person has to settle that conflict
first, because resolving it silently would hide it.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal, cast

from ruamel.yaml import YAML
from ruamel.yaml.error import YAMLError
from sqlalchemy import select

from fragrance_rater.models.fragrance import Note, NoteAlias
from fragrance_rater.services.vocabulary import NOTE_MAPPING_VERSION
from fragrance_rater.utils.labels import NOTE_KEY_MAX_LENGTH, normalize_note_key
from fragrance_rater.utils.logging import get_logger, log_audit_event

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = get_logger(__name__)

TOP_LEVEL_KEYS = frozenset({"mapping_version", "aliases"})
DECISION_KEYS = frozenset({"raw_label", "canonical", "evidence", "decided_by"})
MAPPING_VERSION_PATTERN = re.compile(r"^[a-z0-9][a-z0-9.-]{0,49}$")

Outcome = Literal[
    "create", "unchanged", "conflict", "missing_canonical", "collides_with_note"
]
BLOCKING: frozenset[str] = frozenset(
    {"conflict", "missing_canonical", "collides_with_note"}
)


class AliasFileError(ValueError):
    """The alias file broke one or more rules.

    Args:
        problems (list[str]): Every violation found, each naming its location.

    Attributes:
        problems (list[str]): Every violation found, each naming its location.
    """

    problems: list[str]

    def __init__(self, problems: list[str]) -> None:
        super().__init__("; ".join(problems))
        self.problems = problems


@dataclass(frozen=True)
class AliasDecision:
    """One reviewed decision: ``raw_label`` means the note named ``canonical``.

    Attributes:
        raw_label (str): The spelling being resolved, verbatim.
        canonical (str): The name of the note it resolves to.
        evidence (str): Why a person decided this; what they checked.
        decided_by (str): Who decided.
    """

    raw_label: str
    canonical: str
    evidence: str
    decided_by: str

    @property
    def alias_key(self) -> str:
        """Return the normalized key the resolver looks the label up by."""
        return normalize_note_key(self.raw_label)

    @property
    def canonical_key(self) -> str:
        """Return the normalized key of the canonical note's name."""
        return normalize_note_key(self.canonical)


@dataclass(frozen=True)
class AliasFile:
    """A validated alias file.

    Attributes:
        mapping_version (str): The ``NoteAlias.mapping_version`` these decisions
            belong to.
        decisions (tuple[AliasDecision, ...]): The decisions, in file order.
        content_hash (str): SHA-256 over the version and decisions, independent of
            formatting and comments, so two files with the same meaning hash alike.
    """

    mapping_version: str
    decisions: tuple[AliasDecision, ...]
    content_hash: str


@dataclass(frozen=True)
class AliasLoadItem:
    """What loading would do (or did) for one decision.

    Attributes:
        decision (AliasDecision): The decision.
        outcome (Outcome): ``create``, ``unchanged``, or a blocking outcome.
        detail (str): A sentence a reviewer can act on.
    """

    decision: AliasDecision
    outcome: Outcome
    detail: str


@dataclass(frozen=True)
class AliasLoadReport:
    """The result of comparing an alias file with the database.

    Attributes:
        mapping_version (str): The version the file declares.
        content_hash (str): The file's content hash.
        active (bool): Whether the version is the one the resolver applies now.
        items (tuple[AliasLoadItem, ...]): One entry per decision.
        applied (bool): Whether rows were written.
    """

    mapping_version: str
    content_hash: str
    active: bool
    items: tuple[AliasLoadItem, ...]
    applied: bool

    @property
    def blocked(self) -> bool:
        """Return whether any decision cannot be loaded."""
        return any(item.outcome in BLOCKING for item in self.items)

    def count(self, outcome: Outcome) -> int:
        """Return how many decisions have ``outcome``.

        Args:
            outcome (Outcome): The outcome to count.

        Returns:
            int: The number of decisions with that outcome.
        """
        return sum(1 for item in self.items if item.outcome == outcome)


@dataclass(frozen=True)
class AmbiguousKey:
    """A label the resolver will not guess at.

    Attributes:
        alias_key (str): The normalized label.
        raw_label (str): The curated alias's spelling.
        alias_target (str): Name of the note the curated alias points to.
        key_note (str): Name of the different note whose own key is the same.
    """

    alias_key: str
    raw_label: str
    alias_target: str
    key_note: str


def _text(value: object) -> str:
    return value.strip() if isinstance(value, str) else ""


def _check_text(
    raw: object, where: str, field: str, problems: list[str], *, limit: int | None
) -> str:
    """Return a required string field, recording a problem when it is unusable."""
    if not isinstance(raw, str) or not raw.strip():
        problems.append(f"{where}: {field} is required and must be text")
        return ""
    if raw != raw.strip():
        problems.append(f"{where}: {field} has leading or trailing whitespace")
    if limit is not None and len(raw) > limit:
        problems.append(f"{where}: {field} is longer than {limit} characters")
    return raw.strip()


def _validate_decision(
    entry: object, index: int, problems: list[str]
) -> AliasDecision | None:
    where = f"aliases[{index}]"
    if not isinstance(entry, dict):
        problems.append(f"{where}: must be a mapping")
        return None
    fields = cast("dict[object, object]", entry)
    unknown = sorted(str(key) for key in fields if key not in DECISION_KEYS)
    if unknown:
        problems.append(f"{where}: unrecognized key(s) {', '.join(unknown)}")
    decision = AliasDecision(
        raw_label=_check_text(
            fields.get("raw_label"),
            where,
            "raw_label",
            problems,
            limit=NOTE_KEY_MAX_LENGTH,
        ),
        canonical=_check_text(
            fields.get("canonical"),
            where,
            "canonical",
            problems,
            limit=NOTE_KEY_MAX_LENGTH,
        ),
        evidence=_check_text(
            fields.get("evidence"), where, "evidence", problems, limit=None
        ),
        decided_by=_check_text(
            fields.get("decided_by"), where, "decided_by", problems, limit=None
        ),
    )
    if not (decision.raw_label and decision.canonical):
        return None
    if not decision.alias_key:
        problems.append(f"{where}: raw_label has no letters or digits")
    if not decision.canonical_key:
        problems.append(f"{where}: canonical has no letters or digits")
    if decision.alias_key and decision.alias_key == decision.canonical_key:
        label, target = decision.raw_label, decision.canonical
        problems.append(
            " ".join(
                [
                    f"{where}: {label!r} already has the same key as {target!r},",
                    "so the resolver treats them as one note without a decision",
                ]
            )
        )
    return decision


def _validate_set(decisions: list[AliasDecision], problems: list[str]) -> None:
    """Check rules that span decisions: one decision per key, and no chains."""
    first: dict[str, AliasDecision] = {}
    for decision in decisions:
        key = decision.alias_key
        if not key:
            continue
        if key in first:
            other = first[key].raw_label
            problems.append(
                " ".join(
                    [
                        f"{decision.raw_label!r} and {other!r} share the key {key!r};",
                        "a key has one decision per version",
                    ]
                )
            )
        else:
            first[key] = decision
    for decision in decisions:
        target = first.get(decision.canonical_key)
        # An alias whose own key is its target's is reported once, above; it is not
        # a chain.
        if target is not None and target is not decision:
            problems.append(
                " ".join(
                    [
                        f"{decision.raw_label!r}: canonical {decision.canonical!r}",
                        f"is itself aliased by {target.raw_label!r};",
                        "point to the final note, not a chain",
                    ]
                )
            )


def _content_hash(version: str, decisions: list[AliasDecision]) -> str:
    payload = {
        "mapping_version": version,
        "aliases": sorted(
            (d.raw_label, d.canonical, d.evidence, d.decided_by) for d in decisions
        ),
    }
    canonical = json.dumps(payload, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def parse_alias_file(text: str) -> AliasFile:
    """Parse and validate an alias file.

    Args:
        text (str): The YAML document.

    Returns:
        AliasFile: The validated decisions and their content hash.

    Raises:
        AliasFileError: With every violation found, if the file is not valid.
    """
    try:
        document = cast(
            "object",
            YAML(typ="safe").load(text),  # pyright: ignore[reportUnknownMemberType]
        )
    except YAMLError as exc:
        raise AliasFileError([f"not valid YAML: {exc}"]) from exc
    if not isinstance(document, dict):
        raise AliasFileError(
            ["the document must be a mapping with mapping_version and aliases"]
        )
    top = cast("dict[object, object]", document)

    problems: list[str] = []
    unknown = sorted(str(key) for key in top if key not in TOP_LEVEL_KEYS)
    if unknown:
        problems.append(f"unrecognized top-level key(s) {', '.join(unknown)}")
    version = _text(top.get("mapping_version"))
    if not MAPPING_VERSION_PATTERN.match(version):
        problems.append(
            "mapping_version is required (lowercase letters, digits, '.', '-')"
        )
    entries = top.get("aliases")
    if not isinstance(entries, list):
        problems.append("aliases is required and must be a list (it may be empty)")
        raise AliasFileError(problems)

    decisions: list[AliasDecision] = []
    for index, entry in enumerate(cast("list[object]", entries)):
        decision = _validate_decision(entry, index, problems)
        if decision is not None:
            decisions.append(decision)
    _validate_set(decisions, problems)
    if problems:
        raise AliasFileError(problems)
    return AliasFile(
        mapping_version=version,
        decisions=tuple(decisions),
        content_hash=_content_hash(version, decisions),
    )


async def _classify(
    session: AsyncSession, decision: AliasDecision, version: str
) -> AliasLoadItem:
    canonical = (
        await session.execute(
            select(Note).where(Note.name_key == decision.canonical_key)
        )
    ).scalar_one_or_none()
    if canonical is None:
        return AliasLoadItem(
            decision,
            "missing_canonical",
            f"no catalog note is named {decision.canonical!r}; add or import it first",
        )
    same_spelling = (
        await session.execute(
            select(NoteAlias).where(
                NoteAlias.raw_label == decision.raw_label,
                NoteAlias.mapping_version == version,
            )
        )
    ).scalar_one_or_none()
    if same_spelling is not None:
        if (
            same_spelling.origin == "curated"
            and same_spelling.canonical_note_id == canonical.id
        ):
            return AliasLoadItem(decision, "unchanged", "already loaded")
        origin = same_spelling.origin
        return AliasLoadItem(
            decision,
            "conflict",
            " ".join(
                [
                    f"{decision.raw_label!r} already has a {origin} row for {version}",
                    "pointing elsewhere; a changed decision needs a new version",
                ]
            ),
        )
    other_curated = (
        await session.execute(
            select(NoteAlias).where(
                NoteAlias.alias_key == decision.alias_key,
                NoteAlias.mapping_version == version,
                NoteAlias.origin == "curated",
            )
        )
    ).scalar_one_or_none()
    if other_curated is not None:
        existing = other_curated.raw_label
        return AliasLoadItem(
            decision,
            "conflict",
            " ".join(
                [
                    f"key {decision.alias_key!r} already has a curated decision",
                    f"for {version} ({existing!r}); a key has one decision per version",
                ]
            ),
        )
    named = (
        await session.execute(select(Note).where(Note.name_key == decision.alias_key))
    ).scalar_one_or_none()
    if named is not None and named.id != canonical.id:
        return AliasLoadItem(
            decision,
            "collides_with_note",
            " ".join(
                [
                    f"{decision.raw_label!r} is already the name of a different note",
                    f"({named.name!r}); loading would make the label ambiguous,",
                    "so settle which note it is first",
                ]
            ),
        )
    return AliasLoadItem(
        decision, "create", f"{decision.raw_label!r} -> {canonical.name!r}"
    )


async def load_aliases(
    session: AsyncSession,
    alias_file: AliasFile,
    *,
    execute: bool = False,
    actor: str | None = None,
) -> AliasLoadReport:
    """Compare an alias file with the database, and load it when asked.

    The load is all-or-nothing: if any decision is blocked, nothing is written even
    with ``execute``. Loading is idempotent; a second run reports ``unchanged``.

    Args:
        session (AsyncSession): The session to read and write through.
        alias_file (AliasFile): A file validated by ``parse_alias_file``.
        execute (bool): Write the ``create`` rows. Default is a dry run.
        actor (str | None): Who is loading. Required with ``execute``.

    Returns:
        AliasLoadReport: One item per decision, and whether rows were written.
            The rows are flushed, not committed: the caller commits, then calls
            ``audit_alias_load``.

    Raises:
        ValueError: If ``execute`` is set without an ``actor``.
    """
    # #CRITICAL: data-integrity: a curated alias changes which note every future
    # import of that label lands on, so a load must be reviewable first and
    # attributable after.
    # #VERIFY: the default is a dry run; --execute needs an actor; one blocked
    # decision blocks the whole load; the caller emits the audit event with
    # ``audit_alias_load`` only after its transaction commits.
    if execute and not actor:
        msg = "an actor is required to execute a load"
        raise ValueError(msg)
    version = alias_file.mapping_version
    items = tuple([await _classify(session, d, version) for d in alias_file.decisions])
    report = AliasLoadReport(
        mapping_version=version,
        content_hash=alias_file.content_hash,
        active=version == NOTE_MAPPING_VERSION,
        items=items,
        applied=False,
    )
    to_create = [item for item in items if item.outcome == "create"]
    if not execute or report.blocked or not to_create:
        return report

    for item in to_create:
        canonical = (
            await session.execute(
                select(Note).where(Note.name_key == item.decision.canonical_key)
            )
        ).scalar_one()
        session.add(
            NoteAlias(
                raw_label=item.decision.raw_label,
                alias_key=item.decision.alias_key,
                canonical_note_id=canonical.id,
                mapping_version=version,
                origin="curated",
            )
        )
    await session.flush()
    return AliasLoadReport(
        mapping_version=version,
        content_hash=alias_file.content_hash,
        active=report.active,
        items=items,
        applied=True,
    )


def audit_alias_load(report: AliasLoadReport, actor: str) -> None:
    """Record a committed alias load in the audit log.

    Call this only after the transaction that ``load_aliases`` wrote through has
    committed, so a rolled-back load never leaves an audit event behind.

    Args:
        report (AliasLoadReport): The report ``load_aliases`` returned.
        actor (str): Who loaded the file.
    """
    if not report.applied:
        return
    log_audit_event(
        logger,
        action="note_alias_load",
        actor=actor,
        target_type="note_alias_set",
        target_id=f"{report.mapping_version}:{report.content_hash[:12]}",
        created=report.count("create"),
        content_hash=report.content_hash,
    )


async def find_ambiguities(
    session: AsyncSession, mapping_version: str = NOTE_MAPPING_VERSION
) -> list[AmbiguousKey]:
    """List the labels the resolver refuses to guess at.

    A label is ambiguous when a curated alias and the note whose own key matches it
    name different notes.

    Args:
        session (AsyncSession): The session to read through.
        mapping_version (str): The decision set to check.

    Returns:
        list[AmbiguousKey]: One entry per ambiguous key, ordered by key.
    """
    aliases = (
        (
            await session.execute(
                select(NoteAlias).where(
                    NoteAlias.mapping_version == mapping_version,
                    NoteAlias.origin == "curated",
                )
            )
        )
        .scalars()
        .all()
    )
    found: list[AmbiguousKey] = []
    for alias in aliases:
        key_note = (
            await session.execute(select(Note).where(Note.name_key == alias.alias_key))
        ).scalar_one_or_none()
        if key_note is None or key_note.id == alias.canonical_note_id:
            continue
        target = await session.get(Note, alias.canonical_note_id)
        found.append(
            AmbiguousKey(
                alias_key=alias.alias_key,
                raw_label=alias.raw_label,
                alias_target=target.name
                if target is not None
                else alias.canonical_note_id,
                key_note=key_note.name,
            )
        )
    return sorted(found, key=lambda item: item.alias_key)
