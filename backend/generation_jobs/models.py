"""Status, stage, and API models for async generation jobs."""

from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict


class JobStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class JobStage(str, Enum):
    QUEUED = "queued"
    PREPARING = "preparing"
    GENERATING = "generating"
    VALIDATING = "validating"
    CORRECTING = "correcting"
    OPTIMIZING_BUDGET = "optimizing_budget"
    SAVING = "saving"
    COMPLETED = "completed"
    FAILED = "failed"


STAGE_PROGRESS: dict[str, int | None] = {
    JobStage.QUEUED.value: 0,
    JobStage.PREPARING.value: 5,
    JobStage.GENERATING.value: 15,
    JobStage.VALIDATING.value: 45,
    JobStage.CORRECTING.value: 55,
    JobStage.OPTIMIZING_BUDGET.value: 75,
    JobStage.SAVING.value: 90,
    JobStage.COMPLETED.value: 100,
    JobStage.FAILED.value: None,
}

JobStatusLiteral = Literal["queued", "running", "succeeded", "failed", "cancelled"]
JobStageLiteral = Literal[
    "queued",
    "preparing",
    "generating",
    "validating",
    "correcting",
    "optimizing_budget",
    "saving",
    "completed",
    "failed",
]


class GenerationJobRecord(BaseModel):
    """Row shape for generation_jobs."""

    model_config = ConfigDict(extra="ignore")

    job_id: str
    user_id: int
    status: JobStatusLiteral
    stage: JobStageLiteral = "queued"
    progress_percent: int | None = None
    attempt: int | None = None
    max_attempts: int | None = None
    message_code: str | None = None
    days: int | None = None
    persons: int | None = None
    plan_start_date: str | None = None
    strategy_id: str | None = None
    menu_plan_id: str | None = None
    error_code: str | None = None
    safe_message: str | None = None
    internal_request_id: str | None = None
    duration_ms: int | None = None
    request_json: str | None = None
    created_at: str
    updated_at: str
    started_at: str | None = None
    completed_at: str | None = None


class GenerationJobStatusResponse(BaseModel):
    """Public job status DTO (no request_json / internal fields)."""

    model_config = ConfigDict(extra="forbid")

    job_id: str
    status: JobStatusLiteral
    stage: JobStageLiteral
    progress_percent: int | None = None
    attempt: int | None = None
    max_attempts: int | None = None
    menu_plan_id: str | None = None
    strategy_id: str | None = None
    error_code: str | None = None
    safe_message: str | None = None
    duration_ms: int | None = None
    created_at: str
    started_at: str | None = None
    completed_at: str | None = None
    days: int | None = None
    persons: int | None = None
    plan_start_date: str | None = None
    message_code: str | None = None


class CreateGenerationJobResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    job_id: str
    status: JobStatusLiteral


class ActiveGenerationJobResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    job: GenerationJobStatusResponse | None = None


def record_to_status_response(record: GenerationJobRecord) -> GenerationJobStatusResponse:
    return GenerationJobStatusResponse(
        job_id=record.job_id,
        status=record.status,
        stage=record.stage,
        progress_percent=record.progress_percent,
        attempt=record.attempt,
        max_attempts=record.max_attempts,
        menu_plan_id=record.menu_plan_id,
        strategy_id=record.strategy_id,
        error_code=record.error_code,
        safe_message=record.safe_message,
        duration_ms=record.duration_ms,
        created_at=record.created_at,
        started_at=record.started_at,
        completed_at=record.completed_at,
        days=record.days,
        persons=record.persons,
        plan_start_date=record.plan_start_date,
        message_code=record.message_code,
    )


class PreparedGeneration(BaseModel):
    """Output of prepare_generation_request."""

    model_config = ConfigDict(extra="forbid")

    request_payload: dict
    days: int
    persons: int
    plan_start_date: str
