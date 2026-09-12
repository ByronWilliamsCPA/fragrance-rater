"""One preference history with explicit measurement and training provenance."""

from __future__ import annotations

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

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class ObservationFeatures(TypedDict):
    """Named, typed ML feature values frozen into a controlled manifest row.

    Every entry mirrors a bounded, numeric/boolean ``Observation`` column
    (see its ``CheckConstraint``-enforced ranges in
    ``models/calibration.py``) except ``perceived_notes``, which is
    intentionally an unbounded list of free-text labels kept here rather
    than in ``notes_text``: downstream consumers treat it as a queryable
    per-observation feature (see
    ``test_controlled_manifest_exposes_typed_features_not_a_responses_blob``),
    not as prose to be read.
    """

    detected: bool | None
    intensity: int | None
    elapsed_minutes: int
    confidence: int | None
    sweetness: int | None
    freshness: int | None
    density: int | None
    familiarity: int | None
    dryness: int | None
    clean_soapy: int | None
    earthy_rooty: int | None
    bodily_animalic: int | None
    discomfort: int | None
    opening_liking: int | None
    drydown_liking: int | None
    would_wear: int | None
    would_buy: int | None
    artistic_appreciation: int | None
    projection: int | None
    longevity_minutes: int | None
    perceived_notes: list[str] | None


class ObservationNotesText(TypedDict):
    """Raw free-text fields frozen into a controlled manifest row."""

    likes: str | None
    dislikes: str | None
    reminds_me_of: str | None
    comments: str | None


