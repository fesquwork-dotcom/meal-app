"""Pure, privacy-safe Learned Preferences input for Decision resolution."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from learned_preferences.models import LearnedPreference

LEARNED_PREFERENCES_CONTEXT_VERSION = 1
SUPPORTED_DECISION_TYPES = frozenset(
    {"prefer_familiar_meals", "prefer_fast_meals"}
)


@dataclass(frozen=True)
class ActiveLearnedPreference:
    preference_type: str
    preference_version: int


@dataclass(frozen=True)
class LearnedPreferencesContext:
    version: int
    enabled: bool
    prefer_familiar_meals: bool | None
    prefer_faster_meals: bool | None
    source_preferences: tuple[ActiveLearnedPreference, ...]

    @classmethod
    def empty(cls, *, enabled: bool = False) -> "LearnedPreferencesContext":
        return cls(
            version=LEARNED_PREFERENCES_CONTEXT_VERSION,
            enabled=enabled,
            prefer_familiar_meals=None,
            prefer_faster_meals=None,
            source_preferences=(),
        )


def build_learned_preferences_context(
    preferences: Sequence[LearnedPreference],
    *,
    enabled: bool,
) -> LearnedPreferencesContext:
    """Build a stable context from active, supported preferences only."""
    if not enabled:
        return LearnedPreferencesContext.empty(enabled=False)

    by_type: dict[str, ActiveLearnedPreference] = {}
    for preference in preferences:
        if (
            preference.status != "active"
            or preference.type not in SUPPORTED_DECISION_TYPES
        ):
            continue
        by_type.setdefault(
            preference.type,
            ActiveLearnedPreference(
                preference_type=preference.type,
                preference_version=preference.version,
            ),
        )

    sources = tuple(by_type[key] for key in sorted(by_type))
    return LearnedPreferencesContext(
        version=LEARNED_PREFERENCES_CONTEXT_VERSION,
        enabled=True,
        prefer_familiar_meals=True
        if "prefer_familiar_meals" in by_type
        else None,
        prefer_faster_meals=True if "prefer_fast_meals" in by_type else None,
        source_preferences=sources,
    )
