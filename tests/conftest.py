"""Pytest configuration and shared fixtures for Fragrance Rater tests.

This module provides:
- Test fixture paths and directories
- Pytest markers for test categorization
- Shared fixtures for common test resources
- Temporary directory management
- Database fixtures for integration tests
"""

from collections.abc import AsyncGenerator, Generator
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio
from sqlalchemy import StaticPool, create_engine
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import Session, sessionmaker

from fragrance_rater.core.database import Base

# ============================================================================
# Test Fixture Paths
# ============================================================================

# Root paths
PROJECT_ROOT = Path(__file__).parent.parent
FIXTURES_DIR = PROJECT_ROOT / "data" / "test_fixtures"
BENCHMARKS_DIR = PROJECT_ROOT / "data" / "benchmarks"


# ============================================================================
# Pytest Markers
# ============================================================================


def pytest_configure(config: pytest.Config) -> None:
    """Register custom pytest markers for test pyramid.

    Test Pyramid Markers:
        unit: Fast, isolated tests (no external dependencies)
        integration: Tests verifying component interaction
        security: Security-focused assertion tests
        perf: Performance and load tests
        slow: Tests that take significant time

    Args:
        config: Pytest configuration object.
    """
    # Test type markers (for test pyramid)
    config.addinivalue_line(
        "markers",
        "unit: Unit tests (fast, isolated, no external dependencies)",
    )
    config.addinivalue_line(
        "markers",
        "integration: Integration tests (moderate speed, may use fixtures)",
    )
    config.addinivalue_line(
        "markers",
        "security: Security-focused tests (auth, input validation, etc.)",
    )
    config.addinivalue_line(
        "markers",
        "perf: Performance and load tests (benchmarking, stress testing)",
    )
    config.addinivalue_line(
        "markers",
        "performance: Alias for perf marker",
    )

    # Execution modifier markers
    config.addinivalue_line(
        "markers",
        "slow: Slow tests (can be excluded with -m 'not slow')",
    )
    config.addinivalue_line(
        "markers",
        "smoke: Smoke tests for quick sanity checks",
    )
    config.addinivalue_line(
        "markers",
        "regression: Regression tests for previously fixed bugs",
    )


# ============================================================================
# Fixture Directory Fixtures
# ============================================================================


@pytest.fixture(scope="session")
def fixtures_dir() -> Path:
    """Return path to test fixtures directory.

    Returns:
        Path object pointing to the test fixtures directory.
    """
    return FIXTURES_DIR


@pytest.fixture(scope="session")
def benchmarks_dir() -> Path:
    """Return path to benchmarks directory.

    Returns:
        Path object pointing to the benchmarks directory.
    """
    return BENCHMARKS_DIR


# ============================================================================
# Temporary Directory Fixtures
# ============================================================================


@pytest.fixture
def tmp_output_dir(tmp_path: Path) -> Path:
    """Return temporary directory for test outputs.

    Creates and returns a clean temporary directory for each test to write
    output files.

    Args:
        tmp_path: Pytest's built-in tmp_path fixture.

    Returns:
        Path object pointing to the temporary output directory.
    """
    output_dir = tmp_path / "output"
    output_dir.mkdir(exist_ok=True)
    return output_dir


@pytest.fixture
def tmp_cache_dir(tmp_path: Path) -> Path:
    """Return temporary directory for caching.

    Creates and returns a clean temporary cache directory for each test.

    Args:
        tmp_path: Pytest's built-in tmp_path fixture.

    Returns:
        Path object pointing to the temporary cache directory.
    """
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir(exist_ok=True)
    return cache_dir


# ============================================================================
# Logging Fixtures
# ============================================================================


@pytest.fixture(autouse=True)
def setup_logging() -> None:
    """Setup test logging configuration.

    Automatically applied to all tests to ensure consistent logging setup.
    """
    from fragrance_rater.utils.logging import setup_logging

    setup_logging(level="DEBUG", json_logs=False, include_timestamp=False)


# ============================================================================
# Database Fixtures
# ============================================================================

