"""Fragrance house intake endpoints.

A house contributor drafts, submits, and corrects descriptions of its own
fragrances. A calibration manager may read every house's submissions but
cannot write them: a manager speaking for a house would defeat the point of
manufacturer-provided evidence (ADR-012). Everyone else is refused.
"""

from dataclasses import dataclass
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from fragrance_rater.core.auth import AuthenticatedIdentity, get_current_identity
from fragrance_rater.core.config import settings
from fragrance_rater.core.database import get_db
from fragrance_rater.schemas.house_intake import (
    HouseAccessResponse,
    HouseSubmissionPayload,
    HouseSubmissionResponse,
)
from fragrance_rater.services.house_intake_service import HouseIntakeService

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


@dataclass(frozen=True)
class IntakeActor:
    """Who is calling and what they may do here."""

    username: str
    house: str | None
    manager: bool


def _actor(identity: AuthenticatedIdentity) -> IntakeActor:
    # Fail closed without a named identity, including local development, the
    # same rule calibration's actor() applies.
    if not identity.username:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="A named account is required",
        )
    username = identity.username
    return IntakeActor(
        username=username,
        house=settings.house_contributors.get(username),
        manager=username in settings.calibration_admin_usernames,
    )


def _forbidden(message: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail={"error": "HOUSE_ACCESS_REQUIRED", "message": message},
    )


def reader(identity: Identity) -> IntakeActor:
    """Require a house contributor or a manager.

    Args:
        identity (Identity): Forward-auth identity.

    Returns:
        IntakeActor: The caller.

    Raises:
        _forbidden: 403 when the caller is neither.
    """
    actor = _actor(identity)
    if actor.house is None and not actor.manager:
        msg = "House submissions are available to house contributors and managers."
        raise _forbidden(msg)
    return actor


def writer(identity: Identity) -> tuple[IntakeActor, str]:
    """Require a house contributor; return the caller and their house.

    Args:
        identity (Identity): Forward-auth identity.

    Returns:
        tuple[IntakeActor, str]: The caller and the house they speak for.

    Raises:
        _forbidden: 403 when the caller is not a house contributor.
    """
    actor = _actor(identity)
    if actor.house is None:
        msg = "Only a fragrance house contributor can write house submissions."
        raise _forbidden(msg)
    return actor, actor.house


Reader = Annotated[IntakeActor, Depends(reader)]
Writer = Annotated[tuple[IntakeActor, str], Depends(writer)]


@router.get("/access", response_model=HouseAccessResponse)
async def access(identity: Identity) -> HouseAccessResponse:
    """Report whether the caller is a house contributor or a manager.

    Open to every named account so the frontend can choose the right
    experience before requesting anything else.
    """
    actor = _actor(identity)
    return HouseAccessResponse(
        username=actor.username, house=actor.house, manager=actor.manager
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
