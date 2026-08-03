"""Domain errors for generation job prepare / ownership."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from profile_validation import ProfileValidationResult


class GenerationPrepareError(Exception):
    """Validation failure before a job row is created."""

    def __init__(
        self,
        *,
        code: str,
        message: str,
        status_code: int = 422,
        validation_result: ProfileValidationResult | Any | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.validation_result = validation_result


class GenerationJobNotFoundError(Exception):
    """Job missing or owned by another user."""

    def __init__(self, job_id: str) -> None:
        super().__init__(f"generation job not found: {job_id}")
        self.job_id = job_id
