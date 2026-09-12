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
    SourceSnapshot,
)
from fragrance_rater.models.fragrance import Fragrance
from fragrance_rater.models.reviewer import Reviewer
from fragrance_rater.services.llm_service import get_llm_service
from fragrance_rater.utils.gtin import normalize_gtin
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

    async def _check_gtin_against_source_evidence(
        self, fragrance_id: str, gtin: str
    ) -> None:
        """Reject an operator-entered GTIN that contradicts scraped source evidence.

        # #CRITICAL: data-integrity: this is the actual gap-closing
        # mechanism a barcode is meant to provide - if the physical
        # bottle's scanned GTIN does not match a GTIN already recorded in
        # any of this fragrance's source snapshots (e.g. its Parfumo
        # page), that is a strong, mechanical signal the wrong catalog
        # version is about to be assigned, independent of any text-based
        # ambiguity. Silently accepting the operator's value in that case
        # would defeat the entire point of capturing a barcode.
        # `ParfumoScraper._save_source` appends a new snapshot on every
        # re-scrape rather than updating one in place, so a fragrance can
        # accumulate several snapshots over time - checking only the
        # newest would miss a conflict an older refresh recorded but a
        # later, GTIN-less refresh silently dropped. Absence of a
        # recorded source GTIN in a given snapshot is not evidence of
        # anything (many pages simply do not publish one - see
        # `ParfumoScraper._extract_gtin`) and is not treated as a
        # conflict.
        # #VERIFY: covered by a test asserting a mismatched GTIN is
        # rejected and a matching or absent one is accepted, including
        # when the conflict is on an older, non-latest snapshot.

        Args:
            fragrance_id (str): Catalog version being assigned.
            gtin (str): The operator-entered, already check-digit-valid GTIN.
        """
        snapshots = await self.db.scalars(
            select(SourceSnapshot).where(SourceSnapshot.fragrance_id == fragrance_id)
        )
        normalized_gtin = normalize_gtin(gtin)
        for snapshot in snapshots:
            source_gtin = snapshot.payload.get("gtin")
            if not isinstance(source_gtin, str) or not source_gtin:
                continue
            # Normalize both sides to GTIN-14 (zero-padded) before
            # comparing: a UPC-A (GTIN-12) and the EAN-13/GTIN-14
            # encoding of the exact same product are different-length
            # strings for the identical item, and a raw string compare
            # would reject a legitimate match as a false conflict. Only
            # normalize a source value that is itself all-ASCII digits;
            # anything else falls back to the raw compare rather than
            # risk padding non-numeric scraped text into a misleading
            # match.
            normalized_source = (
                normalize_gtin(source_gtin)
                if source_gtin.isascii() and source_gtin.isdigit()
                else source_gtin
            )
            if normalized_source != normalized_gtin:
                reject(
                    "Entered GTIN does not match this fragrance's recorded "
                    "source evidence - re-check the physical bottle and the "
                    "catalog entry before assigning it"
                )

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
        if data.gtin is not None:
            await self._check_gtin_against_source_evidence(data.fragrance_id, data.gtin)
        selection = dict(data.selection)
        # `selection` is a client-controlled free-form dict; never let a
        # raw "gtin" key inside it stand in for the validated, cross-
        # checked top-level `data.gtin` field, or both the check-digit
        # validation and the source-evidence conflict check above can be
        # bypassed by putting the value under "selection" instead.
        selection.pop("gtin", None)
        selection["identity_evidence"] = data.identity_evidence
        if data.gtin is not None:
            selection["gtin"] = data.gtin
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
        presentations = await self.presentations(enrollment_id)
        members = {
            member.id: member
            for member in await self.db.scalars(
                select(Membership).where(
                    Membership.id.in_({obj.membership_id for obj in presentations})
                )
            )
        }
        blocker = self.reveal_blocker(enrollment, presentations, members)
        if blocker == "SKIN_PLAN":
            reject("Finalize the planned skin tests before reveal")
        if blocker == "BLOTTER":
            reject("All baseline and repeat blotter responses must be locked")
        if blocker == "SKIN":
            reject("All planned blind skin tests must be locked")
        enrollment.revealed_at = now_naive_utc()
        enrollment.revealed_by = username
        get_llm_service().invalidate_reviewer_cache(enrollment.reviewer_id)
        await self.db.flush()

    @staticmethod
    def reveal_blocker(
        enrollment: Enrollment,
        presentations: list[Presentation],
        members: dict[str, Membership],
    ) -> str | None:
        """Return a disclosure-safe reason that currently prevents reveal."""
        if enrollment.skin_plan_locked_at is None:
            return "SKIN_PLAN"
        if any(
            members[obj.membership_id].role != "HOLDOUT"
            and obj.blotter_locked_at is None
            for obj in presentations
        ):
            return "BLOTTER"
        if any(obj.skin_reason and obj.skin_locked_at is None for obj in presentations):
            return "SKIN"
        return None

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
        reveal_blocker = (
            None
            if enrollment.revealed_at
            else self.reveal_blocker(enrollment, presentations, members)
        )
        return {
            "id": enrollment.id,
            "program_id": enrollment.program_id,
            "reviewer_id": enrollment.reviewer_id,
            "revealed": enrollment.revealed_at is not None,
            "reveal_eligible": reveal_blocker is None
            and enrollment.revealed_at is None,
            "reveal_blocker": reveal_blocker,
            "skin_plan_locked": enrollment.skin_plan_locked_at is not None,
            "presentations": result,
        }
