"""Unit tests for FragranceService."""

import pytest

from fragrance_rater.models.fragrance import Fragrance
from fragrance_rater.schemas.fragrance import (
    FragranceAccordCreate,
    FragranceCreate,
    FragranceNoteCreate,
    FragranceSearchParams,
    FragranceUpdate,
)
from fragrance_rater.services.fragrance_service import FragranceService


@pytest.mark.asyncio
class TestFragranceService:
    """Integration tests for FragranceService."""

    async def test_create_fragrance(self, async_session):
        """Test creating a fragrance."""
        service = FragranceService(async_session)
        data = FragranceCreate(
            name="Test Fragrance",
            brand="Test Brand",
            concentration="EDP",
            gender_target="Unisex",
            primary_family="woody",
            subfamily="aromatic",
        )
        fragrance = await service.create(data)
        await async_session.commit()

        assert fragrance is not None
        assert fragrance.name == "Test Fragrance"
        assert fragrance.brand == "Test Brand"
        assert fragrance.data_source == "manual"

    async def test_create_fragrance_with_year(self, async_session):
        """Test creating a fragrance with launch year."""
        service = FragranceService(async_session)
        data = FragranceCreate(
            name="Vintage Scent",
            brand="Classic Brand",
            concentration="EDT",
            launch_year=2020,
            gender_target="Masculine",
            primary_family="fresh",
            subfamily="citrus",
        )
        fragrance = await service.create(data)
        await async_session.commit()

        assert fragrance.launch_year == 2020
        assert fragrance.gender_target == "Masculine"

    async def test_create_fragrance_with_notes(self, async_session):
        """Test creating a fragrance with notes."""
        service = FragranceService(async_session)
        data = FragranceCreate(
            name="Complex Scent",
            brand="Niche Brand",
            concentration="Parfum",
            gender_target="Unisex",
            primary_family="oriental",
            subfamily="spicy",
            notes=[
                FragranceNoteCreate(
                    note_name="Bergamot", note_category="citrus", position="top"
                ),
                FragranceNoteCreate(
                    note_name="Rose", note_category="floral", position="heart"
                ),
                FragranceNoteCreate(
                    note_name="Sandalwood", note_category="woody", position="base"
                ),
            ],
        )
        fragrance = await service.create(data)
        await async_session.commit()

        assert fragrance is not None
        assert len(fragrance.notes) == 3

    async def test_create_fragrance_with_accords(self, async_session):
        """Test creating a fragrance with accords."""
        service = FragranceService(async_session)
        data = FragranceCreate(
            name="Accord Test",
            brand="Test Brand",
            concentration="EDP",
            gender_target="Unisex",
            primary_family="woody",
            subfamily="amber",
            accords=[
                FragranceAccordCreate(accord_type="woody", intensity=0.8),
                FragranceAccordCreate(accord_type="amber", intensity=0.6),
            ],
        )
        fragrance = await service.create(data)
        await async_session.commit()

        assert len(fragrance.accords) == 2

    async def test_get_by_id(self, async_session):
        """Test getting fragrance by ID."""
        # Create fragrance directly
        fragrance = Fragrance(
            id="get-frag-001",
            name="Get Test",
            brand="Brand",
            concentration="EDP",
            gender_target="unisex",
            primary_family="fresh",
            subfamily="aquatic",
            data_source="manual",
        )
        async_session.add(fragrance)
        await async_session.commit()

        service = FragranceService(async_session)
        found = await service.get_by_id("get-frag-001")

        assert found is not None
        assert found.name == "Get Test"

    async def test_get_by_id_not_found(self, async_session):
        """Test getting non-existent fragrance."""
        service = FragranceService(async_session)
        found = await service.get_by_id("nonexistent")

        assert found is None

    async def test_search_by_query(self, async_session):
        """Test searching fragrances by query (name or brand)."""
        # Create test fragrances
        async_session.add(
            Fragrance(
                id="search-1",
                name="Aventus",
                brand="Creed",
                concentration="EDP",
                gender_target="Masculine",
                primary_family="woody",
                subfamily="aromatic",
                data_source="manual",
            )
        )
        async_session.add(
            Fragrance(
                id="search-2",
                name="Sauvage",
                brand="Dior",
                concentration="EDT",
                gender_target="Masculine",
                primary_family="fresh",
                subfamily="aromatic",
                data_source="manual",
            )
        )
        await async_session.commit()

        service = FragranceService(async_session)
        params = FragranceSearchParams(q="Aventus")
        results = await service.search(params)

        assert len(results) == 1
        assert results[0].name == "Aventus"

    async def test_search_by_brand(self, async_session):
        """Test searching fragrances by brand."""
        async_session.add(
            Fragrance(
                id="brand-1",
                name="Green Irish Tweed",
                brand="Creed",
                concentration="EDP",
                gender_target="Masculine",
                primary_family="fresh",
                subfamily="aromatic",
                data_source="manual",
            )
        )
        async_session.add(
            Fragrance(
                id="brand-2",
                name="Silver Mountain Water",
                brand="Creed",
                concentration="EDP",
                gender_target="Unisex",
                primary_family="fresh",
                subfamily="citrus",
                data_source="manual",
            )
        )
        await async_session.commit()

        service = FragranceService(async_session)
        params = FragranceSearchParams(brand="Creed")
        results = await service.search(params)

        assert len(results) == 2
        assert all(r.brand == "Creed" for r in results)

    async def test_search_by_family(self, async_session):
        """Test searching fragrances by family."""
        async_session.add(
            Fragrance(
                id="family-1",
                name="Woody One",
                brand="Brand A",
                concentration="EDP",
                gender_target="Unisex",
                primary_family="woody",
                subfamily="aromatic",
                data_source="manual",
            )
        )
        async_session.add(
            Fragrance(
                id="family-2",
                name="Fresh One",
                brand="Brand B",
                concentration="EDT",
                gender_target="Unisex",
                primary_family="fresh",
                subfamily="citrus",
                data_source="manual",
            )
        )
        await async_session.commit()

        service = FragranceService(async_session)
        params = FragranceSearchParams(primary_family="woody")
        results = await service.search(params)

        assert len(results) == 1
        assert results[0].primary_family == "woody"

    async def test_search_by_gender(self, async_session):
        """Test searching fragrances by gender target."""
        async_session.add(
            Fragrance(
                id="gender-1",
                name="For Her",
                brand="Brand",
                concentration="EDP",
                gender_target="Feminine",
                primary_family="floral",
                subfamily="rose",
                data_source="manual",
            )
        )
        async_session.add(
            Fragrance(
                id="gender-2",
                name="For Him",
                brand="Brand",
                concentration="EDT",
                gender_target="Masculine",
                primary_family="woody",
                subfamily="oud",
                data_source="manual",
            )
        )
        await async_session.commit()

        service = FragranceService(async_session)
        params = FragranceSearchParams(gender_target="Feminine")
        results = await service.search(params)

        assert len(results) == 1
        assert results[0].gender_target == "Feminine"

    async def test_search_with_limit(self, async_session):
        """Test search respects limit parameter."""
        # Create multiple fragrances
        for i in range(10):
            async_session.add(
                Fragrance(
                    id=f"limit-{i}",
                    name=f"Limit Test {i}",
                    brand="Brand",
                    concentration="EDP",
                    gender_target="Unisex",
                    primary_family="woody",
                    subfamily="aromatic",
                    data_source="manual",
                )
            )
        await async_session.commit()

        service = FragranceService(async_session)
        params = FragranceSearchParams(limit=5)
        results = await service.search(params)

        assert len(results) == 5

    async def test_search_with_offset(self, async_session):
        """Test search respects offset parameter."""
        for i in range(10):
            async_session.add(
                Fragrance(
                    id=f"offset-{i}",
                    name=f"Offset Test {i:02d}",  # Pad with zeros for consistent ordering
                    brand="Brand",
                    concentration="EDP",
                    gender_target="Unisex",
                    primary_family="woody",
                    subfamily="aromatic",
                    data_source="manual",
                )
            )
        await async_session.commit()

        service = FragranceService(async_session)
        params = FragranceSearchParams(limit=5, offset=5)
        results = await service.search(params)

        assert len(results) == 5

    async def test_update_fragrance(self, async_session):
        """Test updating a fragrance."""
        fragrance = Fragrance(
            id="update-frag-001",
            name="Original Name",
            brand="Original Brand",
            concentration="EDT",
            gender_target="Masculine",
            primary_family="fresh",
            subfamily="citrus",
            data_source="manual",
        )
        async_session.add(fragrance)
        await async_session.commit()

        service = FragranceService(async_session)
        update_data = FragranceUpdate(name="Updated Name", concentration="EDP")
        updated = await service.update("update-frag-001", update_data)
        await async_session.commit()

        assert updated is not None
        assert updated.name == "Updated Name"
        assert updated.concentration == "EDP"
        # Unchanged fields should remain
        assert updated.brand == "Original Brand"

    async def test_update_nonexistent_fragrance(self, async_session):
        """Test updating non-existent fragrance."""
        service = FragranceService(async_session)
        update_data = FragranceUpdate(name="New Name")
        updated = await service.update("nonexistent", update_data)

        assert updated is None

    async def test_delete_fragrance(self, async_session):
        """Test deleting a fragrance."""
        fragrance = Fragrance(
            id="delete-frag-001",
            name="To Delete",
            brand="Brand",
            concentration="EDP",
            gender_target="Unisex",
            primary_family="woody",
            subfamily="aromatic",
            data_source="manual",
        )
        async_session.add(fragrance)
        await async_session.commit()

        service = FragranceService(async_session)
        result = await service.delete("delete-frag-001")
        await async_session.commit()

        assert result is True

        # Verify deleted
        found = await service.get_by_id("delete-frag-001")
        assert found is None

    async def test_delete_nonexistent_fragrance(self, async_session):
        """Test deleting non-existent fragrance."""
        service = FragranceService(async_session)
        result = await service.delete("nonexistent")

        assert result is False

    async def test_search_empty_results(self, async_session):
        """Test search returns empty list when no matches."""
        service = FragranceService(async_session)
        params = FragranceSearchParams(q="NonexistentFragrance123")
        results = await service.search(params)

        assert results == []