# SQLite URL for async testing
ASYNC_SQLITE_URL = "sqlite+aiosqlite:///:memory:"
SYNC_SQLITE_URL = "sqlite:///:memory:"


@pytest_asyncio.fixture(scope="function")
async def async_engine():
    """Create async SQLite engine for testing."""
    engine = create_async_engine(
        ASYNC_SQLITE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def async_session(async_engine) -> AsyncGenerator[AsyncSession, None]:
    """Create async session for testing."""
    async_session_maker = async_sessionmaker(
        async_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    async with async_session_maker() as session:
        yield session


@pytest.fixture(scope="function")
def sync_engine():
    """Create sync SQLite engine for testing."""
    engine = create_engine(
        SYNC_SQLITE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


@pytest.fixture(scope="function")
def sync_session(sync_engine) -> Generator[Session, None, None]:
    """Create sync session for testing."""
    session_maker = sessionmaker(bind=sync_engine, expire_on_commit=False)
    session = session_maker()
    yield session
    session.close()


# ============================================================================
# Model Fixtures
# ============================================================================


@pytest.fixture
def sample_fragrance_data() -> dict[str, Any]:
    """Return sample fragrance data for testing."""
    return {
        "id": "test-fragrance-001",
        "name": "Test Fragrance",
        "brand": "Test Brand",
        "concentration": "EDP",
        "launch_year": 2024,
        "gender_target": "unisex",
        "primary_family": "woody",
        "subfamily": "aromatic",
        "data_source": "manual",
    }


@pytest.fixture
def sample_reviewer_data() -> dict[str, Any]:
    """Return sample reviewer data for testing."""
    return {
        "id": "test-reviewer-001",
        "name": "Test Reviewer",
    }


@pytest.fixture
def sample_evaluation_data() -> dict[str, Any]:
    """Return sample evaluation data for testing."""
    return {
        "id": "test-eval-001",
        "fragrance_id": "test-fragrance-001",
        "reviewer_id": "test-reviewer-001",
        "rating": 4,
        "notes": "Great fragrance!",
    }


@pytest.fixture
def sample_note_data() -> dict[str, Any]:
    """Return sample note data for testing."""
    return {
        "id": "test-note-001",
        "name": "Bergamot",
        "category": "citrus",
    }


# ============================================================================
# Mock Fixtures
# ============================================================================


@pytest.fixture
def mock_httpx_client() -> MagicMock:
    """Create a mock httpx client for testing scrapers."""
    client = MagicMock()
    response = MagicMock()
    response.status_code = 200
    response.text = "<html><body>Mock response</body></html>"
    client.get.return_value = response
    client.__enter__ = MagicMock(return_value=client)
    client.__exit__ = MagicMock(return_value=False)
    return client


@pytest.fixture
def mock_openrouter_response() -> dict[str, Any]:
    """Return mock OpenRouter API response."""
    return {
        "choices": [
            {
                "message": {
                    "content": "This is a mock LLM response for testing."
                }
            }
        ],
        "model": "anthropic/claude-3-haiku",
    }


# ============================================================================
# API Testing Fixtures
# ============================================================================


@pytest_asyncio.fixture
async def test_app(tmp_path):
    """Create a FastAPI test app with database override using a temp file."""
    import os

    from httpx import ASGITransport, AsyncClient

    from fragrance_rater.core.database import get_db
    from fragrance_rater.main import app

    # Clear any existing overrides from previous tests
    app.dependency_overrides.clear()

    # Create a unique database file for each test
    db_path = tmp_path / "test.db"
    db_url = f"sqlite+aiosqlite:///{db_path}"

    engine = create_async_engine(
        db_url,
        connect_args={"check_same_thread": False},
    )

    # Create all tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        async_session_maker = async_sessionmaker(
            engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )
        async with async_session_maker() as session:
            yield session
            await session.commit()

    app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=app)  # type: ignore[arg-type]
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client

    app.dependency_overrides.clear()

    # Cleanup
    await engine.dispose()
    if os.path.exists(db_path):
        os.remove(db_path)
