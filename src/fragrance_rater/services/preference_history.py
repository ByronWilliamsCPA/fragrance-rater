"""One preference history with explicit measurement and training provenance."""

from __future__ import annotations

from typing import TYPE_CHECKING

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
        """Load live ordinary encounters newest first."""
        return list(
            await self.db.scalars(
                select(Evaluation)
                .where(
                    Evaluation.reviewer_id == reviewer_id,
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
                    "responses": observation.responses,
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
