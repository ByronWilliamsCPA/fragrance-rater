"""Staged fragrance house submissions.

A submission is what a house said, held apart from the catalog. Nothing here
writes a ``Fragrance``, ``SourceSnapshot``, or (from D1) ``declared_label``
row: adopting a submission as evidence is a reviewed manager step, kept out
of this table so a house can never change catalog facts directly (ADR-012,
ADR-017).
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, CheckConstraint, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from fragrance_rater.core.database import Base
from fragrance_rater.models.calibration import identifier
from fragrance_rater.utils.timestamps import now_naive_utc


class HouseSubmission(Base):
    """One house's description of one fragrance, draft or submitted.

    Attributes:
        id (Mapped[str]): Unique identifier (UUID).
        house (Mapped[str]): House the submission speaks for, taken from the
            server's contributor mapping, never from the request body.
        status (Mapped[str]): ``draft`` (editable) or ``submitted`` (frozen).
        created_by (Mapped[str]): Authentik username that started the draft.
        created_at (Mapped[datetime]): When the draft was started.
        updated_at (Mapped[datetime]): Last content change.
        submitted_at (Mapped[datetime | None]): When the house submitted.
        submitted_by (Mapped[str | None]): Authentik username that submitted.
        permission_state (Mapped[str | None]): ADR-012 permission the house
            granted, fixed at submission.
        supersedes_id (Mapped[str | None]): The submitted record this one
            corrects, if any.
        payload (Mapped[dict[str, object]]): The validated
            ``HouseSubmissionPayload``.
    """

    __tablename__ = "house_submissions"
    # #ASSUME: data-integrity: a submitted row is evidence and is never edited
    # (ADR-006's append-only rule); a correction is a new row pointing at the
    # one it replaces. The service enforces "drafts only" on update; these
    # constraints keep a submitted row from ever lacking the facts that make
    # it evidence: when, by whom, and under which permission.
    # #VERIFY: test_house_submission_constraints asserts each violation fails
    # at flush(); the expressions must stay identical to migration
    # b7e3d91a4c2f.
    __table_args__ = (
        CheckConstraint(
            "status IN ('draft', 'submitted')",
            name="ck_house_submissions_status",
        ),
        CheckConstraint(
            "permission_state IS NULL OR permission_state IN ('retain_and_train', 'retain_for_qc_only')",
            name="ck_house_submissions_permission_state",
        ),
        CheckConstraint(
            "status = 'draft' OR (submitted_at IS NOT NULL AND submitted_by IS NOT NULL AND permission_state IS NOT NULL)",
            name="ck_house_submissions_submitted_complete",
        ),
        Index("ix_house_submissions_house_status", "house", "status"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=identifier)
    house: Mapped[str] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(20), default="draft")
    created_by: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(default=now_naive_utc)
    updated_at: Mapped[datetime] = mapped_column(
        default=now_naive_utc, onupdate=now_naive_utc
    )
    submitted_at: Mapped[datetime | None] = mapped_column(nullable=True)
    submitted_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    permission_state: Mapped[str | None] = mapped_column(String(30), nullable=True)
    supersedes_id: Mapped[str | None] = mapped_column(
        ForeignKey("house_submissions.id", ondelete="RESTRICT"),
        nullable=True,
        unique=True,
    )
    payload: Mapped[dict[str, object]] = mapped_column(JSON)
