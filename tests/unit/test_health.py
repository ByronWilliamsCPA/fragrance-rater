"""Tests for health probe endpoints.

This module provides comprehensive tests for the health check endpoints
covering:
- Liveness probe endpoint (/health/live)
- Readiness probe endpoint (/health/ready)
- Startup probe endpoint (/health/startup)
- Basic health alias endpoint (/health/)
- check_database dependency probe (ImportError and success branches)
- Pydantic response models (HealthStatus, ReadinessCheck, ReadinessStatus)
"""

from __future__ import annotations

import sys
from collections.abc import AsyncIterator, Callable
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from types import ModuleType
from typing import cast

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

GetSession = Callable[[], AbstractAsyncContextManager[object]]


class _FakeDatabaseModule(ModuleType):
    """Typed stand-in for ``fragrance_rater.core.database`` in tests."""

    def __init__(self, name: str, get_session: GetSession) -> None:
        super().__init__(name)
        self.get_session: GetSession = get_session


def _make_db_module(get_session: GetSession) -> _FakeDatabaseModule:
    """Build a fake database module exposing ``get_session``."""
    return _FakeDatabaseModule("fragrance_rater.core.database", get_session)


def _build_client() -> TestClient:
    """Mount the health router on a fresh FastAPI app and return a TestClient."""
    from fragrance_rater.api.health import router

    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def _json(client: TestClient, path: str) -> tuple[int, dict[str, object]]:
    """Issue a GET and return ``(status_code, parsed_json)`` typed as a dict."""
    response = client.get(path)
    return response.status_code, cast("dict[str, object]", response.json())


class TestLivenessEndpoint:
    """Tests for the /health/live endpoint."""

    @pytest.mark.unit
    def test_liveness_returns_200(self) -> None:
        """Liveness probe returns HTTP 200."""
        client = _build_client()

        status_code, _ = _json(client, "/health/live")

        assert status_code == 200

    @pytest.mark.unit
    def test_liveness_response_shape(self) -> None:
        """Liveness response contains expected HealthStatus fields."""
        client = _build_client()

        _, body = _json(client, "/health/live")

        assert body["status"] == "ok"
        assert cast("float", body["uptime_seconds"]) >= 0
        assert body["version"] == "0.1.0"
        assert body["python_version"] == sys.version.split()[0]
        assert isinstance(body["timestamp"], (int, float))


class TestStartupEndpoint:
    """Tests for the /health/startup endpoint."""

    @pytest.mark.unit
    def test_startup_returns_200_and_started(self) -> None:
        """Startup probe returns HTTP 200 with status=started."""
        client = _build_client()

        status_code, body = _json(client, "/health/startup")

        assert status_code == 200
        assert body["status"] == "started"
        assert cast("float", body["uptime_seconds"]) >= 0


class TestHealthAliasEndpoint:
    """Tests for the /health/ alias endpoint."""

    @pytest.mark.unit
    def test_health_alias_delegates_to_liveness(self) -> None:
        """Basic /health/ endpoint returns same shape as liveness."""
        client = _build_client()

        status_code, body = _json(client, "/health/")

        assert status_code == 200
        assert body["status"] == "ok"
        assert cast("float", body["uptime_seconds"]) >= 0
        assert body["version"] == "0.1.0"


