"""Validated inputs for consent events and the session-context answers they gate."""

from typing import Literal

from pydantic import Field

from fragrance_rater.schemas.calibration import StrictInput

ConsentScope = Literal[
    "session_context",
    "household_research",
    "aggregate_reporting",
    "model_training",
    "research_export",
]
ConsentEventType = Literal["granted", "withdrawn"]
ContextAnswer = Literal["yes", "no", "prefer_not_to_answer"]
HormonalAnswer = Literal["yes", "no", "prefer_not_to_answer", "not_applicable"]
HungerLevel = Literal[
    "not_hungry",
    "slightly_hungry",
    "hungry",
    "very_hungry",
    "prefer_not_to_answer",
]


class ConsentEventInput(StrictInput):
    """One grant or withdrawal for one scope.

    The consent text version, its digest, and the consent timestamp are never
    supplied by the caller: the server stamps them, so a recorder cannot
    back-date a consent or point it at text the evaluator was not shown.
    """

    scope: ConsentScope
    event_type: ConsentEventType
    enrollment_id: str | None = Field(default=None, max_length=36)
    note: str | None = Field(default=None, max_length=2000)


class SessionContextInput(StrictInput):
    """Self-reported conditions for one session; every answer is refusable.

    Null means "not asked or not recorded". A refusal is the explicit
    ``prefer_not_to_answer``, so the two stay distinguishable. No field is
    required: a sensitive optional question never gates baseline evaluation.
    """

    illness: ContextAnswer | None = None
    nasal_congestion: ContextAnswer | None = None
    allergy_symptoms: ContextAnswer | None = None
    hunger: HungerLevel | None = None
    hours_since_food: float | None = Field(default=None, ge=0, le=168)
    hours_since_caffeine: float | None = Field(default=None, ge=0, le=168)
    personal_fragrance_worn: ContextAnswer | None = None
    ambient_odor: ContextAnswer | None = None
    ambient_odor_detail: str | None = Field(default=None, max_length=2000)
    room_temperature_c: float | None = Field(default=None, ge=-10, le=50)
    room_humidity_pct: float | None = Field(default=None, ge=0, le=100)
    hormonal_context: HormonalAnswer | None = None
    note: str | None = Field(default=None, max_length=2000)
