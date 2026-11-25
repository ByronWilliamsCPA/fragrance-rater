"""Shared-session enrollment template with balanced Latin-square order (F1).

The facilitated F1 format runs six evaluators in parallel: in each session
every evaluator smells the same stimuli at the same time (a "shared triple"
when the session size is 3), each from their own tray. This module holds the
pure, database-free rules for that design so they can be tested exhaustively:

* A **template** is an ordered list of sessions, each an ordered list of
  membership ids (the canonical order). Every evaluator enrolled under the
  template receives exactly these sessions, in this session order.
* Within a session the order is permuted per evaluator with a Williams
  balanced Latin square. Evaluator ``k`` (the 0-based ordinal of the
  enrollment under this template) in session ``s`` (0-based) uses row
  ``(k + s) mod rows``. For a session of 3 the square has six rows (every
  ordering of three samples), so across six evaluators each sample sits in
  each position exactly twice per session, and each ordered adjacent pair
  occurs equally often (first-order carryover balance). Varying the row by
  session also rotates which canonical slot each evaluator smells first.
* Hidden repeats must sit at least ``2 * session_size`` presentations after
  their original for **every** row assignment, which in practice means at
  least three sessions later when the session size is 2 or more. The check
  is on actual per-evaluator order, not on the canonical slot.
* Holdouts form the last block. Every session of a block is full except the
  block's last one, so 10 holdouts in sessions of 3 give a 3, 3, 3, 1 shape.
* At most one exceptionally persistent or animalic stimulus per session
  (ADR-005 order/position row). No catalog or membership column holds that
  judgement, so it is a manager-supplied constraint: the enrollment request's
  ``persistent_membership_ids`` and/or a membership ``selection`` flag
  ``persistent_or_animalic: true``. The validator enforces whichever is given.

Nothing here reads entropy except through an explicit ``seed`` argument, so a
generated template is reproducible from the seed recorded on the enrollment.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import dataclass
from itertools import pairwise
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence

SHARED_TRIPLES_ALGORITHM = "shared-triples-latin-rotation-v1"
INDEPENDENT_SHUFFLE_ALGORITHM = "system-random-shuffle-v1"

# Attempts before generation gives up. Each attempt is a different
# deterministic permutation derived from the seed, so the outcome is still
# reproducible; a realistic program (33 baseline, 6 repeats, 10 holdouts) needs
# only a handful.
GENERATION_ATTEMPTS = 2000

_RECORD_PATTERN = (
    r"^rotation=(?P<rotation>\d+);template=sha256:(?P<digest>[0-9a-f]{64})"
    r"(?:;generated=(?P<generated>[0-9a-f]{16}))?$"
)
_RECORD = re.compile(_RECORD_PATTERN)


class TemplateError(ValueError):
    """A template that would break a design guarantee; safe to show a manager."""


@dataclass(frozen=True)
class TemplateMember:
    """The facts about one program membership that the template rules need."""

    id: str
    fragrance_id: str
    role: str
    repeat_of_id: str | None = None
    persistent: bool = False

    @property
    def is_holdout(self) -> bool:
        """Whether this stimulus belongs to the final holdout block."""
        return self.role == "HOLDOUT"

    @property
    def is_repeat(self) -> bool:
        """Whether this stimulus is a concealed hidden repeat."""
        return self.role == "HIDDEN_REPEAT"


Template = list[list[str]]


def williams_rows(size: int) -> list[tuple[int, ...]]:
    """Return the rows of a Williams balanced Latin square of order ``size``.

    Each row maps a position (index) to a canonical slot (value). For an even
    order one square of ``size`` rows is balanced; for an odd order the square
    and its mirror image together (``2 * size`` rows) are.

    Args:
        size (int): Number of samples in the session (>= 1).

    Returns:
        list[tuple[int, ...]]: The balanced rows, first row first.

    Raises:
        ValueError: If ``size`` is less than 1.
    """
    if size < 1:
        msg = "A session needs at least one sample"
        raise ValueError(msg)
    first: list[int] = [0]
    low, high = 1, size - 1
    take_low = True
    while len(first) < size:
        if take_low:
            first.append(low)
            low += 1
        else:
            first.append(high)
            high -= 1
        take_low = not take_low
    rows = [tuple((slot + shift) % size for slot in first) for shift in range(size)]
    if size % 2 == 1 and size > 1:
        rows += [tuple(reversed(row)) for row in rows]
    return rows


def rotation_row(rotation: int, session_index: int, size: int) -> tuple[int, ...]:
    """Return the Williams row evaluator ``rotation`` uses in a session.

    Args:
        rotation (int): The evaluator's 0-based ordinal under the template.
        session_index (int): 0-based session number within the template.
        size (int): Number of samples in that session.

    Returns:
        tuple[int, ...]: Canonical slot shown at each position.
    """
    rows = williams_rows(size)
    return rows[(rotation + session_index) % len(rows)]


def evaluator_order(template: Sequence[Sequence[str]], rotation: int) -> Template:
    """Return one evaluator's actual presentation order for every session.

    Args:
        template (Sequence[Sequence[str]]): Canonical sessions.
        rotation (int): The evaluator's 0-based ordinal under the template.

    Returns:
        Template: Sessions in template order, each in this evaluator's order.
    """
    return [
        [session[slot] for slot in rotation_row(rotation, index, len(session))]
        for index, session in enumerate(template)
    ]


def recover_template(actual: Sequence[Sequence[str]], rotation: int) -> Template:
    """Invert :func:`evaluator_order` for an existing enrollment.

    Args:
        actual (Sequence[Sequence[str]]): One evaluator's recorded sessions.
        rotation (int): That evaluator's recorded rotation.

    Returns:
        Template: The canonical template the order was derived from.
    """
    template: Template = []
    for index, session in enumerate(actual):
        canonical = [""] * len(session)
        for position, slot in enumerate(rotation_row(rotation, index, len(session))):
            canonical[slot] = session[position]
        template.append(canonical)
    return template


def template_digest(template: Sequence[Sequence[str]]) -> str:
    """Return the SHA-256 hex digest that names a template in the audit record."""
    payload = json.dumps([list(session) for session in template], separators=(",", ":"))
    return hashlib.sha256(payload.encode()).hexdigest()


def randomization_record(rotation: int, digest: str, generated: str | None) -> str:
    """Format the value stored in ``Enrollment.randomization_seed``.

    Args:
        rotation (int): The evaluator's 0-based ordinal under the template.
        digest (str): :func:`template_digest` of the template.
        generated (str | None): The generation seed, when the server built
            the template; ``None`` when a manager supplied it.

    Returns:
        str: ``rotation=<k>;template=sha256:<hex>[;generated=<seed>]``.
    """
    record = f"rotation={rotation};template=sha256:{digest}"
    return record if generated is None else f"{record};generated={generated}"


def parse_randomization_record(value: str | None) -> tuple[int, str, str | None]:
    """Parse :func:`randomization_record` output.

    Args:
        value (str | None): ``Enrollment.randomization_seed``.

    Returns:
        tuple[int, str, str | None]: Rotation, template digest, generation seed.

    Raises:
        TemplateError: If the value is missing or malformed.
    """
    match = _RECORD.match(value or "")
    if match is None:
        msg = "The recorded shared-session randomization is unreadable"
        raise TemplateError(msg)
    return int(match["rotation"]), match["digest"], match["generated"]


def _rotation_period(template: Sequence[Sequence[str]]) -> int:
    """Number of evaluators after which every session's row assignment repeats."""
    return math.lcm(*(len(williams_rows(len(s))) for s in template if s))


