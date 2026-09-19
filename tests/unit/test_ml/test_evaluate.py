"""Predicted-versus-observed metrics over outcome-linked prediction snapshots."""

import json
import math

import pytest

from fragrance_rater.ml.evaluate import (
    HoldoutScorecard,
    PredictionOutcome,
    linked_outcomes,
    precision_at_k,
    scorecard,
)
from fragrance_rater.ml.reliability import RepeatPair, reliability_report
from fragrance_rater.models.evaluation import Evaluation
from fragrance_rater.models.prediction import PredictionSnapshot
from fragrance_rater.utils.timestamps import now_naive_utc


def _snapshot(
    *,
    identifier,
    predicted=7.0,
    reviewer_id="owner",
    fragrance_id="baseline",
    model_id="affinity",
    model_version="v1",
    scale="0-10",
    evaluation_id=None,
    observation_id=None,
):
    """Build a frozen snapshot already linked to one real outcome."""
    return PredictionSnapshot(
        id=identifier,
        reviewer_id=reviewer_id,
        fragrance_id=fragrance_id,
        model_id=model_id,
        model_version=model_version,
        predicted_scale=scale,
        predicted_rating=predicted,
        outcome_evaluation_id=evaluation_id,
        outcome_observation_id=observation_id,
        outcome_linked_at=(
            now_naive_utc() if (evaluation_id or observation_id) is not None else None
        ),
        outcome_recorded_by="manager",
    )


def _outcome(
    *,
    predicted,
    observed,
    reviewer_id="owner",
    model_id="affinity",
    model_version="v1",
    scale="0-10",
    identifier="p1",
    kind="observation",
):
    return PredictionOutcome(
        reviewer_id=reviewer_id,
        fragrance_id="baseline",
        model_id=model_id,
        model_version=model_version,
        predicted=predicted,
        observed=observed,
        scale=scale,
        prediction_id=identifier,
        outcome_kind=kind,
    )


class TestLinkedOutcomes:
    @pytest.mark.asyncio
    async def test_both_outcome_kinds_are_read(self, program, observation_factory):
        session = program["session"]
        observation = observation_factory(
            program["presentations"]["UNIVERSAL_BASELINE"], liking=9
        )
        evaluation = Evaluation(
            id="ev-1", fragrance_id="extra", reviewer_id="owner", rating=4
        )
        session.add_all([observation, evaluation])
        await session.flush()
        session.add_all(
            [
                _snapshot(
                    identifier="p-obs", predicted=7.5, observation_id=observation.id
                ),
                _snapshot(
                    identifier="p-eval",
                    predicted=3.5,
                    fragrance_id="extra",
                    scale="1-5",
                    evaluation_id=evaluation.id,
                ),
            ]
        )
        await session.flush()

        outcomes = {row.prediction_id: row for row in await linked_outcomes(session)}
        assert set(outcomes) == {"p-obs", "p-eval"}
        controlled = outcomes["p-obs"]
        assert (controlled.observed, controlled.scale) == (9.0, "0-10")
        assert controlled.outcome_kind == "observation"
        ordinary = outcomes["p-eval"]
        assert (ordinary.observed, ordinary.scale) == (4.0, "1-5")
        assert ordinary.outcome_kind == "evaluation"
        assert json.dumps(ordinary.to_dict())

    @pytest.mark.asyncio
    async def test_unlinked_snapshot_is_ignored(self, program):
        session = program["session"]
        session.add(_snapshot(identifier="p-none"))
        await session.flush()
        assert await linked_outcomes(session) == []

    @pytest.mark.asyncio
    async def test_null_prediction_is_skipped(self, program, observation_factory):
        session = program["session"]
        observation = observation_factory(
            program["presentations"]["UNIVERSAL_BASELINE"], liking=9
        )
        session.add(observation)
        await session.flush()
        session.add(
            _snapshot(
                identifier="p-null", predicted=None, observation_id=observation.id
            )
        )
        await session.flush()
        assert await linked_outcomes(session) == []

    @pytest.mark.asyncio
    async def test_null_observed_liking_is_skipped(self, program, observation_factory):
        session = program["session"]
        observation = observation_factory(
            program["presentations"]["UNIVERSAL_BASELINE"], liking=None
        )
        session.add(observation)
        await session.flush()
        session.add(_snapshot(identifier="p-undetected", observation_id=observation.id))
        await session.flush()
        assert await linked_outcomes(session) == []

    @pytest.mark.asyncio
    async def test_reviewer_and_model_filters(self, program, observation_factory):
        session = program["session"]
        observation = observation_factory(
            program["presentations"]["UNIVERSAL_BASELINE"], liking=9
        )
        session.add(observation)
        await session.flush()
        session.add_all(
            [
                _snapshot(identifier="p-a", observation_id=observation.id),
                _snapshot(
                    identifier="p-b",
                    observation_id=observation.id,
                    reviewer_id="other",
                    model_id="ridge",
                ),
            ]
        )
        await session.flush()

        assert len(await linked_outcomes(session)) == 2
        assert [
            row.prediction_id
            for row in await linked_outcomes(session, reviewer_id="other")
        ] == ["p-b"]
        assert [
            row.prediction_id
            for row in await linked_outcomes(session, model_id="affinity")
        ] == ["p-a"]


