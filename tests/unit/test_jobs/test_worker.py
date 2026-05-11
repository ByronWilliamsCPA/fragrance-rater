"""Tests for background job worker task functions."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestExampleBackgroundTask:
    """Tests for example_background_task."""

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_returns_success_result(self) -> None:
        """Verify task returns a success result dict with user_id."""
        from fragrance_rater.jobs.worker import example_background_task

        redis = AsyncMock()
        ctx = {"redis": redis, "job_id": "job-001"}

        with patch("asyncio.sleep", new_callable=AsyncMock):
            result = await example_background_task(ctx, user_id="user-123", _data={})

        assert result["status"] == "success"
        assert result["user_id"] == "user-123"
        assert "processed_at" in result

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_stores_result_in_redis(self) -> None:
        """Verify task result is stored in Redis."""
        from fragrance_rater.jobs.worker import example_background_task

        redis = AsyncMock()
        ctx = {"redis": redis, "job_id": "job-002"}

        with patch("asyncio.sleep", new_callable=AsyncMock):
            await example_background_task(ctx, user_id="user-456", _data={})

        redis.set.assert_awaited_once_with("task_result:user-456", "completed", ex=3600)


class TestSendEmailTask:
    """Tests for send_email_task."""

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_returns_sent_status(self) -> None:
        """Verify task returns sent status with recipient."""
        from fragrance_rater.jobs.worker import send_email_task

        with patch("asyncio.sleep", new_callable=AsyncMock):
            result = await send_email_task(
                {}, recipient="test@example.com", subject="Hello", _body="body"
            )

        assert result["status"] == "sent"
        assert result["recipient"] == "test@example.com"
        assert "sent_at" in result


class TestProcessFileUpload:
    """Tests for process_file_upload."""

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_returns_completed_result(self) -> None:
        """Verify file upload processing returns completed status."""
        from fragrance_rater.jobs.worker import process_file_upload

        with patch("asyncio.sleep", new_callable=AsyncMock):
            result = await process_file_upload({}, file_id="file-1", file_path="/tmp/test.csv")

        assert result["status"] == "completed"
        assert result["file_id"] == "file-1"
        assert "processed_at" in result
        assert result["records_processed"] == 1000

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_re_raises_exception_on_failure(self) -> None:
        """Verify exceptions during processing are re-raised."""
        from fragrance_rater.jobs.worker import process_file_upload

        with patch("asyncio.sleep", new_callable=AsyncMock, side_effect=RuntimeError("disk full")), pytest.raises(RuntimeError, match="disk full"):
            await process_file_upload({}, file_id="file-2", file_path="/tmp/bad.csv")


class TestCleanupOldData:
    """Tests for cleanup_old_data."""

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_returns_zero_deleted_count(self) -> None:
        """Verify cleanup returns deleted record count (placeholder returns 0)."""
        from fragrance_rater.jobs.worker import cleanup_old_data

        result = await cleanup_old_data({})
        assert result == 0


class TestStartupShutdown:
    """Tests for startup and shutdown hooks."""

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_startup_runs_without_error(self) -> None:
        """Verify startup hook completes without raising."""
        from fragrance_rater.jobs.worker import startup

        await startup({})

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_shutdown_runs_without_error(self) -> None:
        """Verify shutdown hook completes without raising."""
        from fragrance_rater.jobs.worker import shutdown

        await shutdown({})


class TestEnqueueTask:
    """Tests for enqueue_task utility."""

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_returns_job_id_on_success(self) -> None:
        """Verify job ID is returned when enqueue succeeds."""
        from fragrance_rater.jobs.worker import enqueue_task

        mock_job = MagicMock()
        mock_job.job_id = "job-abc-123"
        mock_redis = AsyncMock()
        mock_redis.enqueue_job = AsyncMock(return_value=mock_job)

        job_id = await enqueue_task(mock_redis, "example_background_task", "arg1")
        assert job_id == "job-abc-123"
        mock_redis.enqueue_job.assert_awaited_once_with("example_background_task", "arg1")

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_raises_runtime_error_when_job_is_none(self) -> None:
        """Verify RuntimeError is raised when enqueue returns None."""
        from fragrance_rater.jobs.worker import enqueue_task

        mock_redis = AsyncMock()
        mock_redis.enqueue_job = AsyncMock(return_value=None)

        with pytest.raises(RuntimeError, match="Failed to enqueue task"):
            await enqueue_task(mock_redis, "example_background_task")
