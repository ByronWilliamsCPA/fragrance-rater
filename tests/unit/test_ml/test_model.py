"""Tests for the extracted affinity-v1 model object and its frozen spec."""

from __future__ import annotations

import math

import pytest

from fragrance_rater.ml.feature_space import (
    FEATURE_SPACE_VERSION,
    AccordFeature,
    FeatureVector,
    NoteFeature,
    from_source_features,
    vectorize,
)
from fragrance_rater.ml.model import (
    AFFINITY_V1_SPEC,
    COMPONENT_WEIGHTS,
    VETO_SCORE,
    VETO_THRESHOLD,
    AffinityV1,
    ModelSpec,
    UserProfile,
)
from fragrance_rater.models.fragrance import (
    Fragrance,
    FragranceAccord,
    FragranceNote,
    Note,
)
from fragrance_rater.services.recommendation_service import RecommendationService

# Pinned digest of affinity-v1's parameters. If this assertion fails, a
# tunable changed: either revert it, or bump ModelSpec.version to "v2" (and
# update this pin) so the change is a recorded version, per ADR-009.
AFFINITY_V1_DIGEST = "a7ac4c6b12484c662e2521603c00cc62d7d97c1edbb77b1c6c05cabb7300834e"


def _vector(
    *,
    notes: list[tuple[str, str]] | None = None,
    accords: list[tuple[str, float]] | None = None,
    family: str = "woody",
    subfamily: str = "aromatic",
) -> FeatureVector:
    return FeatureVector(
        fragrance_id="f1",
        version_key="f1-key",
        concentration="EDP",
        primary_family=family,
        subfamily=subfamily,
        notes=tuple(NoteFeature(nid, name, "top") for nid, name in (notes or [])),
        accords=tuple(AccordFeature(name, w) for name, w in (accords or [])),
    )


class TestModelSpec:
    def test_algorithm_version_and_record(self) -> None:
        spec = ModelSpec(model_id="demo", version="v3", params={"k": 1})
        assert spec.algorithm_version == "demo-v3"
        record = spec.to_record()
        assert record["algorithm_version"] == "demo-v3"
        assert record["param_digest"] == spec.digest
        assert record["feature_space_version"] == FEATURE_SPACE_VERSION

    def test_digest_changes_when_a_parameter_changes(self) -> None:
        a = ModelSpec(model_id="demo", version="v1", params={"weight": 0.4})
        b = ModelSpec(model_id="demo", version="v1", params={"weight": 0.41})
        assert a.digest != b.digest

    def test_digest_is_order_independent(self) -> None:
        a = ModelSpec(model_id="demo", version="v1", params={"a": 1, "b": 2})
        b = ModelSpec(model_id="demo", version="v1", params={"b": 2, "a": 1})
        assert a.digest == b.digest

    def test_affinity_v1_parameters_are_pinned(self) -> None:
        """A tunable change without a version bump must fail loudly."""
        assert AffinityV1.spec is AFFINITY_V1_SPEC
        assert AffinityV1.spec.algorithm_version == "affinity-v1"
        assert AffinityV1.spec.digest == AFFINITY_V1_DIGEST, (
            "affinity-v1 parameters changed; bump ModelSpec.version and the pin"
        )


class TestAffinityV1Scoring:
    def test_empty_profile_scores_neutral(self) -> None:
        result = AffinityV1().score(UserProfile(reviewer_id="r"), _vector())
        assert result.score == pytest.approx(0.5)
        assert result.score_percent == 50
        assert not result.vetoed
        assert result.n_evidence == 0
        assert result.uncertainty is None

    def test_weighted_components_match_adr_004(self) -> None:
        profile = UserProfile(
            reviewer_id="r",
            note_affinities={"n1": 2.0, "n2": -1.0},
            accord_affinities={"citrus": 1.0},
            family_affinities={"woody": 1.0, "aromatic": 0.5},
            evaluation_count=4,
        )
        features = _vector(
            notes=[("n1", "Bergamot"), ("n2", "Oud")], accords=[("citrus", 0.5)]
        )
        result = AffinityV1().score(profile, features)
        expected_raw = (
            COMPONENT_WEIGHTS["notes"] * 0.5
            + COMPONENT_WEIGHTS["accords"] * 0.5
            + COMPONENT_WEIGHTS["family"] * 1.0
            + COMPONENT_WEIGHTS["subfamily"] * 0.5
        )
        assert result.components["raw"] == pytest.approx(expected_raw)
        assert result.score == pytest.approx(1 / (1 + math.exp(-expected_raw)))
        assert result.n_evidence == 4

    def test_veto_fires_below_threshold_in_source_order(self) -> None:
        profile = UserProfile(
            reviewer_id="r",
            note_affinities={"n1": VETO_THRESHOLD - 0.5, "n2": VETO_THRESHOLD - 5},
        )
        result = AffinityV1().score(
            profile, _vector(notes=[("n1", "Lemon"), ("n2", "Oud")])
        )
        assert result.vetoed
        assert result.veto_note == "Lemon"
        assert result.score == VETO_SCORE

    def test_notes_without_ids_are_ignored(self) -> None:
        """A legacy manifest vector cannot trigger id-keyed affinities."""
        profile = UserProfile(reviewer_id="r", note_affinities={"n1": -10.0})
        features = FeatureVector(
            fragrance_id=None,
            version_key=None,
            concentration=None,
            primary_family=None,
            subfamily=None,
            notes=(NoteFeature(None, "Lemon", "top"),),
        )
        result = AffinityV1().score(profile, features)
        assert not result.vetoed
        assert result.score == pytest.approx(0.5)

    def test_lemon_criterion_from_adr_004(self) -> None:
        """A 1-star rating on a lemon fragrance lowers every lemon candidate."""
        model = AffinityV1()
        lemon = _vector(notes=[("lemon", "Lemon")], family="citrus", subfamily="")
        before = model.build_profile("r", [(lemon, [1.0])])
        after = model.build_profile("r", [(lemon, [1.0]), (lemon, [-2.0])])
        candidate = _vector(notes=[("lemon", "Lemon")], family="citrus", subfamily="")
        assert (
            model.score(after, candidate).score < model.score(before, candidate).score
        )


