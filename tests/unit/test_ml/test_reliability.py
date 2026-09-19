"""Hidden-repeat pairing and the pooled noise-ceiling report."""

import json
import math
from datetime import timedelta

import pytest

from fragrance_rater.ml.reliability import (
    RELIABILITY_NOTE,
    RepeatPair,
    average_ranks,
    bootstrap_interval,
    mean_absolute_difference,
    pearson,
    reliability_report,
    repeat_pairs,
    spearman,
)
from fragrance_rater.utils.timestamps import now_naive_utc


def _pair(reviewer="owner", first=8.0, repeat=7.0, suffix="1", stage="BLOTTER"):
    return RepeatPair(
        reviewer_id=reviewer,
        fragrance_id=f"f{suffix}",
        first_observation_id=f"o{suffix}a",
        repeat_observation_id=f"o{suffix}b",
        first_liking=first,
        repeat_liking=repeat,
        stage=stage,
        first_observed_at="2026-01-01T00:00:00",
        repeat_observed_at="2026-01-02T00:00:00",
    )


class TestPearson:
    def test_perfect_positive_and_negative(self):
        assert pearson([1.0, 2.0, 3.0], [2.0, 4.0, 6.0]) == pytest.approx(1.0)
        assert pearson([1.0, 2.0, 3.0], [6.0, 4.0, 2.0]) == pytest.approx(-1.0)

    def test_known_value(self):
        assert pearson([1.0, 2.0, 3.0], [1.0, 3.0, 2.0]) == pytest.approx(0.5)

    def test_too_few_pairs_is_none(self):
        assert pearson([1.0, 2.0], [1.0, 2.0]) is None

    def test_length_mismatch_is_none(self):
        assert pearson([1.0, 2.0, 3.0], [1.0, 2.0]) is None

    def test_zero_variance_is_none_not_zero(self):
        assert pearson([5.0, 5.0, 5.0], [1.0, 2.0, 3.0]) is None
        assert pearson([1.0, 2.0, 3.0], [5.0, 5.0, 5.0]) is None


class TestAverageRanks:
    def test_ties_share_the_mean_rank(self):
        assert average_ranks([10.0, 20.0, 20.0, 30.0]) == [1.0, 2.5, 2.5, 4.0]

    def test_all_tied(self):
        assert average_ranks([4.0, 4.0, 4.0]) == [2.0, 2.0, 2.0]

    def test_unsorted_input(self):
        assert average_ranks([30.0, 10.0, 20.0]) == [3.0, 1.0, 2.0]

    def test_empty(self):
        assert average_ranks([]) == []


class TestSpearman:
    def test_monotone_but_nonlinear_is_one(self):
        assert spearman([1.0, 2.0, 3.0, 4.0], [1.0, 4.0, 9.0, 16.0]) == pytest.approx(
            1.0
        )

    def test_ties_use_average_ranks(self):
        # x ranks 1, 2.5, 2.5, 4; y ranks 1, 2, 3, 4 -> r = 0.9486832...
        value = spearman([1.0, 2.0, 2.0, 3.0], [1.0, 2.0, 3.0, 4.0])
        assert value == pytest.approx(3.0 / math.sqrt(10.0))

    def test_fully_tied_series_is_none(self):
        assert spearman([2.0, 2.0, 2.0], [1.0, 2.0, 3.0]) is None

    def test_too_few_pairs_is_none(self):
        assert spearman([1.0, 2.0], [1.0, 2.0]) is None

    def test_length_mismatch_is_none(self):
        assert spearman([1.0, 2.0, 3.0], [1.0]) is None


class TestMeanAbsoluteDifference:
    def test_hand_computed(self):
        assert mean_absolute_difference([1.0, 2.0, 3.0], [2.0, 2.0, 5.0]) == 1.0

    def test_empty_is_none(self):
        assert mean_absolute_difference([], []) is None

    def test_length_mismatch_is_none(self):
        assert mean_absolute_difference([1.0], [1.0, 2.0]) is None


