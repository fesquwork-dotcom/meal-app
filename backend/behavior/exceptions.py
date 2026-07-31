"""Domain exceptions for the Behavior Learning Engine."""

from __future__ import annotations


class BehaviorError(Exception):
    """Base class for Behavior Engine errors."""


class BehaviorInsightNotFoundError(BehaviorError):
    """Raised when a behavior insight does not exist or is not owned by the user."""


class BehaviorInsightInvalidTransitionError(BehaviorError):
    """Raised when a lifecycle transition is not allowed."""


class BehaviorEvaluationError(BehaviorError):
    """Raised when behavior evaluation cannot complete."""


class BehaviorServiceUnavailableError(BehaviorError):
    """Raised when behavior persistence cannot be accessed."""


class BehaviorInsightNotConfirmableError(BehaviorInsightInvalidTransitionError):
    """Raised when an insight cannot be confirmed in its current status."""


class BehaviorInsightNotDismissibleError(BehaviorInsightInvalidTransitionError):
    """Raised when an insight cannot be dismissed in its current status."""


class BehaviorInsightNotSnoozableError(BehaviorInsightInvalidTransitionError):
    """Raised when an insight cannot be snoozed in its current status."""


class BehaviorInsightNotRevokableError(BehaviorInsightInvalidTransitionError):
    """Raised when an insight cannot be revoked in its current status."""


class BehaviorSnoozeDurationInvalidError(BehaviorError):
    """Raised when snooze duration is not one of the allowed enum values."""


class BehaviorSnoozeFailedError(BehaviorError):
    """Raised when snooze persistence fails."""


class BehaviorRevokeFailedError(BehaviorError):
    """Raised when revoke persistence fails."""


class BehaviorRecommendationError(BehaviorError):
    """Base class for behavior recommendation action errors."""


class BehaviorRecommendationNotAvailableError(BehaviorRecommendationError):
    """Raised when recommendation cannot be applied to this insight."""


class BehaviorRecommendationAlreadyAppliedError(BehaviorRecommendationError):
    """Idempotent response when recommendation was already applied."""

    def __init__(
        self,
        message: str,
        *,
        profile_revision: int,
        profile: dict[str, object],
    ) -> None:
        super().__init__(message)
        self.profile_revision = profile_revision
        self.profile = profile


class BehaviorRecommendationProfileStaleError(BehaviorRecommendationError):
    """Raised when profile revision does not match expected revision."""

    def __init__(self, message: str, *, current_revision: int | None) -> None:
        super().__init__(message)
        self.current_revision = current_revision


class BehaviorRecommendationFailedError(BehaviorRecommendationError):
    """Raised when recommendation transaction fails."""
