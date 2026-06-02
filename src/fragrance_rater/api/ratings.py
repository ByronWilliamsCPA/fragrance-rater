"""Rating endpoints backed by an LLM scoring call.

The router exposes a single ``POST /ratings`` endpoint that accepts
a fragrance description and returns a structured rating produced
by the OpenRouter LLM (``anthropic/claude-3.5-sonnet`` by default,
per ADR-003). Latency is dominated by the upstream LLM and can
exceed several seconds; callers should treat the endpoint as
slow and avoid issuing it inside hot request paths.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from fragrance_rater.llm import LLMRatingClient, get_llm_client

router = APIRouter(prefix="/ratings", tags=["ratings"])

FragranceNote = Annotated[str, Field(min_length=1, max_length=64)]


class RatingRequest(BaseModel):
    """Request body for ``POST /ratings``.

    Attributes:
        name (str): Fragrance name (required).
        brand (str | None): Fragrance house or brand. Improves rating accuracy.
        description (str): Free-text description of the scent profile.
        notes (list[FragranceNote] | None): Optional list of accord/top/heart/base notes.
    """

    name: str = Field(
        ...,
        min_length=1,
        max_length=200,
        description="Fragrance name, e.g. 'Aventus'.",
        examples=["Aventus"],
    )
    brand: str | None = Field(
        default=None,
        max_length=200,
        description="Fragrance house or brand, e.g. 'Creed'.",
        examples=["Creed"],
    )
    description: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description=(
            "Free-text description of the scent. Mention projection, "
            "longevity, season, and accords for a better rating."
        ),
        examples=[
            "Smoky pineapple opening with birch, settling into a musky vanilla dry-down.",
        ],
    )
    notes: list[FragranceNote] | None = Field(
        default=None,
        max_length=32,
        description=(
            "Optional list of fragrance notes. Capped at 32 entries of"
            " up to 64 characters each to bound prompt size and"
            " upstream cost."
        ),
        examples=[["bergamot", "blackcurrant", "birch", "musk"]],
    )


class RatingResponse(BaseModel):
    """Response body returned by ``POST /ratings``.

    Attributes:
        score (int): Integer rating, 1 (poor) to 10 (excellent).
        reasoning (str): Human-readable explanation written by the LLM.
        model (str): Identifier of the LLM that produced the rating.
        notes (list[str]): Echo of accord notes used by the model.
        latency_warning (str): Reminder that LLM latency is variable.
    """

    score: int = Field(
        ..., ge=1, le=10, description="Rating from 1 (poor) to 10 (excellent)."
    )
    reasoning: str = Field(..., description="LLM-authored explanation of the score.")
    model: str = Field(
        ..., description="LLM model identifier (e.g. 'anthropic/claude-3.5-sonnet')."
    )
    notes: list[str] = Field(
        default_factory=list,
        description="Accord notes used in the rating.",
    )
    latency_warning: str = Field(
        default=("LLM responses vary in latency; expect 1-10 seconds per call."),
        description="Operational note about response time variability.",
    )


@router.post(
    "",
    response_model=RatingResponse,
    status_code=status.HTTP_200_OK,
    summary="Rate a fragrance with an LLM",
    responses={
        200: {"description": "Rating produced successfully."},
        422: {"description": "Request body failed validation."},
        503: {"description": "LLM upstream is unavailable."},
    },
)
def create_rating(
    payload: RatingRequest,
    client: LLMRatingClient = Depends(get_llm_client),  # pyright: ignore[reportCallInDefaultInitializer]
) -> RatingResponse:
    """Produce an LLM-powered rating for a fragrance.

    Accepted fields: ``name`` (required), ``brand``, ``description``
    (required), and an optional list of accord ``notes``.

    Returned fields: ``score`` (1-10), ``reasoning`` (LLM-authored
    explanation), ``model`` identifier, echoed ``notes``, and a
    ``latency_warning`` string.

    The endpoint calls OpenRouter using the ``anthropic/claude-3.5-sonnet``
    model by default (see ADR-003). When the service is started
    with ``TEST_MODE=true``, a deterministic fixture is returned
    instead of issuing a network call; CI relies on this seam.

    Response time may vary by several seconds because the LLM
    backend is the dominant cost; clients should not block hot
    paths on this call.

    Args:
        payload (RatingRequest): Validated rating request body.
        client (LLMRatingClient): LLM rating client injected via FastAPI dependency.

    Returns:
        RatingResponse: The LLM-authored rating, model identifier, and latency note.

    Raises:
        HTTPException: 503 when the upstream LLM client is unavailable
            or returns a runtime error.
    """
    try:
        result = client.rate(
            name=payload.name,
            brand=payload.brand,
            description=payload.description,
            notes=payload.notes,
        )
    except RuntimeError as exc:
        # Upstream LLM unavailable or unconfigured. Translate to the
        # documented 503 contract instead of leaking a 500.
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="LLM upstream is unavailable",
        ) from exc
    return RatingResponse(
        score=result.score,
        reasoning=result.reasoning,
        model=result.model,
        notes=result.notes,
    )
