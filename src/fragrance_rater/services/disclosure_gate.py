"""Server-side holdout gate, checkpoint readiness, and the household reveal.

Three rules protect prospective evaluation (ADR-009) and blind collection
(ADR-005) independently of any UI:

* **Holdout gate.** A ``HOLDOUT`` sample takes no exposure, observation, lock,
  session start, or ranking until a checkpoint exists for its enrollment.
  Checkpoint creation is refused once a holdout has been observed, so a holdout
  answered first would lose its prospective evaluation for good; the gate makes
  that order impossible rather than merely discouraged.
* **Checkpoint readiness.** Which enrollments can be checkpointed now: blind
  baseline and repeat blotters locked, the skin plan finalized, planned
  non-holdout skin stages locked, and no holdout observed.
* **Reveal policy.** ``ENROLLMENT`` programs keep the per-evaluator reveal they
  always had. ``HOUSEHOLD`` programs reveal every enrollment together, by a
  manager, once every enrollment has finished all blind work (checkpoint and
  holdouts included), because evaluators who share samples share what a reveal
  tells them.

Every refusal is an HTTP 409 (403 for authorization) whose text names no
fragrance, role, or blind mapping beyond what the caller already holds.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, NoReturn

from fastapi import HTTPException
from sqlalchemy import select

from fragrance_rater.models.calibration import (
    CalibrationSession,
    Enrollment,
    Membership,
    ModelCheckpoint,
    Observation,
    Presentation,
    Program,
)
from fragrance_rater.services.llm_service import get_llm_service
from fragrance_rater.utils.timestamps import now_naive_utc

if TYPE_CHECKING:
    from datetime import datetime

    from sqlalchemy.ext.asyncio import AsyncSession

HOUSEHOLD = "HOUSEHOLD"
ENROLLMENT = "ENROLLMENT"
_HOLDOUT_ROLE = "HOLDOUT"

# reveal_blocker values. The first three predate F1 and keep their meaning;
# the last three occur only on HOUSEHOLD programs.
SKIN_PLAN = "SKIN_PLAN"
BLOTTER = "BLOTTER"
SKIN = "SKIN"
CHECKPOINT = "CHECKPOINT"
HOLDOUT = "HOLDOUT"
HOUSEHOLD_WAIT = "HOUSEHOLD_WAIT"
# checkpoint_blocker only: a holdout already has a response, so no checkpoint
# for this enrollment can be prospective any more.
HOLDOUT_OBSERVED = "HOLDOUT_OBSERVED"

# Deliberately silent about which role the sample has: the participant payload
# never labels holdouts, and an error message must not either.
CHECKPOINT_REQUIRED = (
    "This sample is not open yet: it opens after the organizer freezes "
    "this evaluator's checkpoint"
)
HOUSEHOLD_ONLY = (
    "This program reveals every evaluator together; a manager reveals it "
    "from the program"
)


def _refuse(message: str, status: int = 409) -> NoReturn:
    raise HTTPException(status_code=status, detail=message)


@dataclass(frozen=True)
class EnrollmentState:
    """What the gates need to know about one enrollment.

    Attributes:
        enrollment (Enrollment): The row.
        presentations (list[Presentation]): Its whole schedule.
        roles (dict[str, str]): Membership role by presentation id.
        checkpoint_count (int): Checkpoints frozen for it.
        holdout_observed (bool): Whether any holdout has an observation.
    """

    enrollment: Enrollment
    presentations: list[Presentation]
    roles: dict[str, str]
    checkpoint_count: int
    holdout_observed: bool

    def _blind(self, *, holdout: bool) -> list[Presentation]:
        return [
            p
            for p in self.presentations
            if (self.roles[p.id] == _HOLDOUT_ROLE) is holdout
        ]

    def baseline_blocker(self) -> str | None:
        """Return what still blocks the end of the non-holdout blind work.

        Returns:
            str | None: ``SKIN_PLAN``, ``BLOTTER``, ``SKIN``, or ``None``.
        """
        if self.enrollment.skin_plan_locked_at is None:
            return SKIN_PLAN
        baseline = self._blind(holdout=False)
        if any(p.blotter_locked_at is None for p in baseline):
            return BLOTTER
        if any(p.skin_reason and p.skin_locked_at is None for p in baseline):
            return SKIN
        return None

    def checkpoint_blocker(self) -> str | None:
        """Return why a checkpoint cannot be frozen now, or ``None`` if it can.

        Returns:
            str | None: A ``baseline_blocker`` value, ``HOLDOUT_OBSERVED``, or
                ``None``.
        """
        if self.holdout_observed:
            return HOLDOUT_OBSERVED
        return self.baseline_blocker()

    def household_blocker(self) -> str | None:
        """Return this enrollment's own blocker under the household policy.

        Order is the F1 phase order: baseline, skin plan, planned skin,
        checkpoint, holdouts. A planned skin test on a holdout is part of the
        holdout block (it can only follow the checkpoint).

        Returns:
            str | None: ``SKIN_PLAN``, ``BLOTTER``, ``SKIN``, ``CHECKPOINT``,
                ``HOLDOUT``, or ``None``.
        """
        blocker = self.baseline_blocker()
        if blocker is not None:
            return blocker
        if self.checkpoint_count == 0:
            return CHECKPOINT
        if any(
            p.blotter_locked_at is None or (p.skin_reason and p.skin_locked_at is None)
            for p in self._blind(holdout=True)
        ):
            return HOLDOUT
        return None


def enrollment_blocker(
    enrollment: Enrollment,
    presentations: list[Presentation],
    roles: dict[str, str],
) -> str | None:
    """Return the per-evaluator (``ENROLLMENT`` policy) reveal blocker.

    Unchanged from before F1: the skin plan, every non-holdout blotter, and
    every planned skin stage (holdouts included) must be locked.

    Args:
        enrollment (Enrollment): The enrollment.
        presentations (list[Presentation]): Its schedule.
        roles (dict[str, str]): Membership role by presentation id.

    Returns:
        str | None: ``SKIN_PLAN``, ``BLOTTER``, ``SKIN``, or ``None``.
    """
    if enrollment.skin_plan_locked_at is None:
        return SKIN_PLAN
    if any(
        roles[p.id] != _HOLDOUT_ROLE and p.blotter_locked_at is None
        for p in presentations
    ):
        return BLOTTER
    if any(p.skin_reason and p.skin_locked_at is None for p in presentations):
        return SKIN
    return None


class DisclosureGate:
    """Holdout gate, checkpoint readiness, and reveal policy for one session."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # --- holdout gate -----------------------------------------------------

    async def checkpoint_count(self, enrollment_id: str) -> int:
        """Return how many checkpoints are frozen for an enrollment.

        Args:
            enrollment_id (str): The enrollment.

        Returns:
            int: The count.
        """
        return len(
            list(
                await self.db.scalars(
                    select(ModelCheckpoint.id).where(
                        ModelCheckpoint.enrollment_id == enrollment_id
                    )
                )
            )
        )

    async def require_open(self, enrollment: Enrollment, roles: list[str]) -> None:
        """Refuse work on holdout samples before the enrollment's checkpoint.

        # #CRITICAL: data-integrity: a holdout observed before a checkpoint
        # permanently closes prospective evaluation for that evaluator
        # (api/calibration.py refuses the checkpoint once any holdout has a
        # response, ADR-009). The UI's step order is not a control: this gate
        # is, and it applies to every caller, manager included.
        # #ASSUME: concurrency: the caller holds the enrollment row lock
        # (CalibrationService.enrollment uses FOR UPDATE), and checkpoint
        # creation takes the same lock, so a checkpoint cannot appear or a
        # holdout observation slip in between this check and the write.
        # #VERIFY: tests/unit/test_services/test_disclosure_gate.py covers
        # exposure, observation, lock, session start, and ranking refusals and
        # their opening once a checkpoint exists.

        Args:
            enrollment (Enrollment): The locked enrollment.
            roles (list[str]): Membership roles of the samples the write touches.
        """
        if _HOLDOUT_ROLE not in roles:
            return
        if await self.checkpoint_count(enrollment.id) == 0:
            _refuse(CHECKPOINT_REQUIRED)

    async def session_roles(self, session_id: str) -> list[str]:
        """Return the membership roles of every sample in a session.

        Args:
            session_id (str): The calibration session.

        Returns:
            list[str]: One role per presentation.
        """
        return list(
            await self.db.scalars(
                select(Membership.role)
                .join(Presentation, Presentation.membership_id == Membership.id)
                .where(Presentation.session_id == session_id)
            )
        )

    # --- state ------------------------------------------------------------

    async def state(self, enrollment: Enrollment) -> EnrollmentState:
        """Load what the readiness and reveal rules read for one enrollment.

        Args:
            enrollment (Enrollment): The enrollment.

        Returns:
            EnrollmentState: Its schedule, roles, checkpoints, and holdout use.
        """
        rows = list(
            (
                await self.db.execute(
                    select(Presentation, Membership.role)
                    .join(
                        CalibrationSession,
                        Presentation.session_id == CalibrationSession.id,
                    )
                    .join(Membership, Presentation.membership_id == Membership.id)
                    .where(CalibrationSession.enrollment_id == enrollment.id)
                    .order_by(
                        CalibrationSession.created_at,
                        CalibrationSession.id,
                        Presentation.position,
                    )
                )
            ).all()
        )
        presentations = [presentation for presentation, _ in rows]
        roles = {presentation.id: role for presentation, role in rows}
        holdout_ids = [p.id for p in presentations if roles[p.id] == _HOLDOUT_ROLE]
        holdout_observed = bool(holdout_ids) and (
            await self.db.scalar(
                select(Observation.id)
                .where(Observation.presentation_id.in_(holdout_ids))
                .limit(1)
            )
            is not None
        )
        return EnrollmentState(
            enrollment=enrollment,
            presentations=presentations,
            roles=roles,
            checkpoint_count=await self.checkpoint_count(enrollment.id),
            holdout_observed=holdout_observed,
        )

    async def policy(self, program_id: str) -> str:
        """Return a program's reveal policy.

        Args:
            program_id (str): The program.

        Returns:
            str: ``ENROLLMENT`` or ``HOUSEHOLD``.
        """
        program = await self.db.get(Program, program_id)
        if program is None:
            _refuse("Program not found", 404)
        return program.reveal_policy

    async def _program_enrollments(
        self, program_id: str, *, lock: bool = False
    ) -> list[Enrollment]:
        query = (
            select(Enrollment)
            .where(Enrollment.program_id == program_id)
            .order_by(Enrollment.id)
        )
        # Locking in id order: two household actions on one program cannot
        # deadlock each other, and per-enrollment writers lock one row only.
        return list(await self.db.scalars(query.with_for_update() if lock else query))

    async def reveal_blocker(self, enrollment: Enrollment) -> str | None:
        """Return the policy-aware reveal blocker for one enrollment.

        ``ENROLLMENT`` programs get exactly the pre-F1 values. ``HOUSEHOLD``
        programs get the enrollment's own blocker, or ``HOUSEHOLD_WAIT`` when
        its own work is done but another enrollment's is not.

        Args:
            enrollment (Enrollment): The enrollment.

        Returns:
            str | None: The blocker, or ``None`` when reveal may proceed.
        """
        state = await self.state(enrollment)
        if await self.policy(enrollment.program_id) != HOUSEHOLD:
            return enrollment_blocker(enrollment, state.presentations, state.roles)
        own = state.household_blocker()
        if own is not None:
            return own
        for other in await self._program_enrollments(enrollment.program_id):
            if other.id == enrollment.id:
                continue
            if (await self.state(other)).household_blocker() is not None:
                return HOUSEHOLD_WAIT
        return None

    # --- checkpoints --------------------------------------------------------

    async def readiness(self, program_id: str) -> list[EnrollmentState]:
        """Return every enrollment of a program with its readiness facts.

        Args:
            program_id (str): The program.

        Returns:
            list[EnrollmentState]: In enrollment id order.
        """
        return [
            await self.state(enrollment)
            for enrollment in await self._program_enrollments(program_id)
        ]

    async def require_checkpoint_ready(self, enrollment: Enrollment) -> None:
        """Refuse a checkpoint a ``HOUSEHOLD`` program is not ready for.

        ``ENROLLMENT`` programs keep their earlier rule (any time before a
        holdout response; the caller checks that), so the P6 rehearsal path is
        unchanged.

        Args:
            enrollment (Enrollment): The locked enrollment.
        """
        if await self.policy(enrollment.program_id) != HOUSEHOLD:
            return
        blocker = (await self.state(enrollment)).checkpoint_blocker()
        if blocker == SKIN_PLAN:
            _refuse("Finalize the skin plan before the checkpoint")
        if blocker == BLOTTER:
            _refuse("Lock every blind baseline blotter before the checkpoint")
        if blocker == SKIN:
            _refuse("Lock every planned blind skin test before the checkpoint")

    # --- household reveal -------------------------------------------------

    async def require_enrollment_reveal_allowed(self, enrollment: Enrollment) -> None:
        """Refuse the per-evaluator reveal on a ``HOUSEHOLD`` program.

        Args:
            enrollment (Enrollment): The enrollment a recorder tries to reveal.
        """
        if await self.policy(enrollment.program_id) == HOUSEHOLD:
            _refuse(HOUSEHOLD_ONLY)

    async def require_enrollment_open(self, program_id: str) -> None:
        """Refuse a new enrollment in a household that is already revealed.

        Args:
            program_id (str): The program being enrolled into.
        """
        if await self.policy(program_id) != HOUSEHOLD:
            return
        if any(e.revealed_at for e in await self._program_enrollments(program_id)):
            _refuse("This household is already revealed; enroll in a new program")

    async def reveal_household(
        self, program_id: str, username: str
    ) -> tuple[list[str], datetime]:
        """Reveal every enrollment of a ``HOUSEHOLD`` program together.

        # #CRITICAL: security: one evaluator's reveal tells the others what
        # their shared samples were, so either every enrollment is revealed in
        # this transaction or none is. The caller is a verified manager.
        # #ASSUME: concurrency: the program row and then every enrollment row
        # (id order) are locked FOR UPDATE before the readiness check, so no
        # observation, lock, or checkpoint can change the answer between the
        # check and the write.
        # #VERIFY: test_household_reveal_* in
        # tests/unit/test_services/test_disclosure_gate.py.

        Args:
            program_id (str): The program.
            username (str): The manager.

        Returns:
            tuple[list[str], datetime]: Enrollment ids revealed and when. An
                already revealed household returns its ids and earliest time.
        """
        program = await self.db.scalar(
            select(Program).where(Program.id == program_id).with_for_update()
        )
        if program is None:
            _refuse("Program not found", 404)
        if program.reveal_policy != HOUSEHOLD:
            _refuse("This program reveals each evaluator separately")
        enrollments = await self._program_enrollments(program_id, lock=True)
        if not enrollments:
            _refuse("Enroll evaluators before the household reveal")
        pending = [e for e in enrollments if e.revealed_at is None]
        if not pending:
            revealed = [e.revealed_at for e in enrollments if e.revealed_at]
            return [e.id for e in enrollments], min(revealed)
        blocked = 0
        for enrollment in pending:
            if (await self.state(enrollment)).household_blocker() is not None:
                blocked += 1
        if blocked:
            outstanding = "blind work, a checkpoint, or final samples outstanding"
            _refuse(f"{blocked} of {len(pending)} evaluators still have {outstanding}")
        at = now_naive_utc()
        llm = get_llm_service()
        for enrollment in pending:
            enrollment.revealed_at = at
            enrollment.revealed_by = username
            llm.invalidate_reviewer_cache(enrollment.reviewer_id)
        await self.db.flush()
        return [e.id for e in pending], at