@pytest.mark.asyncio
class TestFragranceSoftDelete:
    """Critical finding 2: delete() soft-deletes, never issues a real DELETE."""

    async def test_delete_sets_deleted_at_without_removing_row(self, async_session):
        """The row must survive delete(), only deleted_at is set."""
        from sqlalchemy import select

        fragrance = Fragrance(
            id="soft-delete-frag-001",
            name="Soft Delete Me",
            brand="Brand",
            concentration="EDP",
            gender_target="Unisex",
            primary_family="woody",
            subfamily="aromatic",
            data_source="manual",
        )
        async_session.add(fragrance)
        await async_session.commit()

        service = FragranceService(async_session)
        result = await service.delete("soft-delete-frag-001")
        await async_session.commit()

        assert result is True

        # The row is still physically present in the table.
        raw = await async_session.execute(
            select(Fragrance).where(Fragrance.id == "soft-delete-frag-001")
        )
        row = raw.scalar_one_or_none()
        assert row is not None
        assert row.deleted_at is not None

        # But excluded from get_by_id/search.
        assert await service.get_by_id("soft-delete-frag-001") is None

    async def test_search_excludes_soft_deleted_fragrances(self, async_session):
        """search() must never return a soft-deleted fragrance."""
        fragrance = Fragrance(
            id="soft-delete-frag-002",
            name="Hidden Fragrance",
            brand="Brand",
            concentration="EDP",
            gender_target="Unisex",
            primary_family="woody",
            subfamily="aromatic",
            data_source="manual",
        )
        async_session.add(fragrance)
        await async_session.commit()

        service = FragranceService(async_session)
        await service.delete("soft-delete-frag-002")
        await async_session.commit()

        results = await service.search(FragranceSearchParams(q="Hidden Fragrance"))
        assert results == []


