"""Property tests for the shared-session template and Latin-square rotation."""

from collections import Counter
from itertools import pairwise, permutations

import pytest

from fragrance_rater.schemas.calibration import RandomizationAlgorithm
from fragrance_rater.services.calibration_service import RANDOMIZATION_ALGORITHM
from fragrance_rater.services.shared_triples import (
    INDEPENDENT_SHUFFLE_ALGORITHM,
    SHARED_TRIPLES_ALGORITHM,
    TemplateError,
    TemplateMember,
    evaluator_order,
    generate_template,
    parse_randomization_record,
    randomization_record,
    recover_template,
    rotation_row,
    template_digest,
    validate_template,
    williams_rows,
)

SIX = range(6)


def f1_members(
    baseline: int = 33, repeats: int = 6, holdouts: int = 10
) -> list[TemplateMember]:
    """A program shaped like F1: baseline, hidden repeats of the first few, holdouts."""
    members = [
        TemplateMember(
            id=f"b{i:02d}", fragrance_id=f"f{i:02d}", role="UNIVERSAL_BASELINE"
        )
        for i in range(baseline)
    ]
    members += [
        TemplateMember(
            id=f"r{i:02d}",
            fragrance_id=f"f{i:02d}",
            role="HIDDEN_REPEAT",
            repeat_of_id=f"b{i:02d}",
        )
        for i in range(repeats)
    ]
    members += [
        TemplateMember(id=f"h{i:02d}", fragrance_id=f"g{i:02d}", role="HOLDOUT")
        for i in range(holdouts)
    ]
    return members


@pytest.fixture(scope="module")
def template() -> list[list[str]]:
    return generate_template(f1_members(), 3, "0123456789abcdef")


def test_algorithm_names_agree_with_the_schema():
    assert set(RandomizationAlgorithm.__args__) == {
        INDEPENDENT_SHUFFLE_ALGORITHM,
        SHARED_TRIPLES_ALGORITHM,
    }
    assert RANDOMIZATION_ALGORITHM == INDEPENDENT_SHUFFLE_ALGORITHM