class TestBootstrapInterval:
    def test_same_seed_is_deterministic(self):
        pairs = [(float(i), float(i % 4)) for i in range(12)]
        first = bootstrap_interval(pairs, spearman, n_resamples=200, seed=7)
        second = bootstrap_interval(pairs, spearman, n_resamples=200, seed=7)
        assert first == second
        assert first is not None
        assert first[0] <= first[1]

    def test_a_different_seed_gives_a_different_draw(self):
        pairs = [(float(i), float((7 * i) % 11)) for i in range(15)]
        assert bootstrap_interval(
            pairs, spearman, n_resamples=200, seed=1
        ) != bootstrap_interval(pairs, spearman, n_resamples=200, seed=2)

    def test_identical_pairs_collapse_to_a_point(self):
        pairs = [(1.0, 2.0), (2.0, 3.0), (3.0, 4.0), (4.0, 5.0)]
        interval = bootstrap_interval(
            pairs, mean_absolute_difference, n_resamples=50, seed=0
        )
        assert interval == (1.0, 1.0)

    def test_too_few_pairs_is_none(self):
        assert bootstrap_interval([(1.0, 2.0), (2.0, 3.0)], spearman) is None

    def test_no_resamples_is_none(self):
        pairs = [(float(i), float(i)) for i in range(5)]
        assert bootstrap_interval(pairs, spearman, n_resamples=0) is None

    def test_all_undefined_statistics_is_none(self):
        pairs = [(1.0, 1.0), (1.0, 1.0), (1.0, 1.0), (1.0, 1.0)]
        assert bootstrap_interval(pairs, spearman, n_resamples=20) is None

    def test_level_widens_the_interval(self):
        pairs = [(float(i), float((i * 3) % 7)) for i in range(20)]
        narrow = bootstrap_interval(
            pairs, mean_absolute_difference, n_resamples=300, seed=3, level=0.50
        )
        wide = bootstrap_interval(
            pairs, mean_absolute_difference, n_resamples=300, seed=3, level=0.99
        )
        assert narrow is not None
        assert wide is not None
        assert (wide[1] - wide[0]) >= (narrow[1] - narrow[0])


