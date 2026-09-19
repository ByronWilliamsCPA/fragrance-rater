"""Predicted-versus-observed metrics over frozen, outcome-linked predictions.

No code in this project compared a prediction to what actually happened:
``RecommendationMeasurementService.metrics()`` reports counts and a mean
ordinary rating, and a repo-wide search for an error, rank-correlation or
ranking metric found nothing (ML structure review M-10).

This module reads the prospective record the schema already guarantees. A
``PredictionSnapshot`` is frozen before the encounter exists and exactly one
real outcome is linked to it afterwards, under a row lock, so every pair this
module returns is genuinely out-of-sample.

Reporting rules, from ADR-009 and review finding M-11:

- Every rate is accompanied by its ``n``. There is no ``accuracy`` field
  anywhere: on a 0-10 liking scale a hit rate would require an arbitrary
  threshold, and on 40 pooled holdouts it would be noise with a decimal
  point.
- Reports are grouped by ``(model_id, model_version, scale)`` so two models
  are compared under one denominator, and the two scales are never pooled:
  an ordinary 1-5 rating and a controlled 0-10 liking have no calibrated map
  between them (ADR-007).
- Every report object serializes through ``to_dict()``.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from sqlalchemy import select

from fragrance_rater.ml.reliability import (
    ReliabilityReport,
    bootstrap_interval,
    mean_absolute_difference,
    spearman,
)
from fragrance_rater.models.calibration import Observation
from fragrance_rater.models.evaluation import Evaluation
from fragrance_rater.models.prediction import PredictionSnapshot

if TYPE_CHECKING:
    from collections.abc import Sequence

    from sqlalchemy.ext.asyncio import AsyncSession

EVALUATION_SCALE = "1-5"
"""Scale of an ordinary ``Evaluation.rating`` outcome."""

OBSERVATION_SCALE = "0-10"
"""Scale of a controlled ``Observation.liking`` outcome."""


@dataclass(frozen=True)
class PredictionOutcome:
    """One frozen prediction beside the single real outcome linked to it.

    Attributes:
        reviewer_id (str): The evaluator the prediction was made for.
        fragrance_id (str): The fragrance version predicted.
        model_id (str): Model family that produced the prediction.
        model_version (str): Version within that family.
        predicted (float): The frozen predicted value.
        observed (float): The linked outcome's value.
        scale (str): ``"1-5"`` or ``"0-10"``, taken from the outcome kind,
            so predicted and observed are always on one scale.
        prediction_id (str): ``PredictionSnapshot.id``.
        outcome_kind (str): ``"evaluation"`` or ``"observation"``.
    """

    reviewer_id: str
    fragrance_id: str
    model_id: str
    model_version: str
    predicted: float
    observed: float
    scale: str
    prediction_id: str
    outcome_kind: str

    def to_dict(self) -> dict[str, object]:
        """Serialize to a JSON-safe dict.

        Returns:
            dict[str, object]: Every attribute, unchanged.
        """
        return {
            "reviewer_id": self.reviewer_id,
            "fragrance_id": self.fragrance_id,
            "model_id": self.model_id,
            "model_version": self.model_version,
            "predicted": self.predicted,
            "observed": self.observed,
            "scale": self.scale,
            "prediction_id": self.prediction_id,
            "outcome_kind": self.outcome_kind,
        }


async def _observed_values(
    session: AsyncSession, snapshots: Sequence[PredictionSnapshot]
) -> tuple[dict[str, int], dict[str, int | None]]:
    """Batch-load the outcome values the snapshots point at."""
    evaluation_ids = {
        s.outcome_evaluation_id for s in snapshots if s.outcome_evaluation_id
    }
    observation_ids = {
        s.outcome_observation_id for s in snapshots if s.outcome_observation_id
    }
    ratings: dict[str, int] = {}
    if evaluation_ids:
        ratings = {
            row.id: row.rating
            for row in await session.scalars(
                select(Evaluation).where(Evaluation.id.in_(evaluation_ids))
            )
        }
    likings: dict[str, int | None] = {}
    if observation_ids:
        likings = {
            row.id: row.liking
            for row in await session.scalars(
                select(Observation).where(Observation.id.in_(observation_ids))
            )
        }
    return ratings, likings


def _outcome_for(
    snapshot: PredictionSnapshot,
    ratings: dict[str, int],
    likings: dict[str, int | None],
) -> tuple[float, str, str] | None:
    """Return ``(observed, scale, kind)`` for a snapshot, or ``None``."""
    if snapshot.outcome_evaluation_id is not None:
        rating = ratings.get(snapshot.outcome_evaluation_id)
        if rating is None:
            return None
        return (float(rating), EVALUATION_SCALE, "evaluation")
    if snapshot.outcome_observation_id is not None:
        liking = likings.get(snapshot.outcome_observation_id)
        if liking is None:
            return None
        return (float(liking), OBSERVATION_SCALE, "observation")
    return None


async def linked_outcomes(
    session: AsyncSession,
    *,
    reviewer_id: str | None = None,
    model_id: str | None = None,
) -> list[PredictionOutcome]:
    """Load every frozen prediction that has a real outcome linked to it.

    Args:
        session (AsyncSession): Open database session.
        reviewer_id (str | None): Restrict to one evaluator.
        model_id (str | None): Restrict to one model family.

    Returns:
        list[PredictionOutcome]: Pairs in prediction-creation order. Rows
            whose ``predicted_rating`` or whose linked outcome value is NULL
            are skipped: a NULL liking means the evaluator could not detect
            the fragrance, which is evidence about the stimulus and not an
            error the model can be charged with.
    """
    statement = (
        select(PredictionSnapshot)
        .where(PredictionSnapshot.outcome_linked_at.is_not(None))
        .order_by(PredictionSnapshot.created_at, PredictionSnapshot.id)
    )
    if reviewer_id is not None:
        statement = statement.where(PredictionSnapshot.reviewer_id == reviewer_id)
    if model_id is not None:
        statement = statement.where(PredictionSnapshot.model_id == model_id)
    snapshots = list(await session.scalars(statement))
    ratings, likings = await _observed_values(session, snapshots)

    outcomes: list[PredictionOutcome] = []
    for snapshot in snapshots:
        if snapshot.predicted_rating is None:
            continue
        resolved = _outcome_for(snapshot, ratings, likings)
        if resolved is None:
            continue
        observed, scale, kind = resolved
        outcomes.append(
            PredictionOutcome(
                reviewer_id=snapshot.reviewer_id,
                fragrance_id=snapshot.fragrance_id,
                model_id=snapshot.model_id,
                model_version=snapshot.model_version,
                predicted=float(snapshot.predicted_rating),
                observed=observed,
                scale=scale,
                prediction_id=snapshot.id,
                outcome_kind=kind,
            )
        )
    return outcomes


@dataclass(frozen=True)
class HoldoutScorecard:
    """Error and rank agreement for one model version on one scale.

    Attributes:
        model_id (str): Model family.
        model_version (str): Version within the family.
        scale (str): ``"1-5"`` or ``"0-10"``; scales are never pooled.
        n (int): Number of predicted/observed pairs behind every figure.
        mae (float | None): Mean absolute error.
        rmse (float | None): Root mean squared error.
        spearman (float | None): Rank correlation of predicted vs observed.
        interval_mae (tuple[float, float] | None): Percentile bootstrap
            interval for ``mae``.
        per_reviewer (dict[str, dict[str, float | int | None]]): Per
            evaluator ``{"n": int, "mae": float | None}``, since ADR-009
            requires results reported per evaluator as well as pooled.
        noise_ceiling (ReliabilityReport | None): The hidden-repeat ceiling
            this result must be read against; a model beating the ceiling is
            fitting noise, not preference.
    """

    model_id: str
    model_version: str
    scale: str
    n: int
    mae: float | None = None
    rmse: float | None = None
    spearman: float | None = None
    interval_mae: tuple[float, float] | None = None
    per_reviewer: dict[str, dict[str, float | int | None]] = field(default_factory=dict)
    noise_ceiling: ReliabilityReport | None = None

    def to_dict(self) -> dict[str, object]:
        """Serialize to a JSON-safe dict.

        Returns:
            dict[str, object]: Every attribute, with the interval as a
                two-element list and the ceiling recursively serialized.
        """
        return {
            "model_id": self.model_id,
            "model_version": self.model_version,
            "scale": self.scale,
            "n": self.n,
            "mae": self.mae,
            "rmse": self.rmse,
            "spearman": self.spearman,
            "interval_mae": (
                None
                if self.interval_mae is None
                else [self.interval_mae[0], self.interval_mae[1]]
            ),
            "per_reviewer": {
                reviewer: dict(values) for reviewer, values in self.per_reviewer.items()
            },
            "noise_ceiling": (
                None if self.noise_ceiling is None else self.noise_ceiling.to_dict()
            ),
        }


def _root_mean_square_error(
    predicted: Sequence[float], observed: Sequence[float]
) -> float | None:
    if not predicted:
        return None
    squared = [(p - o) ** 2 for p, o in zip(predicted, observed, strict=True)]
    return math.sqrt(sum(squared) / len(squared))


def _per_reviewer_rows(
    outcomes: Sequence[PredictionOutcome],
) -> dict[str, dict[str, float | int | None]]:
    grouped: dict[str, list[PredictionOutcome]] = {}
    for outcome in outcomes:
        grouped.setdefault(outcome.reviewer_id, []).append(outcome)
    return {
        reviewer: {
            "n": len(rows),
            "mae": mean_absolute_difference(
                [row.predicted for row in rows], [row.observed for row in rows]
            ),
        }
        for reviewer, rows in sorted(grouped.items())
    }


def scorecard(
    outcomes: Sequence[PredictionOutcome],
    *,
    ceiling: ReliabilityReport | None = None,
) -> list[HoldoutScorecard]:
    """Summarize linked outcomes into one scorecard per model and scale.

    Args:
        outcomes (Sequence[PredictionOutcome]): Pairs from
            ``linked_outcomes``.
        ceiling (ReliabilityReport | None): The hidden-repeat noise ceiling
            to attach to every scorecard.

    Returns:
        list[HoldoutScorecard]: One card per ``(model_id, model_version,
            scale)``, sorted by that key. Every figure carries its ``n``.
    """
    grouped: dict[tuple[str, str, str], list[PredictionOutcome]] = {}
    for outcome in outcomes:
        key = (outcome.model_id, outcome.model_version, outcome.scale)
        grouped.setdefault(key, []).append(outcome)

    cards: list[HoldoutScorecard] = []
    for (model_id, model_version, scale), rows in sorted(grouped.items()):
        predicted = [row.predicted for row in rows]
        observed = [row.observed for row in rows]
        cards.append(
            HoldoutScorecard(
                model_id=model_id,
                model_version=model_version,
                scale=scale,
                n=len(rows),
                mae=mean_absolute_difference(predicted, observed),
                rmse=_root_mean_square_error(predicted, observed),
                spearman=spearman(predicted, observed),
                interval_mae=bootstrap_interval(
                    list(zip(predicted, observed, strict=True)),
                    mean_absolute_difference,
                ),
                per_reviewer=_per_reviewer_rows(rows),
                noise_ceiling=ceiling,
            )
        )
    return cards


def precision_at_k(ranked_interest: Sequence[bool], k: int) -> float | None:
    """Return precision at ``k`` over a ranked list of interest flags.

    A funnel metric only (review Section 3): it says how many of the top
    ``k`` shown candidates drew interest, not how well liking is predicted.
    Report it beside its denominator, which is ``min(k, len(...))`` when the
    ranked list is shorter than ``k``.

    Args:
        ranked_interest (Sequence[bool]): Interest flags in rank order,
            best-ranked first.
        k (int): Cut-off.

    Returns:
        float | None: Fraction of the first ``k`` entries that drew
            interest, or ``None`` when ``k`` is not positive or the ranked
            list is empty (a rate over zero candidates is undefined, not
            zero).
    """
    if k <= 0 or not ranked_interest:
        return None
    window = list(ranked_interest[:k])
    return sum(1 for flag in window if flag) / len(window)


__all__ = [
    "EVALUATION_SCALE",
    "OBSERVATION_SCALE",
    "HoldoutScorecard",
    "PredictionOutcome",
    "linked_outcomes",
    "precision_at_k",
    "scorecard",
]
