"""Recommendation service implementing ADR-004 weighted affinity scoring.

This module implements the recommendation algorithm with:
- Cumulative note/accord/family affinities from user ratings
- Veto mechanism for strongly disliked notes
- Weighted scoring with configurable component weights
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, TypedDict

from sqlalchemy import or_, select
from sqlalchemy.orm import selectinload

from fragrance_rater.core.exceptions import BusinessLogicError
from fragrance_rater.core.vocabulary import TRAINING_INELIGIBLE_CODES
from fragrance_rater.ml.feature_space import vectorize
from fragrance_rater.ml.model import (
    COMPONENT_WEIGHTS,
    DEFAULT_SCORER_FACTORY,
    RATING_WEIGHTS,
    VETO_THRESHOLD,
    Scorer,
    UserProfile,
)
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


# Minimum contributing versions required before recommendations are shown.
# This is a display gate, not a scoring parameter; scoring itself lives in
# fragrance_rater.ml.model (RATING_WEIGHTS, COMPONENT_WEIGHTS, VETO_THRESHOLD
# and UserProfile are re-exported from there for compatibility).
MIN_EVALUATIONS = 3


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
        model (Scorer | None): Scoring model; defaults to the registered default
            scorer (``affinity-v2``). Inject ``AffinityV1()`` for reference
            comparisons.
    """

    def __init__(self, session: AsyncSession, model: Scorer | None = None) -> None:
        self.session = session
        # The scoring model. Defaults to the frozen affinity-v1 heuristic; a
        # registered alternative can be injected to score the same eligible
        # evidence under the same rules (ML structure review, M-03/M-11).
        self.model: Scorer = model if model is not None else DEFAULT_SCORER_FACTORY()

    async def build_preference_profile(
        self, reviewer_id: str, *, excluded: set[str] | None = None
    ) -> UserProfile:
        """Build a user preference profile from their evaluations.

        Aggregates note/accord/family affinities using rating weights:
        - 5 stars = +2.0
        - 4 stars = +1.0
        - 3 stars = 0.0 (neutral)
        - 2 stars = -1.0
        - 1 star = -2.0

        Args:
            reviewer_id (str): UUID of the reviewer.
            excluded (set[str] | None): Precomputed experiment exclusions.

        Returns:
            UserProfile: UserProfile with computed affinities.
        """
        # Fetch all evaluations with fragrance details
        # Critical finding 2: soft-delete filter on the evaluation aggregation.
        #
        # ADR-011: worn_by_reviewer_id.is_(None) excludes "on others"
        # ratings (e.g. a partner's opinion of how a fragrance smells on
        # this reviewer) from this reviewer's own affinity profile. That
        # evidence is captured for display but is not yet an accepted
        # scoring input; folding it in would require its own versioned
        # adapter and prospective comparison per ADR-007.
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
                Evaluation.worn_by_reviewer_id.is_(None),
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
        excluded = (
            excluded
            if excluded is not None
            else await history.excluded_versions(reviewer_id)
        )
        # One latest ordinary encounter contributes per version; retain all history.
        evaluations.sort(
            key=lambda e: (e.evaluated_at, e.created_at, e.id), reverse=True
        )
        latest: dict[str, Evaluation] = {}
        for item in evaluations:
            if item.fragrance_id not in excluded:
                latest.setdefault(item.fragrance_id, item)
        evaluations = list(latest.values())

        contributions = await self._contributions(
            reviewer_id, evaluations, history, excluded
        )
        # Accumulation is the model's job (fragrance_rater.ml.model); this
        # service only selects eligible evidence and vectorizes features.
        #
        # ADR-014: a fragrance flagged as not yet eligible to train
        # affinities (e.g. no real Michael Edwards Wheel classification yet)
        # must not contribute its notes/accords/family here. NULL (every
        # fragrance as of this ADR) means "eligible".
        # #ASSUME: data-integrity: `training_eligibility_code` is a trusted
        # match against `TRAINING_INELIGIBLE_CODES` only because both sides
        # are sourced from `core/vocabulary.py` (see that module's own RAD
        # tag); a code that exists in the database but was removed from this
        # frozenset would silently start contributing again instead of
        # raising.
        # #VERIFY: no direct write path assigns a code to
        # `training_eligibility_code` outside the values seeded by
        # `alembic/versions/7daf681ed339_training_eligibility_lookup.py`; the
        # FK to `training_eligibilities.code` is the schema-level backstop
        # against an unknown code, not against a known code later being
        # dropped from `TRAINING_INELIGIBLE_CODES`.
        return self.model.build_profile(
            reviewer_id,
            [
                (vectorize(fragrance), weights)
                for fragrance, weights in contributions.values()
                if fragrance.training_eligibility_code not in TRAINING_INELIGIBLE_CODES
            ],
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
                    # Explicit affinity-v1 conversion (ADR-007); not predicted liking.
                    rating = row["rating"]
                    # #CRITICAL: data integrity: training_manifest already filters
                    # PRE_REVEAL rows with a NULL liking, so a non-numeric rating here
                    # means that upstream invariant regressed. Raising (rather than
                    # silently dropping the row) matches the sibling assert-replacement
                    # in prediction_service.py._link_outcome and keeps a manifest gap
                    # from silently shrinking the evidence a frozen ADR-009 prediction
                    # is scored against.
                    # #VERIFY: if a legitimate non-numeric rating source is ever added,
                    # filter it in training_manifest instead of relaxing this check.
                    if not isinstance(rating, (int, float)):
                        message = (
                            f"controlled manifest row for fragrance {fid!r} has a "
                            f"non-numeric rating {rating!r}; training_manifest should "
                            "have already excluded it"
                        )
                        raise BusinessLogicError(
                            message, rule="numeric_controlled_rating"
                        )
                    contribution = self.model.controlled_affinity(float(rating))
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
        result = self.model.score(profile, vectorize(fragrance))
        return MatchResult(
            score=result.score,
            score_percent=result.score_percent,
            vetoed=result.vetoed,
            veto_note=result.veto_note,
            components=dict(result.components),
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
        history = PreferenceHistoryService(self.session)
        holdout_ids = await history.excluded_versions(reviewer_id)

        # Build the profile and candidate query from one consistent holdout set.
        profile = await self.build_preference_profile(reviewer_id, excluded=holdout_ids)

        if profile.evaluation_count < MIN_EVALUATIONS:
            msg = f"Need at least {MIN_EVALUATIONS} evaluations for recommendations"
            raise InsufficientDataError(msg)

        # Get candidate fragrances
        # Critical finding 2: soft-delete filter on the recommendation
        # engine's catalog scan.
        # ADR-014: a fragrance whose training_eligibility_code is in
        # TRAINING_INELIGIBLE_CODES is correctly excluded from CONTRIBUTING
        # to the trained profile (see build_preference_profile above), but
        # that alone does not stop it being SHOWN as a candidate here; a
        # known-bad/unclassifiable fragrance must not be recommendable
        # either. NULL (eligible) fragrances pass this filter unchanged,
        # since `NOT IN` never matches NULL in SQL.
        stmt = (
            select(Fragrance)
            .where(Fragrance.deleted_at.is_(None))
            .where(
                or_(
                    Fragrance.training_eligibility_code.is_(None),
                    Fragrance.training_eligibility_code.notin_(
                        TRAINING_INELIGIBLE_CODES
                    ),
                )
            )
            .options(
                selectinload(Fragrance.notes).selectinload(FragranceNote.note),
                selectinload(Fragrance.accords),
            )
        )

        # Assigned holdouts must remain absent from every recommendation
        # surface, even when exclude_rated is false. Merely showing the
        # candidate would disclose a concealed program version.
        if holdout_ids:
            stmt = stmt.where(Fragrance.id.notin_(holdout_ids))

        # Exclude already-rated fragrances if requested
        if exclude_rated:
            # ADR-011: an "on others" rating (worn_by_reviewer_id set) means
            # reviewer_id smelled this fragrance on someone else, not that
            # they rated it for themselves; it must not suppress the
            # fragrance from this reviewer's own candidate set.
            rated_stmt = select(Evaluation.fragrance_id).where(
                Evaluation.reviewer_id == reviewer_id,
                Evaluation.worn_by_reviewer_id.is_(None),
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


__all__ = [
    "COMPONENT_WEIGHTS",
    "MIN_EVALUATIONS",
    "RATING_WEIGHTS",
    "VETO_THRESHOLD",
    "InsufficientDataError",
    "MatchResult",
    "Recommendation",
    "RecommendationService",
    "ReviewerProfileSummary",
    "UserProfile",
]
