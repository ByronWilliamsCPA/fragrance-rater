"""Recommendation service implementing ADR-004 weighted affinity scoring.

This module implements the recommendation algorithm with:
- Cumulative note/accord/family affinities from user ratings
- Veto mechanism for strongly disliked notes
- Weighted scoring with configurable component weights
"""

from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, TypedDict

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from fragrance_rater.models.calibration import (
    CalibrationSession,
    Enrollment,
    Membership,
    Observation,
    Presentation,
)
from fragrance_rater.models.evaluation import Evaluation
from fragrance_rater.models.fragrance import Fragrance, FragranceNote
from fragrance_rater.services.preference_history import PreferenceHistoryService

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


# Rating weight mapping: 1-5 stars → -2 to +2
RATING_WEIGHTS = {1: -2.0, 2: -1.0, 3: 0.0, 4: 1.0, 5: 2.0}

# Component weights for match score calculation
COMPONENT_WEIGHTS = {
    "notes": 0.40,
    "accords": 0.30,
    "family": 0.20,
    "subfamily": 0.10,
}

# Veto threshold: cumulative score below this triggers veto
VETO_THRESHOLD = -3.0

# Minimum evaluations required for recommendations
MIN_EVALUATIONS = 3


@dataclass
class UserProfile:
    """User profile whose count is distinct contributing fragrance versions."""

    reviewer_id: str
    note_affinities: dict[str, float] = field(default_factory=dict)
    accord_affinities: dict[str, float] = field(default_factory=dict)
    family_affinities: dict[str, float] = field(default_factory=dict)
    evaluation_count: int = 0

    # For preference display
    top_liked_notes: list[tuple[str, float]] = field(default_factory=list)
    top_disliked_notes: list[tuple[str, float]] = field(default_factory=list)


@dataclass
class MatchResult:
    """Result of calculating match score for a fragrance."""

    score: float  # 0.0 to 1.0
    score_percent: int  # 0 to 100
    vetoed: bool = False
    veto_note: str | None = None
    components: dict[str, float] = field(default_factory=dict)


@dataclass
class Recommendation:
    """A fragrance recommendation with match details."""

    fragrance_id: str
    fragrance_name: str
    fragrance_brand: str
    match_score: float
    match_percent: int
    vetoed: bool = False
    veto_reason: str | None = None
    components: dict[str, float] = field(default_factory=dict)


class ReviewerProfileSummary(TypedDict):
    """Reviewer preference summary prepared for display.

    Attributes:
        evaluation_count (int): Number of distinct fragrance versions contributing
            ordinary or revealed controlled evidence to the profile.
        top_liked_notes (list[tuple[str, float]]): Highest-affinity notes.
        top_disliked_notes (list[tuple[str, float]]): Lowest-affinity notes.
        top_accords (list[tuple[str, float]]): Highest-affinity accords.
        top_families (list[tuple[str, float]]): Highest-affinity families.
    """

    evaluation_count: int
    top_liked_notes: list[tuple[str, float]]
    top_disliked_notes: list[tuple[str, float]]
    top_accords: list[tuple[str, float]]
    top_families: list[tuple[str, float]]


class InsufficientDataError(Exception):
    """Raised when user doesn't have enough evaluations for recommendations."""


