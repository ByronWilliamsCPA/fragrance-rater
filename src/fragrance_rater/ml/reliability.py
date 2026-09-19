"""Hidden-repeat agreement: the noise ceiling every model result is quoted against.

The calibration design places 6 hidden repeats per evaluator, each a second
concealed presentation of a version the evaluator has already smelled in the
same enrollment. Until now ``repeat_of_id`` was read only for setup
validation and interleaving, so the repeats were excluded from training and
used for nothing (ML structure review M-19).

This module turns them into a test-retest estimate. That estimate is the
upper bound on any achievable out-of-sample agreement: a model cannot predict
an evaluator's liking more reliably than the evaluator reproduces it.

Everything above ``repeat_pairs`` is pure and dependency-free (no numpy), so
a report can be recomputed from stored pairs without a database.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, cast

from sqlalchemy import select

from fragrance_rater.models.calibration import (
    CalibrationSession,
    Enrollment,
    Membership,
    Observation,
    Presentation,
)

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

    from sqlalchemy.ext.asyncio import AsyncSession

MIN_PAIRS = 3
"""Fewest paired values a correlation or interval is computed from."""

RELIABILITY_NOTE = (
    "Pooled across evaluators. ADR-009 sanctions treating evaluators as "
    "exchangeable for the reliability parameter only; no preference "
    "parameter may be pooled on this basis. The day effect is not separable "
    "from measurement error here because protocol day is not stored (ML "
    "structure review X-08), so day-to-day variation is absorbed into this "
    "estimate and deflates the ceiling."
)
"""Fixed caveat carried on every reliability report."""

# Stages examined for a repeat pair. Repeats are blotter by design, so
# BLOTTER comes first; a SKIN pair is reported as well when both sides of
# the pair have a locked, liking-bearing skin observation.
_STAGES = ("BLOTTER", "SKIN")


def _mean(values: Sequence[float]) -> float:
    return sum(values) / len(values)


def pearson(xs: Sequence[float], ys: Sequence[float]) -> float | None:
    """Return the Pearson correlation of two equal-length series.

    Args:
        xs (Sequence[float]): First series.
        ys (Sequence[float]): Second series.

    Returns:
        float | None: The correlation, or ``None`` when the series differ in
            length, hold fewer than ``MIN_PAIRS`` pairs, or either side has
            zero variance (in which case a correlation is undefined rather
            than zero).
    """
    if len(xs) != len(ys) or len(xs) < MIN_PAIRS:
        return None
    mean_x = _mean(xs)
    mean_y = _mean(ys)
    dx = [x - mean_x for x in xs]
    dy = [y - mean_y for y in ys]
    var_x = sum(value * value for value in dx)
    var_y = sum(value * value for value in dy)
    if var_x <= 0.0 or var_y <= 0.0:
        return None
    return sum(a * b for a, b in zip(dx, dy, strict=True)) / math.sqrt(var_x * var_y)


def average_ranks(values: Sequence[float]) -> list[float]:
    """Rank values ascending, assigning tied values their average rank.

    Args:
        values (Sequence[float]): Values to rank.

    Returns:
        list[float]: One 1-based rank per input position; a run of ``k``
            tied values all receive the mean of the ``k`` ranks they span.
    """
    order = sorted(range(len(values)), key=lambda i: values[i])
    ranks = [0.0] * len(values)
    start = 0
    while start < len(order):
        stop = start
        while stop + 1 < len(order) and values[order[stop + 1]] == values[order[start]]:
            stop += 1
        shared = (start + stop) / 2.0 + 1.0
        for position in range(start, stop + 1):
            ranks[order[position]] = shared
        start = stop + 1
    return ranks


def spearman(xs: Sequence[float], ys: Sequence[float]) -> float | None:
    """Return the Spearman rank correlation, averaging ranks over ties.

    Args:
        xs (Sequence[float]): First series.
        ys (Sequence[float]): Second series.

    Returns:
        float | None: The rank correlation, or ``None`` under the same
            conditions as ``pearson`` (including a series that is entirely
            tied, whose ranks have zero variance).
    """
    if len(xs) != len(ys) or len(xs) < MIN_PAIRS:
        return None
    return pearson(average_ranks(xs), average_ranks(ys))


def mean_absolute_difference(xs: Sequence[float], ys: Sequence[float]) -> float | None:
    """Return the mean absolute paired difference between two series.

    Args:
        xs (Sequence[float]): First series.
        ys (Sequence[float]): Second series.

    Returns:
        float | None: Mean of ``|x - y|``, or ``None`` when the series are
            empty or differ in length.
    """
    if len(xs) != len(ys) or not xs:
        return None
    return _mean([abs(a - b) for a, b in zip(xs, ys, strict=True)])


def bootstrap_interval(
    pairs: Sequence[tuple[float, float]],
    statistic: Callable[[Sequence[float], Sequence[float]], float | None],
    *,
    n_resamples: int = 1000,
    seed: int = 0,
    level: float = 0.95,
) -> tuple[float, float] | None:
    """Return a percentile bootstrap interval for a paired statistic.

    Deterministic: the same pairs, statistic, resample count and seed always
    produce the same interval, so an interval quoted in a report can be
    reproduced exactly (ADR-009 requires uncertainty beside every estimate).

    Args:
        pairs (Sequence[tuple[float, float]]): Paired observations,
            resampled together so the pairing is preserved.
        statistic (Callable[[Sequence[float], Sequence[float]], float | None]):
            Callable taking the two resampled series and returning
            the statistic, or ``None`` when it is undefined for that
            resample (which is then skipped).
        n_resamples (int): Number of bootstrap resamples.
        seed (int): Seed for ``random.Random``.
        level (float): Central mass of the interval, e.g. ``0.95``.

    Returns:
        tuple[float, float] | None: Lower and upper percentile bounds, or
            ``None`` when there are fewer than ``MIN_PAIRS`` pairs or too
            few resamples produced a defined statistic.
    """
    if len(pairs) < MIN_PAIRS or n_resamples < 1:
        return None
    # Not a cryptographic use: a seeded PRNG is exactly the point, since the
    # interval must be reproducible from the seed recorded in the report.
    rng = random.Random(seed)  # noqa: S311
    size = len(pairs)
    estimates: list[float] = []
    for _ in range(n_resamples):
        picks = [pairs[rng.randrange(size)] for _ in range(size)]
        value = statistic([p[0] for p in picks], [p[1] for p in picks])
        if value is not None:
            estimates.append(value)
    if len(estimates) < 2:
        return None
    estimates.sort()
    tail = (1.0 - level) / 2.0
    last = len(estimates) - 1
    lower = estimates[min(last, max(0, math.floor(tail * last)))]
    upper = estimates[min(last, max(0, math.ceil((1.0 - tail) * last)))]
    return (lower, upper)


@dataclass(frozen=True)
class RepeatPair:
    """One evaluator's two blind encounters with the same fragrance version.

    Carries no role, no ``repeat_of_id`` and no blind code: a reliability
    consumer needs the two values and their identity, never the experimental
    design that produced them (X-06).

    Attributes:
        reviewer_id (str): The evaluator.
        fragrance_id (str): The version both encounters presented.
        first_observation_id (str): Observation on the original membership.
        repeat_observation_id (str): Observation on the repeat membership.
        first_liking (float): Liking recorded on the original, 0-10.
        repeat_liking (float): Liking recorded on the repeat, 0-10.
        stage (str): ``"BLOTTER"`` or ``"SKIN"``; both sides share it.
        first_observed_at (str): ISO-8601 timestamp of the original.
        repeat_observed_at (str): ISO-8601 timestamp of the repeat.
    """

    reviewer_id: str
    fragrance_id: str
    first_observation_id: str
    repeat_observation_id: str
    first_liking: float
    repeat_liking: float
    stage: str
    first_observed_at: str
    repeat_observed_at: str

    def to_dict(self) -> dict[str, object]:
        """Serialize to a JSON-safe dict.

        Returns:
            dict[str, object]: Every attribute, unchanged.
        """
        return {
            "reviewer_id": self.reviewer_id,
            "fragrance_id": self.fragrance_id,
            "first_observation_id": self.first_observation_id,
            "repeat_observation_id": self.repeat_observation_id,
            "first_liking": self.first_liking,
            "repeat_liking": self.repeat_liking,
            "stage": self.stage,
            "first_observed_at": self.first_observed_at,
            "repeat_observed_at": self.repeat_observed_at,
        }


def _is_locked(presentation: Presentation, stage: str) -> bool:
    locked = (
        presentation.skin_locked_at
        if stage == "SKIN"
        else presentation.blotter_locked_at
    )
    return locked is not None


async def repeat_pairs(
    session: AsyncSession, reviewer_id: str | None = None
) -> list[RepeatPair]:
    """Pair each hidden repeat with its original blind encounter.

    For every membership carrying a ``repeat_of_id``, the latest locked
    pre-reveal observation on the repeat's presentation is paired with the
    latest locked pre-reveal observation on the original membership's
    presentation, within the same enrollment and at the same stage. Only
    pairs where both likings are non-NULL are returned.

    Args:
        session (AsyncSession): Open database session.
        reviewer_id (str | None): Restrict to one evaluator; ``None`` pools
            every evaluator.

    Returns:
        list[RepeatPair]: Pairs ordered by evaluator, version and stage,
            blotter before skin.
    """
    statement = (
        select(Observation, Presentation, Membership, Enrollment)
        .join(Presentation, Observation.presentation_id == Presentation.id)
        .join(Membership, Presentation.membership_id == Membership.id)
        .join(CalibrationSession, Presentation.session_id == CalibrationSession.id)
        .join(Enrollment, CalibrationSession.enrollment_id == Enrollment.id)
        .where(Observation.phase == "PRE_REVEAL")
        .order_by(Observation.created_at.desc(), Observation.id.desc())
    )
    if reviewer_id is not None:
        statement = statement.where(Enrollment.reviewer_id == reviewer_id)
    # The four-entity select returns untyped Rows; naming the tuple shape
    # once here keeps the loop below fully typed instead of Any.
    rows = cast(
        "list[tuple[Observation, Presentation, Membership, Enrollment]]",
        (await session.execute(statement)).all(),
    )

    latest: dict[tuple[str, str, str], Observation] = {}
    memberships: dict[str, Membership] = {}
    reviewers: dict[str, str] = {}
    for observation, presentation, member, enrollment in rows:
        memberships[member.id] = member
        reviewers[enrollment.id] = enrollment.reviewer_id
        if not _is_locked(presentation, observation.stage):
            continue
        key = (enrollment.id, member.id, observation.stage)
        # Rows arrive newest first, so the first one seen for a key wins.
        latest.setdefault(key, observation)

    pairs: list[RepeatPair] = []
    for (enrollment_id, membership_id, stage), repeat in latest.items():
        member = memberships[membership_id]
        if member.repeat_of_id is None or stage not in _STAGES:
            continue
        original = latest.get((enrollment_id, member.repeat_of_id, stage))
        if original is None or original.liking is None or repeat.liking is None:
            continue
        pairs.append(
            RepeatPair(
                reviewer_id=reviewers[enrollment_id],
                fragrance_id=member.fragrance_id,
                first_observation_id=original.id,
                repeat_observation_id=repeat.id,
                first_liking=float(original.liking),
                repeat_liking=float(repeat.liking),
                stage=stage,
                first_observed_at=original.created_at.isoformat(),
                repeat_observed_at=repeat.created_at.isoformat(),
            )
        )
    pairs.sort(
        key=lambda p: (
            p.reviewer_id,
            p.fragrance_id,
            _STAGES.index(p.stage),
            p.repeat_observation_id,
        )
    )
    return pairs


@dataclass(frozen=True)
class ReliabilityReport:
    """Test-retest agreement over hidden repeats, with its caveat attached.

    Attributes:
        n_pairs (int): Number of repeat pairs the estimates rest on.
        per_reviewer (dict[str, int]): Pair count per evaluator, so a reader
            can see how thin the pooling is.
        spearman (float | None): Rank agreement between first and repeat.
        pearson (float | None): Linear agreement between first and repeat.
        mean_absolute_difference (float | None): Mean ``|first - repeat|``
            on the 0-10 liking scale.
        interval_spearman (tuple[float, float] | None): Percentile bootstrap
            interval for ``spearman``.
        note (str): ``RELIABILITY_NOTE``.
    """

    n_pairs: int
    per_reviewer: dict[str, int] = field(default_factory=dict)
    spearman: float | None = None
    pearson: float | None = None
    mean_absolute_difference: float | None = None
    interval_spearman: tuple[float, float] | None = None
    note: str = RELIABILITY_NOTE

    def to_dict(self) -> dict[str, object]:
        """Serialize to a JSON-safe dict.

        Returns:
            dict[str, object]: Every attribute, with the interval as a
                two-element list.
        """
        return {
            "n_pairs": self.n_pairs,
            "per_reviewer": dict(self.per_reviewer),
            "spearman": self.spearman,
            "pearson": self.pearson,
            "mean_absolute_difference": self.mean_absolute_difference,
            "interval_spearman": (
                None
                if self.interval_spearman is None
                else [self.interval_spearman[0], self.interval_spearman[1]]
            ),
            "note": self.note,
        }


def reliability_report(pairs: Sequence[RepeatPair]) -> ReliabilityReport:
    """Summarize repeat pairs into the noise ceiling.

    Args:
        pairs (Sequence[RepeatPair]): Pairs from ``repeat_pairs``.

    Returns:
        ReliabilityReport: Counts, agreement statistics and the bootstrap
            interval; statistics are ``None`` when there are too few pairs
            rather than being reported from a handful of points.
    """
    firsts = [pair.first_liking for pair in pairs]
    repeats = [pair.repeat_liking for pair in pairs]
    per_reviewer: dict[str, int] = {}
    for pair in pairs:
        per_reviewer[pair.reviewer_id] = per_reviewer.get(pair.reviewer_id, 0) + 1
    return ReliabilityReport(
        n_pairs=len(pairs),
        per_reviewer=per_reviewer,
        spearman=spearman(firsts, repeats),
        pearson=pearson(firsts, repeats),
        mean_absolute_difference=mean_absolute_difference(firsts, repeats),
        interval_spearman=bootstrap_interval(
            list(zip(firsts, repeats, strict=True)), spearman
        ),
    )


__all__ = [
    "MIN_PAIRS",
    "RELIABILITY_NOTE",
    "ReliabilityReport",
    "RepeatPair",
    "average_ranks",
    "bootstrap_interval",
    "mean_absolute_difference",
    "pearson",
    "reliability_report",
    "repeat_pairs",
    "spearman",
]
