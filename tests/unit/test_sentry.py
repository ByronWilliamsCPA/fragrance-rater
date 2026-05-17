"""Tests for Sentry error tracking integration.

This module provides comprehensive tests for the Sentry init module covering:
- init_sentry happy path with mocked sentry_sdk
- DSN env-var fallback and skip-when-missing behavior
- Environment and release env-var fallbacks
- Tracing and profiling disable flags
- _get_release_version git SHA, package version, and fallback paths
- before_send_hook event filtering and PII scrubbing
- before_breadcrumb_hook query filtering
"""

from __future__ import annotations

import subprocess
from importlib.metadata import PackageNotFoundError
from typing import TYPE_CHECKING, Any, cast
from unittest.mock import MagicMock, patch

import pytest

if TYPE_CHECKING:
    from sentry_sdk.types import Breadcrumb, BreadcrumbHint, Event, Hint


class TestInitSentry:
    """Tests for init_sentry function."""

    @pytest.mark.unit
    def test_init_sentry_skips_when_no_dsn(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Verify init_sentry returns early when DSN is not set."""
        monkeypatch.delenv("SENTRY_DSN", raising=False)

        with patch("fragrance_rater.core.sentry.sentry_sdk.init") as mock_init:
            from fragrance_rater.core.sentry import init_sentry

            init_sentry()

            mock_init.assert_not_called()

    @pytest.mark.unit
    def test_init_sentry_happy_path_with_explicit_dsn(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Verify init_sentry calls sentry_sdk.init with expected kwargs."""
        monkeypatch.delenv("SENTRY_DSN", raising=False)
        monkeypatch.delenv("SENTRY_ENVIRONMENT", raising=False)
        monkeypatch.delenv("ENVIRONMENT", raising=False)
        monkeypatch.delenv("SENTRY_RELEASE", raising=False)

        with (
            patch("fragrance_rater.core.sentry.sentry_sdk.init") as mock_init,
            patch(
                "fragrance_rater.core.sentry._get_release_version",
                return_value="fragrance_rater@abc123",
            ),
        ):
            from fragrance_rater.core.sentry import init_sentry

            init_sentry(
                dsn="https://test@sentry.io/1",
                environment="production",
                release="my-release",
                traces_sample_rate=0.5,
                profiles_sample_rate=0.3,
            )

            mock_init.assert_called_once()
            kwargs = mock_init.call_args.kwargs
            assert kwargs["dsn"] == "https://test@sentry.io/1"
            assert kwargs["environment"] == "production"
            assert kwargs["release"] == "my-release"
            assert kwargs["traces_sample_rate"] == 0.5
            assert kwargs["profiles_sample_rate"] == 0.3
            assert kwargs["sample_rate"] == 1.0
            assert kwargs["attach_stacktrace"] is True
            assert kwargs["send_default_pii"] is False
            assert callable(kwargs["before_send"])
            assert callable(kwargs["before_breadcrumb"])
            assert len(kwargs["integrations"]) == 4

    @pytest.mark.unit
    def test_init_sentry_uses_sentry_dsn_env_var(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Verify init_sentry falls back to SENTRY_DSN env var."""
        monkeypatch.setenv("SENTRY_DSN", "https://env@sentry.io/2")
        monkeypatch.delenv("SENTRY_ENVIRONMENT", raising=False)
        monkeypatch.delenv("ENVIRONMENT", raising=False)
        monkeypatch.delenv("SENTRY_RELEASE", raising=False)

        with (
            patch("fragrance_rater.core.sentry.sentry_sdk.init") as mock_init,
            patch(
                "fragrance_rater.core.sentry._get_release_version",
                return_value="fragrance_rater@xyz",
            ),
        ):
            from fragrance_rater.core.sentry import init_sentry

            init_sentry()

            mock_init.assert_called_once()
            kwargs = mock_init.call_args.kwargs
            assert kwargs["dsn"] == "https://env@sentry.io/2"
            assert kwargs["environment"] == "development"

    @pytest.mark.unit
    def test_init_sentry_uses_sentry_environment_env_var(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Verify init_sentry falls back to SENTRY_ENVIRONMENT env var."""
        monkeypatch.setenv("SENTRY_DSN", "https://env@sentry.io/2")
        monkeypatch.setenv("SENTRY_ENVIRONMENT", "staging")
        monkeypatch.delenv("ENVIRONMENT", raising=False)
        monkeypatch.delenv("SENTRY_RELEASE", raising=False)

        with (
            patch("fragrance_rater.core.sentry.sentry_sdk.init") as mock_init,
            patch(
                "fragrance_rater.core.sentry._get_release_version",
                return_value="fragrance_rater@xyz",
            ),
        ):
            from fragrance_rater.core.sentry import init_sentry

            init_sentry()

            kwargs = mock_init.call_args.kwargs
            assert kwargs["environment"] == "staging"

    @pytest.mark.unit
    def test_init_sentry_uses_sentry_release_env_var(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Verify init_sentry falls back to SENTRY_RELEASE env var."""
        monkeypatch.setenv("SENTRY_DSN", "https://env@sentry.io/2")
        monkeypatch.setenv("SENTRY_RELEASE", "release-from-env")
        monkeypatch.delenv("SENTRY_ENVIRONMENT", raising=False)
        monkeypatch.delenv("ENVIRONMENT", raising=False)

        with patch("fragrance_rater.core.sentry.sentry_sdk.init") as mock_init:
            from fragrance_rater.core.sentry import init_sentry

            init_sentry()

            kwargs = mock_init.call_args.kwargs
            assert kwargs["release"] == "release-from-env"

    @pytest.mark.unit
    def test_init_sentry_disables_tracing(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Verify enable_tracing=False sets traces_sample_rate to 0.0."""
        monkeypatch.delenv("SENTRY_DSN", raising=False)

        with (
            patch("fragrance_rater.core.sentry.sentry_sdk.init") as mock_init,
            patch(
                "fragrance_rater.core.sentry._get_release_version",
                return_value="fragrance_rater@x",
            ),
        ):
            from fragrance_rater.core.sentry import init_sentry

            init_sentry(
                dsn="https://test@sentry.io/1",
                enable_tracing=False,
                traces_sample_rate=0.5,
            )

            kwargs = mock_init.call_args.kwargs
            assert kwargs["traces_sample_rate"] == 0.0

    @pytest.mark.unit
    def test_init_sentry_disables_profiling(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Verify enable_profiling=False sets profiles_sample_rate to 0.0."""
        monkeypatch.delenv("SENTRY_DSN", raising=False)

        with (
            patch("fragrance_rater.core.sentry.sentry_sdk.init") as mock_init,
            patch(
                "fragrance_rater.core.sentry._get_release_version",
                return_value="fragrance_rater@x",
            ),
        ):
            from fragrance_rater.core.sentry import init_sentry

            init_sentry(
                dsn="https://test@sentry.io/1",
                enable_profiling=False,
                profiles_sample_rate=0.7,
            )

            kwargs = mock_init.call_args.kwargs
            assert kwargs["profiles_sample_rate"] == 0.0

    @pytest.mark.unit
    def test_init_sentry_debug_flag_passed_through(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Verify debug=True is forwarded to sentry_sdk.init."""
        monkeypatch.delenv("SENTRY_DSN", raising=False)

        with (
            patch("fragrance_rater.core.sentry.sentry_sdk.init") as mock_init,
            patch(
                "fragrance_rater.core.sentry._get_release_version",
                return_value="fragrance_rater@x",
            ),
        ):
            from fragrance_rater.core.sentry import init_sentry

            init_sentry(dsn="https://test@sentry.io/1", debug=True)

            kwargs = mock_init.call_args.kwargs
            assert kwargs["debug"] is True


class TestGetReleaseVersion:
    """Tests for _get_release_version helper."""

    @pytest.mark.unit
    def test_get_release_version_uses_git_sha(self) -> None:
        """Verify _get_release_version returns git SHA on success."""
        with patch(
            "fragrance_rater.core.sentry.subprocess.check_output",
            return_value=b"deadbee\n",
        ):
            from fragrance_rater.core.sentry import _get_release_version

            result = _get_release_version()

            assert result == "fragrance_rater@deadbee"

    @pytest.mark.unit
    def test_get_release_version_falls_back_to_package_version(self) -> None:
        """Verify fallback to package version when git fails."""
        with (
            patch(
                "fragrance_rater.core.sentry.subprocess.check_output",
                side_effect=FileNotFoundError("git not found"),
            ),
            patch(
                "fragrance_rater.core.sentry.version", return_value="1.2.3"
            ) as mock_version,
        ):
            from fragrance_rater.core.sentry import _get_release_version

            result = _get_release_version()

            assert result == "fragrance_rater@1.2.3"
            mock_version.assert_called_once_with("fragrance-rater")

    @pytest.mark.unit
    def test_get_release_version_handles_called_process_error(self) -> None:
        """Verify CalledProcessError triggers package-version fallback."""
        with (
            patch(
                "fragrance_rater.core.sentry.subprocess.check_output",
                side_effect=subprocess.CalledProcessError(1, "git"),
            ),
            patch("fragrance_rater.core.sentry.version", return_value="2.0.0"),
        ):
            from fragrance_rater.core.sentry import _get_release_version

            result = _get_release_version()

            assert result == "fragrance_rater@2.0.0"

    @pytest.mark.unit
    def test_get_release_version_ultimate_fallback(self) -> None:
        """Verify ultimate fallback when both git and package version fail."""
        with (
            patch(
                "fragrance_rater.core.sentry.subprocess.check_output",
                side_effect=FileNotFoundError("git not found"),
            ),
            patch(
                "fragrance_rater.core.sentry.version",
                side_effect=PackageNotFoundError("fragrance-rater"),
            ),
        ):
            from fragrance_rater.core.sentry import _get_release_version

            result = _get_release_version()

            assert result == "fragrance_rater@0.1.0"


class TestBeforeSendHook:
    """Tests for before_send_hook filter function."""

    @pytest.mark.unit
    def test_drops_keyboard_interrupt(self) -> None:
        """Verify KeyboardInterrupt events are dropped."""
        from fragrance_rater.core.sentry import before_send_hook

        event: dict[str, Any] = {"event_id": "abc"}
        hint: dict[str, Any] = {
            "exc_info": (KeyboardInterrupt, KeyboardInterrupt(), None)
        }

        result = before_send_hook(cast("Event", event), cast("Hint", hint))

        assert result is None

    @pytest.mark.unit
    def test_drops_system_exit(self) -> None:
        """Verify SystemExit events are dropped."""
        from fragrance_rater.core.sentry import before_send_hook

        event: dict[str, Any] = {"event_id": "abc"}
        hint: dict[str, Any] = {"exc_info": (SystemExit, SystemExit(), None)}

        result = before_send_hook(cast("Event", event), cast("Hint", hint))

        assert result is None

    @pytest.mark.unit
    def test_returns_event_for_other_exceptions(self) -> None:
        """Verify normal exceptions return the event unchanged."""
        from fragrance_rater.core.sentry import before_send_hook

        event: dict[str, Any] = {"event_id": "abc"}
        hint: dict[str, Any] = {"exc_info": (ValueError, ValueError("oops"), None)}

        result = before_send_hook(cast("Event", event), cast("Hint", hint))

        assert result is event

    @pytest.mark.unit
    def test_returns_event_when_no_exc_info(self) -> None:
        """Verify hook returns event when hint has no exc_info."""
        from fragrance_rater.core.sentry import before_send_hook

        event: dict[str, Any] = {"event_id": "abc"}
        hint: dict[str, Any] = {}

        result = before_send_hook(cast("Event", event), cast("Hint", hint))

        assert result is event

    @pytest.mark.unit
    def test_scrubs_sensitive_fields_from_request_data(self) -> None:
        """Verify sensitive fields are redacted in request.data."""
        from fragrance_rater.core.sentry import before_send_hook

        event: dict[str, Any] = {
            "request": {
                "data": {
                    "password": "hunter2",
                    "token": "abc123",
                    "api_key": "key-xyz",
                    "secret": "shh",
                    "username": "alice",
                }
            }
        }
        hint: dict[str, Any] = {}

        result = before_send_hook(cast("Event", event), cast("Hint", hint))

        assert result is not None
        result_dict = cast("dict[str, Any]", result)
        data = result_dict["request"]["data"]
        assert data["password"] == "[REDACTED]"
        assert data["token"] == "[REDACTED]"
        assert data["api_key"] == "[REDACTED]"
        assert data["secret"] == "[REDACTED]"
        assert data["username"] == "alice"

    @pytest.mark.unit
    def test_handles_request_without_data(self) -> None:
        """Verify hook tolerates request with no data key."""
        from fragrance_rater.core.sentry import before_send_hook

        event: dict[str, Any] = {"request": {"url": "/foo"}}
        hint: dict[str, Any] = {}

        result = before_send_hook(cast("Event", event), cast("Hint", hint))

        assert result is event

    @pytest.mark.unit
    def test_handles_non_dict_request_data(self) -> None:
        """Verify hook leaves non-dict request.data alone."""
        from fragrance_rater.core.sentry import before_send_hook

        event: dict[str, Any] = {"request": {"data": "raw-body-string"}}
        hint: dict[str, Any] = {}

        result = before_send_hook(cast("Event", event), cast("Hint", hint))

        assert result is not None
        result_dict = cast("dict[str, Any]", result)
        assert result_dict["request"]["data"] == "raw-body-string"


class TestBeforeBreadcrumbHook:
    """Tests for before_breadcrumb_hook filter function."""

    @pytest.mark.unit
    def test_filters_httplib_query_param(self) -> None:
        """Verify httplib breadcrumbs have query data filtered."""
        from fragrance_rater.core.sentry import before_breadcrumb_hook

        crumb: dict[str, Any] = {
            "category": "httplib",
            "data": {"query": "secret=value", "url": "https://api"},
        }
        hint: dict[str, Any] = {}

        result = before_breadcrumb_hook(
            cast("Breadcrumb", crumb), cast("BreadcrumbHint", hint)
        )

        assert result is not None
        result_dict = cast("dict[str, Any]", result)
        assert result_dict["data"]["query"] == "[FILTERED]"
        assert result_dict["data"]["url"] == "https://api"

    @pytest.mark.unit
    def test_returns_non_httplib_crumb_unchanged(self) -> None:
        """Verify non-httplib breadcrumbs pass through unchanged."""
        from fragrance_rater.core.sentry import before_breadcrumb_hook

        crumb: dict[str, Any] = {
            "category": "ui",
            "data": {"query": "still-here"},
        }
        hint: dict[str, Any] = {}

        result = before_breadcrumb_hook(
            cast("Breadcrumb", crumb), cast("BreadcrumbHint", hint)
        )

        assert result is not None
        result_dict = cast("dict[str, Any]", result)
        assert result_dict["data"]["query"] == "still-here"

    @pytest.mark.unit
    def test_httplib_without_query_data_unchanged(self) -> None:
        """Verify httplib breadcrumb without query is unchanged."""
        from fragrance_rater.core.sentry import before_breadcrumb_hook

        crumb: dict[str, Any] = {
            "category": "httplib",
            "data": {"url": "https://api"},
        }
        hint: dict[str, Any] = {}

        result = before_breadcrumb_hook(
            cast("Breadcrumb", crumb), cast("BreadcrumbHint", hint)
        )

        assert result is not None
        result_dict = cast("dict[str, Any]", result)
        assert "query" not in result_dict["data"]

    @pytest.mark.unit
    def test_httplib_without_data_key_unchanged(self) -> None:
        """Verify httplib breadcrumb with no data key is unchanged."""
        from fragrance_rater.core.sentry import before_breadcrumb_hook

        crumb: dict[str, Any] = {"category": "httplib"}
        hint: dict[str, Any] = {}

        result = before_breadcrumb_hook(
            cast("Breadcrumb", crumb), cast("BreadcrumbHint", hint)
        )

        assert result is crumb


class TestModuleHelpers:
    """Smoke tests for module-level helpers used by init."""

    @pytest.mark.unit
    def test_capture_exception_uses_scope(self) -> None:
        """Verify capture_exception sets level, tags, extras, and dispatches."""
        with patch("fragrance_rater.core.sentry.sentry_sdk") as mock_sdk:
            scope = MagicMock()
            mock_sdk.push_scope.return_value.__enter__.return_value = scope

            from fragrance_rater.core.sentry import capture_exception

            exc = ValueError("boom")
            capture_exception(
                exc,
                level="warning",
                tags={"api": "v1"},
                extra={"row": 1},
            )

            assert scope.level == "warning"
            scope.set_tag.assert_called_once_with("api", "v1")
            scope.set_extra.assert_called_once_with("row", 1)
            mock_sdk.capture_exception.assert_called_once_with(exc)
