"""Fragrance service for CRUD operations."""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import or_, select
from sqlalchemy.orm import selectinload

from fragrance_rater.core.exceptions import DatabaseError, ValidationError
from fragrance_rater.models.calibration import Membership
from fragrance_rater.models.fragrance import (
    Fragrance,
    FragranceAccord,
    FragranceNote,
    Note,
    TrainingEligibility,
)
from fragrance_rater.utils.timestamps import now_naive_utc

if TYPE_CHECKING:
    from collections.abc import Iterable

    from sqlalchemy.ext.asyncio import AsyncSession

    from fragrance_rater.schemas.fragrance import (
        FragranceCreate,
        FragranceSearchParams,
        FragranceUpdate,
    )


class FragranceService:
    """Service for fragrance CRUD operations.

    Args:
        session (AsyncSession): Async database session.
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(self, fragrance_id: str) -> Fragrance | None:
        """Get a fragrance by ID with all relationships loaded.

        Args:
            fragrance_id (str): UUID of the fragrance.

        Returns:
            Fragrance | None: Fragrance if found, None otherwise.
        """
        stmt = (
            select(Fragrance)
            .where(Fragrance.id == fragrance_id, Fragrance.deleted_at.is_(None))
            .options(selectinload(Fragrance.notes).selectinload(FragranceNote.note))
            .options(selectinload(Fragrance.accords))
            .options(selectinload(Fragrance.perfumers))
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def search(self, params: FragranceSearchParams) -> list[Fragrance]:
        """Search fragrances with filters.

        Args:
            params (FragranceSearchParams): Search parameters.

        Returns:
            list[Fragrance]: List of matching fragrances.
        """
        # Critical finding 2: soft-delete filter. Every read query against
        # fragrances/evaluations/reviewers must exclude deleted_at IS NOT NULL.
        stmt = (
            select(Fragrance)
            .where(Fragrance.deleted_at.is_(None))
            .options(
                selectinload(Fragrance.notes).selectinload(FragranceNote.note),
                selectinload(Fragrance.accords),
                # Eager-loaded with the rest: a search returning 100 rows would
                # otherwise issue a query per fragrance for its attribution.
                selectinload(Fragrance.perfumers),
            )
        )

        if params.q:
            search_term = f"%{params.q}%"
            stmt = stmt.where(
                or_(
                    Fragrance.name.ilike(search_term),
                    Fragrance.brand.ilike(search_term),
                )
            )

        if params.brand:
            stmt = stmt.where(Fragrance.brand.ilike(f"%{params.brand}%"))

        if params.primary_family:
            stmt = stmt.where(Fragrance.primary_family == params.primary_family)

        if params.gender_target:
            stmt = stmt.where(Fragrance.gender_target == params.gender_target)

        stmt = stmt.order_by(Fragrance.name).offset(params.offset).limit(params.limit)

        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def create(self, data: FragranceCreate) -> Fragrance:
        """Create a new fragrance with notes and accords.

        Args:
            data (FragranceCreate): Fragrance creation data. If
                `data.training_eligibility_code` is set, it is validated via
                `_validate_training_eligibility_code` before the fragrance is
                built, which raises `ValidationError` if the code does not
                exist or is inactive in `training_eligibilities`.

        Returns:
            Fragrance: Created fragrance.

        Raises:
            DatabaseError: If the flushed fragrance cannot be read back.
        """
        if data.training_eligibility_code is not None:
            await self._validate_training_eligibility_code(
                data.training_eligibility_code
            )
        fragrance = Fragrance(
            id=str(uuid4()),
            name=data.name,
            brand=data.brand,
            concentration=data.concentration,
            version_key=data.version_key,
            launch_year=data.launch_year,
            gender_target=data.gender_target,
            primary_family=data.primary_family,
            subfamily=data.subfamily,
            intensity=data.intensity,
            training_eligibility_code=data.training_eligibility_code,
            data_source="manual",
        )
        self.session.add(fragrance)

        # Add notes
        for note_data in data.notes:
            note = await self._get_or_create_note(
                note_data.note_name, note_data.note_category
            )
            fragrance_note = FragranceNote(
                fragrance_id=fragrance.id,
                note_id=note.id,
                position=note_data.position,
            )
            self.session.add(fragrance_note)

        # Add accords
        for accord_data in data.accords:
            accord = FragranceAccord(
                fragrance_id=fragrance.id,
                accord_type=accord_data.accord_type,
                intensity=accord_data.intensity,
            )
            self.session.add(accord)

        await self.session.flush()
        created = await self.get_by_id(fragrance.id)
        if created is None:
            msg = f"Fragrance {fragrance.id} was not readable after flush"
            raise DatabaseError(msg, operation="create", table="fragrances")
        return created

    async def update(
        self, fragrance_id: str, data: FragranceUpdate
    ) -> Fragrance | None:
        """Update an existing fragrance.

        Args:
            fragrance_id (str): UUID of the fragrance.
            data (FragranceUpdate): Update data. If
                `data.training_eligibility_code` is explicitly set to a
                non-null value, it is validated via
                `_validate_training_eligibility_code` before the update is
                applied, which raises `ValidationError` if the code does not
                exist or is inactive in `training_eligibilities`.

        Returns:
            Fragrance | None: Updated fragrance if found, None otherwise.

        Raises:
            HTTPException: If calibration references the version and an
                identity field would change.
        """
        fragrance = await self.get_by_id(fragrance_id)
        if not fragrance:
            return None

        update_data = data.model_dump(exclude_unset=True)
        new_eligibility_code = update_data.get("training_eligibility_code")
        if (
            "training_eligibility_code" in update_data
            and new_eligibility_code is not None
        ):
            await self._validate_training_eligibility_code(new_eligibility_code)
        identity_fields = {
            "name",
            "brand",
            "concentration",
            "launch_year",
            "version_key",
            "gender_target",
            "primary_family",
            "subfamily",
            "intensity",
        }
        if identity_fields.intersection(update_data):
            # Membership creation takes the same row lock so assignment cannot
            # race an identity correction between this check and the update.
            await self.session.execute(
                select(Fragrance.id)
                .where(Fragrance.id == fragrance_id)
                .with_for_update()
            )
            await self.session.refresh(fragrance)
            if fragrance.deleted_at is not None:
                return None
            identity_changed = any(
                getattr(fragrance, field) != update_data[field]
                for field in identity_fields.intersection(update_data)
            )
            if identity_changed and await self.session.scalar(
                select(Membership.id)
                .where(Membership.fragrance_id == fragrance_id)
                .limit(1)
            ):
                raise HTTPException(
                    status_code=409,
                    detail="Calibration references this version; create a new version to change its identity",
                )
        for field, value in update_data.items():
            setattr(fragrance, field, value)

        await self.session.flush()
        return fragrance

    async def delete(self, fragrance_id: str) -> bool:
        """Soft-delete a fragrance by ID.

        Critical finding 2: this sets `deleted_at` instead of issuing a real
        DELETE, so it never triggers cascade="all, delete-orphan" on the
        fragrance's notes/accords/evaluations; no row is actually removed.

        Args:
            fragrance_id (str): UUID of the fragrance.

        Returns:
            bool: True if soft-deleted, False if not found (or already
                soft-deleted, since get_by_id excludes it).

        Raises:
            HTTPException: If calibration references the version.
        """
        fragrance = await self.get_by_id(fragrance_id)
        if not fragrance:
            return False

        # Calibration memberships preserve the identity of an assigned
        # stimulus. Lock the catalog row so assignment cannot race this check,
        # then refuse deletion rather than leaving presentations pointing at a
        # version that silently disappears from histories and training data.
        await self.session.execute(
            select(Fragrance.id).where(Fragrance.id == fragrance_id).with_for_update()
        )
        if await self.session.scalar(
            select(Membership.id)
            .where(Membership.fragrance_id == fragrance_id)
            .limit(1)
        ):
            raise HTTPException(
                status_code=409,
                detail="Calibration references this version; it cannot be deleted",
            )

        fragrance.deleted_at = now_naive_utc()
        await self.session.flush()
        return True

    async def _get_or_create_note(self, name: str, category: str) -> Note:
        """Get an existing note or create a new one.

        Args:
            name (str): Note name.
            category (str): Note category.

        Returns:
            Note: Note instance.
        """
        stmt = select(Note).where(Note.name == name)
        result = await self.session.execute(stmt)
        note = result.scalar_one_or_none()

        if not note:
            note = Note(id=str(uuid4()), name=name, category=category)
            self.session.add(note)
            await self.session.flush()

        return note

    async def _validate_training_eligibility_code(self, code: str) -> None:
        """Ensure a training_eligibility_code exists and is active.

        A portable, driver-independent pre-check by query, deliberately
        unlike the catch-and-discriminate style `create()`/`update()` use
        for the `uq_fragrance_name_brand` uniqueness constraint elsewhere in
        this codebase: that style exists specifically to avoid a
        check-then-insert race on a user-controlled uniqueness constraint,
        which does not apply here. `training_eligibilities` is a small,
        rarely-mutated reference table, so a pre-check carries no such race
        and avoids sniffing `IntegrityError.orig` constraint names, which is
        fragile across the asyncpg/sqlite backends this project's test
        suite uses.

        Args:
            code (str): The candidate `training_eligibility_code` value to
                validate against the `training_eligibilities` lookup table.

        Raises:
            ValidationError: If no row for `code` exists, or the matching
                row's `active` flag is False.
        """
        eligibility = await self.session.get(TrainingEligibility, code)
        if eligibility is None or not eligibility.active:
            msg = f"training_eligibility_code {code!r} does not exist or is inactive"
            raise ValidationError(
                msg,
                field="training_eligibility_code",
                value=code,
                error_code="INVALID_TRAINING_ELIGIBILITY_CODE",
            )

    async def get_training_eligibility_display_label(
        self, code: str | None
    ) -> str | None:
        """Look up the display label for a single training eligibility code.

        Args:
            code (str | None): A fragrance's `training_eligibility_code`,
                or None when the fragrance has no eligibility override.

        Returns:
            str | None: The lookup row's `display_label`, or None if `code`
                is None or no matching row exists.
        """
        if code is None:
            return None
        eligibility = await self.session.get(TrainingEligibility, code)
        return eligibility.display_label if eligibility else None

    async def get_training_eligibility_labels(
        self, codes: Iterable[str]
    ) -> dict[str, str]:
        """Batch look up display labels for several training eligibility codes.

        Args:
            codes (Iterable[str]): Codes to look up; typically the distinct
                non-null `training_eligibility_code` values across a page
                of search results.

        Returns:
            dict[str, str]: Mapping of code to `display_label` for each
                code with a matching row; a code with no matching row is
                simply absent from the result.
        """
        code_set = set(codes)
        if not code_set:
            return {}
        stmt = select(TrainingEligibility).where(TrainingEligibility.code.in_(code_set))
        result = await self.session.execute(stmt)
        return {row.code: row.display_label for row in result.scalars().all()}
