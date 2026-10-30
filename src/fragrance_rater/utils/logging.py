"""Structured logging configuration using structlog and rich.

Provides JSON-formatted logs for production environments with rich console
output for development. All logs include contextual information for debugging
and monitoring.

Features:
- Rich console output for development
- JSON-formatted logs for production
- Correlation ID support for distributed tracing
- Performance logging helpers

Note: Module named "logging" intentionally shadows stdlib for project-specific
configuration.
"""

import logging
import re
import sys
from typing import TYPE_CHECKING, cast

import structlog
from pydantic import SecretStr
from rich.console import Console
from rich.logging import RichHandler
from structlog.stdlib import BoundLogger

if TYPE_CHECKING:
    from collections.abc import MutableMapping

    from structlog.types import EventDict, Processor, WrappedLogger

# Global console for rich output (stderr for proper output separation)
console = Console(stderr=True)

REDACTED = "[REDACTED]"

# Audit events go through this logger, whose level setup_logging pins at INFO
# or lower so LOG_LEVEL=WARNING cannot silence the audit trail.
AUDIT_LOGGER = "fragrance_rater.audit"

# Whole underscore-separated words, so ``prompt_tokens`` and ``total_tokens``
# (LLM usage counts) survive while ``api_key``, ``x_api_key``,
# ``authorization``, ``csrf_token``, and ``db_password`` are masked.
_SENSITIVE_WORDS = (
    "api[_-]?key|authorization|cookie|credentials?|passw(?:or)?d|secret|token"
)
_SENSITIVE_KEY = re.compile(
    rf"(?:^|[_-])(?:{_SENSITIVE_WORDS})(?:$|[_-])", re.IGNORECASE
)
_URL_PASSWORD = re.compile(r"(?P<scheme>[a-z][a-z0-9+.-]*://[^/:@\s]+):[^@/\s]+@")


def _configured_secrets() -> list[str]:
    """Return the non-empty secret values from settings, longest first."""
    from fragrance_rater.core.config import secret_value, settings  # noqa: PLC0415

    values = {
        secret_value(settings.api_key),
        secret_value(settings.openrouter_api_key),
        secret_value(settings.fragella_api_key),
    }
    # Any configured value is masked, however short; a short key that also
    # masks an ordinary word is the lesser harm.
    return sorted((v for v in values if v), key=len, reverse=True)


def _redact_value(value: object, secrets: list[str]) -> object:
    if isinstance(value, SecretStr):
        return REDACTED
    if isinstance(value, str):
        text = _URL_PASSWORD.sub(rf"\g<scheme>:{REDACTED}@", value)
        for secret in secrets:
            text = text.replace(secret, REDACTED)
        return text
    if isinstance(value, dict):
        mapping = cast("dict[object, object]", value)
        return {
            key: (
                REDACTED
                if isinstance(key, str) and _SENSITIVE_KEY.search(key)
                else _redact_value(item, secrets)
            )
            for key, item in mapping.items()
        }
    if isinstance(value, list | tuple):
        items = cast("list[object] | tuple[object, ...]", value)
        return type(items)(_redact_value(item, secrets) for item in items)
    return value


def redact_secrets(
    _logger: object,
    _method_name: str,
    event_dict: "MutableMapping[str, object]",
) -> "MutableMapping[str, object]":
    """Mask secrets before any renderer sees the event (architecture review S-15).

    Fields whose names mark them as secrets are replaced outright; in every
    other string, the configured key values and URL passwords (for example a
    ``DATABASE_URL``) are masked. Nested dicts and lists are walked.
    """
    secrets = _configured_secrets()
    for key in list(event_dict):
        if _SENSITIVE_KEY.search(key) and event_dict[key] is not None:
            event_dict[key] = REDACTED
        else:
            event_dict[key] = _redact_value(event_dict[key], secrets)
    return event_dict


