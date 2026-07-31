"""Exceptions for Claude menu generation pipeline."""


class ClaudeResponseError(Exception):
    """Base error for Claude response processing."""


class ClaudeJsonError(ClaudeResponseError):
    """Raised when Claude response cannot be parsed as a single JSON object."""


class ClaudeValidationError(ClaudeResponseError):
    """Raised when parsed JSON fails Pydantic schema validation."""

    def __init__(self, message: str, details: list[str] | None = None) -> None:
        super().__init__(message)
        self.details = details or []


class MenuConstraintError(ClaudeResponseError):
    """Raised when menu plan violates business constraints."""

    def __init__(
        self,
        message: str,
        issue_codes: list[str] | None = None,
        issue_messages: list[str] | None = None,
        issues: list[dict[str, object]] | None = None,
        menu_stats: dict[str, object] | None = None,
        meal_inventory: dict[str, object] | None = None,
    ) -> None:
        super().__init__(message)
        self.issue_codes = issue_codes or []
        # Per-issue human-readable details (same order as issue_codes) used to
        # build a specific correction prompt; never returned to the client.
        self.issue_messages = issue_messages or []
        # Structured issues ({code, message, path, meta}) for targeted
        # correction prompts and diagnostics; never returned to the client.
        self.issues = issues or []
        # Quality metrics of the rejected plan (unique_recipe_count,
        # meal_count) used for retry regression detection.
        self.menu_stats = menu_stats or {}
        # Independent meal usage inventory for deterministic replacement prompts.
        self.meal_inventory = meal_inventory or {}


class ClaudeOutputTruncatedError(ClaudeResponseError):
    """Raised when the model exhausted max_tokens without a usable text block."""

    def __init__(
        self,
        message: str,
        *,
        stop_reason: str | None = None,
        output_tokens: int | None = None,
        raw_chars: int = 0,
    ) -> None:
        super().__init__(message)
        self.stop_reason = stop_reason
        self.output_tokens = output_tokens
        self.raw_chars = raw_chars


class ClaudeTimeoutError(ClaudeResponseError):
    """Raised when Claude request times out."""


class ClaudeUnavailableError(ClaudeResponseError):
    """Raised when Claude API is unavailable or returns an error status."""
