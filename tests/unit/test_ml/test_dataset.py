"""Uniform training rows, target selection, and array export."""

import json

import pytest

from fragrance_rater.ml.dataset import (
    FEATURE_SPACES,
    PERCEPTION_DIMENSIONS,
    TARGETS,
    TrainingRow,
    build_examples,
    resolve_target,
    rows_from_manifest,
    split_for,
    to_arrays,
)
from fragrance_rater.ml.feature_space import AccordFeature, FeatureVector, NoteFeature
from fragrance_rater.models.evaluation import Evaluation
from fragrance_rater.utils.timestamps import now_naive_utc


def _row(
    *,
    label=8.0,
    notes=(("n1", "One", "top"),),
    accords=(("citrus", 0.8),),
    family="woody",
    subfamily="aromatic",
    observation_features=None,
    reviewer_id="owner",
):
    """Build a TrainingRow directly, for the pure array-export tests."""
    return TrainingRow(
        reviewer_id=reviewer_id,
        fragrance_id="f1",
        source_row_id="r1",
        workflow="CONTROLLED",
        scale="0-10",
        label=label,
        target="liking",
        stage="BLOTTER",
        phase="PRE_REVEAL",
        program_id="p1",
        observed_at="2026-01-01T00:00:00",
        features=FeatureVector(
            fragrance_id="f1",
            version_key="f1-key",
            concentration="EDP",
            primary_family=family,
            subfamily=subfamily,
            notes=tuple(NoteFeature(i, n, p) for i, n, p in notes),
            accords=tuple(AccordFeature(n, w) for n, w in accords),
        ),
        observation_features=observation_features,
        notes_text=None,
        split="DEV",
        contributed_to_affinity_v1=True,
    )


class TestSplitFor:
    def test_holdout_and_repeat_and_default(self):
        assert split_for("HOLDOUT") == "HOLDOUT"
        assert split_for("HIDDEN_REPEAT") == "REPEAT"
        assert split_for("UNIVERSAL_BASELINE") == "DEV"
        assert split_for("ACTIVE_LEARNING") == "DEV"
        assert split_for("") == "DEV"


class TestResolveTarget:
    def test_primary_differs_by_workflow(self):
        assert resolve_target("ORDINARY", "primary") == "rating"
        assert resolve_target("CONTROLLED", "primary") == "liking"

    def test_explicit_target_passes_through(self):
        for target in TARGETS:
            assert resolve_target("CONTROLLED", target) == target

    def test_unknown_target_rejected(self):
        with pytest.raises(ValueError, match="unsupported target"):
            resolve_target("CONTROLLED", "enjoyment")


