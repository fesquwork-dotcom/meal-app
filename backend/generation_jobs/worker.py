"""In-process asyncio worker for generation jobs (no Celery/Redis)."""

from __future__ import annotations

import asyncio
import logging

import config
from generation_jobs.errors import (
    ERROR_CODE_INTERRUPTED,
    SAFE_MESSAGE_INTERRUPTED,
)
from generation_jobs.execute import run_generation_job
from generation_jobs.repository import GenerationJobRepository

logger = logging.getLogger(__name__)


class GenerationWorker:
    """Singleton-friendly worker: semaphore + wakeup queue drain."""

    def __init__(
        self,
        *,
        repository: GenerationJobRepository | None = None,
        max_concurrent: int | None = None,
    ) -> None:
        self._repository = repository or GenerationJobRepository()
        self._max_concurrent = (
            max_concurrent
            if max_concurrent is not None
            else config.GENERATION_MAX_CONCURRENT_JOBS
        )
        # Created in start() so they bind to the active event loop (TestClient
        # recreates loops across lifespan cycles).
        self._semaphore: asyncio.Semaphore | None = None
        self._wakeup: asyncio.Event | None = None
        self._loop_task: asyncio.Task | None = None
        self._job_tasks: set[asyncio.Task] = set()
        self._scheduled_job_ids: set[str] = set()
        self._stopping = False

    async def interrupt_running_on_startup(self) -> int:
        return await self._repository.mark_interrupted_running(
            error_code=ERROR_CODE_INTERRUPTED,
            safe_message=SAFE_MESSAGE_INTERRUPTED,
        )

    def kick(self) -> None:
        wakeup = self._wakeup
        if wakeup is None:
            return
        try:
            wakeup.set()
        except RuntimeError:
            # Event bound to a closed/different loop — next start() recreates it.
            logger.warning("generation_worker_kick_loop_mismatch")

    async def start(self) -> None:
        # Always bind primitives to the current running loop.
        if self._loop_task is not None and not self._loop_task.done():
            await self.stop()

        self._stopping = False
        limit = max(1, int(self._max_concurrent))
        self._semaphore = asyncio.Semaphore(limit)
        self._wakeup = asyncio.Event()
        self._scheduled_job_ids.clear()
        self._job_tasks.clear()
        self._loop_task = asyncio.create_task(
            self._run_loop(), name="generation-worker"
        )
        self.kick()
        logger.info("generation_worker_started max_concurrent=%s", limit)

    async def stop(self) -> None:
        self._stopping = True
        wakeup = self._wakeup
        self._wakeup = None
        if wakeup is not None:
            try:
                wakeup.set()
            except RuntimeError:
                pass

        for task in list(self._job_tasks):
            task.cancel()
        if self._job_tasks:
            await asyncio.gather(*self._job_tasks, return_exceptions=True)
        self._job_tasks.clear()
        self._scheduled_job_ids.clear()

        loop_task = self._loop_task
        self._loop_task = None
        if loop_task is not None and not loop_task.done():
            loop_task.cancel()
            try:
                await loop_task
            except asyncio.CancelledError:
                pass
            except RuntimeError:
                logger.warning("generation_worker_stop_loop_mismatch")
        self._semaphore = None
        logger.info("generation_worker_stopped")

    async def _run_loop(self) -> None:
        try:
            while not self._stopping:
                try:
                    await self._drain_queue()
                except Exception:
                    logger.exception("generation_worker_drain_failed")

                if self._stopping:
                    break

                wakeup = self._wakeup
                if wakeup is None:
                    break
                try:
                    # Clear only after a successful wait so a kick that arrives
                    # between drain and wait is not lost.
                    await asyncio.wait_for(wakeup.wait(), timeout=2.0)
                    wakeup.clear()
                except asyncio.TimeoutError:
                    continue
                except asyncio.CancelledError:
                    raise
                except RuntimeError:
                    logger.warning("generation_worker_wakeup_loop_mismatch")
                    break
        except asyncio.CancelledError:
            raise

    async def _drain_queue(self) -> None:
        queued = await self._repository.list_queued(limit=20)
        for job in queued:
            if self._stopping:
                return
            if job.job_id in self._scheduled_job_ids:
                continue
            self._scheduled_job_ids.add(job.job_id)
            task = asyncio.create_task(
                self._run_one(job.job_id),
                name=f"generation-job-{job.job_id}",
            )
            self._job_tasks.add(task)

            def _on_done(
                done: asyncio.Task,
                *,
                jid: str = job.job_id,
            ) -> None:
                self._job_tasks.discard(done)
                self._scheduled_job_ids.discard(jid)

            task.add_done_callback(_on_done)

    async def _run_one(self, job_id: str) -> None:
        semaphore = self._semaphore
        if semaphore is None:
            return
        try:
            async with semaphore:
                if self._stopping:
                    return
                try:
                    await run_generation_job(job_id)
                except asyncio.CancelledError:
                    raise
                except Exception:
                    logger.exception(
                        "generation_worker_job_crashed job_id=%s", job_id
                    )
        except asyncio.CancelledError:
            # Leave job queued/running for restart interrupt policy; do not
            # silently succeed.
            raise


_worker: GenerationWorker | None = None


def get_generation_worker() -> GenerationWorker:
    global _worker
    if _worker is None:
        _worker = GenerationWorker()
    return _worker


def reset_generation_worker_for_tests() -> None:
    """Drop singleton so the next start() binds to a fresh event loop."""
    global _worker
    _worker = None
