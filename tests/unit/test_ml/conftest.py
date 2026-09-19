"""A small controlled program the ml dataset/reliability tests build on.

Mirrors the ``history_data`` fixture in
``tests/unit/test_services/test_preference_history.py``: one enrolled
evaluator, one calibration session, and one membership per role, so the
eligibility rules the manifest enforces are exercised for real rather than
stubbed. Kept here rather than imported across test packages.
"""

import pytest
import pytest_asyncio

from fragrance_rater.models.calibration import (
    CalibrationSession,
    Enrollment,
    Membership,
    Observation,
    Presentation,
    Program,
)
from fragrance_rater.models.fragrance import (
    Fragrance,
    FragranceAccord,
    FragranceNote,
    Note,
)
from fragrance_rater.models.reviewer import Reviewer
from fragrance_rater.utils.timestamps import now_naive_utc

CATALOG = {
    "baseline": {
        "family": "woody",
        "subfamily": "aromatic",
        "notes": [("note-bergamot", "top"), ("note-cedar", "base")],
        "accords": [("citrus", 0.8), ("woody", 0.5)],
    },
    "holdout": {
        "family": "floral",
        "subfamily": "",
        "notes": [("note-rose", "heart")],
        "accords": [("floral", 0.9)],
    },
    "extra": {
        "family": "fresh",
        "subfamily": "citrus",
        "notes": [("note-bergamot", "top")],
        "accords": [("citrus", 0.4)],
    },
}

NOTES = {
    "note-bergamot": "Bergamot",
    "note-cedar": "Cedar",
    "note-rose": "Rose",
}


def make_observation(
    presentation,
    *,
    liking=8,
    stage="BLOTTER",
    phase="PRE_REVEAL",
    created_at=None,
    **columns,
):
    """Build a submitted response with the null-detection semantics intact."""
    return Observation(
        presentation_id=presentation.id,
        stage=stage,
        phase=phase,
        detected=liking is not None,
        intensity=3 if liking is not None else 0,
        liking=liking,
        perceived_notes=["pencil"],
        recorded_by="recorder",
        created_at=created_at or now_naive_utc(),
        **columns,
    )


@pytest.fixture
def observation_factory():
    """Expose ``make_observation`` to tests without a cross-package import."""
    return make_observation


@pytest_asyncio.fixture
async def program(async_session):
    """Create an enrolled evaluator with one membership per role.

    Returns:
        dict: ``session``, ``program``, ``enrollment``, ``memberships`` and
            ``presentations`` keyed by role name (the hidden repeat is
            ``HIDDEN_REPEAT`` and points at ``UNIVERSAL_BASELINE``).
    """
    async_session.add(Reviewer(id="owner", name="Owner"))
    async_session.add(Reviewer(id="other", name="Other"))
    for note_id, name in NOTES.items():
        async_session.add(Note(id=note_id, name=name, category="Top"))
    for key, spec in CATALOG.items():
        async_session.add(
            Fragrance(
                id=key,
                name=key,
                brand="House",
                concentration="EDP",
                gender_target="unisex",
                primary_family=spec["family"],
                subfamily=spec["subfamily"],
                data_source="manual",
            )
        )
    await async_session.flush()
    for key, spec in CATALOG.items():
        for note_id, position in spec["notes"]:
            async_session.add(
                FragranceNote(fragrance_id=key, note_id=note_id, position=position)
            )
        for accord, intensity in spec["accords"]:
            async_session.add(
                FragranceAccord(
                    fragrance_id=key, accord_type=accord, intensity=intensity
                )
            )
    protocol = Program(name="ML fixtures", version="1")
    async_session.add(protocol)
    await async_session.flush()
    enrollment = Enrollment(
        program_id=protocol.id, reviewer_id="owner", recorder_usernames=["recorder"]
    )
    async_session.add(enrollment)
    await async_session.flush()
    session = CalibrationSession(enrollment_id=enrollment.id)
    async_session.add(session)
    await async_session.flush()

    memberships = {}
    presentations = {}
    roles = [
        ("UNIVERSAL_BASELINE", "baseline"),
        ("HIDDEN_REPEAT", "baseline"),
        ("HOLDOUT", "holdout"),
        ("EXTRA_BASELINE", "extra"),
    ]
    for position, (role, fragrance_id) in enumerate(roles):
        member = Membership(
            program_id=protocol.id,
            fragrance_id=fragrance_id,
            role="UNIVERSAL_BASELINE" if role == "EXTRA_BASELINE" else role,
            repeat_of_id=(
                memberships["UNIVERSAL_BASELINE"].id
                if role == "HIDDEN_REPEAT"
                else None
            ),
        )
        async_session.add(member)
        await async_session.flush()
        presentation = Presentation(
            session_id=session.id,
            membership_id=member.id,
            blind_code=f"BLIND-{position}",
            position=position,
            blotter_locked_at=now_naive_utc(),
        )
        async_session.add(presentation)
        await async_session.flush()
        memberships[role] = member
        presentations[role] = presentation
    return {
        "session": async_session,
        "program": protocol,
        "enrollment": enrollment,
        "memberships": memberships,
        "presentations": presentations,
    }