def _check_coverage(
    template: Sequence[Sequence[str]], members: dict[str, TemplateMember]
) -> None:
    """Every program stimulus exactly once; each fragrance once plus its repeat."""
    if not template:
        msg = "The session template has no sessions"
        raise TemplateError(msg)
    seen: list[str] = [mid for session in template for mid in session]
    unknown = [mid for mid in seen if mid not in members]
    if unknown:
        msg = "The session template names a stimulus that is not in this program"
        raise TemplateError(msg)
    if len(seen) != len(set(seen)):
        msg = "Each stimulus must appear exactly once in the session template"
        raise TemplateError(msg)
    if set(seen) != set(members):
        msg = "The session template must include every stimulus in the program"
        raise TemplateError(msg)
    fragrances = [
        members[mid].fragrance_id for mid in seen if not members[mid].is_repeat
    ]
    if len(fragrances) != len(set(fragrances)):
        msg = "Each fragrance may appear once per evaluator, plus its hidden repeat"
        raise TemplateError(msg)


def _check_blocks(
    template: Sequence[Sequence[str]],
    members: dict[str, TemplateMember],
    session_size: int,
) -> None:
    """Session sizes and the holdout-last block shape."""
    for session in template:
        if not session or len(session) > session_size:
            msg = f"Every session must hold between 1 and {session_size} samples"
            raise TemplateError(msg)
    kinds = [{members[mid].is_holdout for mid in session} for session in template]
    if any(len(kind) > 1 for kind in kinds):
        msg = "A session cannot mix holdouts with other stimuli"
        raise TemplateError(msg)
    holdout_flags = [kind == {True} for kind in kinds]
    if any(earlier and not later for earlier, later in pairwise(holdout_flags)):
        msg = "Holdout sessions must form the last block of the schedule"
        raise TemplateError(msg)
    for block in (False, True):
        sizes = [
            len(s)
            for s, flag in zip(template, holdout_flags, strict=True)
            if flag is block
        ]
        if any(size != session_size for size in sizes[:-1]):
            msg = (
                f"Every session except the last of each block must hold "
                f"exactly {session_size} samples"
            )
            raise TemplateError(msg)