class TestRepeatPairs:
    @pytest.mark.asyncio
    async def test_finds_the_blotter_pair(self, program, observation_factory):
        session = program["session"]
        earlier = now_naive_utc() - timedelta(days=1)
        first = observation_factory(
            program["presentations"]["UNIVERSAL_BASELINE"],
            liking=8,
            created_at=earlier,
        )
        repeat = observation_factory(
            program["presentations"]["HIDDEN_REPEAT"], liking=6
        )
        session.add_all([first, repeat])
        await session.flush()

        (pair,) = await repeat_pairs(session)
        assert pair.reviewer_id == "owner"
        assert pair.fragrance_id == "baseline"
        assert pair.first_observation_id == first.id
        assert pair.repeat_observation_id == repeat.id
        assert (pair.first_liking, pair.repeat_liking) == (8.0, 6.0)
        assert pair.stage == "BLOTTER"
        assert pair.first_observed_at == earlier.isoformat()
        assert json.dumps(pair.to_dict())
        assert "role" not in pair.to_dict()
        assert "repeat_of_id" not in pair.to_dict()

    @pytest.mark.asyncio
    async def test_latest_observation_on_each_side_wins(
        self, program, observation_factory
    ):
        session = program["session"]
        old = observation_factory(
            program["presentations"]["UNIVERSAL_BASELINE"],
            liking=1,
            created_at=now_naive_utc() - timedelta(days=2),
        )
        newest = observation_factory(
            program["presentations"]["UNIVERSAL_BASELINE"], liking=9
        )
        session.add_all(
            [
                old,
                newest,
                observation_factory(
                    program["presentations"]["HIDDEN_REPEAT"], liking=6
                ),
            ]
        )
        await session.flush()

        (pair,) = await repeat_pairs(session)
        assert pair.first_liking == 9.0
        assert pair.first_observation_id == newest.id

    @pytest.mark.asyncio
    async def test_unlocked_stage_yields_no_pair(self, program, observation_factory):
        session = program["session"]
        program["presentations"]["HIDDEN_REPEAT"].blotter_locked_at = None
        session.add_all(
            [
                observation_factory(program["presentations"]["UNIVERSAL_BASELINE"]),
                observation_factory(program["presentations"]["HIDDEN_REPEAT"]),
            ]
        )
        await session.flush()
        assert await repeat_pairs(session) == []

    @pytest.mark.asyncio
    async def test_null_liking_yields_no_pair(self, program, observation_factory):
        session = program["session"]
        session.add_all(
            [
                observation_factory(program["presentations"]["UNIVERSAL_BASELINE"]),
                observation_factory(
                    program["presentations"]["HIDDEN_REPEAT"], liking=None
                ),
            ]
        )
        await session.flush()
        assert await repeat_pairs(session) == []

    @pytest.mark.asyncio
    async def test_post_reveal_observations_are_not_paired(
        self, program, observation_factory
    ):
        session = program["session"]
        session.add_all(
            [
                observation_factory(program["presentations"]["UNIVERSAL_BASELINE"]),
                observation_factory(
                    program["presentations"]["HIDDEN_REPEAT"], phase="POST_REVEAL"
                ),
            ]
        )
        await session.flush()
        assert await repeat_pairs(session) == []

    @pytest.mark.asyncio
    async def test_skin_pair_reported_when_both_sides_are_locked(
        self, program, observation_factory
    ):
        session = program["session"]
        for role in ("UNIVERSAL_BASELINE", "HIDDEN_REPEAT"):
            program["presentations"][role].skin_locked_at = now_naive_utc()
            session.add(observation_factory(program["presentations"][role], liking=5))
            session.add(
                observation_factory(
                    program["presentations"][role], liking=4, stage="SKIN"
                )
            )
        await session.flush()

        pairs = await repeat_pairs(session)
        assert [pair.stage for pair in pairs] == ["BLOTTER", "SKIN"]

    @pytest.mark.asyncio
    async def test_reviewer_filter(self, program, observation_factory):
        session = program["session"]
        session.add_all(
            [
                observation_factory(program["presentations"]["UNIVERSAL_BASELINE"]),
                observation_factory(
                    program["presentations"]["HIDDEN_REPEAT"], liking=6
                ),
            ]
        )
        await session.flush()
        assert len(await repeat_pairs(session, "owner")) == 1
        assert await repeat_pairs(session, "other") == []

    @pytest.mark.asyncio
    async def test_no_observations_at_all(self, program):
        assert await repeat_pairs(program["session"]) == []


class TestReliabilityReport:
    def test_counts_statistics_and_note(self):
        pairs = [
            _pair(first=8.0, repeat=7.0, suffix="1"),
            _pair(first=5.0, repeat=6.0, suffix="2"),
            _pair(first=2.0, repeat=3.0, suffix="3"),
            _pair(reviewer="other", first=9.0, repeat=9.0, suffix="4"),
        ]
        report = reliability_report(pairs)
        assert report.n_pairs == 4
        assert report.per_reviewer == {"owner": 3, "other": 1}
        assert report.mean_absolute_difference == pytest.approx(0.75)
        assert report.pearson is not None
        assert report.spearman is not None
        assert report.interval_spearman is not None
        assert report.note == RELIABILITY_NOTE
        assert "ADR-009" in report.note
        assert "X-08" in report.note

    def test_empty_report_is_all_none_with_zero_n(self):
        report = reliability_report([])
        assert report.n_pairs == 0
        assert report.per_reviewer == {}
        assert report.spearman is None
        assert report.pearson is None
        assert report.mean_absolute_difference is None
        assert report.interval_spearman is None

    def test_to_dict_is_json_serializable(self):
        pairs = [
            _pair(first=float(i), repeat=float(i + 1), suffix=str(i)) for i in range(5)
        ]
        payload = reliability_report(pairs).to_dict()
        assert json.loads(json.dumps(payload))["n_pairs"] == 5
        assert isinstance(payload["interval_spearman"], list)
        assert "accuracy" not in payload

    def test_interval_is_none_without_enough_pairs(self):
        report = reliability_report([_pair(suffix="1"), _pair(suffix="2")])
        assert report.n_pairs == 2
        assert report.interval_spearman is None
        assert report.to_dict()["interval_spearman"] is None
