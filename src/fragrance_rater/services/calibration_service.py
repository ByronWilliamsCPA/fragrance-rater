"""Transactional controlled evaluations and identity-safe participant views."""

from __future__ import annotations

import secrets
from typing import TYPE_CHECKING, NoReturn

from fastapi import HTTPException
from sqlalchemy import or_, select

from fragrance_rater.models.calibration import (
    CalibrationSession,
    Enrollment,
    Membership,
    Observation,
    Presentation,
    Program,
)
from fragrance_rater.models.fragrance import Fragrance
from fragrance_rater.models.reviewer import Reviewer
from fragrance_rater.services.llm_service import get_llm_service
from fragrance_rater.utils.timestamps import now_naive_utc

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from fragrance_rater.schemas.calibration import (
        EnrollmentInput,
        MembershipInput,
        ResponseInput,
    )


def reject(message: str, status: int = 409) -> NoReturn:
    """Raise a public domain error without disclosing hidden identity."""
    raise HTTPException(status_code=status, detail=message)


class CalibrationService:
    """Serialize all mutations on an evaluator's enrollment row."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def program(self, program_id: str) -> Program:
        """Fetch and lock a definition before edits or activation."""
        obj = await self.db.scalar(
            select(Program).where(Program.id == program_id).with_for_update()
        )
        if obj is None:
            reject("Program not found", 404)
        assert obj is not None
        return obj

    async def add_member(self, program_id: str, data: MembershipInput) -> Membership:
        """Require explicit version evidence and consistent hidden-repeat linkage."""
        program = await self.program(program_id)
        if program.status != "draft":
            reject("Program definition is locked")
        fragrance = await self.db.scalar(
            select(Fragrance).where(Fragrance.id == data.fragrance_id).with_for_update()
        )
        if fragrance is None or fragrance.deleted_at is not None:
            reject("Catalog version not found", 404)
        assert fragrance is not None
        if fragrance.concentration in {"", "Unknown"}:
            reject("Resolve concentration before assignment")
        if data.role == "HIDDEN_REPEAT":
            original = (
                await self.db.get(Membership, data.repeat_of_id)
                if data.repeat_of_id
                else None
            )
            if (
                original is None
                or original.program_id != program_id
                or original.fragrance_id != data.fragrance_id
                or original.role != "UNIVERSAL_BASELINE"
            ):
                reject("Hidden repeat must link to its baseline version")
        elif data.repeat_of_id is not None:
            reject("Only hidden repeats may link to an original")
        existing = list(
            await self.db.scalars(
                select(Membership).where(
                    Membership.program_id == program_id,
                    Membership.fragrance_id == data.fragrance_id,
                )
            )
        )
        if (data.role == "HOLDOUT" and existing) or any(
            x.role == "HOLDOUT" for x in existing
        ):
            reject("Holdout version cannot also be a training member")
        selection = dict(data.selection)
        selection["identity_evidence"] = data.identity_evidence
        member = Membership(
            program_id=program_id,
            fragrance_id=data.fragrance_id,
            role=data.role,
            repeat_of_id=data.repeat_of_id,
            group_name=data.group_name,
            selection=selection,
        )
        self.db.add(member)
        await self.db.flush()
        return member

    async def enroll(self, program_id: str, data: EnrollmentInput) -> Enrollment:
        """Assign independent blind codes and randomized order for each evaluator."""
        program = await self.program(program_id)
        if program.status != "active":
            reject("Activate the definition before enrollment")
        reviewer = await self.db.get(Reviewer, data.reviewer_id)
        if reviewer is None or reviewer.deleted_at is not None:
            reject("Reviewer not found", 404)
        if await self.db.scalar(
            select(Enrollment.id).where(
                Enrollment.program_id == program_id,
                Enrollment.reviewer_id == data.reviewer_id,
            )
        ):
            reject("Reviewer already enrolled")
        get_llm_service().invalidate_reviewer_cache(data.reviewer_id)
        enrollment = Enrollment(
            program_id=program_id,
            reviewer_id=data.reviewer_id,
            recorder_usernames=data.recorder_usernames,
        )
        self.db.add(enrollment)
        await self.db.flush()
        members = list(
            await self.db.scalars(
                select(Membership).where(Membership.program_id == program_id)
            )
        )
        # Mix concealed repeats into the baseline with at least one session's
        # separation when enough stimuli exist. Holdouts remain a later block.
        baseline = [m for m in members if m.role not in {"HIDDEN_REPEAT", "HOLDOUT"}]
        secrets.SystemRandom().shuffle(baseline)
        for repeat in [m for m in members if m.role == "HIDDEN_REPEAT"]:
            original_index = next(
                i for i, m in enumerate(baseline) if m.id == repeat.repeat_of_id
            )
            earliest = min(original_index + 2 * data.session_size, len(baseline))
            position = earliest + secrets.randbelow(len(baseline) - earliest + 1)
            baseline.insert(position, repeat)
        holdouts = [m for m in members if m.role == "HOLDOUT"]
        secrets.SystemRandom().shuffle(holdouts)
        blocks = [baseline, holdouts]
        for block in blocks:
            for offset in range(0, len(block), data.session_size):
                session = CalibrationSession(enrollment_id=enrollment.id, context={})
                self.db.add(session)
                await self.db.flush()
                for position, member in enumerate(
                    block[offset : offset + data.session_size], start=1
                ):
                    self.db.add(
                        Presentation(
                            session_id=session.id,
                            membership_id=member.id,
                            blind_code=secrets.token_hex(4).upper(),
                            position=position,
                        )
                    )
        await self.db.flush()
        return enrollment

    async def enrollment(
        self, enrollment_id: str, username: str, admin: bool
    ) -> Enrollment:
        """Enforce explicit recorder grants; never infer reviewer from username."""
        obj = await self.db.scalar(
            select(Enrollment).where(Enrollment.id == enrollment_id).with_for_update()
        )
        if obj is None:
            reject("Enrollment not found", 404)
        assert obj is not None
        if not admin and username not in obj.recorder_usernames:
            reject("Recorder is not assigned to this evaluator", 403)
        return obj

    async def presentations(self, enrollment_id: str) -> list[Presentation]:
        """List presentation records for internal use only."""
        return list(
            await self.db.scalars(
                select(Presentation)
                .join(CalibrationSession)
                .where(CalibrationSession.enrollment_id == enrollment_id)
                .order_by(
                    CalibrationSession.created_at,
                    CalibrationSession.id,
                    Presentation.position,
                )
            )
        )

    async def target(
        self, presentation_id: str, username: str, admin: bool
    ) -> tuple[Presentation, Enrollment]:
        """Resolve a target through enrollment authorization and locking."""
        obj = await self.db.get(Presentation, presentation_id)
        if obj is None:
            reject("Presentation not found", 404)
        assert obj is not None
        session = await self.db.get(CalibrationSession, obj.session_id)
        assert session is not None
        enrollment = await self.enrollment(session.enrollment_id, username, admin)
        # Refresh after acquiring the enrollment lock: another transaction may have locked it.
        await self.db.refresh(obj)
        return obj, enrollment

    async def observe(
        self,
        presentation_id: str,
        data: ResponseInput,
        username: str,
        admin: bool,
        post_reveal: bool = False,
    ) -> Observation:
        """Append responses only; no update route exists for submitted observations."""
        obj, enrollment = await self.target(presentation_id, username, admin)
        member = await self.db.get(Membership, obj.membership_id)
        assert member is not None
        identity_visible = enrollment.revealed_at is not None and (
            member.role != "HOLDOUT" or obj.blotter_locked_at is not None
        )
        if post_reveal:
            if not identity_visible:
                reject("Identity has not been revealed")
        else:
            if identity_visible:
                reject("Blind collection ended at reveal")
            if data.stage == "SKIN" and obj.skin_reason is None:
                reject("Skin test must be planned")
            if (data.stage == "BLOTTER" and obj.blotter_locked_at) or (
                data.stage == "SKIN" and obj.skin_locked_at
            ):
                reject("Stage is locked; original responses are retained")
        prior_exposure = await self.db.scalar(
            select(Enrollment.id)
            .join(CalibrationSession, CalibrationSession.enrollment_id == Enrollment.id)
            .join(Presentation, Presentation.session_id == CalibrationSession.id)
            .join(Membership, Presentation.membership_id == Membership.id)
            .where(
                Enrollment.reviewer_id == enrollment.reviewer_id,
                Enrollment.revealed_at.is_not(None),
                Membership.fragrance_id == member.fragrance_id,
                Enrollment.id != enrollment.id,
                or_(
                    Membership.role != "HOLDOUT",
                    Presentation.blotter_locked_at.is_not(None),
                ),
            )
        )
        phase = (
            "POST_REVEAL"
            if post_reveal
            else ("PREVIOUSLY_REVEALED" if prior_exposure else "PRE_REVEAL")
        )
        observation = Observation(
            presentation_id=obj.id,
            stage=data.stage,
            phase=phase,
            elapsed_minutes=data.elapsed_minutes,
            detected=data.detected,
            intensity=data.intensity,
            liking=data.liking,
            responses=data.model_dump(mode="json"),
            recorded_by=username,
        )
        self.db.add(observation)
        await self.db.flush()
        return observation

    async def lock_stage(
        self, presentation_id: str, stage: str, username: str, admin: bool
    ) -> None:
        """Lock a stage only after at least one detection answer is submitted."""
        obj, enrollment = await self.target(presentation_id, username, admin)
        member = await self.db.get(Membership, obj.membership_id)
        assert member is not None
        if enrollment.revealed_at is not None and member.role != "HOLDOUT":
            reject("Blind collection ended at reveal")
        if stage not in {"BLOTTER", "SKIN"} or (
            stage == "SKIN" and not obj.skin_reason
        ):
            reject("Invalid stage")
        answered = await self.db.scalar(
            select(Observation.id).where(
                Observation.presentation_id == obj.id,
                Observation.stage == stage,
                Observation.phase.in_(["PRE_REVEAL", "PREVIOUSLY_REVEALED"]),
                Observation.detected.is_not(None),
            )
        )
        if answered is None:
            reject("Submit a detection response before locking")
        if stage == "BLOTTER":
            obj.blotter_locked_at = obj.blotter_locked_at or now_naive_utc()
        else:
            obj.skin_locked_at = obj.skin_locked_at or now_naive_utc()
        await self.db.flush()

    async def reveal(self, enrollment_id: str, username: str, admin: bool) -> None:
        """Reveal only after baseline, repeats, and the finalized skin plan are locked."""
        enrollment = await self.enrollment(enrollment_id, username, admin)
        if enrollment.revealed_at:
            return
        if enrollment.skin_plan_locked_at is None:
            reject("Finalize the planned skin tests before reveal")
        presentations = await self.presentations(enrollment_id)
        for obj in presentations:
            member = await self.db.get(Membership, obj.membership_id)
            assert member is not None
            if member.role != "HOLDOUT" and obj.blotter_locked_at is None:
                reject("All baseline and repeat blotter responses must be locked")
            if obj.skin_reason and obj.skin_locked_at is None:
                reject("All planned blind skin tests must be locked")
        enrollment.revealed_at = now_naive_utc()
        enrollment.revealed_by = username
        get_llm_service().invalidate_reviewer_cache(enrollment.reviewer_id)
        await self.db.flush()

    async def participant_view(self, enrollment: Enrollment) -> dict[str, object]:
        """Build an allowlisted payload; never serialize hidden ORM rows."""
        presentations = await self.presentations(enrollment.id)
        membership_ids = {obj.membership_id for obj in presentations}
        members = {
            member.id: member
            for member in await self.db.scalars(
                select(Membership).where(Membership.id.in_(membership_ids))
            )
        }
        presentation_ids = {obj.id for obj in presentations}
        observations_by_presentation: dict[str, list[Observation]] = {
            presentation_id: [] for presentation_id in presentation_ids
        }
        for observation in await self.db.scalars(
            select(Observation)
            .where(Observation.presentation_id.in_(presentation_ids))
            .order_by(Observation.created_at, Observation.id)
        ):
            observations_by_presentation[observation.presentation_id].append(
                observation
            )
        fragrance_ids = {member.fragrance_id for member in members.values()}
        fragrances = (
            {
                fragrance.id: fragrance
                for fragrance in await self.db.scalars(
                    select(Fragrance).where(Fragrance.id.in_(fragrance_ids))
                )
            }
            if enrollment.revealed_at
            else {}
        )
        result: list[dict[str, object]] = []
        for obj in presentations:
            row: dict[str, object] = {
                "id": obj.id,
                "session_id": obj.session_id,
                "blind_code": obj.blind_code,
                "position": obj.position,
                "skin_planned": obj.skin_reason is not None,
                "blotter_locked": obj.blotter_locked_at is not None,
                "skin_locked": obj.skin_locked_at is not None,
            }
            observations = observations_by_presentation[obj.id]
            row["observations"] = [
                {
                    "id": o.id,
                    "phase": o.phase,
                    "created_at": o.created_at.isoformat(),
                    **o.responses,
                }
                for o in observations
            ]
            member = members[obj.membership_id]
            # Holdout identities stay concealed until their own blind response is locked.
            if enrollment.revealed_at and (
                member.role != "HOLDOUT" or obj.blotter_locked_at
            ):
                fragrance = fragrances[member.fragrance_id]
                row["identity"] = {
                    "fragrance_id": fragrance.id,
                    "name": fragrance.name,
                    "brand": fragrance.brand,
                    "concentration": fragrance.concentration,
                }
            result.append(row)
        return {
            "id": enrollment.id,
            "program_id": enrollment.program_id,
            "reviewer_id": enrollment.reviewer_id,
            "revealed": enrollment.revealed_at is not None,
            "skin_plan_locked": enrollment.skin_plan_locked_at is not None,
            "presentations": result,
        }
