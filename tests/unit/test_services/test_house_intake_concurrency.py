"""House intake under interleaved requests: stale reads must not win.

Each test holds one session's stale view of a row while a second session
commits a change, then lets the first session act, reproducing the
interleavings a real database allows between two simultaneous requests.
"""

import pytest
import pytest_asyncio
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from fragrance_rater.core.database import Base
from fragrance_rater.models.house_intake import HouseSubmission
from fragrance_rater.schemas.house_intake import HouseSubmissionPayload
from fragrance_rater.services.house_intake_service import HouseIntakeService
from fragrance_rater.utils.timestamps import now_naive_utc

HOUSE = "Maison A"


def payload(**overrides: object) -> HouseSubmissionPayload:
    data: dict[str, object] = {
        "fragrance_name": "Cèdre Nocturne",
        "concentration": "EDP",
        "launch_year": 2019,
        "availability": "in_production",
        "notes": [{"text": "Musk", "position": "base"}],
        "permission_scope": "retain_and_train",
        "contact_name": "Ana Ruiz",
        "contact_role": "Founder",
        "attested": True,
    }
    data.update(overrides)
    return HouseSubmissionPayload.model_validate(data)


@pytest_asyncio.fixture
async def sessions(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'race.db'}")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    yield maker
    await engine.dispose()


async def create_draft(maker, **overrides: object) -> str:
    async with maker() as session:
        draft = await HouseIntakeService(session).create(
            HOUSE, "maison-rep", payload(**overrides)
        )
        await session.commit()
        return draft.id


@pytest.mark.asyncio
async def test_a_stale_draft_read_cannot_edit_a_submitted_record(sessions):
    draft_id = await create_draft(sessions)
    async with sessions() as stale, sessions() as other:
        # The first request has already loaded the row while it was a draft.
        # Holding the reference keeps it in the session's (weak) identity map,
        # as a real request holding the row it loaded would.
        loaded = await stale.get(HouseSubmission, draft_id)
        assert loaded.status == "draft"
        await HouseIntakeService(other).submit(draft_id, HOUSE, "colleague")
        await other.commit()

        service = HouseIntakeService(stale)
        with pytest.raises(HTTPException) as edit:
            await service.update(draft_id, HOUSE, payload(fragrance_name="Rewritten"))
        assert edit.value.status_code == 409
        with pytest.raises(HTTPException) as removal:
            await service.delete(draft_id, HOUSE)
        assert removal.value.status_code == 409

    async with sessions() as check:
        row = await check.get(HouseSubmission, draft_id)
        assert row.status == "submitted"
        assert row.payload["fragrance_name"] == "Cèdre Nocturne"


@pytest.mark.asyncio
async def test_supersede_never_overwrites_a_review(sessions):
    original_id = await create_draft(sessions)
    async with sessions() as session:
        service = HouseIntakeService(session)
        await service.submit(original_id, HOUSE, "maison-rep")
        correction = await service.revise(original_id, HOUSE, "maison-rep")
        # A correction clears the attestation; the house confirms again.
        await service.update(correction.id, HOUSE, payload(launch_year=2020))
        await session.commit()

    async with sessions() as house, sessions() as manager:
        # The house's request saw the original as still pending...
        seen = await house.get(HouseSubmission, original_id)
        assert seen.review_status == "pending"
        # ...then a manager's decline committed before the correction landed.
        declined = await manager.get(HouseSubmission, original_id)
        declined.review_status = "declined"
        declined.reviewed_by = "manager"
        declined.reviewed_at = now_naive_utc()
        declined.review_note = "Barcode needed"
        await manager.commit()

        await HouseIntakeService(house).submit(correction.id, HOUSE, "maison-rep")
        await house.commit()

    async with sessions() as check:
        assert (
            await check.get(HouseSubmission, original_id)
        ).review_status == "declined"
        assert (
            await check.get(HouseSubmission, correction.id)
        ).review_status == "pending"
