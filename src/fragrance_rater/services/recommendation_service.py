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
from typing import TYPE_CHECKING

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from fragrance_rater.models.evaluation import Evaluation
from fragrance_rater.models.fragrance import Fragrance, FragranceNote

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
    """User preference profile built from evaluations."""

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


class InsufficientDataError(Exception):
    """Raised when user doesn't have enough evaluations for recommendations."""


class RecommendationService:
    """Service for generating personalized fragrance recommendations.

    Implements the weighted affinity scoring algorithm from ADR-004.
    """

    def __init__(self, session: AsyncSession) -> None:
        """Initialize the service with a database session.

        Args:
            session: Async database session.
        """
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
            reviewer_id: UUID of the reviewer.

        Returns:
            UserProfile with computed affinities.
        """
        # Fetch all evaluations with fragrance details
        stmt = (
            select(Evaluation)
            .where(Evaluation.reviewer_id == reviewer_id)
            .options(
                selectinload(Evaluation.fragrance)
                .selectinload(Fragrance.notes)
                .selectinload(FragranceNote.note),
                selectinload(Evaluation.fragrance).selectinload(Fragrance.accords),
            )
        )
        result = await self.session.execute(stmt)
        evaluations = list(result.scalars().all())

        # Initialize affinity dictionaries
        note_affinities: dict[str, float] = defaultdict(float)
        note_names: dict[str, str] = {}  # id -> name mapping
        accord_affinities: dict[str, float] = defaultdict(float)
        family_affinities: dict[str, float] = defaultdict(float)

        for evaluation in evaluations:
            weight = RATING_WEIGHTS.get(evaluation.rating, 0.0)
            fragrance = evaluation.fragrance

            # Accumulate note affinities
            for fn in fragrance.notes:
                note_affinities[fn.note.id] += weight
                note_names[fn.note.id] = fn.note.name

            # Accumulate accord affinities (weighted by intensity)
            for accord in fragrance.accords:
                accord_affinities[accord.accord_type] += weight * accord.intensity

            # Accumulate family affinities
            family_affinities[fragrance.primary_family] += weight
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
            evaluation_count=len(evaluations),
            top_liked_notes=top_liked,
            top_disliked_notes=list(reversed(top_disliked)),
        )

    async def calculate_match_score(
        self, profile: UserProfile, fragrance: Fragrance
    ) -> MatchResult:
        """Calculate match score for a fragrance against user preferences.

        Uses weighted component scoring with veto mechanism for strong dislikes.

        Args:
            profile: User preference profile.
            fragrance: Fragrance to score.

        Returns:
            MatchResult with normalized score and components.
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
        normalized = 1 / (1 + math.exp(-raw_score))

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
            reviewer_id: UUID of the reviewer.
            limit: Maximum recommendations to return.
            exclude_rated: Whether to exclude already-rated fragrances.

        Returns:
            List of recommendations sorted by match score.

        Raises:
            InsufficientDataError: If user has fewer than MIN_EVALUATIONS.
        """
        # Build preference profile
        profile = await self.build_preference_profile(reviewer_id)

        if profile.evaluation_count < MIN_EVALUATIONS:
            msg = f"Need at least {MIN_EVALUATIONS} evaluations for recommendations"
            raise InsufficientDataError(msg)

        # Get candidate fragrances
        stmt = select(Fragrance).options(
            selectinload(Fragrance.notes).selectinload(FragranceNote.note),
            selectinload(Fragrance.accords),
        )

        # Exclude already-rated fragrances if requested
        if exclude_rated:
            rated_stmt = select(Evaluation.fragrance_id).where(
                Evaluation.reviewer_id == reviewer_id
            )
            rated_result = await self.session.execute(rated_stmt)
            rated_ids = {row[0] for row in rated_result.all()}
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
    ) -> dict[str, list[tuple[str, float]] | int]:
        """Get a summary of reviewer preferences for display.

        Args:
            reviewer_id: UUID of the reviewer.

        Returns:
            Dictionary with liked notes, disliked notes, and evaluation count.
        """
        profile = await self.build_preference_profile(reviewer_id)

        return {
            "evaluation_count": profile.evaluation_count,
            "top_liked_notes": profile.top_liked_notes,
            "top_disliked_notes": profile.top_disliked_notes,
            "top_accords": sorted(
                profile.accord_affinities.items(), key=lambda x: x[1], reverse=True
            )[:5],
            "top_families": sorted(
                profile.family_affinities.items(), key=lambda x: x[1], reverse=True
            )[:5],
        }
