"""Shared profile limits for writes and legacy-read compatibility."""

PROFILE_DAYS_MIN = 1
PROFILE_DAYS_MAX = 7
PROFILE_BUDGET_MIN = 500.0
PROFILE_BUDGET_MAX = 50_000.0


def clamp_legacy_days(value: object, *, default: int) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        return default
    return max(PROFILE_DAYS_MIN, min(value, PROFILE_DAYS_MAX))


def clamp_legacy_budget(value: object, *, default: float) -> float:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return default
    return max(PROFILE_BUDGET_MIN, min(float(value), PROFILE_BUDGET_MAX))
