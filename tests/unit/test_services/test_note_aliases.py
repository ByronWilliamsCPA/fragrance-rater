"""Tests for the curated note-alias file, validator, and loader (R6 PR 2)."""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import select

from fragrance_rater.models.fragrance import Note, NoteAlias
from fragrance_rater.services.note_aliases import (
    AliasFileError,
    audit_alias_load,
    find_ambiguities,
    load_aliases,
    parse_alias_file,
)
from fragrance_rater.services.vocabulary import NOTE_MAPPING_VERSION, VocabularyResolver

pytestmark = pytest.mark.asyncio

COMMITTED = Path(__file__).parents[3] / "data/aliases/note-aliases-nm-v1.yaml"


def _file(*decisions: str, version: str = "nm-v1") -> str:
    body = "\n".join(decisions) if decisions else ""
    return f"mapping_version: {version}\naliases:{' []' if not decisions else chr(10) + body}\n"


def _decision(
    raw: str, canonical: str, evidence: str = "checked", by: str = "owner"
) -> str:
    return (
        f"  - raw_label: {raw}\n    canonical: {canonical}\n"
        f'    evidence: "{evidence}"\n    decided_by: {by}'
    )


class TestParse:
    def test_the_committed_file_is_valid_and_empty(self) -> None:
        parsed = parse_alias_file(COMMITTED.read_text(encoding="utf-8"))

        assert parsed.mapping_version == NOTE_MAPPING_VERSION
        assert parsed.decisions == ()

    def test_a_valid_decision_round_trips(self) -> None:
        parsed = parse_alias_file(_file(_decision("vanille", "Vanilla")))

        (decision,) = parsed.decisions
        assert (decision.raw_label, decision.canonical) == ("vanille", "Vanilla")
        assert (decision.alias_key, decision.canonical_key) == ("vanille", "vanilla")

    def test_the_hash_ignores_comments_and_order_but_not_meaning(self) -> None:
        a = _decision("vanille", "Vanilla")
        b = _decision("tonka", "Tonka Bean")
        first = parse_alias_file(_file(a, b))
        reordered = parse_alias_file("# a comment\n" + _file(b, a))
        changed = parse_alias_file(
            _file(a, _decision("tonka", "Tonka Bean", by="someone else"))
        )

        assert first.content_hash == reordered.content_hash
        assert first.content_hash != changed.content_hash

    @pytest.mark.parametrize(
        ("text", "fragment"),
        [
            ("- just\n- a list\n", "must be a mapping"),
            ("mapping_version: nm-v1\n", "aliases is required"),
            ("aliases: []\n", "mapping_version is required"),
            ("mapping_version: NM V1\naliases: []\n", "mapping_version is required"),
            (
                "mapping_version: nm-v1\naliases: []\nextra: 1\n",
                "unrecognized top-level",
            ),
            (
                "mapping_version: nm-v1\nmapping_version: nm-v2\naliases: []\n",
                "not valid YAML",
            ),
        ],
    )
    def test_structural_problems(self, text: str, fragment: str) -> None:
        with pytest.raises(AliasFileError, match=fragment):
            parse_alias_file(text)

    @pytest.mark.parametrize(
        ("raw", "canonical", "fragment"),
        [
            ("true", "Vanilla", "raw_label is required and must be text"),
            ("1", "Vanilla", "raw_label is required and must be text"),
            ('"---"', "Vanilla", "raw_label has no letters or digits"),
            ("vanille", '"---"', "canonical has no letters or digits"),
        ],
    )
    def test_unusable_labels_are_reported(
        self, raw: str, canonical: str, fragment: str
    ) -> None:
        with pytest.raises(AliasFileError, match=fragment):
            parse_alias_file(_file(_decision(raw, canonical)))

    def test_every_violation_is_reported_not_just_the_first(self) -> None:
        text = _file(
            "  - raw_label: vanille\n    canonical: Vanilla\n    colour: red",
            "  - raw_label: Oak Moss\n    canonical: oakmoss\n    evidence: x\n    decided_by: y",
        )

        with pytest.raises(AliasFileError) as caught:
            parse_alias_file(text)

        joined = " | ".join(caught.value.problems)
        assert "unrecognized key(s) colour" in joined
        assert "evidence is required" in joined
        assert "decided_by is required" in joined
        assert "already has the same key" in joined
        assert "chain" not in joined

    def test_two_decisions_for_one_key_are_refused(self) -> None:
        text = _file(
            _decision("Vanille", "Vanilla"), _decision("vanille", "Vanilla Bean")
        )

        with pytest.raises(AliasFileError, match="share the key"):
            parse_alias_file(text)

    def test_a_chain_is_refused(self) -> None:
        text = _file(
            _decision("vanille", "Vanilla"), _decision("vanilla", "Vanilla Bean")
        )

        with pytest.raises(AliasFileError, match="not a chain"):
            parse_alias_file(text)

    def test_whitespace_and_length_are_checked(self) -> None:
        padded = _file(
            '  - raw_label: " vanille"\n    canonical: Vanilla\n'
            "    evidence: checked\n    decided_by: owner"
        )
        with pytest.raises(AliasFileError, match="leading or trailing whitespace"):
            parse_alias_file(padded)
        long_text = _file(_decision("x" * 101, "Vanilla"))
        with pytest.raises(AliasFileError, match="longer than 100"):
            parse_alias_file(long_text)