class RecommendationService:
    """Service for generating personalized fragrance recommendations.

    Implements the weighted affinity scoring algorithm from ADR-004.

    Args:
        session (AsyncSession): Async database session.
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def build_preference_profile(self, reviewer_id: str) -> UserProfile:
        """Build a user preference profile from their evaluations.

        Aggregates note/accord/family affinities using rating weights:
        - 5 stars = +2.0
        - 4 stars = +1.0
        - 3 stars = 0.0 (neutral)
        - 2 stars = -1.0
        - 1 star = -2.0

        Args:
            reviewer_id (str): UUID of the reviewer.

        Returns:
            UserProfile: UserProfile with computed affinities.
        """
        # Fetch all evaluations with fragrance details
        # Critical finding 2: soft-delete filter on the evaluation aggregation.
        #
        # #CRITICAL: data integrity: Evaluation.deleted_at above only guards
        # the evaluation row itself; a live (non-soft-deleted) evaluation can
        # still point at a fragrance that has since been soft-deleted out of
        # the active catalog (Fragrance.deleted_at IS NOT NULL). Without an
        # explicit filter on the joined Fragrance, such "ghost" evaluations
        # would keep contributing their notes/accords/family to the
        # reviewer's affinity profile even though that fragrance can never
        # again be scored or recommended, skewing the profile with data the
        # recommendation logic can no longer act on.
        # #VERIFY: join explicitly and filter Fragrance.deleted_at.is_(None)
        # here rather than relying on the Evaluation.fragrance relationship's
        # primaryjoin -- mirrors reviewer_service.py's count_evaluations/
        # list_all comments explaining why this project keeps soft-delete
        # filters as explicit query-level joins/subqueries instead of
        # relationship-level filters (which would also affect cascade
        # semantics). Keep this in sync with the identical
        # Fragrance.deleted_at.is_(None) guard on the candidate-fragrance
        # query in get_recommendations below.
        stmt = (
            select(Evaluation)
            .join(Fragrance, Evaluation.fragrance_id == Fragrance.id)
            .where(
                Evaluation.reviewer_id == reviewer_id,
                Evaluation.deleted_at.is_(None),
                Fragrance.deleted_at.is_(None),
            )
            .options(
                selectinload(Evaluation.fragrance)
                .selectinload(Fragrance.notes)
                .selectinload(FragranceNote.note),
                selectinload(Evaluation.fragrance).selectinload(Fragrance.accords),
            )
        )
        result = await self.session.execute(stmt)
        evaluations = list(result.scalars().all())
        history = PreferenceHistoryService(self.session)
        excluded = await history.excluded_versions(reviewer_id)
        # One latest ordinary encounter contributes per version; retain all history.
        evaluations.sort(
            key=lambda e: (e.evaluated_at, e.created_at, e.id), reverse=True
        )
        latest: dict[str, Evaluation] = {}
        for item in evaluations:
            if item.fragrance_id not in excluded:
                latest.setdefault(item.fragrance_id, item)
        evaluations = list(latest.values())

        # Initialize affinity dictionaries
        note_affinities: dict[str, float] = defaultdict(float)
        note_names: dict[str, str] = {}  # id -> name mapping
        accord_affinities: dict[str, float] = defaultdict(float)
        family_affinities: dict[str, float] = defaultdict(float)

        contributions = await self._contributions(
            reviewer_id, evaluations, history, excluded
        )
        for fragrance, weights in contributions.values():
            weight = sum(weights) / len(weights)

            # Accumulate note affinities
            for fn in fragrance.notes:
                note_affinities[fn.note.id] += weight
                note_names[fn.note.id] = fn.note.name

            # Accumulate accord affinities (weighted by intensity)
            for accord in fragrance.accords:
                accord_affinities[accord.accord_type] += weight * accord.intensity

            # Accumulate family affinities. An empty/null subfamily means
            # "unknown" (e.g. scraped data that never got a subfamily
            # assigned) rather than a real taxonomy bucket, so it must not
            # pollute the affinity dict with a "" key that every
            # unknown-subfamily fragrance would then match against.
            family_affinities[fragrance.primary_family] += weight
            if fragrance.subfamily:
                family_affinities[fragrance.subfamily] += weight * 0.5

        # Calculate top liked/disliked notes for profile display
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
            evaluation_count=len(contributions),
            top_liked_notes=top_liked,
            top_disliked_notes=list(reversed(top_disliked)),
        )

    async def _contributions(
        self,
        reviewer_id: str,
        evaluations: list[Evaluation],
        history: PreferenceHistoryService,
        excluded: set[str],
    ) -> dict[str, tuple[Fragrance, list[float]]]:
        """Average available workflow evidence once per canonical version."""
        contributions: dict[str, tuple[Fragrance, list[float]]] = {
            e.fragrance_id: (e.fragrance, [RATING_WEIGHTS.get(e.rating, 0.0)])
            for e in evaluations
        }
        # Controlled data contributes to ordinary recommendations only after reveal.
        # Experimental checkpoints may consume locked blind data through the manifest.
        revealed_programs = set(
            await self.session.scalars(
                select(Enrollment.program_id).where(
                    Enrollment.reviewer_id == reviewer_id,
                    Enrollment.revealed_at.is_not(None),
                )
            )
        )
        if revealed_programs:
            manifest = await history.training_manifest(
                reviewer_id, excluded=excluded, ordinary=evaluations
            )
            controlled: dict[str, dict[str, object]] = {}
            for row in manifest:
                if (
                    row["workflow"] != "CONTROLLED"
                    or row["program_id"] not in revealed_programs
                ):
                    continue
                fid = str(row["fragrance_id"])
                if fid not in controlled or (
                    row["stage"] == "SKIN" and controlled[fid]["stage"] != "SKIN"
                ):
                    controlled[fid] = row
            for fid, row in controlled.items():
                fragrance = await self.session.scalar(
                    select(Fragrance)
                    .where(Fragrance.id == fid)
                    .options(
                        selectinload(Fragrance.notes).selectinload(FragranceNote.note),
                        selectinload(Fragrance.accords),
                    )
                )
                if fragrance is not None:
                    # Explicit linear affinity-v1 conversion; this is not predicted liking.
                    rating = row["rating"]
                    assert isinstance(rating, (int, float))
                    contribution = (rating - 5.0) / 2.5
                    if fid in contributions:
                        contributions[fid][1].append(contribution)
                    else:
                        contributions[fid] = (fragrance, [contribution])
        return contributions

    async def calculate_match_score(
        self, profile: UserProfile, fragrance: Fragrance
    ) -> MatchResult:
        """Calculate match score for a fragrance against user preferences.

        Uses weighted component scoring with veto mechanism for strong dislikes.

        Args:
            profile (UserProfile): User preference profile.
            fragrance (Fragrance): Fragrance to score.

        Returns:
            MatchResult: MatchResult with normalized score and components.
        """
        # Build note ID to name mapping for veto reporting
        note_names: dict[str, str] = {}
        for fn in fragrance.notes:
            note_names[fn.note.id] = fn.note.name

        # Check for veto (strong dislike of any note)
        for fn in fragrance.notes:
            affinity = profile.note_affinities.get(fn.note.id, 0)
            if affinity < VETO_THRESHOLD:
                return MatchResult(
                    score=0.1,
                    score_percent=10,
                    vetoed=True,
                    veto_note=fn.note.name,
                )

        # Calculate note score
        note_scores = [
            profile.note_affinities.get(fn.note.id, 0) for fn in fragrance.notes
        ]
        note_score = sum(note_scores) / max(len(note_scores), 1)

        # Calculate accord score
        accord_scores = [
            profile.accord_affinities.get(acc.accord_type, 0) * acc.intensity
            for acc in fragrance.accords
        ]
        accord_score = sum(accord_scores) / max(len(accord_scores), 1)

        # Calculate family scores
        family_score = profile.family_affinities.get(fragrance.primary_family, 0)
        subfamily_score = profile.family_affinities.get(fragrance.subfamily, 0)

        # Weighted sum (raw score can be negative)
        raw_score = (
            COMPONENT_WEIGHTS["notes"] * note_score
            + COMPONENT_WEIGHTS["accords"] * accord_score
            + COMPONENT_WEIGHTS["family"] * family_score
            + COMPONENT_WEIGHTS["subfamily"] * subfamily_score
        )

        # Normalize to 0-1 range using sigmoid
        # Maps roughly: -4 → 0.1, 0 → 0.5, +4 → 0.9
        #
        # #EDGE: data integrity: raw_score is an unbounded weighted sum of
        # accumulated note/accord/family affinities, so it grows without
        # bound as a reviewer's evaluation history grows (more evaluations
        # -> larger affinity magnitudes -> larger raw_score). math.exp(-x)
        # raises OverflowError once x exceeds ~709.78 (float64 max), and the
        # sigmoid is already indistinguishable from 0.0/1.0 at float
        # precision long before that.
        # #VERIFY: clamp the sigmoid input to +/-50 before calling
        # math.exp; sigmoid(+/-50) already round-trips to 1.0/~1.9e-22 in
        # float64, so this loses no precision the raw float couldn't
        # already lose, while guaranteeing no OverflowError regardless of
        # how large raw_score grows in either direction.
        clamped_raw_score = max(-50.0, min(50.0, raw_score))
        normalized = 1 / (1 + math.exp(-clamped_raw_score))

        return MatchResult(
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
        )

    async def get_recommendations(
        self,
        reviewer_id: str,
        limit: int = 10,
        exclude_rated: bool = True,
    ) -> list[Recommendation]:
        """Generate personalized fragrance recommendations.

        Args:
            reviewer_id (str): UUID of the reviewer.
            limit (int): Maximum recommendations to return.
            exclude_rated (bool): Whether to exclude already-rated fragrances.

        Returns:
            list[Recommendation]: List of recommendations sorted by match score.

        Raises:
            InsufficientDataError: If user has fewer than MIN_EVALUATIONS.
        """
        # Build preference profile
        profile = await self.build_preference_profile(reviewer_id)

        if profile.evaluation_count < MIN_EVALUATIONS:
            msg = f"Need at least {MIN_EVALUATIONS} evaluations for recommendations"
            raise InsufficientDataError(msg)

        # Get candidate fragrances
        # Critical finding 2: soft-delete filter on the recommendation
        # engine's catalog scan.
        stmt = (
            select(Fragrance)
            .where(Fragrance.deleted_at.is_(None))
            .options(
                selectinload(Fragrance.notes).selectinload(FragranceNote.note),
                selectinload(Fragrance.accords),
            )
        )

        # Assigned holdouts must remain absent from every recommendation
        # surface, even when exclude_rated is false. Merely showing the
        # candidate would disclose a concealed program version.
        holdout_ids = await PreferenceHistoryService(self.session).excluded_versions(
            reviewer_id
        )
        if holdout_ids:
            stmt = stmt.where(Fragrance.id.notin_(holdout_ids))

        # Exclude already-rated fragrances if requested
        if exclude_rated:
            rated_stmt = select(Evaluation.fragrance_id).where(
                Evaluation.reviewer_id == reviewer_id,
                Evaluation.deleted_at.is_(None),
            )
            rated_result = await self.session.execute(rated_stmt)
            rated_ids = {row[0] for row in rated_result.all()}
            controlled_ids = await self.session.scalars(
                select(Membership.fragrance_id)
                .join(Presentation, Presentation.membership_id == Membership.id)
                .join(
                    CalibrationSession, CalibrationSession.id == Presentation.session_id
                )
                .join(Enrollment, Enrollment.id == CalibrationSession.enrollment_id)
                .join(Observation, Observation.presentation_id == Presentation.id)
                .where(
                    Enrollment.reviewer_id == reviewer_id,
                    Enrollment.revealed_at.is_not(None),
                    Presentation.blotter_locked_at.is_not(None),
                )
            )
            rated_ids.update(controlled_ids)
            stmt = stmt.where(Fragrance.id.notin_(rated_ids))

        result = await self.session.execute(stmt)
        candidates = list(result.scalars().all())

        # Score all candidates
        recommendations: list[Recommendation] = []
        for fragrance in candidates:
            match_result = await self.calculate_match_score(profile, fragrance)
            recommendations.append(
                Recommendation(
                    fragrance_id=fragrance.id,
                    fragrance_name=fragrance.name,
                    fragrance_brand=fragrance.brand,
                    match_score=match_result.score,
                    match_percent=match_result.score_percent,
                    vetoed=match_result.vetoed,
                    veto_reason=(
                        f"Contains {match_result.veto_note} which you dislike"
                        if match_result.vetoed
                        else None
                    ),
                    components=match_result.components,
                )
            )

        # Sort by score descending, vetoed items last
        recommendations.sort(key=lambda r: (not r.vetoed, r.match_score), reverse=True)

        return recommendations[:limit]

    async def get_reviewer_profile_summary(
        self, reviewer_id: str
    ) -> ReviewerProfileSummary:
        """Get a summary of reviewer preferences for display.

        Args:
            reviewer_id (str): UUID of the reviewer.

        Returns:
            ReviewerProfileSummary: Liked and disliked notes, top accords and
                families, and the evaluation count.
        """
        profile = await self.build_preference_profile(reviewer_id)

        return ReviewerProfileSummary(
            evaluation_count=profile.evaluation_count,
            top_liked_notes=profile.top_liked_notes,
            top_disliked_notes=profile.top_disliked_notes,
            top_accords=sorted(
                profile.accord_affinities.items(), key=lambda x: x[1], reverse=True
            )[:5],
            top_families=sorted(
                profile.family_affinities.items(), key=lambda x: x[1], reverse=True
            )[:5],
        )
