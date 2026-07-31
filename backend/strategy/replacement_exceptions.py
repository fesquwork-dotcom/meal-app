"""Domain exceptions for single-meal replacement within an active strategy."""


class ReplacementError(Exception):
    """Base error for meal replacement flow."""

    def __init__(self, message: str, code: str | None = None) -> None:
        super().__init__(message)
        self.code = code or "REPLACEMENT_ERROR"


class MealNotFoundError(ReplacementError):
    def __init__(self, meal_id: str) -> None:
        super().__init__(f"Meal '{meal_id}' not found", code="MEAL_NOT_FOUND")
        self.meal_id = meal_id


class StrategyNotActiveError(ReplacementError):
    def __init__(self, status: str) -> None:
        super().__init__(f"Strategy is not active (status={status})", code="STRATEGY_NOT_ACTIVE")
        self.status = status


class MenuStrategyMismatchError(ReplacementError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message, code=code)


class ReplacementScopeError(ReplacementError):
    def __init__(self, message: str, code: str = "REPLACEMENT_SCOPE_TOO_LARGE") -> None:
        super().__init__(message, code=code)


class ReplacementValidationError(ReplacementError):
    """Raised when merged plan fails validation after replacement."""

    def __init__(
        self,
        message: str,
        issue_codes: list[str] | None = None,
        issue_messages: list[str] | None = None,
    ) -> None:
        super().__init__(message, code="REPLACEMENT_VALIDATION_FAILED")
        self.issue_codes = issue_codes or []
        # Correction-prompt details (same order as issue_codes); internal only.
        self.issue_messages = issue_messages or []


class ReplacementFailedError(ReplacementError):
    """Raised when Claude cannot produce a valid replacement after all attempts."""

    def __init__(self, issue_codes: list[str] | None = None) -> None:
        super().__init__("Replacement generation failed", code="REPLACEMENT_FAILED")
        self.issue_codes = issue_codes or []


class ReplacementPriceResolutionError(ReplacementError):
    """Raised when basket rebuild cannot resolve prices for replacement ingredients.

    Internal payload may retain canonical/display names for correction prompts
    and diagnostics. Public API handlers must not expose the full list.
    """

    def __init__(self, unresolved_items: list[str] | tuple[str, ...] | None = None) -> None:
        items = tuple(item for item in (unresolved_items or ()) if item)
        super().__init__(
            f"Replacement price resolution failed for {len(items)} item(s)",
            code="REPLACEMENT_PRICE_UNRESOLVED",
        )
        self.unresolved_items = items
        self.issue_codes = ["REPLACEMENT_PRICE_UNRESOLVED"]