async def _notes(session, *names: str) -> None:
    for name in names:
        session.add(Note(name=name))
    await session.flush()


class TestLoad:
    async def test_a_dry_run_reports_and_writes_nothing(self, async_session) -> None:
        await _notes(async_session, "Vanilla")
        parsed = parse_alias_file(_file(_decision("vanille", "Vanilla")))

        report = await load_aliases(async_session, parsed)

        assert [item.outcome for item in report.items] == ["create"]
        assert report.applied is False
        assert (await async_session.execute(select(NoteAlias))).scalars().all() == []

    async def test_execute_loads_and_the_resolver_then_applies_it(
        self, async_session
    ) -> None:
        await _notes(async_session, "Vanilla")
        parsed = parse_alias_file(_file(_decision("vanille", "Vanilla")))

        report = await load_aliases(async_session, parsed, execute=True, actor="owner")
        resolved = await VocabularyResolver(async_session).resolve_note("Vanille")

        assert report.applied is True
        assert (resolved.status, resolved.note.name if resolved.note else None) == (
            "alias",
            "Vanilla",
        )
        (row,) = (await async_session.execute(select(NoteAlias))).scalars().all()
        assert (row.raw_label, row.origin, row.mapping_version) == (
            "vanille",
            "curated",
            "nm-v1",
        )

    async def test_load_itself_emits_no_audit_event(
        self, async_session, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        calls: list[dict[str, object]] = []
        monkeypatch.setattr(
            "fragrance_rater.services.note_aliases.log_audit_event",
            lambda _logger, **kw: calls.append(kw),
        )
        await _notes(async_session, "Vanilla")
        parsed = parse_alias_file(_file(_decision("vanille", "Vanilla")))

        await load_aliases(async_session, parsed, execute=True, actor="owner")

        assert calls == []

    async def test_a_second_load_is_unchanged(self, async_session) -> None:
        await _notes(async_session, "Vanilla")
        parsed = parse_alias_file(_file(_decision("vanille", "Vanilla")))
        await load_aliases(async_session, parsed, execute=True, actor="owner")

        again = await load_aliases(async_session, parsed, execute=True, actor="owner")

        assert [item.outcome for item in again.items] == ["unchanged"]
        assert again.applied is False
        assert (
            len((await async_session.execute(select(NoteAlias))).scalars().all()) == 1
        )

    async def test_execute_needs_an_actor(self, async_session) -> None:
        parsed = parse_alias_file(_file())

        with pytest.raises(ValueError, match="actor"):
            await load_aliases(async_session, parsed, execute=True)

    async def test_a_missing_canonical_note_blocks(self, async_session) -> None:
        parsed = parse_alias_file(_file(_decision("vanille", "Vanilla")))

        report = await load_aliases(async_session, parsed, execute=True, actor="owner")

        assert [item.outcome for item in report.items] == ["missing_canonical"]
        assert report.blocked is True
        assert report.applied is False

    async def test_a_label_that_already_names_another_note_blocks(
        self, async_session
    ) -> None:
        await _notes(async_session, "Vanilla", "Vanille")
        parsed = parse_alias_file(_file(_decision("vanille", "Vanilla")))

        report = await load_aliases(async_session, parsed, execute=True, actor="owner")

        (item,) = report.items
        assert item.outcome == "collides_with_note"
        assert "ambiguous" in item.detail
        assert report.applied is False

    async def test_one_blocked_decision_blocks_the_whole_load(
        self, async_session
    ) -> None:
        await _notes(async_session, "Vanilla")
        parsed = parse_alias_file(
            _file(_decision("vanille", "Vanilla"), _decision("tonka", "Tonka Bean"))
        )

        report = await load_aliases(async_session, parsed, execute=True, actor="owner")

        assert {item.outcome for item in report.items} == {
            "create",
            "missing_canonical",
        }
        assert report.applied is False
        assert (await async_session.execute(select(NoteAlias))).scalars().all() == []

    async def test_a_changed_decision_for_a_loaded_label_conflicts(
        self, async_session
    ) -> None:
        await _notes(async_session, "Vanilla", "Vanilla Bean")
        await load_aliases(
            async_session,
            parse_alias_file(_file(_decision("vanille", "Vanilla"))),
            execute=True,
            actor="owner",
        )

        report = await load_aliases(
            async_session,
            parse_alias_file(_file(_decision("vanille", "Vanilla Bean"))),
            execute=True,
            actor="owner",
        )

        (item,) = report.items
        assert item.outcome == "conflict"
        assert "new version" in item.detail

    async def test_a_second_spelling_of_a_decided_key_conflicts(
        self, async_session
    ) -> None:
        await _notes(async_session, "Vanilla")
        await load_aliases(
            async_session,
            parse_alias_file(_file(_decision("vanille", "Vanilla"))),
            execute=True,
            actor="owner",
        )

        report = await load_aliases(
            async_session,
            parse_alias_file(_file(_decision("Vanille!", "Vanilla"))),
        )

        (item,) = report.items
        assert item.outcome == "conflict"
        assert "one decision per version" in item.detail

    async def test_a_version_other_than_the_active_one_is_flagged(
        self, async_session
    ) -> None:
        await _notes(async_session, "Vanilla")
        parsed = parse_alias_file(
            _file(_decision("vanille", "Vanilla"), version="nm-v2")
        )

        report = await load_aliases(async_session, parsed)

        assert report.active is False


class TestAudit:
    async def test_an_applied_load_is_audited_with_the_content_hash(
        self, async_session, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        calls: list[dict[str, object]] = []
        monkeypatch.setattr(
            "fragrance_rater.services.note_aliases.log_audit_event",
            lambda _logger, **kw: calls.append(kw),
        )
        await _notes(async_session, "Vanilla")
        parsed = parse_alias_file(_file(_decision("vanille", "Vanilla")))
        report = await load_aliases(async_session, parsed, execute=True, actor="owner")

        audit_alias_load(report, "owner")

        (event,) = calls
        assert event["action"] == "note_alias_load"
        assert event["actor"] == "owner"
        assert event["created"] == 1
        assert event["content_hash"] == parsed.content_hash
        assert event["target_id"] == f"nm-v1:{parsed.content_hash[:12]}"

    async def test_dry_run_blocked_and_unchanged_loads_are_not_audited(
        self, async_session, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        calls: list[dict[str, object]] = []
        monkeypatch.setattr(
            "fragrance_rater.services.note_aliases.log_audit_event",
            lambda _logger, **kw: calls.append(kw),
        )
        await _notes(async_session, "Vanilla")
        parsed = parse_alias_file(_file(_decision("vanille", "Vanilla")))
        dry = await load_aliases(async_session, parsed)
        applied = await load_aliases(async_session, parsed, execute=True, actor="o")
        unchanged = await load_aliases(async_session, parsed, execute=True, actor="o")
        blocked = await load_aliases(
            async_session,
            parse_alias_file(_file(_decision("tonka", "Missing Note"))),
            execute=True,
            actor="o",
        )

        for report in (dry, unchanged, blocked):
            audit_alias_load(report, "o")

        assert applied.applied is True
        assert calls == []


class TestAmbiguities:
    async def test_none_when_nothing_is_curated(self, async_session) -> None:
        await _notes(async_session, "Vanilla")

        assert await find_ambiguities(async_session) == []

    async def test_a_curated_alias_that_disagrees_with_a_key_match_is_listed(
        self, async_session
    ) -> None:
        await _notes(async_session, "Musk", "White Musk")
        musk = (
            await async_session.execute(select(Note).where(Note.name == "White Musk"))
        ).scalar_one()
        async_session.add(
            NoteAlias(
                raw_label="Musk",
                alias_key="musk",
                canonical_note_id=musk.id,
                mapping_version=NOTE_MAPPING_VERSION,
                origin="curated",
            )
        )
        await async_session.flush()

        (found,) = await find_ambiguities(async_session)

        assert (found.alias_key, found.alias_target, found.key_note) == (
            "musk",
            "White Musk",
            "Musk",
        )
