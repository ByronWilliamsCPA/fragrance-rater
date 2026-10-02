"""House intake lifecycle: draft, submit, and correct a house submission.

Every method takes the house explicitly. The house always comes from the
server's contributor mapping (``settings.house_contributors``), never from a
request body, so one house can neither read nor write another's records.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from fragrance_rater.models.house_intake import HouseSubmission
from fragrance_rater.schemas.house_intake import (
    HouseSubmissionPayload,
    HouseSubmissionResponse,
    submission_problems,
)
from fragrance_rater.utils.timestamps import now_naive_utc

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


NOT_SUBMITTED = "NOT_SUBMITTED"
ALREADY_SUBMITTED = "ALREADY_SUBMITTED"
ALREADY_REVISED = "ALREADY_REVISED"


def _conflict(error: str, message: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail={"error": error, "message": message},
    )


class HouseIntakeService:
    """Reads and writes ``house_submissions`` for one house or a manager.

    Args:
        db (AsyncSession): Request-scoped session.
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def list_submissions(
        self, house: str | None
    ) -> list[HouseSubmissionResponse]:
        """List submissions, newest first.

        Args:
            house (str | None): The house to scope to, or None for a manager's
                view of every house.

        Returns:
            list[HouseSubmissionResponse]: The visible submissions.
        """
        query = select(HouseSubmission).order_by(
            HouseSubmission.updated_at.desc(), HouseSubmission.id
        )
        if house is not None:
            query = query.where(HouseSubmission.house == house)
        rows = list(await self.db.scalars(query))
        successors = {row.supersedes_id: row.id for row in rows if row.supersedes_id}
        return [self._response(row, successors.get(row.id)) for row in rows]

    async def get(
        self, submission_id: str, house: str | None
    ) -> HouseSubmissionResponse:
        """Fetch one submission the caller may see.

        Args:
            submission_id (str): Submission id.
            house (str | None): The caller's house, or None for a manager.

        Returns:
            HouseSubmissionResponse: The submission.
        """
        row = await self._visible(submission_id, house)
        return self._response(row, await self._successor_id(row.id))

    async def create(
        self, house: str, username: str, payload: HouseSubmissionPayload
    ) -> HouseSubmissionResponse:
        """Start a new draft for ``house``.

        Args:
            house (str): The caller's house.
            username (str): The caller's Authentik username.
            payload (HouseSubmissionPayload): The draft content.

        Returns:
            HouseSubmissionResponse: The stored draft.
        """
        row = HouseSubmission(
            house=house,
            created_by=username,
            status="draft",
            payload=payload.model_dump(mode="json"),
        )
        self.db.add(row)
        await self.db.flush()
        return self._response(row, None)

    async def update(
        self, submission_id: str, house: str, payload: HouseSubmissionPayload
    ) -> HouseSubmissionResponse:
        """Replace a draft's content.

        Args:
            submission_id (str): Draft id.
            house (str): The caller's house.
            payload (HouseSubmissionPayload): The full new content.

        Returns:
            HouseSubmissionResponse: The updated draft.
        """
        row = await self._draft(submission_id, house)
        row.payload = payload.model_dump(mode="json")
        row.updated_at = now_naive_utc()
        await self.db.flush()
        return self._response(row, None)

    async def delete(self, submission_id: str, house: str) -> None:
        """Discard a draft. Submitted records are evidence and are kept.

        Args:
            submission_id (str): Draft id.
            house (str): The caller's house.
        """
        row = await self._draft(submission_id, house)
        await self.db.delete(row)
        await self.db.flush()

    async def submit(
        self, submission_id: str, house: str, username: str
    ) -> HouseSubmissionResponse:
        """Freeze a complete draft as the house's statement.

        Args:
            submission_id (str): Draft id.
            house (str): The caller's house.
            username (str): The caller's Authentik username.

        Returns:
            HouseSubmissionResponse: The submitted record.

        Raises:
            HTTPException: 422 listing what is missing when incomplete.
        """
        row = await self._draft(submission_id, house)
        payload = HouseSubmissionPayload.model_validate(row.payload)
        problems = submission_problems(payload)
        if problems:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail={
                    "error": "SUBMISSION_INCOMPLETE",
                    "message": "Some answers are still needed before submitting.",
                    "problems": [problem.model_dump() for problem in problems],
                },
            )
        # #ASSUME: data-integrity: ADR-012 says a reply from a named brand
        # representative defaults to retain_and_train, and one stating a
        # narrower scope must not. The house chose the scope explicitly and
        # submission_problems refused a missing name, so the permission is
        # the house's stated choice, never a default.
        # #VERIFY: test_submit_records_permission_and_freezes asserts a
        # retain_for_qc_only choice is stored as given.
        now = now_naive_utc()
        row.permission_state = payload.permission_scope
        row.status = "submitted"
        row.submitted_at = now
        row.submitted_by = username
        row.updated_at = now
        await self.db.flush()
        return self._response(row, None)

    async def revise(
        self, submission_id: str, house: str, username: str
    ) -> HouseSubmissionResponse:
        """Start a correction: a new draft that will supersede a submitted record.

        The attestation is cleared so the house confirms the corrected
        content afresh rather than inheriting the earlier confirmation.

        Args:
            submission_id (str): The submitted record to correct.
            house (str): The caller's house.
            username (str): The caller's Authentik username.

        Returns:
            HouseSubmissionResponse: The new draft.

        Raises:
            _conflict: 409 when the record is not submitted or was already
                corrected.
        """
        original = await self._visible(submission_id, house)
        if original.status != "submitted":
            msg = "Only a submitted record can be corrected; edit the draft instead."
            raise _conflict(NOT_SUBMITTED, msg)
        if await self._successor_id(original.id) is not None:
            msg = "A correction for this record already exists."
            raise _conflict(ALREADY_REVISED, msg)
        payload = HouseSubmissionPayload.model_validate(original.payload)
        draft = HouseSubmission(
            house=house,
            created_by=username,
            status="draft",
            supersedes_id=original.id,
            payload=payload.model_copy(update={"attested": False}).model_dump(
                mode="json"
            ),
        )
        self.db.add(draft)
        # #ASSUME: concurrency: two simultaneous corrections of one record
        # both pass the successor check above; the UNIQUE constraint on
        # supersedes_id lets exactly one insert succeed.
        # #VERIFY: the loser surfaces as the same 409 as the sequential case.
        try:
            await self.db.flush()
        except IntegrityError as error:
            msg = "A correction for this record already exists."
            raise _conflict(ALREADY_REVISED, msg) from error
        return self._response(draft, None)

    async def _visible(self, submission_id: str, house: str | None) -> HouseSubmission:
        row = await self.db.get(HouseSubmission, submission_id)
        # A record of another house is reported exactly like a missing one,
        # so ids cannot be probed across houses.
        if row is None or (house is not None and row.house != house):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": "NOT_FOUND", "message": "Submission not found."},
            )
        return row

    async def _draft(self, submission_id: str, house: str) -> HouseSubmission:
        row = await self._visible(submission_id, house)
        if row.status != "draft":
            msg = (
                "This record has been submitted and can no longer be edited. "
                "Start a correction instead."
            )
            raise _conflict(ALREADY_SUBMITTED, msg)
        return row

    async def _successor_id(self, submission_id: str) -> str | None:
        return await self.db.scalar(
            select(HouseSubmission.id).where(
                HouseSubmission.supersedes_id == submission_id
            )
        )

    @staticmethod
    def _response(
        row: HouseSubmission, superseded_by_id: str | None
    ) -> HouseSubmissionResponse:
        return HouseSubmissionResponse.model_validate(
            {
                "id": row.id,
                "house": row.house,
                "status": row.status,
                "created_by": row.created_by,
                "created_at": row.created_at,
                "updated_at": row.updated_at,
                "submitted_at": row.submitted_at,
                "submitted_by": row.submitted_by,
                "permission_state": row.permission_state,
                "supersedes_id": row.supersedes_id,
                "superseded_by_id": superseded_by_id,
                "payload": row.payload,
            }
        )