class PreferenceHistoryService:
    """Centralize holdout exclusions and immutable input manifests."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def excluded_versions(self, reviewer_id: str) -> set[str]:
        """Conservatively exclude every assigned holdout across all workflows."""
        return set(
            await self.db.scalars(
                select(Membership.fragrance_id)
                .join(Enrollment, Enrollment.program_id == Membership.program_id)
                .where(
                    Enrollment.reviewer_id == reviewer_id, Membership.role == "HOLDOUT"
                )
            )
        )

    async def _ordinary(self, reviewer_id: str) -> list[Evaluation]:
        """Load live ordinary encounters newest first.

        ADR-011: excludes "on others" ratings (`worn_by_reviewer_id` set),
        e.g. a partner's opinion of a fragrance worn by someone else. Those
        are captured evidence, not yet an accepted input to this reviewer's
        own training manifest; see the identical exclusion in
        recommendation_service.py's affinity query.
        """
        return list(
            await self.db.scalars(
                select(Evaluation)
                .where(
                    Evaluation.reviewer_id == reviewer_id,
                    Evaluation.worn_by_reviewer_id.is_(None),
                    Evaluation.deleted_at.is_(None),
                )
                .order_by(
                    Evaluation.evaluated_at.desc(),
                    Evaluation.created_at.desc(),
                    Evaluation.id.desc(),
                )
            )
        )

    async def training_manifest(
        self,
        reviewer_id: str,
        *,
        excluded: set[str] | None = None,
        ordinary: list[Evaluation] | None = None,
    ) -> list[dict[str, object]]:
        """Freeze raw response values and source features; no scale conflation."""
        excluded = (
            excluded
            if excluded is not None
            else await self.excluded_versions(reviewer_id)
        )
        ordinary = (
            ordinary if ordinary is not None else await self._ordinary(reviewer_id)
        )
        rows: list[dict[str, object]] = []
        seen: set[str] = set()
        # Latest encounter per version contributes; every encounter remains in history.
        for obj in ordinary:
            if obj.fragrance_id in excluded or obj.fragrance_id in seen:
                continue
            seen.add(obj.fragrance_id)
            rows.append(
                {
                    "id": obj.id,
                    "fragrance_id": obj.fragrance_id,
                    "workflow": "ORDINARY",
                    "scale": "1-5",
                    "rating": obj.rating,
                    "observed_at": obj.evaluated_at.isoformat(),
                    "notes": obj.notes,
                }
            )
        controlled = (
            await self.db.execute(
                select(Observation, Presentation, Membership, Enrollment)
                .join(Presentation, Observation.presentation_id == Presentation.id)
                .join(Membership, Presentation.membership_id == Membership.id)
                .join(
                    CalibrationSession, Presentation.session_id == CalibrationSession.id
                )
                .join(Enrollment, CalibrationSession.enrollment_id == Enrollment.id)
                .where(
                    Enrollment.reviewer_id == reviewer_id,
                    Observation.phase == "PRE_REVEAL",
                )
                .order_by(Observation.created_at.desc(), Observation.id.desc())
            )
        ).all()
        selected: set[tuple[str, str]] = set()
        for observation, presentation, member, enrollment in controlled:
            key = (presentation.id, observation.stage)
            if (
                member.fragrance_id in excluded
                or member.role == "HIDDEN_REPEAT"
                or key in selected
            ):
                continue
            locked = (
                presentation.skin_locked_at
                if observation.stage == "SKIN"
                else presentation.blotter_locked_at
            )
            if locked is None:
                continue
            selected.add(key)
            if observation.liking is None:
                continue
            # Named, typed ML features (previously one opaque `responses`
            # JSON blob), per the facts/derived/inference and published-vs-
            # perceived distinctions in
            # docs/planning/data-model-gap-analysis.md. Most entries are
            # bounded, typed values; `perceived_notes` is the deliberate
            # exception, kept here as free-text labels rather than in
            # `notes_text` (see `ObservationFeatures`'s docstring). Backed by
            # a TypedDict so a future key rename/removal is caught by
            # basedpyright rather than silently drifting in the frozen
            # manifest.
            features: ObservationFeatures = {
                "detected": observation.detected,
                "intensity": observation.intensity,
                "elapsed_minutes": observation.elapsed_minutes,
                "confidence": observation.confidence,
                "sweetness": observation.sweetness,
                "freshness": observation.freshness,
                "density": observation.density,
                "familiarity": observation.familiarity,
                "dryness": observation.dryness,
                "clean_soapy": observation.clean_soapy,
                "earthy_rooty": observation.earthy_rooty,
                "bodily_animalic": observation.bodily_animalic,
                "discomfort": observation.discomfort,
                "opening_liking": observation.opening_liking,
                "drydown_liking": observation.drydown_liking,
                "would_wear": observation.would_wear,
                "would_buy": observation.would_buy,
                "artistic_appreciation": observation.artistic_appreciation,
                "projection": observation.projection,
                "longevity_minutes": observation.longevity_minutes,
                "perceived_notes": observation.perceived_notes,
            }
            notes_text: ObservationNotesText = {
                "likes": observation.likes,
                "dislikes": observation.dislikes,
                "reminds_me_of": observation.reminds_me_of,
                "comments": observation.comments,
            }
            rows.append(
                {
                    "id": observation.id,
                    "fragrance_id": member.fragrance_id,
                    "workflow": "CONTROLLED",
                    "stage": observation.stage,
                    "role": member.role,
                    "phase": observation.phase,
                    "program_id": enrollment.program_id,
                    "scale": "0-10",
                    "rating": observation.liking,
                    "features": features,
                    "notes_text": notes_text,
                    "observed_at": observation.created_at.isoformat(),
                }
            )
        fragrance_ids = {str(row["fragrance_id"]) for row in rows}
        fragrances = {
            fragrance.id: fragrance
            for fragrance in await self.db.scalars(
                select(Fragrance)
                .where(Fragrance.id.in_(fragrance_ids), Fragrance.deleted_at.is_(None))
                .options(
                    selectinload(Fragrance.notes).selectinload(FragranceNote.note),
                    selectinload(Fragrance.accords),
                )
            )
        }
        result: list[dict[str, object]] = []
        for row in rows:
            fragrance = fragrances.get(str(row["fragrance_id"]))
            if fragrance is None:
                continue
            row["source_features"] = {
                "version_key": fragrance.version_key,
                "concentration": fragrance.concentration,
                "primary_family": fragrance.primary_family,
                "subfamily": fragrance.subfamily,
                "notes": [
                    {"name": n.note.name, "position": n.position}
                    for n in fragrance.notes
                ],
                "accords": [
                    {"name": a.accord_type, "intensity": a.intensity}
                    for a in fragrance.accords
                ],
            }
            result.append(row)
        return result