class TestBuildExamples:
    @pytest.mark.asyncio
    async def test_uniform_key_set_across_workflows_and_no_role(
        self, program, observation_factory
    ):
        session = program["session"]
        session.add(observation_factory(program["presentations"]["UNIVERSAL_BASELINE"]))
        session.add(
            Evaluation(
                id="ord-1",
                fragrance_id="extra",
                reviewer_id="owner",
                rating=4,
                notes="liked it",
                evaluated_at=now_naive_utc(),
            )
        )
        await session.flush()

        rows = await build_examples(session, "owner")
        assert len(rows) == 2
        workflows = {row.workflow for row in rows}
        assert workflows == {"ORDINARY", "CONTROLLED"}
        key_sets = {tuple(sorted(row.to_dict())) for row in rows}
        assert len(key_sets) == 1
        for row in rows:
            payload = row.to_dict()
            assert "role" not in payload
            assert row.split == "DEV"
            json.dumps(payload)

    @pytest.mark.asyncio
    async def test_ordinary_row_carries_rating_on_its_own_scale(
        self, program, observation_factory
    ):
        session = program["session"]
        session.add(
            Evaluation(fragrance_id="extra", reviewer_id="owner", rating=4, notes="hm")
        )
        await session.flush()

        (row,) = await build_examples(session, "owner")
        assert row.workflow == "ORDINARY"
        assert (row.scale, row.target, row.label) == ("1-5", "rating", 4.0)
        assert row.contributed_to_affinity_v1 is True
        assert row.observation_features is None
        assert row.notes_text == {"notes": "hm"}
        assert row.features.primary_family == "fresh"

    @pytest.mark.asyncio
    async def test_ordinary_row_has_no_controlled_target(self, program):
        session = program["session"]
        session.add(Evaluation(fragrance_id="extra", reviewer_id="owner", rating=4))
        await session.flush()

        (row,) = await build_examples(session, "owner", target="would_buy")
        assert row.target == "would_buy"
        assert row.label is None
        assert row.scale == "1-5"

    @pytest.mark.asyncio
    async def test_controlled_null_target_is_kept_with_none_label(
        self, program, observation_factory
    ):
        session = program["session"]
        session.add(
            observation_factory(
                program["presentations"]["UNIVERSAL_BASELINE"], liking=8
            )
        )
        await session.flush()

        (row,) = await build_examples(session, "owner", target="would_buy")
        assert row.workflow == "CONTROLLED"
        assert row.target == "would_buy"
        assert row.label is None
        assert row.scale == "0-10"
        assert row.observation_features is not None
        assert row.observation_features["would_buy"] is None

    @pytest.mark.asyncio
    async def test_controlled_secondary_target_read_from_features(
        self, program, observation_factory
    ):
        session = program["session"]
        session.add(
            observation_factory(
                program["presentations"]["UNIVERSAL_BASELINE"],
                liking=8,
                would_wear=7,
                artistic_appreciation=3,
            )
        )
        await session.flush()

        (wear,) = await build_examples(session, "owner", target="would_wear")
        assert wear.label == 7.0
        (art,) = await build_examples(session, "owner", target="artistic_appreciation")
        assert art.label == 3.0
        (primary,) = await build_examples(session, "owner")
        assert (primary.target, primary.label) == ("liking", 8.0)

    @pytest.mark.asyncio
    async def test_controlled_row_has_no_ordinary_rating_target(
        self, program, observation_factory
    ):
        session = program["session"]
        session.add(observation_factory(program["presentations"]["UNIVERSAL_BASELINE"]))
        await session.flush()

        (row,) = await build_examples(session, "owner", target="rating")
        assert row.workflow == "CONTROLLED"
        assert row.label is None

    @pytest.mark.asyncio
    async def test_contributed_flag_follows_the_reveal_gate(
        self, program, observation_factory
    ):
        session = program["session"]
        session.add(observation_factory(program["presentations"]["UNIVERSAL_BASELINE"]))
        await session.flush()

        (blind,) = await build_examples(session, "owner")
        assert blind.contributed_to_affinity_v1 is False
        assert blind.program_id == program["program"].id
        assert blind.phase == "PRE_REVEAL"
        assert blind.stage == "BLOTTER"

        program["enrollment"].revealed_at = now_naive_utc()
        await session.flush()
        (revealed,) = await build_examples(session, "owner")
        assert revealed.contributed_to_affinity_v1 is True

    @pytest.mark.asyncio
    async def test_include_flags_select_workflows(self, program, observation_factory):
        session = program["session"]
        session.add(observation_factory(program["presentations"]["UNIVERSAL_BASELINE"]))
        session.add(Evaluation(fragrance_id="extra", reviewer_id="owner", rating=4))
        await session.flush()

        ordinary_only = await build_examples(session, "owner", include_controlled=False)
        assert [row.workflow for row in ordinary_only] == ["ORDINARY"]
        controlled_only = await build_examples(session, "owner", include_ordinary=False)
        assert [row.workflow for row in controlled_only] == ["CONTROLLED"]
        assert (
            await build_examples(
                session, "owner", include_ordinary=False, include_controlled=False
            )
            == []
        )

    @pytest.mark.asyncio
    async def test_holdouts_and_hidden_repeats_never_reach_a_row(
        self, program, observation_factory
    ):
        session = program["session"]
        session.add(observation_factory(program["presentations"]["HOLDOUT"]))
        session.add(observation_factory(program["presentations"]["HIDDEN_REPEAT"]))
        session.add(Evaluation(fragrance_id="holdout", reviewer_id="owner", rating=5))
        await session.flush()

        assert await build_examples(session, "owner") == []

    @pytest.mark.asyncio
    async def test_unknown_target_rejected_by_builder(self, program):
        session = program["session"]
        session.add(Evaluation(fragrance_id="extra", reviewer_id="owner", rating=4))
        await session.flush()
        with pytest.raises(ValueError, match="unsupported target"):
            await build_examples(session, "owner", target="vibes")


