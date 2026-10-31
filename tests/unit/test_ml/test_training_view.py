"""R8 PR 2: trainers read ``v_training_rows`` only (X-05, X-06).

Proves three things about ``ml.training_view`` and its callers
(``ml.dataset.build_examples``, ``ml.predict.predict_and_freeze``):

* for a reviewer whose rows are all ``eligible`` the view-built manifest is the
  legacy ``PreferenceHistoryService.training_manifest`` minus ``role`` and
  ``program_id``, plus ``revealed`` (behaviour unchanged);
* a row with any other code never reaches a trainer, a frozen prediction's
  manifest, or the profile a prediction is scored from;
* the input digest is deterministic over the rows read and changes when one
  of them changes.
"""

from __future__ import annotations

from datetime import timedelta

import pytest
from sqlalchemy import select

from fragrance_rater.core.vocabulary import EVIDENCE_TRAINING_ELIGIBILITIES
from fragrance_rater.ml.dataset import build_examples
from fragrance_rater.ml.predict import predict_and_freeze
from fragrance_rater.ml.training_view import (
    read_rows,
    read_training,
    rows_digest,
    training_manifest,
)
from fragrance_rater.models.evaluation import Evaluation
from fragrance_rater.models.prediction import PredictionSnapshot
from fragrance_rater.services.preference_history import PreferenceHistoryService
from fragrance_rater.utils.timestamps import now_naive_utc

INELIGIBLE = [code for code in EVIDENCE_TRAINING_ELIGIBILITIES if code != "eligible"]


def _evaluation(fragrance_id, rating, *, code="eligible", at=None, **extra):
    return Evaluation(
        fragrance_id=fragrance_id,
        reviewer_id="owner",
        rating=rating,
        evaluated_at=at or now_naive_utc(),
        training_eligibility=code,
        **extra,
    )


async def _eligible_world(program, observation_factory):
    """Every R7a structural case, with every row eligible."""
    session = program["session"]
    presentations = program["presentations"]
    start = now_naive_utc() - timedelta(hours=1)
    # Two answers on one locked sample: only the later one trains.
    session.add(
        observation_factory(
            presentations["UNIVERSAL_BASELINE"], liking=3, created_at=start
        )
    )
    session.add(
        observation_factory(
            presentations["UNIVERSAL_BASELINE"],
            liking=9,
            created_at=start + timedelta(minutes=5),
        )
    )
    # A later answer without liking hides the earlier one, in both readers.
    session.add(
        observation_factory(presentations["EXTRA_BASELINE"], liking=6, created_at=start)
    )
    session.add(
        observation_factory(
            presentations["EXTRA_BASELINE"],
            liking=None,
            created_at=start + timedelta(minutes=5),
        )
    )
    # Hidden repeats and holdouts never train.
    session.add(observation_factory(presentations["HIDDEN_REPEAT"], liking=8))
    session.add(observation_factory(presentations["HOLDOUT"], liking=8))
    # Ordinary: two encounters of one version (latest wins) and the holdout.
    session.add(_evaluation("extra", 2, at=start))
    session.add(_evaluation("extra", 5, at=start + timedelta(minutes=1)))
    session.add(_evaluation("holdout", 4))
    await session.flush()
    return session


def _legacy_shape(row: dict[str, object]) -> dict[str, object]:
    return {k: v for k, v in row.items() if k not in {"role", "program_id"}}


def _view_shape(row: dict[str, object]) -> dict[str, object]:
    return {k: v for k, v in row.items() if k != "revealed"}


@pytest.mark.asyncio
async def test_all_eligible_manifest_equals_the_legacy_manifest(
    program, observation_factory
):
    session = await _eligible_world(program, observation_factory)

    legacy = await PreferenceHistoryService(session).training_manifest("owner")
    current = await training_manifest(session, "owner")

    assert [_view_shape(row) for row in current] == [
        _legacy_shape(row) for row in legacy
    ]
    assert {row["fragrance_id"] for row in current} == {"baseline", "extra"}
    assert [row["rating"] for row in current] == [5, 9]


