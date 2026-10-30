"""Manager-only evidence export for one enrollment (R7b; P6.3 acceptance).

One JSON document carries every field the R7a schema and the R7b instrument
capture, so a synthetic run through the released UI can show that each of them
reaches an export non-null at least once (``PROJECT-PLAN.md`` R7b acceptance).

Identity stays concealed: the export names samples by blind code and position
only, exactly as the participant view does before reveal. The identity mapping
is a separate manager endpoint with its own audit event.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

from sqlalchemy import select

from fragrance_rater.models.calibration import (
    CalibrationSession,
    FitChoice,
    Observation,
    Presentation,
    Program,
    SessionContext,
)
from fragrance_rater.services.calibration_service import (
    CalibrationService,
    observation_payload,
)
from fragrance_rater.services.capture_service import CaptureService
from fragrance_rater.services.consent import ConsentService
from fragrance_rater.utils.timestamps import now_naive_utc

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

EXPORT_VERSION = "r7b-evidence-v1"

_PRESENTATION_FIELDS = (
    "intended_position",
    "presented_at",
    "applied_at",
    "application_timezone",
    "application_method",
    "application_dose_sprays",
    "sample_source_type",
    "sample_container",
    "sample_volume_ml",
    "sample_acquired_on",
    "sample_decanted_on",
    "sample_opened_on",
    "sample_batch_code",
    "physical_sample_confirmed",
)
_CONTEXT_FIELDS = (
    "illness",
    "nasal_congestion",
    "allergy_symptoms",
    "hunger",
    "hours_since_food",
    "hours_since_caffeine",
    "personal_fragrance_worn",
    "ambient_odor",
    "ambient_odor_detail",
    "room_temperature_c",
    "room_humidity_pct",
    "hormonal_context",
    "note",
)


def _iso(value: object) -> object:
    """Return ISO text for a date or datetime, and any other value unchanged."""
    isoformat = getattr(value, "isoformat", None)
    return isoformat() if callable(isoformat) else value


async def _fit_choices(
    db: AsyncSession, observation_ids: list[str]
) -> dict[str, dict[str, list[str]]]:
    """Return each observation's ticked season and setting options."""
    result: dict[str, dict[str, list[str]]] = {
        observation_id: {"season": [], "setting": []}
        for observation_id in observation_ids
    }
    for choice in await db.scalars(
        select(FitChoice)
        .where(FitChoice.observation_id.in_(observation_ids))
        .order_by(FitChoice.created_at, FitChoice.id)
    ):
        result[choice.observation_id][choice.dimension].append(choice.code)
    return result


async def build_evidence_export(
    db: AsyncSession, enrollment_id: str, username: str
) -> dict[str, object]:
    """Build the evidence export for one enrollment.

    The caller must be a manager: the route checks, and this passes
    ``admin=True`` to the shared enrollment lookup. Session context is included
    only while ``session_context`` consent currently stands; otherwise it is
    withheld and the session says so.

    Args:
        db (AsyncSession): Database session.
        enrollment_id (str): The enrollment to export.
        username (str): The verified manager.

    Returns:
        dict[str, object]: The export document.
    """
    calibration = CalibrationService(db)
    capture = CaptureService(db)
    enrollment = await calibration.enrollment(enrollment_id, username, admin=True)
    program = await db.get(Program, enrollment.program_id)
    assert program is not None
    consent = ConsentService(db)
    consent_state = await consent.state(enrollment.reviewer_id)
    context_allowed = consent_state.get("session_context") == "granted"

    sessions = list(
        await db.scalars(
            select(CalibrationSession)
            .where(CalibrationSession.enrollment_id == enrollment.id)
            .order_by(CalibrationSession.created_at, CalibrationSession.id)
        )
    )
    session_documents: list[dict[str, object]] = []
    for session in sessions:
        presentations = list(
            await db.scalars(
                select(Presentation)
                .where(Presentation.session_id == session.id)
                .order_by(Presentation.position)
            )
        )
        observations = list(
            await db.scalars(
                select(Observation)
                .where(Observation.presentation_id.in_([p.id for p in presentations]))
                .order_by(Observation.created_at, Observation.id)
            )
        )
        fits = await _fit_choices(db, [o.id for o in observations])
        context = await db.scalar(
            select(SessionContext).where(SessionContext.session_id == session.id)
        )
        context_document: dict[str, object] | None = None
        if context is not None and context_allowed:
            context_document = {
                name: getattr(context, name) for name in _CONTEXT_FIELDS
            }
        presentation_documents: list[dict[str, object]] = []
        for presentation in presentations:
            document: dict[str, object] = {
                "id": presentation.id,
                "blind_code": presentation.blind_code,
                "position": presentation.position,
                **{
                    name: _iso(cast("object", getattr(presentation, name)))
                    for name in _PRESENTATION_FIELDS
                },
                "observations": [
                    {**observation_payload(o), "fit_choices": fits[o.id]}
                    for o in observations
                    if o.presentation_id == presentation.id
                ],
            }
            presentation_documents.append(document)
        session_documents.append(
            {
                "id": session.id,
                "occurred_on": _iso(session.occurred_on),
                "started_at": _iso(session.started_at),
                "ended_at": _iso(session.ended_at),
                "evaluator_timezone": session.evaluator_timezone,
                "context": context_document,
                "context_withheld": context is not None and not context_allowed,
                "presentations": presentation_documents,
                "rankings": await capture.rankings(session.id, username, admin=True),
                "quality_flags": await capture.flags(session.id, username, admin=True),
            }
        )
    return {
        "export_version": EXPORT_VERSION,
        "generated_at": now_naive_utc().isoformat(),
        "program": {
            "id": program.id,
            "name": program.name,
            "version": program.version,
            "status": program.status,
            "instrument_version": program.instrument_version,
        },
        "enrollment": {
            "id": enrollment.id,
            "reviewer_id": enrollment.reviewer_id,
            "randomization_algorithm": enrollment.randomization_algorithm,
            "randomization_seed": enrollment.randomization_seed,
            "revealed": enrollment.revealed_at is not None,
        },
        "consent": {
            "state": consent_state,
            "events": [
                {
                    "event_type": event.event_type,
                    "scope": event.scope,
                    "consent_text_version": event.consent_text_version,
                    "consent_text_sha256": event.consent_text_sha256,
                    "occurred_at": _iso(event.occurred_at),
                }
                for event in await consent.events(enrollment.reviewer_id)
            ],
        },
        "sessions": session_documents,
    }
