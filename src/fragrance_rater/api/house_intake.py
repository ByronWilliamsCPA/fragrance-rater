"""Fragrance house intake endpoints.

A house contributor drafts, submits, and corrects descriptions of its own
fragrances. A calibration manager may read every house's submitted records
and review them (adopt as evidence, or decline), but cannot write their
content: a manager speaking for a house would defeat the point of
manufacturer-provided evidence (ADR-012). Everyone else is refused.
"""

from dataclasses import dataclass
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from fragrance_rater.core.auth import (
    AUTHENTIK_GROUPS_HEADER,
    AuthenticatedIdentity,
    get_current_identity,
)
from fragrance_rater.core.config import settings
from fragrance_rater.core.database import get_db
from fragrance_rater.middleware.house_fence import is_house_account
from fragrance_rater.schemas.house_intake import (
    HouseAccessResponse,
    HouseSubmissionPayload,
    HouseSubmissionResponse,
)
from fragrance_rater.schemas.house_review import (
    AdoptInput,
    DeclineInput,
    ReviewContext,
)
from fragrance_rater.services.house_intake_service import HouseIntakeService
from fragrance_rater.services.house_review_service import HouseReviewService

router = APIRouter(prefix="/house-intake", tags=["house-intake"])
Identity = Annotated[AuthenticatedIdentity, Depends(get_current_identity)]


def get_service(db: Annotated[AsyncSession, Depends(get_db)]) -> HouseIntakeService:
    """Build the request-scoped intake service.

    Args:
        db (Annotated[AsyncSession, Depends(get_db)]): Request-scoped session.

    Returns:
        HouseIntakeService: The service.
    """
    return HouseIntakeService(db)


Service = Annotated[HouseIntakeService, Depends(get_service)]


def get_review_service(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> HouseReviewService:
    """Build the request-scoped review service.

    Args:
        db (Annotated[AsyncSession, Depends(get_db)]): Request-scoped session.

    Returns:
        HouseReviewService: The service.
    """
    return HouseReviewService(db)


ReviewService = Annotated[HouseReviewService, Depends(get_review_service)]


@dataclass(frozen=True)
class IntakeActor:
    """Who is calling and what they may do here."""

    username: str
    house: str | None
    manager: bool
    #: An external house account (mapped, or in the house group), whether or
    #: not it is still mapped to a house.
    house_account: bool


def _actor(identity: AuthenticatedIdentity, request: Request) -> IntakeActor:
    # Fail closed without a named identity, including local development, the
    # same rule calibration's actor() applies.
    if not identity.username:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="A named account is required",
        )
    username = identity.username
    house_account = is_house_account(
        username, request.headers.get(AUTHENTIK_GROUPS_HEADER)
    )
    return IntakeActor(
        username=username,
        house=settings.house_contributors.get(username),
        # Fail closed: an external house account never reviews, even if it
        # also appears in the manager list.
        manager=not house_account and username in settings.calibration_admin_usernames,
        house_account=house_account,
    )


def _forbidden(message: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail={"error": "HOUSE_ACCESS_REQUIRED", "message": message},
    )


def reader(identity: Identity, request: Request) -> IntakeActor:
    """Require a house contributor or a manager.

    Args:
        identity (Identity): Forward-auth identity.
        request (Request): The request, for the forwarded groups header.

    Returns:
        IntakeActor: The caller.

    Raises:
        _forbidden: 403 when the caller is neither.
    """
    actor = _actor(identity, request)
    if actor.house is None and not actor.manager:
        msg = "House submissions are available to house contributors and managers."
        raise _forbidden(msg)
    return actor


def writer(identity: Identity, request: Request) -> tuple[IntakeActor, str]:
    """Require a house contributor; return the caller and their house.

    Args:
        identity (Identity): Forward-auth identity.
        request (Request): The request, for the forwarded groups header.

    Returns:
        tuple[IntakeActor, str]: The caller and the house they speak for.

    Raises:
        _forbidden: 403 when the caller is not a house contributor.
    """
    actor = _actor(identity, request)
    if actor.house is None:
        msg = "Only a fragrance house contributor can write house submissions."
        raise _forbidden(msg)
    return actor, actor.house


