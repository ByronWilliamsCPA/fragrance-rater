"""Tests for Sentry integration utilities."""

from unittest.mock import MagicMock, patch

import pytest


class TestBeforeSendHook:
    """Tests for before_send_hook event filter."""

    @pytest.mark.unit
    def test_returns_event_unchanged_by_default(self) -> None:
        """Verify normal events pass through unmodified."""
        from fragrance_rater.core.sentry import before_send_hook

        event: dict = {"message": "test error"}
        result = before_send_hook(event, {})
        assert result == event

    @pytest.mark.unit
    def test_filters_keyboard_interrupt(self) -> None:
        """Verify KeyboardInterrupt events are dropped."""
        from fragrance_rater.core.sentry import before_send_hook

        event: dict = {"message": "keyboard interrupt"}
        hint = {"exc_info": (KeyboardInterrupt, KeyboardInterrupt(), None)}
        result = before_send_hook(event, hint)
        assert result is None

    @pytest.mark.unit
    def test_filters_system_exit(self) -> None:
        """Verify SystemExit events are dropped."""
        from fragrance_rater.core.sentry import before_send_hook

        event: dict = {"message": "system exit"}
        hint = {"exc_info": (SystemExit, SystemExit(0), None)}
        result = before_send_hook(event, hint)
        assert result is None

    @pytest.mark.unit
    def test_passes_other_exceptions(self) -> None:
        """Verify other exception types are not filtered."""
        from fragrance_rater.core.sentry import before_send_hook

        event: dict = {"message": "value error"}
        hint = {"exc_info": (ValueError, ValueError("bad"), None)}
        result = before_send_hook(event, hint)
        assert result is event

    @pytest.mark.unit
    def test_redacts_password_in_request_data(self) -> None:
        """Verify password field is redacted from request data."""
        from fragrance_rater.core.sentry import before_send_hook

        event: dict = {
            "request": {"data": {"password": "secret123", "username": "alice"}}
        }
        result = before_send_hook(event, {})
        assert result is not None
        assert result["request"]["data"]["password"] == "[REDACTED]"
        assert result["request"]["data"]["username"] == "alice"

    @pytest.mark.unit
    def test_redacts_token_and_api_key(self) -> None:
        """Verify token and api_key fields are redacted."""
        from fragrance_rater.core.sentry import before_send_hook

        event: dict = {
            "request": {
                "data": {"token": "abc123", "api_key": "key456", "name": "test"}
            }
        }
        result = before_send_hook(event, {})
        assert result is not None
        assert result["request"]["data"]["token"] == "[REDACTED]"
        assert result["request"]["data"]["api_key"] == "[REDACTED]"
        assert result["request"]["data"]["name"] == "test"

    @pytest.mark.unit
    def test_skips_redaction_for_non_dict_request_data(self) -> None:
        """Verify non-dict request data is not redacted."""
        from fragrance_rater.core.sentry import before_send_hook

        event: dict = {"request": {"data": "raw string body"}}
        result = before_send_hook(event, {})
        assert result is not None
        assert result["request"]["data"] == "raw string body"

    @pytest.mark.unit
    def test_event_without_request_passes_through(self) -> None:
        """Verify events without a request key pass through cleanly."""
        from fragrance_rater.core.sentry import before_send_hook

        event: dict = {"level": "error", "message": "background task failed"}
        result = before_send_hook(event, {})
        assert result == event


class TestBeforeBreadcrumbHook:
    """Tests for before_breadcrumb_hook breadcrumb filter."""

    @pytest.mark.unit
    def test_returns_crumb_unchanged_for_non_httplib(self) -> None:
        """Verify non-HTTP breadcrumbs are returned unchanged."""
        from fragrance_rater.core.sentry import before_breadcrumb_hook

        crumb: dict = {"category": "auth", "message": "user logged in"}
        result = before_breadcrumb_hook(crumb, {})
        assert result == crumb

    @pytest.mark.unit
    def test_filters_query_from_httplib_breadcrumb(self) -> None:
        """Verify query param is redacted from HTTP breadcrumbs."""
        from fragrance_rater.core.sentry import before_breadcrumb_hook

        crumb: dict = {
            "category": "httplib",
            "data": {"url": "https://api.example.com", "query": "token=secret"},
        }
        result = before_breadcrumb_hook(crumb, {})
        assert result is not None
        assert result["data"]["query"] == "[FILTERED]"

    @pytest.mark.unit
    def test_httplib_without_data_passes_through(self) -> None:
        """Verify HTTP breadcrumbs without data are not modified."""
        from fragrance_rater.core.sentry import before_breadcrumb_hook

        crumb: dict = {"category": "httplib", "message": "GET /api/v1/health"}
        result = before_breadcrumb_hook(crumb, {})
        assert result == crumb

    @pytest.mark.unit
    def test_httplib_data_without_query_passes_through(self) -> None:
        """Verify HTTP breadcrumbs with data but no query are not modified."""
        from fragrance_rater.core.sentry import before_breadcrumb_hook

        crumb: dict = {
            "category": "httplib",
            "data": {"url": "https://api.example.com"},
        }
        result = before_breadcrumb_hook(crumb, {})
        assert result == crumb


