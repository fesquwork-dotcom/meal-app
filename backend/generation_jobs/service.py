"""Application service for async generation jobs."""

from __future__ import annotations

import json
import logging
import uuid

from generation_jobs.exceptions import GenerationJobNotFoundError
from generation_jobs.models import GenerationJobRecord
from generation_jobs.prepare import prepare_generation_request
from generation_jobs.repository import GenerationJobRepository
from generation_jobs.worker import GenerationWorker, get_generation_worker
from claude_service import MAX_LLM_ATTEMPTS

logger = logging.getLogger(__name__)


class GenerationJobService:
    def __init__(
        self,
        *,
        repository: GenerationJobRepository | None = None,
        worker: GenerationWorker | None = None,
    ) -> None:
        self._repository = repository or GenerationJobRepository()
        self._worker = worker

    def _resolve_worker(self) -> GenerationWorker:
        return self._worker or get_generation_worker()

    async def create_job(
        self,
        *,
        user_id: int,
        preview_token: str,
    ) -> GenerationJobRecord:
        active = await self._repository.get_active_for_user(user_id)
        if active is not None:
            logger.info(
                "generation_job_duplicate_prevented user_id=%s job_id=%s status=%s",
                user_id,
                active.job_id,
                active.status,
            )
            return active

        prepared = await prepare_generation_request(
            user_id=user_id,
            preview_token=preview_token,
        )
        job_id = str(uuid.uuid4())
        record = await self._repository.create(
            job_id=job_id,
            user_id=user_id,
            request_json=json.dumps(prepared.request_payload, ensure_ascii=False),
            days=prepared.days,
            persons=prepared.persons,
            plan_start_date=prepared.plan_start_date,
            internal_request_id=str(uuid.uuid4()),
            max_attempts=MAX_LLM_ATTEMPTS,
        )
        logger.info(
            "generation_job_created user_id=%s job_id=%s days=%s persons=%s",
            user_id,
            job_id,
            prepared.days,
            prepared.persons,
        )
        self._resolve_worker().kick()
        return record

    async def get_job(self, job_id: str, user_id: int) -> GenerationJobRecord:
        record = await self._repository.get(job_id)
        if record is None or record.user_id != user_id:
            raise GenerationJobNotFoundError(job_id)
        return record

    async def get_active(self, user_id: int) -> GenerationJobRecord | None:
        return await self._repository.get_active_for_user(user_id)


_service: GenerationJobService | None = None


def get_generation_job_service() -> GenerationJobService:
    global _service
    if _service is None:
        _service = GenerationJobService()
    return _service
