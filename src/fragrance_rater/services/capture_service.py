"""Rankings and quality flags (R7b PR 1c; ADR-005 2026-09-19 amendment).

Both are append-only. A ranking is one event over a session's detected samples;
a correction is an ``invalidated`` event plus a new one. A quality flag is
closed by a later row that names it. Nothing here edits or deletes evidence.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import select

from fragrance_rater.models.calibration import (
    CalibrationSession,
    Observation,
    Presentation,
    QualityFlag,
    RankEntry,
    RankEvent,
)
from fragrance_rater.services.calibration_service import CalibrationService, reject
from fragrance_rater.services.training_eligibility import (
    TrainingEligibilityService,
    Transition,
)
from fragrance_rater.utils.timestamps import now_naive_utc

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from fragrance_rater.schemas.capture import QualityFlagInput, RankingInput

# A sample the evaluator could not assess is not ranked, however it was answered.
_UNRANKABLE_STATUSES = {"skipped", "unable_to_assess", "interrupted", "invalidated"}


class CaptureService:
    """Record rankings and quality flags for one database session."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.calibration = CalibrationService(db)

    # --- rankings ---------------------------------------------------------

    async def _latest_by_presentation(
        self, presentation_ids: list[str], stage: str
    ) -> dict[str, Observation]:
        """Return each presentation's latest observation at ``stage``."""
        latest: dict[str, Observation] = {}
        for observation in await self.db.scalars(
            select(Observation)
            .where(
                Observation.presentation_id.in_(presentation_ids),
                Observation.stage == stage,
            )
            .order_by(Observation.created_at, Observation.id)
        ):
            latest[observation.presentation_id] = observation
        return latest

    async def record_ranking(
        self, session_id: str, data: RankingInput, username: str, admin: bool
    ) -> tuple[RankEvent, int]:
        """Append one ranking event over the session's detected samples.

        Eligibility is the server's call: a sample is ranked only if its latest
        response at the stage says it was detected and was not skipped or
        unassessable. The client orders exactly that subset; the server records
        every other sample as an ineligible entry with no position.

        Refuses with HTTP 409 unless every sample has been assessed, the detected
        samples are exactly the ones ranked, and no active ranking exists for the
        same stage and disclosure state (invalidate it first).

        Args:
            session_id (str): The calibration session being ranked.
            data (RankingInput): The stage, status, and ordered entries.
            username (str): The verified caller.
            admin (bool): Whether the caller is a manager.

        Returns:
            tuple[RankEvent, int]: The event and how many samples were eligible.
        """
        session, enrollment = await self.calibration.session_target(
            session_id, username, admin
        )
        presentations = list(
            await self.db.scalars(
                select(Presentation)
                .where(Presentation.session_id == session.id)
                .order_by(Presentation.position)
            )
        )
        latest = await self._latest_by_presentation(
            [p.id for p in presentations], data.stage
        )
        unassessed = [p.blind_code for p in presentations if p.id not in latest]
        if unassessed:
            reject(
                f"Every sample must be assessed before ranking: {len(unassessed)} left"
            )
        eligible = {
            p.id
            for p in presentations
            if latest[p.id].detected is True
            and latest[p.id].response_status not in _UNRANKABLE_STATUSES
        }
        phase = self._phase(enrollment.revealed_at is not None, latest)
        await self._check_ranking_state(session, data, phase, eligible)
        event = RankEvent(
            session_id=session.id,
            stage=data.stage,
            phase=phase,
            criterion=data.criterion,
            response_status=data.response_status,
            ranked_at=data.ranked_at or now_naive_utc(),
            recorded_by=username,
        )
        self.db.add(event)
        await self.db.flush()
        if data.response_status == "completed":
            positions = {e.presentation_id: e.rank_position for e in data.entries}
            for presentation in presentations:
                position = positions.get(presentation.id)
                self.db.add(
                    RankEntry(
                        rank_event_id=event.id,
                        presentation_id=presentation.id,
                        eligible_for_rank=presentation.id in eligible,
                        rank_position=position,
                    )
                )
        await self.db.flush()
        return event, len(eligible)

    @staticmethod
    def _phase(revealed: bool, latest: dict[str, Observation]) -> str:
        """Return the disclosure state a ranking was made in."""
        if revealed:
            return "POST_REVEAL"
        if any(o.phase == "PREVIOUSLY_REVEALED" for o in latest.values()):
            return "PREVIOUSLY_REVEALED"
        return "PRE_REVEAL"

    async def _check_ranking_state(
        self,
        session: CalibrationSession,
        data: RankingInput,
        phase: str,
        eligible: set[str],
    ) -> None:
        """Refuse a ranking that does not fit the session's current evidence."""
        earlier = list(
            await self.db.scalars(
                select(RankEvent)
                .where(
                    RankEvent.session_id == session.id,
                    RankEvent.stage == data.stage,
                    RankEvent.phase == phase,
                    RankEvent.criterion == data.criterion,
                )
                .order_by(RankEvent.created_at, RankEvent.id)
            )
        )
        active = bool(earlier) and earlier[-1].response_status == "completed"
        if data.response_status == "invalidated":
            if not active:
                reject("There is no completed ranking to invalidate")
            return
        if active:
            reject("This session is already ranked; invalidate the ranking first")
        if data.response_status != "completed":
            return
        ranked = {entry.presentation_id for entry in data.entries}
        if ranked != eligible:
            counts = f"{len(eligible)} detected, {len(ranked)} ranked"
            reject(f"Rank exactly the detected samples: {counts}")

    async def rankings(
        self, session_id: str, username: str, admin: bool
    ) -> list[dict[str, object]]:
        """List a session's ranking events with their entries, oldest first.

        Args:
            session_id (str): The calibration session.
            username (str): The verified caller.
            admin (bool): Whether the caller is a manager.

        Returns:
            list[dict[str, object]]: Each event and its entries.
        """
        session, _ = await self.calibration.session_target(session_id, username, admin)
        events = list(
            await self.db.scalars(
                select(RankEvent)
                .where(RankEvent.session_id == session.id)
                .order_by(RankEvent.created_at, RankEvent.id)
            )
        )
        result: list[dict[str, object]] = []
        for event in events:
            entries = list(
                await self.db.scalars(
                    select(RankEntry)
                    .where(RankEntry.rank_event_id == event.id)
                    .order_by(RankEntry.rank_position, RankEntry.id)
                )
            )
            result.append(
                {
                    "id": event.id,
                    "stage": event.stage,
                    "phase": event.phase,
                    "criterion": event.criterion,
                    "response_status": event.response_status,
                    "ranked_at": event.ranked_at,
                    "recorded_by": event.recorded_by,
                    "entries": [
                        {
                            "presentation_id": e.presentation_id,
                            "eligible_for_rank": e.eligible_for_rank,
                            "rank_position": e.rank_position,
                        }
                        for e in entries
                    ],
                }
            )
        return result

    # --- quality flags ----------------------------------------------------

    async def _flag_target(
        self, target_type: str, target_id: str, username: str, admin: bool
    ) -> dict[str, str]:
        """Authorize and resolve a flag target to its foreign-key column."""
        if target_type == "session":
            await self.calibration.session_target(target_id, username, admin)
            return {"session_id": target_id}
        if target_type == "presentation":
            await self.calibration.target(target_id, username, admin)
            return {"presentation_id": target_id}
        observation = await self.db.get(Observation, target_id)
        if observation is None:
            reject("Observation not found", 404)
        assert observation is not None
        await self.calibration.target(observation.presentation_id, username, admin)
        return {"observation_id": target_id}

    async def record_flag(
        self, data: QualityFlagInput, username: str, admin: bool
    ) -> QualityFlag:
        """Raise a quality flag, or close one with a later row.

        Args:
            data (QualityFlagInput): The flag to raise or the closing row.
            username (str): The verified caller.
            admin (bool): Whether the caller is a manager.

        Returns:
            QualityFlag: The stored row.
        """
        flag, _ = await self.record_flag_with_eligibility(data, username, admin)
        return flag

    async def record_flag_with_eligibility(
        self, data: QualityFlagInput, username: str, admin: bool
    ) -> tuple[QualityFlag, list[Transition]]:
        """Raise or close a flag and apply R8's eligibility rules to its rows.

        Flags describe evidence; they never change or hide it. The ``manager``
        source needs a manager, and a closing row inherits its target and code
        from the raised flag it names. Refuses with HTTP 409 when the named flag
        is not a raised flag, or is already closed, and with 403 when a
        non-manager sends a ``training_outcome``.

        Raising demotes the covered ``unreviewed``/``eligible`` observations to
        ``questionable``; closing settles the ``questionable`` ones (see
        ``TrainingEligibilityService.flag_closed``).

        Args:
            data (QualityFlagInput): The flag to raise or the closing row.
            username (str): The verified caller.
            admin (bool): Whether the caller is a manager.

        Returns:
            tuple[QualityFlag, list[Transition]]: The stored row and the
                eligibility changes it caused.
        """
        if data.source == "manager" and not admin:
            reject("Only a manager can raise a flag as the manager", 403)
        if data.training_outcome is not None and not admin:
            reject("Only a manager can decide training eligibility", 403)
        if data.action == "raised":
            assert data.target_type is not None
            assert data.target_id is not None
            assert data.code is not None
            assert data.severity is not None
            target = await self._flag_target(
                data.target_type, data.target_id, username, admin
            )
            code, severity, supersedes_id = data.code, data.severity, None
        else:
            assert data.supersedes_id is not None
            raised = await self.db.get(QualityFlag, data.supersedes_id)
            if raised is None:
                reject("Flag not found", 404)
            assert raised is not None
            # Authorize through the original target, so closing a flag needs the
            # same standing as raising it. That also takes the enrollment lock, so
            # the closing-state checks below run under it and cannot race.
            target_type = (
                "session"
                if raised.session_id
                else "presentation"
                if raised.presentation_id
                else "observation"
            )
            target_id = (
                raised.session_id or raised.presentation_id or raised.observation_id
            )
            assert target_id is not None
            target = await self._flag_target(target_type, target_id, username, admin)
            if raised.action != "raised":
                reject("Only a raised flag can be closed")
            if await self.db.scalar(
                select(QualityFlag.id).where(QualityFlag.supersedes_id == raised.id)
            ):
                reject("That flag is already closed")
            code, severity, supersedes_id = (
                raised.code,
                data.severity or raised.severity,
                raised.id,
            )
        flag = QualityFlag(
            action=data.action,
            code=code,
            severity=severity,
            source=data.source,
            disposition=data.disposition,
            explanation=data.explanation,
            training_outcome=data.training_outcome,
            occurred_at=data.occurred_at,
            supersedes_id=supersedes_id,
            recorded_by=username,
            **target,
        )
        self.db.add(flag)
        await self.db.flush()
        eligibility = TrainingEligibilityService(self.db)
        if flag.action == "raised":
            changes = await eligibility.flag_raised(flag, actor=username)
        else:
            changes = await eligibility.flag_closed(
                flag, outcome=data.training_outcome, actor=username
            )
        await self.db.flush()
        return flag, changes

    async def flags(
        self, session_id: str, username: str, admin: bool
    ) -> list[dict[str, object]]:
        """List every flag on a session, its samples, and their responses.

        Each row says whether it is still open: a raised flag that no later row
        closes.

        Args:
            session_id (str): The calibration session.
            username (str): The verified caller.
            admin (bool): Whether the caller is a manager.

        Returns:
            list[dict[str, object]]: The flag rows, oldest first.
        """
        session, _ = await self.calibration.session_target(session_id, username, admin)
        presentation_ids = list(
            await self.db.scalars(
                select(Presentation.id).where(Presentation.session_id == session.id)
            )
        )
        observation_ids = list(
            await self.db.scalars(
                select(Observation.id).where(
                    Observation.presentation_id.in_(presentation_ids)
                )
            )
        )
        rows = list(
            await self.db.scalars(
                select(QualityFlag)
                .where(
                    (QualityFlag.session_id == session.id)
                    | QualityFlag.presentation_id.in_(presentation_ids)
                    | QualityFlag.observation_id.in_(observation_ids)
                )
                .order_by(QualityFlag.created_at, QualityFlag.id)
            )
        )
        closed = {row.supersedes_id for row in rows if row.supersedes_id}
        return [
            {
                "id": row.id,
                "action": row.action,
                "code": row.code,
                "severity": row.severity,
                "source": row.source,
                "disposition": row.disposition,
                "session_id": row.session_id,
                "presentation_id": row.presentation_id,
                "observation_id": row.observation_id,
                "supersedes_id": row.supersedes_id,
                "explanation": row.explanation,
                "occurred_at": row.occurred_at,
                "recorded_by": row.recorded_by,
                "open": row.action == "raised" and row.id not in closed,
            }
            for row in rows
        ]