class TestGetReleaseVersion:
    """Tests for _get_release_version version detection."""

    @pytest.mark.unit
    def test_returns_git_sha_when_available(self) -> None:
        """Verify git SHA is used when git command succeeds."""
        from fragrance_rater.core.sentry import _get_release_version

        with patch("subprocess.check_output", return_value=b"abc1234\n"):
            result = _get_release_version()
        assert result == "fragrance_rater@abc1234"

    @pytest.mark.unit
    def test_falls_back_to_package_version_when_git_fails(self) -> None:
        """Verify package version is used when git is unavailable."""
        import subprocess

        from fragrance_rater.core.sentry import _get_release_version

        with (
            patch(
                "subprocess.check_output",
                side_effect=subprocess.CalledProcessError(1, "git"),
            ),
            patch("importlib.metadata.version", return_value="1.2.3"),
        ):
            result = _get_release_version()
        assert result == "fragrance_rater@1.2.3"

    @pytest.mark.unit
    def test_falls_back_to_hardcoded_version_when_all_fail(self) -> None:
        """Verify hardcoded fallback version is used when everything fails."""
        from importlib.metadata import PackageNotFoundError

        from fragrance_rater.core.sentry import _get_release_version

        with (
            patch("subprocess.check_output", side_effect=FileNotFoundError),
            patch("importlib.metadata.version", side_effect=PackageNotFoundError),
        ):
            result = _get_release_version()
        assert result == "fragrance_rater@0.1.0"


class TestInitSentry:
    """Tests for init_sentry initialization."""

    @pytest.mark.unit
    def test_returns_early_when_no_dsn(self) -> None:
        """Verify Sentry is not initialized when DSN is absent."""
        from fragrance_rater.core.sentry import init_sentry

        with (
            patch.dict("os.environ", {}, clear=True),
            patch("sentry_sdk.init") as mock_init,
        ):
            init_sentry(dsn=None)
        mock_init.assert_not_called()

    @pytest.mark.unit
    def test_initializes_with_dsn(self) -> None:
        """Verify sentry_sdk.init is called when DSN is provided."""
        from fragrance_rater.core.sentry import init_sentry

        with patch("sentry_sdk.init") as mock_init:
            init_sentry(dsn="https://key@sentry.io/123", environment="test")

        mock_init.assert_called_once()
        call_kwargs = mock_init.call_args.kwargs
        assert call_kwargs["dsn"] == "https://key@sentry.io/123"
        assert call_kwargs["environment"] == "test"

    @pytest.mark.unit
    def test_initializes_with_dsn_from_env(self) -> None:
        """Verify DSN is read from SENTRY_DSN env var."""
        from fragrance_rater.core.sentry import init_sentry

        with (
            patch.dict("os.environ", {"SENTRY_DSN": "https://key@sentry.io/456"}),
            patch("sentry_sdk.init") as mock_init,
        ):
            init_sentry()

        mock_init.assert_called_once()
        call_kwargs = mock_init.call_args.kwargs
        assert call_kwargs["dsn"] == "https://key@sentry.io/456"


