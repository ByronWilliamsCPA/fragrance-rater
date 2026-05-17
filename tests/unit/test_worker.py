"""Tests for ARQ background worker module.

This module provides comprehensive tests for the ARQ worker covering:
- Task functions (example_background_task, send_email_task, process_file_upload)
- Scheduled task (cleanup_old_data)
- Lifecycle hooks (startup, shutdown)
- Task enqueuing helper (enqueue_task)
- WorkerSettings configuration

All external dependencies (Redis, asyncio.sleep) are mocked. No real worker
or Redis instance is started.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest


class TestExampleBackgroundTask:
    """Tests for example_background_task."""

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_returns_success_dict(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Verify task returns success status with user_id and timestamp."""
        monkeypatch.setattr("asyncio.sleep", AsyncMock(return_value=None))

        from fragrance_rater.jobs.worker import example_background_task

        ctx: dict[str, Any] = {"redis": AsyncMock(), "job_id": "job-123"}
        result = await example_background_task(ctx, "user_42", {"action": "x"})

        assert result["status"] == "success"
        assert result["user_id"] == "user_42"
        assert "processed_at" in result
        assert isinstance(result["processed_at"], str)

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_writes_to_redis(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Verify task writes completed marker to redis with TTL."""
        monkeypatch.setattr("asyncio.sleep", AsyncMock(return_value=None))

        from fragrance_rater.jobs.worker import example_background_task

        mock_redis = AsyncMock()
        ctx: dict[str, Any] = {"redis": mock_redis, "job_id": "job-1"}

        await example_background_task(ctx, "user_99", {})

        mock_redis.set.assert_awaited_once_with(
            "task_result:user_99", "completed", ex=3600
        )


class TestSendEmailTask:
    """Tests for send_email_task."""

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_returns_sent_dict(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Verify email task returns sent status with recipient."""
        monkeypatch.setattr("asyncio.sleep", AsyncMock(return_value=None))

        from fragrance_rater.jobs.worker import send_email_task

        result = await send_email_task({}, "user@example.com", "Welcome", "Body text")

        assert result["status"] == "sent"
        assert result["recipient"] == "user@example.com"
        assert "sent_at" in result
        assert isinstance(result["sent_at"], str)


class TestProcessFileUpload:
    """Tests for process_file_upload."""

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_returns_completed_dict(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Verify file processing returns completed status."""
        monkeypatch.setattr("asyncio.sleep", AsyncMock(return_value=None))

        from fragrance_rater.jobs.worker import process_file_upload

        result = await process_file_upload({}, "file-1", "uploads/x.csv")

        assert result["status"] == "completed"
        assert result["file_id"] == "file-1"
        assert result["records_processed"] == 1000
        assert "processed_at" in result

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_reraises_on_failure_and_logs(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Verify processing errors are logged and re-raised."""
        boom = AsyncMock(side_effect=RuntimeError("disk full"))
        monkeypatch.setattr("asyncio.sleep", boom)

        mock_logger = MagicMock()
        monkeypatch.setattr("fragrance_rater.jobs.worker.logger", mock_logger)

        from fragrance_rater.jobs.worker import process_file_upload

        with pytest.raises(RuntimeError, match="disk full"):
            await process_file_upload({}, "file-2", "uploads/y.csv")

        mock_logger.exception.assert_called_once()
        call_kwargs = mock_logger.exception.call_args.kwargs
        assert call_kwargs.get("file_id") == "file-2"


class TestCleanupOldData:
    """Tests for cleanup_old_data scheduled task."""

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_returns_zero_placeholder(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Verify cleanup placeholder returns zero and logs completion."""
        mock_logger = MagicMock()
        monkeypatch.setattr("fragrance_rater.jobs.worker.logger", mock_logger)

        from fragrance_rater.jobs.worker import cleanup_old_data

        result = await cleanup_old_data({})

        assert result == 0
        # cleanup_task_completed call should include deleted=0
        completion_calls = [
            call
            for call in mock_logger.info.call_args_list
            if call.args and call.args[0] == "cleanup_task_completed"
        ]
        assert len(completion_calls) == 1
        assert completion_calls[0].kwargs.get("deleted") == 0


class TestLifecycleHooks:
    """Tests for startup and shutdown hooks."""

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_startup_logs(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Verify startup logs the starting message."""
        mock_logger = MagicMock()
        monkeypatch.setattr("fragrance_rater.jobs.worker.logger", mock_logger)

        from fragrance_rater.jobs.worker import startup

        await startup({})

        mock_logger.info.assert_called_once_with("arq_worker_starting")

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_shutdown_logs(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Verify shutdown logs the shutdown message."""
        mock_logger = MagicMock()
        monkeypatch.setattr("fragrance_rater.jobs.worker.logger", mock_logger)

        from fragrance_rater.jobs.worker import shutdown

        await shutdown({})

        mock_logger.info.assert_called_once_with("arq_worker_shutting_down")


class TestEnqueueTask:
    """Tests for enqueue_task helper."""

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_returns_job_id_on_success(self) -> None:
        """Verify enqueue_task returns the job_id from the queued job."""
        from fragrance_rater.jobs.worker import enqueue_task

        mock_job = MagicMock()
        mock_job.job_id = "queued-job-1"

        mock_redis = AsyncMock()
        mock_redis.enqueue_job = AsyncMock(return_value=mock_job)

        result = await enqueue_task(
            mock_redis, "send_email_task", "to@x.com", subject="hi"
        )

        assert result == "queued-job-1"
        mock_redis.enqueue_job.assert_awaited_once_with(
            "send_email_task", "to@x.com", subject="hi"
        )

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_raises_when_job_is_none(self) -> None:
        """Verify RuntimeError is raised with task_name when enqueue returns None."""
        from fragrance_rater.jobs.worker import enqueue_task

        mock_redis = AsyncMock()
        mock_redis.enqueue_job = AsyncMock(return_value=None)

        with pytest.raises(RuntimeError, match="example_background_task"):
            await enqueue_task(mock_redis, "example_background_task", "user_1")


class TestWorkerSettings:
    """Tests for WorkerSettings configuration class."""

    @pytest.mark.unit
    def test_functions_registered(self) -> None:
        """Verify all three task functions are registered."""
        from fragrance_rater.jobs.worker import (
            WorkerSettings,
            example_background_task,
            process_file_upload,
            send_email_task,
        )

        assert example_background_task in WorkerSettings.functions
        assert send_email_task in WorkerSettings.functions
        assert process_file_upload in WorkerSettings.functions

    @pytest.mark.unit
    def test_cron_jobs_configured(self) -> None:
        """Verify exactly one cron job is configured."""
        from fragrance_rater.jobs.worker import WorkerSettings

        assert len(WorkerSettings.cron_jobs) == 1

    @pytest.mark.unit
    def test_worker_limits(self) -> None:
        """Verify worker concurrency, timeout, and retry settings."""
        from fragrance_rater.jobs.worker import WorkerSettings

        assert WorkerSettings.max_jobs == 10
        assert WorkerSettings.job_timeout == 300
        assert WorkerSettings.keep_result == 3600
        assert WorkerSettings.max_tries == 3
        assert WorkerSettings.retry_jobs is True
        assert WorkerSettings.health_check_interval == 60

    @pytest.mark.unit
    def test_lifecycle_hooks_wired(self) -> None:
        """Verify startup/shutdown hooks are wired on WorkerSettings."""
        from fragrance_rater.jobs.worker import WorkerSettings, shutdown, startup

        # Access via __dict__ to bypass descriptor binding (callables become
        # bound methods on attribute access).
        assert vars(WorkerSettings)["on_startup"] is startup
        assert vars(WorkerSettings)["on_shutdown"] is shutdown

    @pytest.mark.unit
    def test_redis_settings_present(self) -> None:
        """Verify redis_settings attribute exists and is populated."""
        from fragrance_rater.jobs.worker import WorkerSettings

        assert WorkerSettings.redis_settings is not None