class TestScorecard:
    def test_hand_computed_error_and_rank_agreement(self):
        outcomes = [
            _outcome(predicted=1.0, observed=2.0, identifier="a"),
            _outcome(predicted=2.0, observed=4.0, identifier="b"),
            _outcome(predicted=3.0, observed=3.0, identifier="c"),
        ]
        (card,) = scorecard(outcomes)
        assert card.n == 3
        assert card.mae == pytest.approx(1.0)
        assert card.rmse == pytest.approx(math.sqrt(5.0 / 3.0))
        assert card.spearman == pytest.approx(0.5)
        assert card.interval_mae is not None
        assert card.interval_mae[0] <= card.mae <= card.interval_mae[1]

    def test_grouped_by_model_version_and_scale(self):
        outcomes = [
            _outcome(predicted=1.0, observed=2.0, identifier="a"),
            _outcome(predicted=1.0, observed=2.0, model_version="v2", identifier="b"),
            _outcome(
                predicted=1.0,
                observed=2.0,
                scale="1-5",
                kind="evaluation",
                identifier="c",
            ),
            _outcome(predicted=4.0, observed=5.0, model_id="ridge", identifier="d"),
        ]
        cards = scorecard(outcomes)
        assert [
            (card.model_id, card.model_version, card.scale, card.n) for card in cards
        ] == [
            ("affinity", "v1", "0-10", 1),
            ("affinity", "v1", "1-5", 1),
            ("affinity", "v2", "0-10", 1),
            ("ridge", "v1", "0-10", 1),
        ]

    def test_per_reviewer_carries_n_and_mae(self):
        outcomes = [
            _outcome(predicted=1.0, observed=2.0, identifier="a"),
            _outcome(predicted=2.0, observed=5.0, identifier="b"),
            _outcome(predicted=4.0, observed=4.0, reviewer_id="other", identifier="c"),
        ]
        (card,) = scorecard(outcomes)
        assert card.per_reviewer == {
            "other": {"n": 1, "mae": 0.0},
            "owner": {"n": 2, "mae": 2.0},
        }

    def test_single_outcome_has_n_but_no_interval_or_correlation(self):
        (card,) = scorecard([_outcome(predicted=1.0, observed=2.0)])
        assert card.n == 1
        assert card.mae == 1.0
        assert card.rmse == 1.0
        assert card.spearman is None
        assert card.interval_mae is None

    def test_empty_outcomes(self):
        assert scorecard([]) == []

    def test_noise_ceiling_is_attached_and_serializes(self):
        ceiling = reliability_report(
            [
                RepeatPair(
                    reviewer_id="owner",
                    fragrance_id=f"f{i}",
                    first_observation_id=f"a{i}",
                    repeat_observation_id=f"b{i}",
                    first_liking=float(i),
                    repeat_liking=float(i) + 1.0,
                    stage="BLOTTER",
                    first_observed_at="2026-01-01T00:00:00",
                    repeat_observed_at="2026-01-02T00:00:00",
                )
                for i in range(4)
            ]
        )
        (card,) = scorecard(
            [
                _outcome(predicted=1.0, observed=2.0, identifier="a"),
                _outcome(predicted=2.0, observed=4.0, identifier="b"),
                _outcome(predicted=3.0, observed=3.0, identifier="c"),
            ],
            ceiling=ceiling,
        )
        payload = card.to_dict()
        assert json.loads(json.dumps(payload))["n"] == 3
        assert payload["noise_ceiling"]["n_pairs"] == 4
        assert isinstance(payload["interval_mae"], list)
        assert "accuracy" not in payload
        assert payload["per_reviewer"]["owner"]["n"] == 3

    def test_to_dict_without_a_ceiling(self):
        payload = HoldoutScorecard(
            model_id="affinity", model_version="v1", scale="0-10", n=0
        ).to_dict()
        assert payload["noise_ceiling"] is None
        assert payload["interval_mae"] is None
        assert payload["per_reviewer"] == {}
        json.dumps(payload)


class TestPrecisionAtK:
    def test_top_k_window(self):
        assert precision_at_k([True, False, True, False], 2) == 0.5
        assert precision_at_k([True, False, True, False], 4) == 0.5

    def test_k_beyond_the_list_uses_the_shorter_denominator(self):
        assert precision_at_k([True, False, True], 10) == pytest.approx(2 / 3)

    def test_all_relevant_and_none_relevant(self):
        assert precision_at_k([True, True], 2) == 1.0
        assert precision_at_k([False, False], 2) == 0.0

    def test_non_positive_k_is_none(self):
        assert precision_at_k([True], 0) is None
        assert precision_at_k([True], -1) is None

    def test_empty_ranking_is_none_not_zero(self):
        assert precision_at_k([], 5) is None
