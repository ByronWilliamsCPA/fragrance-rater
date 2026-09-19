"""The model registry resolves names to scorers and refuses silent replacement."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from fragrance_rater.ml import registry
from fragrance_rater.ml.model import (
    AffinityV1,
    ModelSpec,
    ScoredResult,
    UserProfile,
)
from fragrance_rater.ml.registry import (
    DEFAULT_MODEL_KEY,
    MODELS,
    available,
    register,
    resolve,
)

if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence

    from fragrance_rater.ml.feature_space import FeatureVector


class _StubScorer:
    """Minimal Scorer implementation used to exercise registration."""

    def __init__(self, model_id: str = "stub", version: str = "v1") -> None:
        self.spec = ModelSpec(model_id=model_id, version=version, params={"a": 1})

    def controlled_affinity(self, liking: float) -> float:
        return liking

    def build_profile(
        self,
        reviewer_id: str,
        contributions: Iterable[tuple[FeatureVector, Sequence[float]]],
    ) -> UserProfile:
        return UserProfile(
            reviewer_id=reviewer_id, evaluation_count=len(list(contributions))
        )

    def score(self, profile: UserProfile, features: FeatureVector) -> ScoredResult:
        return ScoredResult(score=0.5, score_percent=50)


@pytest.fixture
def isolated_registry(monkeypatch):
    """Give each test its own copy of MODELS so registration cannot leak."""
    snapshot = dict(MODELS)
    monkeypatch.setattr(registry, "MODELS", snapshot)
    return snapshot


def test_affinity_v1_is_registered_under_its_algorithm_version():
    assert MODELS["affinity-v1"].spec.algorithm_version == "affinity-v1"
    assert isinstance(MODELS["affinity-v1"], AffinityV1)


def test_default_model_key_resolves():
    assert DEFAULT_MODEL_KEY == "affinity-v2"
    assert resolve(DEFAULT_MODEL_KEY).spec.model_id == "affinity"


def test_available_is_sorted_and_contains_the_baseline():
    keys = available()
    assert keys == sorted(keys)
    assert "affinity-v1" in keys


def test_resolve_unknown_key_names_the_known_keys():
    with pytest.raises(KeyError) as excinfo:
        resolve("gbm-v9")
    message = str(excinfo.value)
    assert "gbm-v9" in message
    assert "affinity-v1" in message


def test_register_adds_a_scorer_under_its_own_key(isolated_registry):
    register(_StubScorer())
    assert resolve("stub-v1").spec.model_id == "stub"
    assert "stub-v1" in available()
    assert isolated_registry["stub-v1"].spec.version == "v1"


def test_register_rejects_a_duplicate_key(isolated_registry):
    register(_StubScorer())
    with pytest.raises(ValueError, match="already registered"):
        register(_StubScorer())
    # The rejected second call must not have replaced the first entry.
    assert sorted(isolated_registry) == ["affinity-v1", "affinity-v2", "stub-v1"]


def test_register_rejects_replacing_the_frozen_baseline(isolated_registry):
    with pytest.raises(ValueError, match="affinity-v1"):
        register(_StubScorer(model_id="affinity", version="v1"))
    assert isolated_registry["affinity-v1"].spec.digest == AffinityV1.spec.digest
