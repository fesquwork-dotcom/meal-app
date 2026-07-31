"""Domain exceptions for weekly strategy validation."""


class StrategyValidationError(Exception):
    """Raised when strategy is invalid or conflicts with a menu generation request."""

    def __init__(self, message: str, code: str | None = None) -> None:
        super().__init__(message)
        self.code = code or "STRATEGY_VALIDATION_ERROR"


class StrategyComplianceError(Exception):
    """Raised when a generated menu violates WeeklyStrategy constraints."""

    def __init__(self, message: str, issues: list[object]) -> None:
        super().__init__(message)
        self.issues = issues
        self.issue_codes = [getattr(issue, "code", "STRATEGY_COMPLIANCE_ERROR") for issue in issues]
        self.messages = [getattr(issue, "message", str(issue)) for issue in issues]
        self.paths = [getattr(issue, "path", None) for issue in issues]


class StrategyPersistenceError(Exception):
    """Raised when weekly strategy cannot be saved or loaded from storage."""


class UnsupportedStrategyVersionError(StrategyPersistenceError):
    """Raised when persisted strategy_version is not supported by this application."""

    def __init__(self, version: int) -> None:
        super().__init__(f"Unsupported strategy version: {version}")
        self.version = version


class StrategyNotFoundError(StrategyPersistenceError):
    """Raised when a strategy record does not exist or is not owned by the user."""


class StrategyPreviewStaleError(Exception):
    """Raised when preview fingerprint no longer matches current profile/memory state."""

    def __init__(self, message: str = "Strategy preview is stale") -> None:
        super().__init__(message)
        self.code = "STRATEGY_PREVIEW_STALE"


class ConflictNotFoundError(Exception):
    """Raised when a conflict ID is not present in the current preview state."""

    def __init__(self, message: str = "Conflict not found") -> None:
        super().__init__(message)
        self.code = "CONFLICT_NOT_FOUND"