class TestReadinessEndpoint:
    """Tests for the /health/ready endpoint."""

    @pytest.mark.unit
    def test_readiness_returns_503_when_database_unavailable(self) -> None:
        """Readiness returns 503 when database module is absent."""
        # The fragrance_rater.core.database module is genuinely absent,
        # so check_database hits the ImportError branch and returns unhealthy.
        client = _build_client()

        status_code, body = _json(client, "/health/ready")
        detail = cast("dict[str, object]", body["detail"])
        checks = cast("dict[str, dict[str, object]]", detail["checks"])

        assert status_code == 503
        assert detail["status"] == "unavailable"
        assert "database" in checks
        assert checks["database"]["status"] is False
        assert checks["database"]["error"] == "database module not yet implemented"

    @pytest.mark.unit
    def test_readiness_returns_200_when_database_healthy(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Readiness returns 200 with all checks passing when DB is healthy."""

        class _FakeSession:
            async def execute(self, _query: str) -> None:
                return None

        @asynccontextmanager
        async def _fake_get_session() -> AsyncIterator[_FakeSession]:
            yield _FakeSession()

        monkeypatch.setitem(
            sys.modules,
            "fragrance_rater.core.database",
            _make_db_module(_fake_get_session),
        )

        client = _build_client()
        status_code, body = _json(client, "/health/ready")
        checks = cast("dict[str, dict[str, object]]", body["checks"])

        assert status_code == 200
        assert body["status"] == "ok"
        assert cast("float", body["uptime_seconds"]) >= 0
        assert checks["database"]["status"] is True
        assert checks["database"]["name"] == "database"
        assert checks["database"]["latency_ms"] is not None


class TestCheckDatabase:
    """Tests for the check_database dependency probe."""

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_check_database_import_error_branch(self) -> None:
        """check_database returns failed ReadinessCheck when module missing."""
        from fragrance_rater.api.health import check_database

        result = await check_database()

        assert result.name == "database"
        assert result.status is False
        assert result.latency_ms is None
        assert result.error == "database module not yet implemented"

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_check_database_success_branch(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """check_database returns healthy ReadinessCheck on successful query."""
        from fragrance_rater.api.health import check_database

        class _FakeSession:
            async def execute(self, _query: str) -> None:
                return None

        @asynccontextmanager
        async def _fake_get_session() -> AsyncIterator[_FakeSession]:
            yield _FakeSession()

        monkeypatch.setitem(
            sys.modules,
            "fragrance_rater.core.database",
            _make_db_module(_fake_get_session),
        )

        result = await check_database()

        assert result.name == "database"
        assert result.status is True
        assert result.error is None
        assert result.latency_ms is not None
        assert result.latency_ms >= 0

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_check_database_exception_branch(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """check_database returns failed ReadinessCheck when query raises."""
        from fragrance_rater.api.health import check_database

        class _BrokenContext:
            async def __aenter__(self) -> object:
                raise RuntimeError("connection refused")

            async def __aexit__(self, *_exc: object) -> None:
                return None

        def _broken_get_session() -> AbstractAsyncContextManager[object]:
            return _BrokenContext()

        monkeypatch.setitem(
            sys.modules,
            "fragrance_rater.core.database",
            _make_db_module(_broken_get_session),
        )

        result = await check_database()

        assert result.name == "database"
        assert result.status is False
        assert result.error == "connection refused"
        assert result.latency_ms is not None


class TestCheckCache:
    """Tests for the check_cache placeholder probe."""

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_check_cache_returns_healthy_placeholder(self) -> None:
        """check_cache placeholder returns a healthy ReadinessCheck."""
        from fragrance_rater.api.health import check_cache

        result = await check_cache()

        assert result.name == "cache"
        assert result.status is True
        assert result.latency_ms is not None


class TestCheckExternalService:
    """Tests for the check_external_service placeholder probe."""

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_check_external_service_returns_healthy_placeholder(self) -> None:
        """check_external_service placeholder returns a healthy ReadinessCheck."""
        from fragrance_rater.api.health import check_external_service

        result = await check_external_service()

        assert result.name == "external_api"
        assert result.status is True
        assert result.latency_ms is not None


class TestPydanticModels:
    """Tests for HealthStatus, ReadinessCheck, and ReadinessStatus models."""

    @pytest.mark.unit
    def test_health_status_required_fields(self) -> None:
        """HealthStatus requires status and uptime_seconds; defaults apply."""
        from fragrance_rater.api.health import HealthStatus

        model = HealthStatus(status="ok", uptime_seconds=12.5)
        dumped = model.model_dump()

        assert dumped["status"] == "ok"
        assert dumped["uptime_seconds"] == 12.5
        assert dumped["version"] == "0.1.0"
        assert dumped["python_version"] == sys.version.split()[0]
        assert isinstance(dumped["timestamp"], float)

    @pytest.mark.unit
    def test_readiness_check_minimal_fields(self) -> None:
        """ReadinessCheck accepts minimal name+status; defaults to None elsewhere."""
        from fragrance_rater.api.health import ReadinessCheck

        check = ReadinessCheck(name="database", status=True)
        dumped = check.model_dump()

        assert dumped["name"] == "database"
        assert dumped["status"] is True
        assert dumped["latency_ms"] is None
        assert dumped["error"] is None

    @pytest.mark.unit
    def test_readiness_check_full_fields(self) -> None:
        """ReadinessCheck accepts optional latency_ms and error fields."""
        from fragrance_rater.api.health import ReadinessCheck

        check = ReadinessCheck(
            name="cache",
            status=False,
            latency_ms=42.5,
            error="connection timeout",
        )

        assert check.latency_ms == 42.5
        assert check.error == "connection timeout"

    @pytest.mark.unit
    def test_readiness_status_inherits_health_fields(self) -> None:
        """ReadinessStatus inherits HealthStatus fields and adds checks."""
        from fragrance_rater.api.health import ReadinessCheck, ReadinessStatus

        ready = ReadinessStatus(
            status="ok",
            uptime_seconds=1.0,
            checks={"database": ReadinessCheck(name="database", status=True)},
        )
        dumped = ready.model_dump()
        checks = cast("dict[str, dict[str, object]]", dumped["checks"])

        assert dumped["status"] == "ok"
        assert dumped["uptime_seconds"] == 1.0
        assert checks["database"]["name"] == "database"
        assert checks["database"]["status"] is True

    @pytest.mark.unit
    def test_readiness_status_default_checks_empty(self) -> None:
        """ReadinessStatus defaults checks to an empty dict."""
        from fragrance_rater.api.health import ReadinessStatus

        ready = ReadinessStatus(status="ok", uptime_seconds=0.0)

        assert ready.checks == {}


class TestRouterConfiguration:
    """Tests for router-level configuration."""

    @pytest.mark.unit
    def test_router_prefix_and_tags(self) -> None:
        """Router is mounted under /health with the health tag."""
        from fragrance_rater.api.health import router

        assert router.prefix == "/health"
        assert "health" in router.tags

    @pytest.mark.unit
    def test_router_registers_expected_routes(self) -> None:
        """Router exposes live, ready, startup, and root paths."""
        from fragrance_rater.api.health import router

        paths = {getattr(route, "path", None) for route in router.routes}

        assert "/health/live" in paths
        assert "/health/ready" in paths
        assert "/health/startup" in paths
        assert "/health/" in paths