class TestCaptureException:
    """Tests for capture_exception wrapper."""

    @pytest.mark.unit
    def test_captures_exception_with_sentry(self) -> None:
        """Verify sentry_sdk.capture_exception is called with the exception."""
        from fragrance_rater.core.sentry import capture_exception

        exc = ValueError("test error")
        mock_scope = MagicMock()
        mock_scope.__enter__ = MagicMock(return_value=mock_scope)
        mock_scope.__exit__ = MagicMock(return_value=False)

        with (
            patch("sentry_sdk.push_scope", return_value=mock_scope),
            patch("sentry_sdk.capture_exception") as mock_capture,
        ):
            capture_exception(exc)

        mock_capture.assert_called_once_with(exc)

    @pytest.mark.unit
    def test_capture_exception_with_tags_and_extra(self) -> None:
        """Verify tags and extra context are set on the scope."""
        from fragrance_rater.core.sentry import capture_exception

        exc = RuntimeError("runtime fail")
        mock_scope = MagicMock()
        mock_scope.__enter__ = MagicMock(return_value=mock_scope)
        mock_scope.__exit__ = MagicMock(return_value=False)

        with (
            patch("sentry_sdk.push_scope", return_value=mock_scope),
            patch("sentry_sdk.capture_exception"),
        ):
            capture_exception(exc, tags={"env": "prod"}, extra={"row": 42})

        mock_scope.set_tag.assert_called_with("env", "prod")
        mock_scope.set_extra.assert_called_with("row", 42)


class TestCaptureMessage:
    """Tests for capture_message wrapper."""

    @pytest.mark.unit
    def test_captures_message_with_sentry(self) -> None:
        """Verify sentry_sdk.capture_message is called with the message."""
        from fragrance_rater.core.sentry import capture_message

        mock_scope = MagicMock()
        mock_scope.__enter__ = MagicMock(return_value=mock_scope)
        mock_scope.__exit__ = MagicMock(return_value=False)

        with (
            patch("sentry_sdk.push_scope", return_value=mock_scope),
            patch("sentry_sdk.capture_message") as mock_capture,
        ):
            capture_message("user completed onboarding", level="info")

        mock_capture.assert_called_once_with("user completed onboarding")

    @pytest.mark.unit
    def test_capture_message_with_tags(self) -> None:
        """Verify tags are applied to the Sentry scope."""
        from fragrance_rater.core.sentry import capture_message

        mock_scope = MagicMock()
        mock_scope.__enter__ = MagicMock(return_value=mock_scope)
        mock_scope.__exit__ = MagicMock(return_value=False)

        with (
            patch("sentry_sdk.push_scope", return_value=mock_scope),
            patch("sentry_sdk.capture_message"),
        ):
            capture_message("test", tags={"feature": "import"})

        mock_scope.set_tag.assert_called_with("feature", "import")


class TestSetUserContext:
    """Tests for set_user_context."""

    @pytest.mark.unit
    def test_sets_user_id(self) -> None:
        """Verify user ID is passed to sentry_sdk.set_user."""
        from fragrance_rater.core.sentry import set_user_context

        with patch("sentry_sdk.set_user") as mock_set_user:
            set_user_context(user_id="user-123")

        mock_set_user.assert_called_once_with({"id": "user-123"})

    @pytest.mark.unit
    def test_sets_full_user_context(self) -> None:
        """Verify all user fields are included."""
        from fragrance_rater.core.sentry import set_user_context

        with patch("sentry_sdk.set_user") as mock_set_user:
            set_user_context(user_id="u1", email="test@example.com", username="alice")

        call_arg = mock_set_user.call_args.args[0]
        assert call_arg["id"] == "u1"
        assert call_arg["email"] == "test@example.com"
        assert call_arg["username"] == "alice"

    @pytest.mark.unit
    def test_includes_extra_kwargs(self) -> None:
        """Verify extra keyword arguments are merged into user data."""
        from fragrance_rater.core.sentry import set_user_context

        with patch("sentry_sdk.set_user") as mock_set_user:
            set_user_context(user_id="u1", subscription="premium")

        call_arg = mock_set_user.call_args.args[0]
        assert call_arg["subscription"] == "premium"


class TestAddBreadcrumb:
    """Tests for add_breadcrumb."""

    @pytest.mark.unit
    def test_adds_breadcrumb_with_defaults(self) -> None:
        """Verify sentry_sdk.add_breadcrumb is called with message and defaults."""
        from fragrance_rater.core.sentry import add_breadcrumb

        with patch("sentry_sdk.add_breadcrumb") as mock_add:
            add_breadcrumb("user clicked export")

        mock_add.assert_called_once_with(
            message="user clicked export",
            category="custom",
            level="info",
            data={},
        )

    @pytest.mark.unit
    def test_adds_breadcrumb_with_custom_data(self) -> None:
        """Verify custom category, level, and data are forwarded."""
        from fragrance_rater.core.sentry import add_breadcrumb

        with patch("sentry_sdk.add_breadcrumb") as mock_add:
            add_breadcrumb(
                "import started", category="import", level="warning", data={"rows": 100}
            )

        mock_add.assert_called_once_with(
            message="import started",
            category="import",
            level="warning",
            data={"rows": 100},
        )