class TestRowsFromManifest:
    def test_rows_missing_identity_are_skipped(self):
        manifest = [
            {"workflow": "ORDINARY", "fragrance_id": "f1", "rating": 4},
            {"workflow": "CONTROLLED", "id": "o1", "rating": 8},
            {"workflow": "SOMETHING_ELSE", "id": "x", "fragrance_id": "f1"},
        ]
        assert rows_from_manifest("owner", manifest) == []

    def test_defaults_fill_missing_scale_and_timestamp(self):
        manifest = [
            {
                "workflow": "CONTROLLED",
                "id": "o1",
                "fragrance_id": "f1",
                "rating": 8,
                "source_features": {},
            }
        ]
        (row,) = rows_from_manifest("owner", manifest)
        assert (row.scale, row.observed_at, row.label) == ("0-10", "", 8.0)
        assert row.features.feature_space_version == "fs-v0"
        assert row.contributed_to_affinity_v1 is False


class TestToArrays:
    def test_notes_one_hot_over_sorted_vocabulary(self):
        rows = [
            _row(notes=(("n2", "Two", "top"), ("n1", "One", "base"))),
            _row(label=3.0, notes=(("n1", "One", "base"),)),
        ]
        matrix, labels, groups, vocabulary = to_arrays(rows, feature_space="notes")
        assert vocabulary == ["n1", "n2"]
        assert matrix == [[1.0, 1.0], [1.0, 0.0]]
        assert labels == [8.0, 3.0]
        assert groups == ["owner", "owner"]

    def test_notes_space_skips_unknown_note_ids(self):
        rows = [_row(notes=((None, "Unknown", "top"), ("n1", "One", "top")))]
        _, _, _, vocabulary = to_arrays(rows, feature_space="notes")
        assert vocabulary == ["n1"]

    def test_accords_are_intensity_weighted(self):
        rows = [
            _row(accords=(("citrus", 0.8), ("woody", 0.5))),
            _row(label=2.0, accords=(("woody", 0.25), ("", 0.9))),
        ]
        matrix, _, _, vocabulary = to_arrays(rows, feature_space="accords")
        assert vocabulary == ["citrus", "woody"]
        assert matrix == [[0.8, 0.5], [0.0, 0.25]]

    def test_families_are_namespaced_one_hot(self):
        rows = [
            _row(family="woody", subfamily="woody"),
            _row(label=1.0, family="floral", subfamily=""),
        ]
        matrix, _, _, vocabulary = to_arrays(rows, feature_space="families")
        assert vocabulary == ["family:floral", "family:woody", "subfamily:woody"]
        assert matrix == [[0.0, 1.0, 1.0], [1.0, 0.0, 0.0]]

    def test_perception_uses_the_declared_basis_and_zero_fills(self):
        rows = [
            _row(
                observation_features={
                    "confidence": 4,
                    "sweetness": None,
                    "freshness": 2,
                    "familiarity": 5,
                }
            ),
            _row(label=1.0, observation_features=None),
        ]
        matrix, labels, _, vocabulary = to_arrays(rows, feature_space="perception")
        assert vocabulary == list(PERCEPTION_DIMENSIONS)
        assert "familiarity" not in vocabulary
        assert matrix[0][vocabulary.index("confidence")] == 4.0
        assert matrix[0][vocabulary.index("sweetness")] == 0.0
        assert matrix[0][vocabulary.index("freshness")] == 2.0
        assert matrix[1] == [0.0] * len(vocabulary)
        assert labels == [8.0, 1.0]

    def test_rows_without_a_label_are_excluded(self):
        rows = [_row(label=None), _row(label=6.0)]
        matrix, labels, groups, _ = to_arrays(rows)
        assert labels == [6.0]
        assert len(matrix) == 1
        assert groups == ["owner"]

    def test_groups_track_reviewers(self):
        rows = [_row(reviewer_id="a"), _row(reviewer_id="b", label=1.0)]
        _, _, groups, _ = to_arrays(rows)
        assert groups == ["a", "b"]

    def test_empty_row_set(self):
        assert to_arrays([]) == ([], [], [], [])

    def test_unknown_feature_space_rejected(self):
        with pytest.raises(ValueError, match="unsupported feature_space"):
            to_arrays([_row()], feature_space="embeddings")

    def test_every_declared_space_is_supported(self):
        for space in FEATURE_SPACES:
            matrix, _, _, _ = to_arrays([_row()], feature_space=space)
            assert len(matrix) == 1