@pytest.mark.parametrize("size", range(1, 8))
def test_williams_rows_are_balanced_latin_squares(size):
    rows = williams_rows(size)
    assert len(rows) == (2 * size if size % 2 and size > 1 else size)
    for row in rows:
        assert sorted(row) == list(range(size))
    for position in range(size):
        counts = Counter(row[position] for row in rows)
        assert set(counts.values()) == {len(rows) // size}
    # First-order carryover: each ordered adjacent pair equally often.
    if size > 1:
        pairs = Counter(pair for row in rows for pair in pairwise(row))
        assert len(pairs) == size * (size - 1)
        assert len(set(pairs.values())) == 1


def test_size_three_uses_all_six_orderings():
    assert set(williams_rows(3)) == set(permutations(range(3)))


def test_williams_rows_reject_empty_sessions():
    with pytest.raises(ValueError, match="at least one"):
        williams_rows(0)


def test_six_evaluators_share_composition_and_balance_every_session(template):
    orders = [evaluator_order(template, k) for k in SIX]
    for order in orders:
        assert [sorted(s) for s in order] == [sorted(s) for s in template]
    for index, session in enumerate(template):
        if len(session) != 3:
            continue
        for position in range(3):
            counts = Counter(order[index][position] for order in orders)
            assert counts == dict.fromkeys(session, 2), (index, position)
        # Each evaluator gets a different ordering of the same triple.
        assert len({tuple(order[index]) for order in orders}) == 6


def test_rotation_varies_by_session_for_each_evaluator(template):
    # The 13 full baseline sessions.
    full = [i for i, s in enumerate(template) if len(s) == 3][:13]
    for k in SIX:
        rows = [rotation_row(k, i, 3) for i in full]
        assert len(set(rows[:6])) == 6
        first_slots = Counter(row[0] for row in rows)
        # Canonical slot smelled first is spread across sessions, not fixed.
        assert max(first_slots.values()) - min(first_slots.values()) <= 1


def test_thirty_nine_baseline_slots_give_thirteen_per_position(template):
    baseline_sessions = [s for s in template if not s[0].startswith("h")]
    assert [len(s) for s in baseline_sessions] == [3] * 13
    for k in SIX:
        order = evaluator_order(template, k)[: len(baseline_sessions)]
        positions = Counter(p for session in order for p in range(len(session)))
        assert positions == {0: 13, 1: 13, 2: 13}


def test_holdouts_are_a_last_block_of_three_three_three_one(template):
    flags = [s[0].startswith("h") for s in template]
    assert flags == [False] * 13 + [True] * 4
    assert [len(s) for s in template[13:]] == [3, 3, 3, 1]
    assert all(all(m.startswith("h") for m in s) for s in template[13:])


def test_block_shape_derives_from_counts_not_a_constant():
    generated = generate_template(f1_members(20, 3, 7), 3, "fedcba9876543210")
    holdout = [s for s in generated if s[0].startswith("h")]
    baseline = [s for s in generated if not s[0].startswith("h")]
    assert [len(s) for s in holdout] == [3, 3, 1]
    assert [len(s) for s in baseline] == [3] * 7 + [2]


def test_every_stimulus_once_and_repeats_separated_for_every_rotation(template):
    members = {m.id: m for m in f1_members()}
    for k in range(12):
        flat = [mid for session in evaluator_order(template, k) for mid in session]
        assert sorted(flat) == sorted(members)
        for member in members.values():
            if member.repeat_of_id:
                gap = flat.index(member.id) - flat.index(member.repeat_of_id)
                assert gap >= 6


def test_generation_is_reproducible_from_its_seed(template):
    assert generate_template(f1_members(), 3, "0123456789abcdef") == template
    assert generate_template(f1_members(), 3, "aaaaaaaaaaaaaaaa") != template


def test_recover_template_inverts_any_rotation(template):
    for k in range(7):
        assert recover_template(evaluator_order(template, k), k) == template


def test_randomization_record_round_trips(template):
    digest = template_digest(template)
    record = randomization_record(4, digest, "0123456789abcdef")
    assert len(record) <= 128
    assert parse_randomization_record(record) == (4, digest, "0123456789abcdef")
    assert parse_randomization_record(randomization_record(0, digest, None)) == (
        0,
        digest,
        None,
    )
    with pytest.raises(TemplateError, match="unreadable"):
        parse_randomization_record("rotation=x")
    with pytest.raises(TemplateError, match="unreadable"):
        parse_randomization_record(None)


def test_persistent_stimuli_never_share_a_session():
    members = [
        TemplateMember(
            id=m.id,
            fragrance_id=m.fragrance_id,
            role=m.role,
            repeat_of_id=m.repeat_of_id,
            persistent=m.id in {"b10", "b11", "b12", "b13"},
        )
        for m in f1_members()
    ]
    generated = generate_template(members, 3, "0123456789abcdef")
    persistent = {m.id for m in members if m.persistent}
    assert all(len(persistent & set(s)) <= 1 for s in generated)


def _swap(template, a, b):
    copy = [list(s) for s in template]
    for session in copy:
        for i, mid in enumerate(session):
            if mid == a:
                session[i] = b
            elif mid == b:
                session[i] = a
    return copy


def test_persistent_limit_rejects_two_in_one_session(template):
    first = template[0]
    members = [
        TemplateMember(
            id=m.id,
            fragrance_id=m.fragrance_id,
            role=m.role,
            repeat_of_id=m.repeat_of_id,
            persistent=m.id in first[:2],
        )
        for m in f1_members()
    ]
    with pytest.raises(TemplateError, match="persistent or animalic"):
        validate_template(template, members, 3)


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (lambda t: [], "no sessions"),
        (lambda t: [*t[:-1], [*t[-1], "nope"]], "not in this program"),
        (lambda t: [[t[0][0], *t[0][1:]], *t[1:-1], [t[-1][0], t[0][0]]], "once"),
        (lambda t: t[:-1], "every stimulus"),
        (lambda t: [[*t[0], t[1][0]], t[1][1:], *t[2:]], "between 1 and 3"),
        (lambda t: [t[-1], *t[:-1]], "last block"),
        (
            lambda t: [
                *t[:12],
                [t[12][0], t[13][0], t[12][2]],
                [t[12][1], *t[13][1:]],
                *t[14:],
            ],
            "mix",
        ),
    ],
)
def test_invalid_templates_fail_loudly(template, mutate, message):
    with pytest.raises(TemplateError, match=message):
        validate_template(mutate(template), f1_members(), 3)