@pytest.mark.asyncio
async def test_the_manifest_never_carries_role_or_program(program, observation_factory):
    session = await _eligible_world(program, observation_factory)

    for row in await training_manifest(session, "owner"):
        assert "role" not in row
        assert "program_id" not in row
        assert row["revealed"] is (row["workflow"] == "ORDINARY")


@pytest.mark.asyncio
@pytest.mark.parametrize("code", INELIGIBLE)
async def test_an_ineligible_row_never_reaches_a_trainer(
    program, observation_factory, code
):
    session = program["session"]
    session.add(
        observation_factory(
            program["presentations"]["UNIVERSAL_BASELINE"], training_eligibility=code
        )
    )
    session.add(_evaluation("extra", 5, code=code))
    await session.flush()

    assert await read_rows(session, "owner") == []
    assert await training_manifest(session, "owner") == []
    assert await build_examples(session, "owner") == []
    # The legacy reader, which joins raw tables, would have trained on them.
    assert len(await PreferenceHistoryService(session).training_manifest("owner")) == 2


@pytest.mark.asyncio
@pytest.mark.parametrize("code", INELIGIBLE)
async def test_an_ineligible_row_never_reaches_a_frozen_prediction(
    program, observation_factory, code
):
    session = program["session"]
    session.add(_evaluation("baseline", 5))
    session.add(_evaluation("extra", 1, code=code))
    await session.flush()

    result = await predict_and_freeze(
        session, model_key="affinity-v1", reviewer_id="owner", recorded_by="m"
    )

    snapshot = await session.get(PredictionSnapshot, result.created[0])
    assert snapshot is not None
    assert [row["fragrance_id"] for row in snapshot.input_manifest] == ["baseline"]
    assert result.n_evidence == 1


@pytest.mark.asyncio
async def test_an_older_eligible_encounter_trains_when_the_latest_is_withheld(
    program,
):
    session = program["session"]
    start = now_naive_utc() - timedelta(hours=1)
    older = _evaluation("extra", 2, at=start)
    session.add(older)
    session.add(
        _evaluation("extra", 5, at=start + timedelta(minutes=1), code="withheld")
    )
    await session.flush()

    (row,) = await training_manifest(session, "owner")

    assert (row["id"], row["rating"]) == (older.id, 2)


@pytest.mark.asyncio
async def test_a_later_answer_of_any_code_supersedes_a_controlled_row(
    program, observation_factory
):
    """A sample's earlier blind answer was replaced, so it never trains."""
    session = program["session"]
    presentation = program["presentations"]["UNIVERSAL_BASELINE"]
    start = now_naive_utc() - timedelta(hours=1)
    session.add(observation_factory(presentation, liking=3, created_at=start))
    session.add(
        observation_factory(
            presentation,
            liking=9,
            created_at=start + timedelta(minutes=5),
            training_eligibility="withheld",
        )
    )
    await session.flush()

    assert await training_manifest(session, "owner") == []


@pytest.mark.asyncio
async def test_the_digest_is_deterministic_and_tracks_every_row(
    program, observation_factory
):
    session = await _eligible_world(program, observation_factory)

    first = await read_training(session, "owner")
    second = await read_training(session, "owner")
    assert first.input_digest == second.input_digest
    assert first.input_digest == rows_digest(list(reversed(first.rows)))
    assert len(first.input_digest) == 64

    # Changing one input row's label changes the digest.
    evaluation = await session.scalar(select(Evaluation).where(Evaluation.rating == 5))
    assert evaluation is not None
    evaluation.rating = 4
    await session.flush()
    relabeled = await read_training(session, "owner")
    assert relabeled.input_digest != first.input_digest

    # Withdrawing a row (eligibility) changes it too.
    evaluation.training_eligibility = "withheld"
    await session.flush()
    withdrawn = await read_training(session, "owner")
    assert withdrawn.input_digest not in {first.input_digest, relabeled.input_digest}
