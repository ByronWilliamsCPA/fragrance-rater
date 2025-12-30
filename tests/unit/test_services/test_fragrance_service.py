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