def test_short_sessions_inside_a_block_are_rejected(template):
    reshaped = [template[0][:2], [template[0][2], *template[1]], *template[2:]]
    with pytest.raises(TemplateError, match=r"between 1 and 3|exactly 3"):
        validate_template(reshaped, f1_members(), 3)
    short_first = [template[0][:2], [template[0][2]], *template[1:]]
    with pytest.raises(TemplateError, match="exactly 3"):
        validate_template(short_first, f1_members(), 3)


def test_duplicate_fragrance_outside_a_repeat_is_rejected(template):
    members = [
        TemplateMember(
            id=m.id,
            fragrance_id="f01" if m.id == "b02" else m.fragrance_id,
            role=m.role,
            repeat_of_id=m.repeat_of_id,
        )
        for m in f1_members()
    ]
    with pytest.raises(TemplateError, match="once per evaluator"):
        validate_template(template, members, 3)


def test_repeat_too_close_to_its_original_is_rejected(template):
    flat_session = {mid: i for i, s in enumerate(template) for mid in s}
    repeat = "r00"
    original_session = flat_session["b00"]
    # Move the repeat to the session right after its original: valid in the
    # canonical order for some rotations but not for every evaluator.
    neighbour = template[original_session + 1][0]
    if neighbour.startswith(("r", "b00")):
        neighbour = template[original_session + 1][1]
    moved = _swap(template, repeat, neighbour)
    with pytest.raises(TemplateError, match="hidden repeat"):
        validate_template(moved, f1_members(), 3)


def test_repeat_two_sessions_later_fails_for_some_rotation():
    """Two sessions apart passes canonically but not for every rotation."""
    members = f1_members(9, 1, 0)
    # Original first in session 0, repeat last in session 2: canonical gap 8,
    # but evaluator 1 smells the original last and the repeat first (gap 4).
    template = [
        ["b00", "b01", "b02"],
        ["b03", "b04", "b05"],
        ["b06", "b07", "r00"],
        ["b08"],
    ]
    with pytest.raises(TemplateError, match="every evaluator"):
        validate_template(template, members, 3)


def test_repeat_before_its_original_is_rejected():
    members = f1_members(9, 1, 0)
    others = [m.id for m in members if m.role == "UNIVERSAL_BASELINE" and m.id != "b00"]
    template = [["r00", *others[:2]], others[2:5], others[5:8], ["b00"]]
    with pytest.raises(TemplateError, match="later session"):
        validate_template(template, members, 3)


def test_missing_original_is_rejected():
    members = [
        TemplateMember(id="b0", fragrance_id="f0", role="UNIVERSAL_BASELINE"),
        TemplateMember(
            id="r0", fragrance_id="f0", role="HIDDEN_REPEAT", repeat_of_id="ghost"
        ),
    ]
    with pytest.raises(TemplateError, match="original is missing"):
        validate_template([["b0"], ["r0"]], members, 1)


def test_generation_fails_loudly_when_repeats_cannot_be_separated():
    with pytest.raises(TemplateError, match="Could not build"):
        generate_template(f1_members(3, 1, 0), 3, "0123456789abcdef")
