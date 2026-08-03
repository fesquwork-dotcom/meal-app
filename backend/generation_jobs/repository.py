"""SQLite persistence for generation_jobs."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

import aiosqlite

import database
from generation_jobs.models import (
    STAGE_PROGRESS,
    GenerationJobRecord,
    JobStage,
    JobStatus,
)

logger = logging.getLogger(__name__)

ACTIVE_STATUSES = (JobStatus.QUEUED.value, JobStatus.RUNNING.value)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _row_to_record(row: aiosqlite.Row) -> GenerationJobRecord:
    keys = set(row.keys())
    return GenerationJobRecord(
        job_id=row["job_id"],
        user_id=int(row["user_id"]),
        status=row["status"],
        stage=row["stage"] or JobStage.QUEUED.value,
        progress_percent=row["progress_percent"],
        attempt=row["attempt"],
        max_attempts=row["max_attempts"],
        message_code=row["message_code"],
        days=row["days"],
        persons=row["persons"],
        plan_start_date=row["plan_start_date"],
        strategy_id=row["strategy_id"],
        menu_plan_id=row["menu_plan_id"],
        error_code=row["error_code"],
        safe_message=row["safe_message"],
        internal_request_id=row["internal_request_id"],
        duration_ms=row["duration_ms"],
        request_json=row["request_json"] if "request_json" in keys else None,
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        started_at=row["started_at"],
        completed_at=row["completed_at"],
    )


class GenerationJobRepository:
    async def create(
        self,
        *,
        job_id: str,
        user_id: int,
        request_json: str,
        days: int | None = None,
        persons: int | None = None,
        plan_start_date: str | None = None,
        internal_request_id: str | None = None,
        max_attempts: int | None = None,
    ) -> GenerationJobRecord:
        now = _utc_now_iso()
        db_path = database.resolve_database_path()
        async with aiosqlite.connect(db_path) as db:
            await database._ensure_generation_jobs_table(db)
            await db.execute(
                """
                INSERT INTO generation_jobs (
                    job_id, user_id, status, stage, progress_percent,
                    attempt, max_attempts, message_code,
                    days, persons, plan_start_date,
                    strategy_id, menu_plan_id, error_code, safe_message,
                    internal_request_id, duration_ms, request_json,
                    created_at, updated_at, started_at, completed_at
                ) VALUES (
                    ?, ?, ?, ?, ?,
                    NULL, ?, NULL,
                    ?, ?, ?,
                    NULL, NULL, NULL, NULL,
                    ?, NULL, ?,
                    ?, ?, NULL, NULL
                )
                """,
                (
                    job_id,
                    user_id,
                    JobStatus.QUEUED.value,
                    JobStage.QUEUED.value,
                    STAGE_PROGRESS[JobStage.QUEUED.value],
                    max_attempts,
                    days,
                    persons,
                    plan_start_date,
                    internal_request_id,
                    request_json,
                    now,
                    now,
                ),
            )
            await db.commit()
        record = await self.get(job_id)
        assert record is not None
        return record

    async def get(self, job_id: str) -> GenerationJobRecord | None:
        db_path = database.resolve_database_path()
        async with aiosqlite.connect(db_path) as db:
            await database._ensure_generation_jobs_table(db)
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT * FROM generation_jobs WHERE job_id = ?",
                (job_id,),
            )
            row = await cursor.fetchone()
            await cursor.close()
        if row is None:
            return None
        return _row_to_record(row)

    async def get_active_for_user(self, user_id: int) -> GenerationJobRecord | None:
        db_path = database.resolve_database_path()
        async with aiosqlite.connect(db_path) as db:
            await database._ensure_generation_jobs_table(db)
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                """
                SELECT * FROM generation_jobs
                WHERE user_id = ? AND status IN ('queued', 'running')
                ORDER BY created_at ASC
                LIMIT 1
                """,
                (user_id,),
            )
            row = await cursor.fetchone()
            await cursor.close()
        if row is None:
            return None
        return _row_to_record(row)

    async def list_queued(self, *, limit: int = 20) -> list[GenerationJobRecord]:
        db_path = database.resolve_database_path()
        async with aiosqlite.connect(db_path) as db:
            await database._ensure_generation_jobs_table(db)
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                """
                SELECT * FROM generation_jobs
                WHERE status = 'queued'
                ORDER BY created_at ASC
                LIMIT ?
                """,
                (limit,),
            )
            rows = await cursor.fetchall()
            await cursor.close()
        return [_row_to_record(row) for row in rows]

    async def mark_running(
        self,
        job_id: str,
        *,
        clear_request_json: bool = False,
        max_attempts: int | None = None,
    ) -> GenerationJobRecord | None:
        """Atomically claim a queued job. Returns None if another worker already claimed it."""
        now = _utc_now_iso()
        db_path = database.resolve_database_path()
        async with aiosqlite.connect(db_path) as db:
            await database._ensure_generation_jobs_table(db)
            if clear_request_json:
                cursor = await db.execute(
                    """
                    UPDATE generation_jobs
                    SET status = 'running',
                        stage = 'preparing',
                        progress_percent = ?,
                        started_at = COALESCE(started_at, ?),
                        updated_at = ?,
                        max_attempts = COALESCE(?, max_attempts),
                        request_json = ''
                    WHERE job_id = ? AND status = 'queued'
                    """,
                    (
                        STAGE_PROGRESS[JobStage.PREPARING.value],
                        now,
                        now,
                        max_attempts,
                        job_id,
                    ),
                )
            else:
                cursor = await db.execute(
                    """
                    UPDATE generation_jobs
                    SET status = 'running',
                        stage = 'preparing',
                        progress_percent = ?,
                        started_at = COALESCE(started_at, ?),
                        updated_at = ?,
                        max_attempts = COALESCE(?, max_attempts)
                    WHERE job_id = ? AND status = 'queued'
                    """,
                    (
                        STAGE_PROGRESS[JobStage.PREPARING.value],
                        now,
                        now,
                        max_attempts,
                        job_id,
                    ),
                )
            claimed = cursor.rowcount is not None and cursor.rowcount > 0
            await cursor.close()
            await db.commit()
        if not claimed:
            return None
        return await self.get(job_id)

    async def update_stage(
        self,
        job_id: str,
        *,
        stage: str,
        attempt: int | None = None,
        max_attempts: int | None = None,
        message_code: str | None = None,
        progress_percent: int | None = None,
    ) -> None:
        now = _utc_now_iso()
        progress = (
            progress_percent
            if progress_percent is not None
            else STAGE_PROGRESS.get(stage)
        )
        db_path = database.resolve_database_path()
        async with aiosqlite.connect(db_path) as db:
            await database._ensure_generation_jobs_table(db)
            await db.execute(
                """
                UPDATE generation_jobs
                SET stage = ?,
                    progress_percent = ?,
                    attempt = COALESCE(?, attempt),
                    max_attempts = COALESCE(?, max_attempts),
                    message_code = COALESCE(?, message_code),
                    updated_at = ?
                WHERE job_id = ? AND status = 'running'
                """,
                (stage, progress, attempt, max_attempts, message_code, now, job_id),
            )
            await db.commit()

    async def mark_succeeded(
        self,
        job_id: str,
        *,
        strategy_id: str,
        menu_plan_id: str,
        duration_ms: int | None = None,
        clear_request_json: bool = True,
    ) -> GenerationJobRecord | None:
        now = _utc_now_iso()
        request_json_sql = ", request_json = ''" if clear_request_json else ""
        db_path = database.resolve_database_path()
        async with aiosqlite.connect(db_path) as db:
            await database._ensure_generation_jobs_table(db)
            cursor = await db.execute(
                f"""
                UPDATE generation_jobs
                SET status = 'succeeded',
                    stage = 'completed',
                    progress_percent = ?,
                    strategy_id = ?,
                    menu_plan_id = ?,
                    duration_ms = ?,
                    completed_at = ?,
                    updated_at = ?,
                    error_code = NULL,
                    safe_message = NULL
                    {request_json_sql}
                WHERE job_id = ? AND status = 'running'
                """,
                (
                    STAGE_PROGRESS[JobStage.COMPLETED.value],
                    strategy_id,
                    menu_plan_id,
                    duration_ms,
                    now,
                    now,
                    job_id,
                ),
            )
            updated = cursor.rowcount is not None and cursor.rowcount > 0
            await cursor.close()
            await db.commit()
        if not updated:
            logger.warning(
                "generation_job_succeed_skipped job_id=%s",
                job_id,
            )
            return await self.get(job_id)
        return await self.get(job_id)

    async def mark_failed(
        self,
        job_id: str,
        *,
        error_code: str,
        safe_message: str,
        duration_ms: int | None = None,
        clear_request_json: bool = True,
    ) -> GenerationJobRecord | None:
        now = _utc_now_iso()
        request_json_sql = ", request_json = ''" if clear_request_json else ""
        db_path = database.resolve_database_path()
        async with aiosqlite.connect(db_path) as db:
            await database._ensure_generation_jobs_table(db)
            await db.execute(
                f"""
                UPDATE generation_jobs
                SET status = 'failed',
                    stage = 'failed',
                    progress_percent = NULL,
                    error_code = ?,
                    safe_message = ?,
                    duration_ms = ?,
                    completed_at = ?,
                    updated_at = ?
                    {request_json_sql}
                WHERE job_id = ?
                """,
                (error_code, safe_message, duration_ms, now, now, job_id),
            )
            await db.commit()
        return await self.get(job_id)

    async def mark_interrupted_running(
        self,
        *,
        error_code: str,
        safe_message: str,
    ) -> int:
        """Mark all running jobs as failed (process restart). Returns count."""
        now = _utc_now_iso()
        db_path = database.resolve_database_path()
        async with aiosqlite.connect(db_path) as db:
            await database._ensure_generation_jobs_table(db)
            cursor = await db.execute(
                """
                UPDATE generation_jobs
                SET status = 'failed',
                    stage = 'failed',
                    progress_percent = NULL,
                    error_code = ?,
                    safe_message = ?,
                    completed_at = ?,
                    updated_at = ?,
                    request_json = ''
                WHERE status = 'running'
                """,
                (error_code, safe_message, now, now),
            )
            count = cursor.rowcount if cursor.rowcount is not None else 0
            await cursor.close()
            await db.commit()
        if count:
            logger.warning(
                "generation_jobs_interrupted_on_startup count=%s",
                count,
            )
        return count

    async def clear_request_json(self, job_id: str) -> None:
        now = _utc_now_iso()
        db_path = database.resolve_database_path()
        async with aiosqlite.connect(db_path) as db:
            await database._ensure_generation_jobs_table(db)
            await db.execute(
                """
                UPDATE generation_jobs
                SET request_json = '', updated_at = ?
                WHERE job_id = ?
                """,
                (now, job_id),
            )
            await db.commit()