class TestAffinityV1Profile:
    def test_build_profile_averages_weights_and_counts_versions(self) -> None:
        model = AffinityV1()
        features = _vector(notes=[("n1", "Rose")], accords=[("floral", 0.8)])
        profile = model.build_profile("r", [(features, [2.0, 0.0])])
        assert profile.evaluation_count == 1
        assert profile.note_affinities == {"n1": 1.0}
        assert profile.accord_affinities["floral"] == pytest.approx(0.8)
        assert profile.family_affinities["woody"] == 1.0
        assert profile.family_affinities["aromatic"] == 0.5
        assert profile.top_liked_notes == [("Rose", 1.0)]
        assert profile.top_disliked_notes == []

    def test_unknown_subfamily_is_not_bucketed(self) -> None:
        profile = AffinityV1().build_profile("r", [(_vector(subfamily=""), [1.0])])
        assert "" not in profile.family_affinities

    def test_controlled_affinity_map(self) -> None:
        model = AffinityV1()
        assert model.controlled_affinity(10) == pytest.approx(2.0)
        assert model.controlled_affinity(5) == pytest.approx(0.0)
        assert model.controlled_affinity(0) == pytest.approx(-2.0)


class TestFeatureSpace:
    def _fragrance(self) -> Fragrance:
        fragrance = Fragrance(
            id="frag-1",
            name="Test",
            brand="House",
            concentration="EDT",
            version_key="house-test-edt",
            gender_target="Unisex",
            primary_family="fresh",
            subfamily="citrus",
            data_source="manual",
        )
        fragrance.notes = [
            FragranceNote(
                note=Note(id="n-berg", name="Bergamot", category="citrus"),
                position="top",
            )
        ]
        fragrance.accords = [FragranceAccord(accord_type="citrus", intensity=0.9)]
        return fragrance

    def test_vectorize_and_round_trip_through_manifest(self) -> None:
        vector = vectorize(self._fragrance())
        assert vector.note_ids() == ["n-berg"]
        payload = vector.to_source_features()
        assert payload["feature_space_version"] == FEATURE_SPACE_VERSION
        assert payload["notes"] == [
            {"note_id": "n-berg", "name": "Bergamot", "position": "top"}
        ]
        rebuilt = from_source_features("frag-1", payload)
        assert rebuilt == vector

    def test_legacy_manifest_without_note_ids_is_tolerated(self) -> None:
        rebuilt = from_source_features(
            "frag-1",
            {
                "version_key": "k",
                "concentration": "EDP",
                "primary_family": "woody",
                "subfamily": "",
                "notes": [{"name": "Oud", "position": "base"}],
                "accords": [{"name": "woody", "intensity": "bad"}],
            },
        )
        assert rebuilt.feature_space_version == "fs-v0"
        assert rebuilt.notes[0].note_id is None
        assert rebuilt.note_ids() == []
        assert rebuilt.accords[0].intensity == 0.0


@pytest.mark.asyncio
class TestServiceDelegation:
    async def test_calculate_match_score_matches_model(self, async_session) -> None:
        """The service is a thin adapter over the pure model object."""
        service = RecommendationService(async_session)
        fragrance = TestFeatureSpace()._fragrance()
        profile = UserProfile(
            reviewer_id="r", note_affinities={"n-berg": 1.5}, evaluation_count=2
        )
        via_service = await service.calculate_match_score(profile, fragrance)
        direct = AffinityV1().score(profile, vectorize(fragrance))
        assert via_service.score == direct.score
        assert via_service.components == direct.components
        assert service.model.spec.algorithm_version == "affinity-v1"
