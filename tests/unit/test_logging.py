"""Tests for structured logging helpers, including the audit event helper.

Critical finding 2: every mutating API route on fragrances, evaluations,
and reviewers now calls log_audit_event(). These tests verify the log
event actually fires with the expected shape.
"""

from __future__ import annotations

import structlog

from fragrance_rater.utils.logging import get_logger, log_audit_event


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
