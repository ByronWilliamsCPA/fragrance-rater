"""Fragrance service for CRUD operations."""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import uuid4

from sqlalchemy import or_, select
from sqlalchemy.orm import selectinload

from fragrance_rater.models.fragrance import (
    Fragrance,
    FragranceAccord,
    FragranceNote,
    Note,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from fragrance_rater.schemas.fragrance import (
        FragranceCreate,
        FragranceSearchParams,
        FragranceUpdate,
    )


class FragranceService:
    """Service for fragrance CRUD operations."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialize the service with a database session.

        Args:
            session: Async database session.
        """
        self.session = session

    async def get_by_id(self, fragrance_id: str) -> Fragrance | None:
        """Get a fragrance by ID with all relationships loaded.

        Args:
            fragrance_id: UUID of the fragrance.

        Returns:
            Fragrance if found, None otherwise.
        """
        stmt = (
            select(Fragrance)
            .where(Fragrance.id == fragrance_id)
            .options(selectinload(Fragrance.notes).selectinload(FragranceNote.note))
            .options(selectinload(Fragrance.accords))
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def search(self, params: FragranceSearchParams) -> list[Fragrance]:
        """Search fragrances with filters.

        Args:
            params: Search parameters.

        Returns:
            List of matching fragrances.
        """
        stmt = select(Fragrance).options(
            selectinload(Fragrance.notes).selectinload(FragranceNote.note),
            selectinload(Fragrance.accords),
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
            data: Fragrance creation data.

        Returns:
            Created fragrance.
        """
        fragrance = Fragrance(
            id=str(uuid4()),
            name=data.name,
            brand=data.brand,
            concentration=data.concentration,
            launch_year=data.launch_year,
            gender_target=data.gender_target,
            primary_family=data.primary_family,
            subfamily=data.subfamily,
            intensity=data.intensity,
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
        return await self.get_by_id(fragrance.id)  # type: ignore[return-value]

    async def update(
        self, fragrance_id: str, data: FragranceUpdate
    ) -> Fragrance | None:
        """Update an existing fragrance.

        Args:
            fragrance_id: UUID of the fragrance.
            data: Update data.

        Returns:
            Updated fragrance if found, None otherwise.
        """
        fragrance = await self.get_by_id(fragrance_id)
        if not fragrance:
            return None

        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(fragrance, field, value)

        await self.session.flush()
        return fragrance

    async def delete(self, fragrance_id: str) -> bool:
        """Delete a fragrance by ID.

        Args:
            fragrance_id: UUID of the fragrance.

        Returns:
            True if deleted, False if not found.
        """
        fragrance = await self.get_by_id(fragrance_id)
        if not fragrance:
            return False

        await self.session.delete(fragrance)
        await self.session.flush()
        return True

    async def _get_or_create_note(self, name: str, category: str) -> Note:
        """Get an existing note or create a new one.

        Args:
            name: Note name.
            category: Note category.

        Returns:
            Note instance.
        """
        stmt = select(Note).where(Note.name == name)
        result = await self.session.execute(stmt)
        note = result.scalar_one_or_none()

        if not note:
            note = Note(id=str(uuid4()), name=name, category=category)
            self.session.add(note)
            await self.session.flush()

        return note
