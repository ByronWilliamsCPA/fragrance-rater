"""Background job processing for Fragrance Rater.

This package provides background task processing using ARQ (async Redis queue).

Usage:
    # Start worker
    arq fragrance_rater.jobs.worker.WorkerSettings

    # Enqueue tasks from your FastAPI app
    from fragrance_rater.jobs.worker import enqueue_task

    job_id = await enqueue_task(
        redis,
        "example_background_task",
        user_id="123",
        data={"action": "export"}
    )
"""

from __future__ import annotations

__all__ = []