def setup_logging(
    level: str = "INFO",
    json_logs: bool = False,
    include_timestamp: bool = True,
    include_correlation: bool = True,
) -> None:
    """Configure structured logging for the application.

    Sets up both standard logging and structlog with appropriate handlers
    for the environment (JSON for production, rich console for development).

    Args:
        level (str): Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL).
            Defaults to INFO.
        json_logs (bool): If True, output JSON logs (production mode). If False,
            use rich console formatting (development mode). Defaults to False.
        include_timestamp (bool): Whether to include timestamps in log output.
            Defaults to True.
        include_correlation (bool): Whether to include correlation IDs from request
            context in log output. Defaults to True. Requires API framework.

    Example:
        >>> # Development setup
        >>> setup_logging(level="DEBUG", json_logs=False)

        >>> # Production setup with correlation
        >>> setup_logging(level="INFO", json_logs=True, include_correlation=True)
    """
    log_level = getattr(logging, level.upper(), logging.INFO)
    # #CRITICAL: security: audit events must survive any LOG_LEVEL. Records
    # from the audit logger still reach the root handlers, which have no level
    # of their own.
    # #VERIFY: tests/unit/test_logging.py renders an audit event at WARNING.
    logging.getLogger(AUDIT_LOGGER).setLevel(min(log_level, logging.INFO))

    # Configure standard Python logging
    logging.basicConfig(
        format="%(message)s",
        level=log_level,
        handlers=[
            (
                RichHandler(
                    console=console,
                    rich_tracebacks=True,
                    show_time=include_timestamp,
                    show_level=True,
                    show_path=True,
                )
                if not json_logs
                else logging.StreamHandler(sys.stdout)
            )
        ],
    )

    # Define a no-op processor for when timestamp is disabled
    def noop_processor(
        _logger: "WrappedLogger",
        _method_name: str,
        event_dict: "EventDict",
    ) -> "EventDict":
        """No-op processor that passes through the event dict unchanged."""
        return event_dict

    # Configure structlog processors
    processors: list[Processor] = [
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        (
            structlog.processors.TimeStamper(fmt="iso")
            if include_timestamp
            else noop_processor
        ),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        # Last before the renderer, so exception text is scrubbed too.
        redact_secrets,
    ]

    # Add correlation ID processor for request tracing
    if include_correlation:
        try:
            from fragrance_rater.middleware.correlation import (  # noqa: PLC0415
                correlation_context_processor,
            )

            # Insert after add_log_level for consistent ordering
            processors.insert(3, correlation_context_processor)
        except ImportError:
            # Correlation middleware not available, skip
            pass

    if json_logs:
        # Production: JSON logs for easy parsing and aggregation
        processors.append(structlog.processors.JSONRenderer())
    else:
        # Development: Rich console output with colors and formatting
        processors.append(structlog.dev.ConsoleRenderer(colors=True))

    structlog.configure(
        processors=processors,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str) -> BoundLogger:
    """Get a structured logger instance.

    Creates or retrieves a structlog logger with the given name. This should
    typically be called with __name__ to create module-specific loggers.

    Args:
        name (str): Logger name (typically __name__ of the module).

    Returns:
        BoundLogger: Configured structlog logger instance.

    Example:
        >>> logger = get_logger(__name__)
        >>> logger.info("Processing started", document_id="doc_001")
        >>> logger.warning("Low confidence", confidence=0.45, threshold=0.5)
        >>> logger.error("Processing failed", error="file_not_found")
    """
    # Cast to BoundLogger for type checking - structlog.get_logger returns
    # a BoundLogger when configured with stdlib LoggerFactory
    result: BoundLogger = structlog.get_logger(name)  # pyright: ignore[reportAssignmentType]
    return result


