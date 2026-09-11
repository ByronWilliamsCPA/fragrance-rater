"""Calibration assignments preserve canonical identity during catalog edits."""

import pytest
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from fragrance_rater.models.calibration import Membership, Program
from fragrance_rater.models.fragrance import Fragrance
from fragrance_rater.schemas.fragrance import FragranceUpdate
from fragrance_rater.services.fragrance_service import FragranceService


async def assigned_version(session: AsyncSession) -> Fragrance:
    """Create an assigned version, including a draft program."""
    fragrance = Fragrance(
        name="Assigned scent",
        brand="House",
        concentration="EDP",
        launch_year=2020,
        gender_target="Unisex",
        primary_family="woody",
        subfamily="aromatic",
        data_source="manual",
    )
    program = Program(name="Diagnostic baseline", version="1")
    session.add_all([fragrance, program])
    await session.flush()
    session.add(
        Membership(
            program_id=program.id,
            fragrance_id=fragrance.id,
            role="UNIVERSAL_BASELINE",
        )
    )
    await session.commit()
    return fragrance


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "changes",
    [
        {"name": "Different scent"},
        {"brand": "Different house"},
        {"concentration": "EDT"},
        {"launch_year": 2021},
        {"launch_year": None},
        {"gender_target": "Masculine"},
        {"primary_family": "floral"},
        {"subfamily": "oriental"},
        {"intensity": "Rich"},
    ],
)
async def test_assigned_identity_edit_is_rejected(async_session, changes):
    """An edit cannot silently retarget previously assigned presentations."""
    fragrance = await assigned_version(async_session)
    original = {field: getattr(fragrance, field) for field in changes}
    with pytest.raises(HTTPException) as error:
        await FragranceService(async_session).update(
            fragrance.id, FragranceUpdate(**changes)
        )
    assert error.value.status_code == 409
    await async_session.commit()
    await async_session.refresh(fragrance)
    assert {field: getattr(fragrance, field) for field in changes} == original


@pytest.mark.asyncio
async def test_assigned_unchanged_fields_remain_editable(async_session):
    """A no-op PATCH does not require manufacturing a new version."""
    fragrance = await assigned_version(async_session)
    updated = await FragranceService(async_session).update(
        fragrance.id,
        FragranceUpdate(
            name=fragrance.name,
            primary_family=fragrance.primary_family,
            intensity=fragrance.intensity,
        ),
    )
    assert updated is not None
    assert updated.primary_family == "woody"
    assert updated.name == "Assigned scent"


@pytest.mark.asyncio
async def test_assigned_version_key_cannot_change(async_session):
    """The service also protects version keys if a future schema exposes them."""

    class VersionUpdate(FragranceUpdate):
        version_key: str

    fragrance = await assigned_version(async_session)
    with pytest.raises(HTTPException) as error:
        await FragranceService(async_session).update(
            fragrance.id, VersionUpdate(version_key="reformulation")
        )
    assert error.value.status_code == 409
    assert fragrance.version_key == "legacy"


@pytest.mark.asyncio
async def test_assigned_version_cannot_be_deleted(async_session):
    """Deleting an assigned stimulus must not corrupt calibration history."""
    fragrance = await assigned_version(async_session)

    with pytest.raises(HTTPException) as error:
        await FragranceService(async_session).delete(fragrance.id)

    assert error.value.status_code == 409
    await async_session.refresh(fragrance)
    assert fragrance.deleted_at is None


@pytest.mark.asyncio
async def test_update_does_not_revive_version_deleted_while_waiting_for_lock(
    async_session, monkeypatch
):
    """A delete committed before the update lock is observed after refresh."""
    fragrance = await assigned_version(async_session)
    service = FragranceService(async_session)

    async def mark_deleted(_obj):
        fragrance.deleted_at = fragrance.created_at

    monkeypatch.setattr(async_session, "refresh", mark_deleted)
    updated = await service.update(fragrance.id, FragranceUpdate(name="New name"))
    assert updated is None
    assert fragrance.name == "Assigned scent"
