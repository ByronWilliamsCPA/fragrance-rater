"""Model objects: ``ModelSpec``, the ``Scorer`` protocol, and ``AffinityV1``.

``AffinityV1`` is the ADR-004 weighted-affinity heuristic with the ADR-007
evidence rules, extracted from ``RecommendationService`` as a pure,
synchronous object. Its behavior is unchanged: the same profile and the same
fragrance produce the same score, veto, and components as before. What is
new is that every tunable lives in ``AffinityV1.spec.params`` and is digested,
so a change to any of them is a recorded version change rather than a silent
drift under an unchanged ``algorithm_version`` (ML structure review, M-04).

The protocol is deliberately small so a learned model can sit beside the
heuristic and be compared under identical eligibility rules:

- ``build_profile`` turns per-version evidence into whatever state the model
  scores from (for ``AffinityV1``, accumulated affinities).
- ``score`` maps that state plus a ``FeatureVector`` to a ``ScoredResult``.
- ``controlled_affinity`` is the model's declared map from a controlled 0-10
  liking to the same evidence scale as an ordinary rating weight.

Neither ``build_profile`` nor ``score`` touches a database or an event loop.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections import defaultdict
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Protocol

from fragrance_rater.ml.feature_space import FEATURE_SPACE_VERSION, FeatureVector

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping, Sequence

# Rating weight mapping: 1-5 stars -> -2 to +2 (ADR-004).
RATING_WEIGHTS: dict[int, float] = {1: -2.0, 2: -1.0, 3: 0.0, 4: 1.0, 5: 2.0}

# Component weights for match score calculation (ADR-004).
COMPONENT_WEIGHTS: dict[str, float] = {
    "notes": 0.40,
    "accords": 0.30,
    "family": 0.20,
    "subfamily": 0.10,
}

# Veto threshold: cumulative note affinity below this triggers a veto.
VETO_THRESHOLD = -3.0

# Score assigned to a vetoed fragrance ("very low but not zero", ADR-004).
VETO_SCORE = 0.1

# Subfamily evidence accumulates at half weight (ADR-004 Step 1).
SUBFAMILY_FACTOR = 0.5

# Sigmoid input is clamped to +/- this before math.exp (overflow guard).
SIGMOID_CLAMP = 50.0

# ADR-007: controlled 0-10 liking maps to affinity with (liking - 5) / 2.5.
CONTROLLED_LIKING_OFFSET = 5.0
CONTROLLED_LIKING_DIVISOR = 2.5


@dataclass
class UserProfile:
    """User profile whose count is distinct contributing fragrance versions.

    Attributes:
        reviewer_id (str): The evaluator this profile belongs to.
        note_affinities (dict[str, float]): Accumulated affinity keyed by
            canonical ``Note.id``.
        accord_affinities (dict[str, float]): Accumulated affinity keyed by
            accord label.
        family_affinities (dict[str, float]): Accumulated affinity keyed by
            family or subfamily label (one shared namespace in v1).
        evaluation_count (int): Number of distinct fragrance versions that
            contributed evidence.
        top_liked_notes (list[tuple[str, float]]): Highest-affinity notes by
            name, for display.
        top_disliked_notes (list[tuple[str, float]]): Lowest-affinity notes
            by name, for display.
    """

    reviewer_id: str
    note_affinities: dict[str, float] = field(default_factory=dict)
    accord_affinities: dict[str, float] = field(default_factory=dict)
    family_affinities: dict[str, float] = field(default_factory=dict)
    evaluation_count: int = 0

    # For preference display
    top_liked_notes: list[tuple[str, float]] = field(default_factory=list)
    top_disliked_notes: list[tuple[str, float]] = field(default_factory=list)


@dataclass(frozen=True)
class ModelSpec:
    """Identity, version, and serialized parameters of one model.

    Attributes:
        model_id (str): Stable model family name, e.g. ``"affinity"``.
        version (str): Version label within the family, e.g. ``"v1"``.
        params (Mapping[str, object]): Every tunable the model uses, in a
            JSON-serializable form. The digest is computed from this mapping,
            so a parameter change without a version bump is detectable.
        feature_space_version (str): The feature space the model scores in.
    """

    model_id: str
    version: str
    params: Mapping[str, object]
    feature_space_version: str = FEATURE_SPACE_VERSION

    @property
    def algorithm_version(self) -> str:
        """Return the label recorded on runs, checkpoints, and snapshots.

        Returns:
            str: ``"<model_id>-<version>"``, e.g. ``"affinity-v1"``.
        """
        return f"{self.model_id}-{self.version}"

    @property
    def digest(self) -> str:
        """Return a SHA-256 content digest of the serialized parameters.

        Returns:
            str: Hex digest over the canonical JSON of ``params`` plus the
                feature-space version.
        """
        payload = {
            "feature_space_version": self.feature_space_version,
            "params": self.params,
        }
        canonical = json.dumps(payload, sort_keys=True, default=str)
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def to_record(self) -> dict[str, object]:
        """Serialize for persistence on a run, checkpoint, or snapshot.

        Returns:
            dict[str, object]: JSON-serializable identity and parameters.
        """
        return {
            "model_id": self.model_id,
            "model_version": self.version,
            "algorithm_version": self.algorithm_version,
            "feature_space_version": self.feature_space_version,
            "params": dict(self.params),
            "param_digest": self.digest,
        }


@dataclass(frozen=True)
class ScoredResult:
    """One model's score for one fragrance version against one profile.

    Attributes:
        score (float): Bounded display score in ``[0, 1]``. For
            ``AffinityV1`` this is an uncalibrated affinity, not a probability
            or predicted liking (ADR-007).
        score_percent (int): ``int(score * 100)``.
        vetoed (bool): Whether a strong-dislike veto fired.
        veto_note (str | None): Name of the note that triggered the veto.
        components (dict[str, float]): Component contributions for
            explanation and audit.
        n_evidence (int): Number of contributing versions in the profile,
            carried so every report can state its evidence count.
        uncertainty (float | None): Model-reported uncertainty when the
            model computes one; ``None`` for ``AffinityV1``, which does not.
    """

    score: float
    score_percent: int
    vetoed: bool = False
    veto_note: str | None = None
    components: dict[str, float] = field(default_factory=dict)
    n_evidence: int = 0
    uncertainty: float | None = None


class Scorer(Protocol):
    """What a registered model must provide to be scored and compared."""

    spec: ModelSpec

    def controlled_affinity(self, liking: float) -> float:
        """Map a controlled 0-10 liking onto the ordinary evidence scale."""
        ...

    def build_profile(
        self,
        reviewer_id: str,
        contributions: Iterable[tuple[FeatureVector, Sequence[float]]],
    ) -> UserProfile:
        """Turn per-version evidence into the state ``score`` reads from."""
        ...

    def score(self, profile: UserProfile, features: FeatureVector) -> ScoredResult:
        """Score one fragrance version against a profile."""
        ...


AFFINITY_V1_SPEC = ModelSpec(
    model_id="affinity",
    version="v1",
    params={
        "rating_weights": {str(k): v for k, v in RATING_WEIGHTS.items()},
        "component_weights": COMPONENT_WEIGHTS,
        "veto_threshold": VETO_THRESHOLD,
        "veto_score": VETO_SCORE,
        "subfamily_factor": SUBFAMILY_FACTOR,
        "sigmoid_clamp": SIGMOID_CLAMP,
        "controlled_liking_offset": CONTROLLED_LIKING_OFFSET,
        "controlled_liking_divisor": CONTROLLED_LIKING_DIVISOR,
        "evidence_selection": (
            "latest live ordinary encounter per version; latest eligible "
            "locked pre-reveal controlled observation, skin preferred over "
            "blotter, only after reveal; averaged when both exist; one "
            "contribution per version; holdouts, hidden repeats, "
            "post-reveal and worn-by rows excluded"
        ),
        "score_type": "uncalibrated-affinity",
    },
)
"""Frozen identity and parameters of the ADR-004/ADR-007 heuristic."""


class AffinityV1:
    """ADR-004 weighted affinity with veto, ADR-007 evidence rules, frozen.

    Parameters are fixed class-level constants exposed through ``spec`` so
    the digest pins them; ``tests/unit/test_ml/test_model.py`` asserts the
    pinned digest and fails when any tunable changes without a version bump.
    """

    spec: ModelSpec = AFFINITY_V1_SPEC

    def controlled_affinity(self, liking: float) -> float:
        """Map a controlled 0-10 liking onto the -2..2 ordinary weight scale.

        Args:
            liking (float): Controlled liking on its original 0-10 scale.

        Returns:
            float: ``(liking - 5) / 2.5``; an explicit ADR-007 heuristic,
                not predicted liking.
        """
        return (liking - CONTROLLED_LIKING_OFFSET) / CONTROLLED_LIKING_DIVISOR

    def build_profile(
        self,
        reviewer_id: str,
        contributions: Iterable[tuple[FeatureVector, Sequence[float]]],
    ) -> UserProfile:
        """Accumulate note, accord, and family affinities from evidence.

        Each contribution is one fragrance version's feature vector and the
        list of evidence weights selected for it (ordinary rating weight and,
        after reveal, the controlled affinity); the weights are averaged so a
        version contributes once (ADR-007).

        Args:
            reviewer_id (str): The evaluator the profile belongs to.
            contributions (Iterable[tuple[FeatureVector, Sequence[float]]]):
                Per-version ``(features, weights)`` pairs.

        Returns:
            UserProfile: Accumulated affinities and display summaries.
        """
        note_affinities: defaultdict[str, float] = defaultdict(float)
        note_names: dict[str, str] = {}
        accord_affinities: defaultdict[str, float] = defaultdict(float)
        family_affinities: defaultdict[str, float] = defaultdict(float)
        count = 0

        for features, weights in contributions:
            count += 1
            weight = sum(weights) / len(weights)

            for note in features.notes:
                if note.note_id is None:
                    continue
                note_affinities[note.note_id] += weight
                note_names[note.note_id] = note.name

            for accord in features.accords:
                accord_affinities[accord.name] += weight * accord.intensity

            # An empty/null subfamily means "unknown" rather than a real
            # taxonomy bucket, so it must not pollute the affinity dict with
            # a "" key that every unknown-subfamily fragrance would match.
            family_affinities[features.primary_family or ""] += weight
            if features.subfamily:
                family_affinities[features.subfamily] += weight * SUBFAMILY_FACTOR

        sorted_notes = sorted(
            [
                (note_names.get(nid, nid), score)
                for nid, score in note_affinities.items()
            ],
            key=lambda x: x[1],
            reverse=True,
        )
        top_liked = [(name, score) for name, score in sorted_notes if score > 0][:5]
        top_disliked = [(name, score) for name, score in sorted_notes if score < 0][-5:]

        return UserProfile(
            reviewer_id=reviewer_id,
            note_affinities=dict(note_affinities),
            accord_affinities=dict(accord_affinities),
            family_affinities=dict(family_affinities),
            evaluation_count=count,
            top_liked_notes=top_liked,
            top_disliked_notes=list(reversed(top_disliked)),
        )

    def score(self, profile: UserProfile, features: FeatureVector) -> ScoredResult:
        """Score a fragrance version against a profile (ADR-004 Step 2).

        Args:
            profile (UserProfile): Accumulated affinities.
            features (FeatureVector): The candidate's published features.

        Returns:
            ScoredResult: Bounded score, veto state, and components.
        """
        # Veto on strong dislike of any published note, first in source order.
        for note in features.notes:
            if note.note_id is None:
                continue
            if profile.note_affinities.get(note.note_id, 0) < VETO_THRESHOLD:
                return ScoredResult(
                    score=VETO_SCORE,
                    score_percent=int(VETO_SCORE * 100),
                    vetoed=True,
                    veto_note=note.name,
                    n_evidence=profile.evaluation_count,
                )

        note_scores = [
            profile.note_affinities.get(note.note_id, 0)
            for note in features.notes
            if note.note_id is not None
        ]
        note_score = sum(note_scores) / max(len(note_scores), 1)

        accord_scores = [
            profile.accord_affinities.get(accord.name, 0) * accord.intensity
            for accord in features.accords
        ]
        accord_score = sum(accord_scores) / max(len(accord_scores), 1)

        family_score = profile.family_affinities.get(features.primary_family or "", 0)
        subfamily_score = profile.family_affinities.get(features.subfamily or "", 0)

        raw_score = (
            COMPONENT_WEIGHTS["notes"] * note_score
            + COMPONENT_WEIGHTS["accords"] * accord_score
            + COMPONENT_WEIGHTS["family"] * family_score
            + COMPONENT_WEIGHTS["subfamily"] * subfamily_score
        )

        # raw_score is an unbounded weighted sum that grows with history, so
        # clamp before math.exp to guarantee no OverflowError; sigmoid(+/-50)
        # already round-trips to 1.0 / ~1.9e-22 in float64.
        clamped = max(-SIGMOID_CLAMP, min(SIGMOID_CLAMP, raw_score))
        normalized = 1 / (1 + math.exp(-clamped))

        return ScoredResult(
            score=normalized,
            score_percent=int(normalized * 100),
            vetoed=False,
            components={
                "notes": note_score,
                "accords": accord_score,
                "family": family_score,
                "subfamily": subfamily_score,
                "raw": raw_score,
            },
            n_evidence=profile.evaluation_count,
        )


__all__ = [
    "AFFINITY_V1_SPEC",
    "COMPONENT_WEIGHTS",
    "CONTROLLED_LIKING_DIVISOR",
    "CONTROLLED_LIKING_OFFSET",
    "RATING_WEIGHTS",
    "SIGMOID_CLAMP",
    "SUBFAMILY_FACTOR",
    "VETO_SCORE",
    "VETO_THRESHOLD",
    "AffinityV1",
    "ModelSpec",
    "ScoredResult",
    "Scorer",
    "UserProfile",
]
