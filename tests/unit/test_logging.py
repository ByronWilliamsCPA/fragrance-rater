"""Tests for structured logging helpers, including the audit event helper.

Critical finding 2: every mutating API route on fragrances, evaluations,
and reviewers now calls log_audit_event(). These tests verify the log
event actually fires with the expected shape.
"""

from __future__ import annotations

import io
import json
import logging
from typing import TYPE_CHECKING

import pytest
import structlog
from pydantic import SecretStr

from fragrance_rater.core.config import Settings, secret_value, settings
from fragrance_rater.middleware.correlation import set_correlation_id
from fragrance_rater.utils.logging import (
    AUDIT_LOGGER,
    REDACTED,
    get_logger,
    log_audit_event,
    setup_logging,
)

if TYPE_CHECKING:
    from collections.abc import Iterator


class TestLogAuditEvent:
    """Tests for log_audit_event."""

    def test_logs_expected_fields(self) -> None:
        """The audit event must carry action, actor, target, and correlation_id."""
        logger = get_logger(__name__)

        with structlog.testing.capture_logs() as captured:
            log_audit_event(
                logger,
                action="soft_delete",
                actor="byron",
                target_type="fragrance",
                target_id="frag-123",
            )

        assert len(captured) == 1
        event = captured[0]
        assert event["event"] == "audit_event"
        assert event["action"] == "soft_delete"
        assert event["actor"] == "byron"
        assert event["target_type"] == "fragrance"
        assert event["target_id"] == "frag-123"
        assert "correlation_id" in event

    def test_logs_none_actor_when_no_authentik_identity(self) -> None:
        """actor is None when no Authentik identity is available."""
        logger = get_logger(__name__)

        with structlog.testing.capture_logs() as captured:
            log_audit_event(
                logger,
                action="create",
                actor=None,
                target_type="reviewer",
                target_id="rev-456",
            )

        assert captured[0]["actor"] is None

    def test_extra_fields_are_included(self) -> None:
        """Additional context kwargs pass through into the log event."""
        logger = get_logger(__name__)

        with structlog.testing.capture_logs() as captured:
            log_audit_event(
                logger,
                action="create",
                actor="byron",
                target_type="evaluation",
                target_id="eval-789",
                reviewer_id="rev-1",
                fragrance_id="frag-1",
            )

        event = captured[0]
        assert event["reviewer_id"] == "rev-1"
        assert event["fragrance_id"] == "frag-1"


@pytest.fixture(params=["INFO"])
def json_records(
    request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch
) -> Iterator[io.StringIO]:
    """Configure logging as production does and capture the rendered lines."""
    level: str = request.param
    root = logging.getLogger()
    audit = logging.getLogger(AUDIT_LOGGER)
    saved = (root.level, list(root.handlers), audit.level)
    stream = io.StringIO()
    setup_logging(level=level, json_logs=True, include_correlation=True)
    # basicConfig is a no-op under pytest's own root handlers, so attach the
    # capture stream directly; the rendering is structlog's either way.
    root.addHandler(logging.StreamHandler(stream))
    root.setLevel(getattr(logging, level))
    monkeypatch.setattr(
        settings, "openrouter_api_key", SecretStr("sk-or-very-secret-key")
    )
    try:
        yield stream
    finally:
        structlog.reset_defaults()
        root.handlers[:] = saved[1]
        root.setLevel(saved[0])
        audit.setLevel(saved[2])


def _lines(stream: io.StringIO) -> list[dict[str, object]]:
    return [json.loads(line) for line in stream.getvalue().splitlines() if line]


class TestProductionLogging:
    """S-07 and S-15: the configured pipeline, not just the helpers."""

    def test_json_record_carries_the_correlation_id(
        self, json_records: io.StringIO
    ) -> None:
        set_correlation_id("corr-s07")
        try:
            structlog.get_logger("s07").info("hello")
        finally:
            set_correlation_id("")

        (record,) = _lines(json_records)
        assert record["event"] == "hello"
        assert record["correlation_id"] == "corr-s07"
        assert record["level"] == "info"

    def test_secrets_are_redacted_before_rendering(
        self, json_records: io.StringIO
    ) -> None:
        structlog.get_logger("s15").info(
            "call failed: Bearer sk-or-very-secret-key rejected",
            api_key="household-key-value",
            headers={"Authorization": "Bearer abc", "Accept": "json"},
            database_url="postgresql+asyncpg://fr:hunter2@db/fr",
            prompt_tokens=12,
            secret_value=SecretStr("never-shown"),
        )

        rendered = json_records.getvalue()
        for secret in (
            "sk-or-very-secret-key",
            "household-key-value",
            "hunter2",
            "abc",
        ):
            assert secret not in rendered
        assert "never-shown" not in rendered
        (record,) = _lines(json_records)
        assert record["api_key"] == REDACTED
        assert record["headers"] == {"Authorization": REDACTED, "Accept": "json"}
        assert record["database_url"] == f"postgresql+asyncpg://fr:{REDACTED}@db/fr"
        # Usage counts are not secrets just because they say "tokens".
        assert record["prompt_tokens"] == 12

    @pytest.mark.parametrize("json_records", ["WARNING"], indirect=True)
    def test_audit_events_survive_a_warning_log_level(
        self, json_records: io.StringIO
    ) -> None:
        """B-03: LOG_LEVEL=WARNING drops ordinary INFO, never the audit trail."""
        caller = structlog.get_logger("fragrance_rater.api.calibration")
        caller.info("ordinary_info")
        log_audit_event(
            caller,
            action="reveal",
            actor="manager",
            target_type="calibration_enrollment",
            target_id="enr-1",
        )

        (record,) = _lines(json_records)
        assert record["event"] == "audit_event"
        assert record["action"] == "reveal"
        assert record["logger"] == AUDIT_LOGGER

    def test_short_configured_key_is_redacted(
        self, json_records: io.StringIO, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(settings, "api_key", SecretStr("k3y"))
        structlog.get_logger("s15").info("rejected header k3y")

        (record,) = _lines(json_records)
        assert record["event"] == f"rejected header {REDACTED}"


class TestSecretSettings:
    """S-15: keys are SecretStr, so dumps and reprs never show them."""

    def test_keys_are_masked_in_repr_and_dump(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("FRAGRANCE_RATER_API_KEY", "household-key-value")
        monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-very-secret-key")
        configured = Settings()

        assert isinstance(configured.api_key, SecretStr)
        assert isinstance(configured.openrouter_api_key, SecretStr)
        assert isinstance(configured.fragella_api_key, SecretStr)
        for text in (repr(configured), str(configured.model_dump())):
            assert "household-key-value" not in text
            assert "sk-or-very-secret-key" not in text
        assert secret_value(configured.api_key) == "household-key-value"
        assert secret_value(None) == ""
        assert secret_value("plain") == "plain"


@pytest.mark.asyncio
async def test_lifespan_configures_logging_from_settings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """S-07: starting the app applies LOG_LEVEL and JSON_LOGS."""
    from fragrance_rater import main

    calls: list[dict[str, object]] = []
    monkeypatch.setattr(main, "setup_logging", lambda **kwargs: calls.append(kwargs))
    monkeypatch.setattr(settings, "log_level", "WARNING")
    monkeypatch.setattr(settings, "json_logs", True)

    async with main.lifespan(main.app):
        pass

    assert calls == [
        {"level": "WARNING", "json_logs": True, "include_correlation": True}
    ]
