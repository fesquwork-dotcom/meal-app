"""Domain exceptions for the Memory Engine."""

from __future__ import annotations


class MemoryError(Exception):
    """Base class for Memory Engine errors."""


class MemoryPersistenceError(MemoryError):
    """Raised when a memory event or signal cannot be saved or loaded."""


class MemorySignalNotFoundError(MemoryError):
    """Raised when a preference signal does not exist or is not owned by the user."""


class MemoryPromotionError(MemoryError):
    """Base class for memory signal promotion errors."""

    def __init__(self, message: str, *, code: str) -> None:
        super().__init__(message)
        self.code = code


class MemorySignalNotPromotableError(MemoryPromotionError):
    """Signal type or state does not allow promotion."""

    def __init__(self, message: str) -> None:
        super().__init__(message, code="MEMORY_SIGNAL_NOT_PROMOTABLE")


class MemorySignalNotConfirmedError(MemoryPromotionError):
    """Observed signals must be confirmed before promotion."""

    def __init__(self, message: str) -> None:
        super().__init__(message, code="MEMORY_SIGNAL_NOT_CONFIRMED")


class MemorySignalAlreadyPromotedError(MemoryPromotionError):
    """Idempotent response for a signal that was already promoted."""

    def __init__(
        self,
        message: str,
        *,
        constraint_id: str,
        profile_revision: int,
        profile: dict[str, object],
    ) -> None:
        super().__init__(message, code="MEMORY_SIGNAL_ALREADY_PROMOTED")
        self.constraint_id = constraint_id
        self.profile_revision = profile_revision
        self.profile = profile


class MemoryPromotionProfileStaleError(MemoryPromotionError):
    """Profile revision CAS mismatch during promotion."""

    def __init__(self, message: str, *, current_revision: int | None) -> None:
        super().__init__(message, code="MEMORY_PROMOTION_PROFILE_STALE")
        self.current_revision = current_revision


class MemoryPromotionFailedError(MemoryPromotionError):
    """Unexpected failure during the promotion transaction."""

    def __init__(self, message: str) -> None:
        super().__init__(message, code="MEMORY_PROMOTION_FAILED")