def log_audit_event(
    _logger: BoundLogger,
    *,
    action: str,
    actor: str | None,
    target_type: str,
    target_id: str,
    **extra: object,
) -> None:
    """Log a structured audit event for a mutating action on a tracked entity.

    Critical finding 2: destructive/mutating endpoints on fragrances,
    evaluations, and reviewers previously had no audit trail. This helper
    gives every one of those routes one consistent audit log shape: who did
    what to which entity, with the request's correlation id attached so a
    soft-delete (or any other mutation) can be traced back to both the
    acting identity and the specific request that caused it.

    The event is written through the ``fragrance_rater.audit`` logger, so it
    is kept whatever LOG_LEVEL says (B-03).

    Args:
        _logger (BoundLogger): The calling module's logger. Unused since audit
            events moved to the audit logger; kept so call sites are unchanged.
        action (str): The action performed, e.g. "create", "update",
            "soft_delete".
        actor (str | None): The acting identity's username (from the
            Authentik forward-auth dependency), or None when no Authentik
            identity is available (local dev/tests/seeded data).
        target_type (str): The entity type acted upon, e.g. "fragrance".
        target_id (str): The id of the entity acted upon.
        **extra (object): Additional context fields to include.

    Example:
        >>> logger = get_logger(__name__)
        >>> log_audit_event(
        ...     logger,
        ...     action="soft_delete",
        ...     actor="byron",
        ...     target_type="fragrance",
        ...     target_id="abc-123",
        ... )
    """
    # #CRITICAL: security: this is the audit trail for every mutating
    # request on fragrances/evaluations/reviewers (Critical finding 2). Do
    # not wrap this in a try/except that swallows failures; a mutation that
    # was not audited should be visible, not silently lost.
    # #VERIFY: correlation_id is read directly from request context here
    # rather than relying solely on structlog's correlation_context_processor,
    # since that processor only runs when setup_logging() was called with
    # include_correlation=True in this process (true for the API server and
    # the test suite, not guaranteed for every entry point e.g. the CLI).
    from fragrance_rater.middleware.correlation import (  # noqa: PLC0415
        get_correlation_id,
    )

    get_logger(AUDIT_LOGGER).info(
        "audit_event",
        action=action,
        actor=actor,
        target_type=target_type,
        target_id=target_id,
        correlation_id=get_correlation_id(),
        **extra,
    )


def log_performance(
    logger: BoundLogger,
    operation: str,
    duration_ms: float,
    success: bool = True,
    **context: object,
) -> None:
    """Log performance metrics for an operation.

    Provides a standardized way to log performance data with operation name,
    duration, success status, and additional context.

    Args:
        logger (BoundLogger): Structlog logger instance from get_logger().
        operation (str): Name of the operation being timed.
        duration_ms (float): Duration in milliseconds.
        success (bool): Whether the operation succeeded. Defaults to True.
        **context (object): Additional context key-value pairs to include in the log.

    Example:
        >>> logger = get_logger(__name__)
        >>> log_performance(
        ...     logger,
        ...     operation="image_processing",
        ...     duration_ms=42.5,
        ...     success=True,
        ...     image_count=10,
        ...     output_dir="/results",
        ... )
    """
    logger.info(
        "performance",
        operation=operation,
        duration_ms=round(duration_ms, 2),
        success=success,
        **context,
    )


# Example usage and testing
if __name__ == "__main__":
    # Setup for development (rich console)
    setup_logging(level="DEBUG", json_logs=False)

    logger = get_logger(__name__)

    logger.debug("Debug message", extra_field="debug_value")
    logger.info("Processing started", document_id="doc_001", pages=10)
    logger.warning("Low confidence detection", confidence=0.42, threshold=0.5)
    logger.error("Failed to process", error="file_not_found", path="./missing.pdf")

    log_performance(
        logger,
        operation="image_quality_assessment",
        duration_ms=15.3,
        success=True,
        model="resnet18",
    )

    # Example of structured error logging
    def _raise_example_error() -> None:
        """Helper function to demonstrate error logging."""
        error_msg = "Example error for demonstration"
        raise ValueError(error_msg)

    try:
        _raise_example_error()
    except Exception:
        logger.exception("Unexpected error during processing")
