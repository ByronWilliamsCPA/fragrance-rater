"""House intake lifecycle: draft, submit, and correct a house submission.

Every method takes the house explicitly. The house always comes from the
server's contributor mapping (``settings.house_contributors``), never from a
request body, so one house can neither read nor write another's records.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import HTTPException, status
from sqlalchemy import select, update
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
        else:
            # A draft is not yet a statement by the house; managers review
            # only what a house chose to submit.
            query = query.where(HouseSubmission.status == "submitted")
        rows = list(await self.db.scalars(query))
        successors = await self._successors({row.id for row in rows})
        return [
            self.to_response(row, successors.get(row.id), manager=house is None)
            for row in rows
        ]

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
        return self.to_response(
            row, await self._successor_id(row.id), manager=house is None
        )

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
        return self.to_response(row, None)

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
        return self.to_response(row, None)

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
        row.review_status = "pending"
        row.submitted_at = now
        row.submitted_by = username
        row.updated_at = now
        # #ASSUME: data-integrity: once a correction is submitted, the record
        # it corrects is no longer the house's current statement, so it must
        # not be adopted. A record already adopted or declined keeps its
        # outcome: that decision was made on what the house said at the time.
        # #VERIFY: test_submitted_correction_supersedes_pending_original.
        # #CRITICAL: concurrency: conditional on `pending` in the database, not
        # on a value read earlier, so a manager's adopt or decline that
        # commits between the two keeps its outcome (the same compare-and-set
        # HouseReviewService._claim uses).
        # #VERIFY: test_supersede_never_overwrites_a_review.
        if row.supersedes_id is not None:
            await self.db.execute(
                update(HouseSubmission)
                .where(
                    HouseSubmission.id == row.supersedes_id,
                    HouseSubmission.review_status == "pending",
                )
                .values(review_status="superseded")
                .execution_options(synchronize_session="fetch")
            )
        await self.db.flush()
        return self.to_response(row, None)

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
        return self.to_response(draft, None)

    async def _visible(self, submission_id: str, house: str | None) -> HouseSubmission:
        row = await self.db.get(HouseSubmission, submission_id)
        # A record of another house is reported exactly like a missing one,
        # so ids cannot be probed across houses; a manager cannot see drafts.
        hidden = row is not None and (
            (house is not None and row.house != house)
            or (house is None and row.status == "draft")
        )
        if row is None or hidden:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": "NOT_FOUND", "message": "Submission not found."},
            )
        return row

    async def _draft(self, submission_id: str, house: str) -> HouseSubmission:
        # #CRITICAL: concurrency: colleagues at one house share drafts. The row
        # lock serializes this status check with any concurrent submit, edit,
        # or delete, so a request that loaded the row as a draft cannot then
        # rewrite or delete it after another request submitted it. SQLite
        # ignores FOR UPDATE; its single writer gives the same ordering.
        # #VERIFY: test_a_stale_draft_read_cannot_edit_a_submitted_record.
        row = await self.db.scalar(
            select(HouseSubmission)
            .where(HouseSubmission.id == submission_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if row is None or row.house != house:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": "NOT_FOUND", "message": "Submission not found."},
            )
        if row.status != "draft":
            msg = (
                "This record has been submitted and can no longer be edited. "
                "Start a correction instead."
            )
            raise _conflict(ALREADY_SUBMITTED, msg)
        return row

    async def _successors(self, submission_ids: set[str]) -> dict[str, str]:
        if not submission_ids:
            return {}
        rows = await self.db.execute(
            select(HouseSubmission.supersedes_id, HouseSubmission.id).where(
                HouseSubmission.supersedes_id.in_(submission_ids)
            )
        )
        return {
            original: successor for original, successor in rows.tuples() if original
        }

    async def _successor_id(self, submission_id: str) -> str | None:
        return await self.db.scalar(
            select(HouseSubmission.id).where(
                HouseSubmission.supersedes_id == submission_id
            )
        )

    @staticmethod
    def to_response(
        row: HouseSubmission, superseded_by_id: str | None, *, manager: bool = False
    ) -> HouseSubmissionResponse:
        """Build the API view of a row.

        Args:
            row (HouseSubmission): The stored submission.
            superseded_by_id (str | None): The correction replacing it, if any.
            manager (bool): Include manager-only fields (reviewer, catalog and
                evidence ids); a house sees them blanked.

        Returns:
            HouseSubmissionResponse: The response model.
        """
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
                "review_status": row.review_status,
                "reviewed_at": row.reviewed_at,
                "review_note": row.review_note,
                "reviewed_by": row.reviewed_by if manager else None,
                "fragrance_id": row.fragrance_id if manager else None,
                "source_snapshot_id": row.source_snapshot_id if manager else None,
            }
        )