def _check_repeats(
    template: Sequence[Sequence[str]],
    members: dict[str, TemplateMember],
    session_size: int,
) -> None:
    """Every hidden repeat follows its original far enough, for every evaluator."""
    repeats = [m for m in members.values() if m.is_repeat]
    if not repeats:
        return
    minimum = 2 * session_size
    for rotation in range(_rotation_period(template)):
        where: dict[str, tuple[int, int]] = {}
        flat = 0
        for index, session in enumerate(evaluator_order(template, rotation)):
            for mid in session:
                where[mid] = (index, flat)
                flat += 1
        for repeat in repeats:
            if repeat.repeat_of_id not in where:
                msg = "A hidden repeat's original is missing from the template"
                raise TemplateError(msg)
            original_session, original_slot = where[repeat.repeat_of_id]
            repeat_session, repeat_slot = where[repeat.id]
            if repeat_session <= original_session or (
                repeat_slot - original_slot < minimum
            ):
                msg = (
                    f"A hidden repeat must come in a later session, at least "
                    f"{minimum} presentations after its original, for every "
                    f"evaluator's rotation"
                )
                raise TemplateError(msg)


def validate_template(
    template: Sequence[Sequence[str]],
    members: Iterable[TemplateMember],
    session_size: int,
) -> None:
    """Fail loudly if a template breaks any shared-session guarantee.

    Args:
        template (Sequence[Sequence[str]]): Canonical sessions of membership ids.
        members (Iterable[TemplateMember]): Every membership in the program.
        session_size (int): Samples per full session.

    Raises:
        TemplateError: Naming the first broken rule.
    """
    by_id = {m.id: m for m in members}
    _check_coverage(template, by_id)
    _check_blocks(template, by_id, session_size)
    _check_repeats(template, by_id, session_size)
    for session in template:
        if sum(by_id[mid].persistent for mid in session) > 1:
            msg = (
                "At most one exceptionally persistent or animalic stimulus "
                "may share a session"
            )
            raise TemplateError(msg)


def _rank(seed: str, attempt: int, label: str, key: str) -> int:
    """Deterministic pseudo-random rank; not a secret, only a reproducible order."""
    digest = hashlib.sha256(f"{seed}:{attempt}:{label}:{key}".encode()).hexdigest()
    return int(digest, 16)


def _chunk(items: Sequence[str], size: int) -> Template:
    return [list(items[i : i + size]) for i in range(0, len(items), size)]


def _repeat_slot_gap(session_size: int) -> int:
    """Canonical slots a generated repeat must follow its original by.

    A repeat ``d`` sessions after its original is at least
    ``d * size - (size - 1)`` positions later under the worst rotation
    (original smelled last, repeat first). The smallest ``d`` meeting the
    ``2 * size`` separation is 3 for sessions of two or more and 2 for
    single-sample sessions, where there is only one rotation.

    Args:
        session_size (int): Samples per full session.

    Returns:
        int: The minimum canonical slot distance, a whole number of sessions.
    """
    sessions_apart = -(-(3 * session_size - 1) // session_size)
    return sessions_apart * session_size


def generate_template(
    members: Sequence[TemplateMember], session_size: int, seed: str
) -> Template:
    """Build a valid template deterministically from ``seed``.

    The non-repeat, non-holdout stimuli are ordered by a seeded hash, each
    hidden repeat is inserted enough full sessions after its original that
    the separation survives every within-session rotation (see
    :func:`_repeat_slot_gap`), and the
    holdouts follow as a separately ordered last block. A candidate that
    breaks any rule is discarded and the next attempt tried; the result is
    then checked by :func:`validate_template`.

    Args:
        members (Sequence[TemplateMember]): Every membership in the program.
        session_size (int): Samples per full session.
        seed (str): Generation seed; record it to reproduce the template.

    Returns:
        Template: A template that passes :func:`validate_template`.

    Raises:
        TemplateError: If no attempt satisfies the rules (for example, too few
            baseline stimuli to separate the hidden repeats).
    """
    singles = [m.id for m in members if not m.is_repeat and not m.is_holdout]
    repeats = [m for m in members if m.is_repeat]
    holdouts = [m.id for m in members if m.is_holdout]
    gap = _repeat_slot_gap(session_size)
    for attempt in range(GENERATION_ATTEMPTS):
        order = sorted(singles, key=lambda mid: _rank(seed, attempt, "order", mid))
        placed = True
        for repeat in sorted(
            repeats, key=lambda m: _rank(seed, attempt, "repeat", m.id)
        ):
            if repeat.repeat_of_id not in order:
                placed = False
                break
            earliest = order.index(repeat.repeat_of_id) + gap
            if earliest > len(order):
                placed = False
                break
            span = len(order) - earliest + 1
            offset = _rank(seed, attempt, "place", repeat.id) % span
            order.insert(earliest + offset, repeat.id)
        if not placed:
            continue
        tail = sorted(holdouts, key=lambda mid: _rank(seed, attempt, "holdout", mid))
        candidate = _chunk(order, session_size) + _chunk(tail, session_size)
        try:
            validate_template(candidate, members, session_size)
        except TemplateError:
            continue
        return candidate
    msg = (
        "Could not build a shared session template: the program needs more "
        "baseline stimuli to separate its hidden repeats, or fewer persistent "
        "stimuli per session"
    )
    raise TemplateError(msg)