def reviewer(identity: Identity, request: Request) -> IntakeActor:
    """Require a calibration manager.

    Args:
        identity (Identity): Forward-auth identity.
        request (Request): The request, for the forwarded groups header.

    Returns:
        IntakeActor: The caller.

    Raises:
        _forbidden: 403 when the caller is not a manager.
    """
    actor = _actor(identity, request)
    if not actor.manager:
        msg = "Only a calibration manager can review house submissions."
        raise _forbidden(msg)
    return actor


Reader = Annotated[IntakeActor, Depends(reader)]
Reviewer = Annotated[IntakeActor, Depends(reviewer)]
Writer = Annotated[tuple[IntakeActor, str], Depends(writer)]


@router.get("/access", response_model=HouseAccessResponse)
async def access(identity: Identity, request: Request) -> HouseAccessResponse:
    """Report whether the caller is a house contributor or a manager.

    Open to every named account so the frontend can choose the right
    experience before requesting anything else. ``house_account`` with no
    ``house`` means an external account whose house mapping was removed: it
    is still fenced, and has nothing left to use.
    """
    actor = _actor(identity, request)
    return HouseAccessResponse(
        username=actor.username,
        house=actor.house,
        manager=actor.manager,
        house_account=actor.house_account,
    )


@router.get("/submissions", response_model=list[HouseSubmissionResponse])
async def list_submissions(
    actor: Reader, service: Service
) -> list[HouseSubmissionResponse]:
    """List the caller's house's submissions, or every house's for a manager."""
    return await service.list_submissions(actor.house)


@router.get("/submissions/{submission_id}", response_model=HouseSubmissionResponse)
async def get_submission(
    submission_id: str, actor: Reader, service: Service
) -> HouseSubmissionResponse:
    """Fetch one visible submission."""
    return await service.get(submission_id, actor.house)


@router.post(
    "/submissions",
    response_model=HouseSubmissionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_submission(
    payload: HouseSubmissionPayload, caller: Writer, service: Service
) -> HouseSubmissionResponse:
    """Start a draft for the caller's house."""
    actor, house = caller
    return await service.create(house, actor.username, payload)


@router.put("/submissions/{submission_id}", response_model=HouseSubmissionResponse)
async def update_submission(
    submission_id: str,
    payload: HouseSubmissionPayload,
    caller: Writer,
    service: Service,
) -> HouseSubmissionResponse:
    """Replace a draft's content."""
    _, house = caller
    return await service.update(submission_id, house, payload)


@router.delete("/submissions/{submission_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_submission(
    submission_id: str, caller: Writer, service: Service
) -> Response:
    """Discard a draft."""
    _, house = caller
    await service.delete(submission_id, house)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/submissions/{submission_id}/submit", response_model=HouseSubmissionResponse
)
async def submit_submission(
    submission_id: str, caller: Writer, service: Service
) -> HouseSubmissionResponse:
    """Submit a complete draft; it can no longer be edited afterwards."""
    actor, house = caller
    return await service.submit(submission_id, house, actor.username)


@router.post(
    "/submissions/{submission_id}/revise",
    response_model=HouseSubmissionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def revise_submission(
    submission_id: str, caller: Writer, service: Service
) -> HouseSubmissionResponse:
    """Start a correction that will supersede a submitted record."""
    actor, house = caller
    return await service.revise(submission_id, house, actor.username)


@router.get("/submissions/{submission_id}/review", response_model=ReviewContext)
async def review_context(
    submission_id: str,
    _actor: Reviewer,
    service: ReviewService,
    q: Annotated[str | None, Query(max_length=200)] = None,
) -> ReviewContext:
    """Show a submission beside the catalog versions it might describe."""
    return await service.context(submission_id, q)


@router.post(
    "/submissions/{submission_id}/adopt", response_model=HouseSubmissionResponse
)
async def adopt_submission(
    submission_id: str, decision: AdoptInput, actor: Reviewer, service: ReviewService
) -> HouseSubmissionResponse:
    """Adopt a submission as manufacturer-provided evidence."""
    return await service.adopt(submission_id, actor.username, decision)


@router.post(
    "/submissions/{submission_id}/decline", response_model=HouseSubmissionResponse
)
async def decline_submission(
    submission_id: str, decision: DeclineInput, actor: Reviewer, service: ReviewService
) -> HouseSubmissionResponse:
    """Decline a submission with a reason the house will see."""
    return await service.decline(submission_id, actor.username, decision)