@pytest.mark.asyncio
class TestFragranceDedupPartialUniqueIndex:
    """`uq_fragrance_name_brand` is a partial unique index scoped to live rows.

    Regression coverage for the soft-delete/dedup interaction: a plain
    UniqueConstraint on (name, brand) would let a soft-deleted row block
    recreating/re-scraping the same fragrance forever. See the resolved
    RAD note on `Fragrance.deleted_at`.
    """

    async def test_recreate_after_soft_delete_succeeds(self, async_session):
        """Recreating the same (name, brand) after a soft delete must succeed."""
        from sqlalchemy import select

        original = Fragrance(
            id="dedup-frag-orig",
            name="Reused Name",
            brand="Reused Brand",
            concentration="EDP",
            gender_target="Unisex",
            primary_family="woody",
            subfamily="aromatic",
            data_source="manual",
        )
        async_session.add(original)
        await async_session.commit()

        service = FragranceService(async_session)
        assert await service.delete("dedup-frag-orig") is True
        await async_session.commit()

        recreated = Fragrance(
            id="dedup-frag-new",
            name="Reused Name",
            brand="Reused Brand",
            concentration="EDP",
            gender_target="Unisex",
            primary_family="woody",
            subfamily="aromatic",
            data_source="manual",
        )
        async_session.add(recreated)
        await async_session.commit()  # Must not raise IntegrityError.

        rows = (
            (
                await async_session.execute(
                    select(Fragrance).where(
                        Fragrance.name == "Reused Name",
                        Fragrance.brand == "Reused Brand",
                    )
                )
            )
            .scalars()
            .all()
        )
        assert len(rows) == 2
        live = [r for r in rows if r.deleted_at is None]
        deleted = [r for r in rows if r.deleted_at is not None]
        assert len(live) == 1
        assert len(deleted) == 1
        assert live[0].id == "dedup-frag-new"
        assert deleted[0].id == "dedup-frag-orig"

    async def test_two_live_fragrances_still_reject_duplicate_name_brand(
        self, async_session
    ):
        """Two LIVE fragrances sharing (name, brand) must still be rejected."""
        from sqlalchemy.exc import IntegrityError

        first = Fragrance(
            id="dup-frag-1",
            name="Duplicate Name",
            brand="Duplicate Brand",
            concentration="EDP",
            gender_target="Unisex",
            primary_family="woody",
            subfamily="aromatic",
            data_source="manual",
        )
        async_session.add(first)
        await async_session.commit()

        second = Fragrance(
            id="dup-frag-2",
            name="Duplicate Name",
            brand="Duplicate Brand",
            concentration="EDT",
            gender_target="Unisex",
            primary_family="woody",
            subfamily="aromatic",
            data_source="manual",
        )
        async_session.add(second)
        with pytest.raises(IntegrityError):
            await async_session.commit()
        await async_session.rollback()
