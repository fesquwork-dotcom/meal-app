"""Cooking preferences domain model (Sprint 5.22).

Separates relative cooking preferences (e.g. prefer faster meals within a limit)
from the concrete cooktime hard limit stored on the profile.
"""

from __future__ import annotations

import json

from pydantic import BaseModel, ConfigDict

PREFER_FASTER_PROMOTED_ID = "cooking:prefer_faster_meals"


class CookingPreferences(BaseModel):
    """Permanent cooking preferences owned by the profile."""

    model_config = ConfigDict(extra="ignore")

    prefer_faster_meals: bool | None = None


class CookingPreferencesInput(BaseModel):
    """Cooking preferences accepted from Profile PUT."""

    model_config = ConfigDict(extra="forbid")

    prefer_faster_meals: bool | None = None


def parse_cooking_preferences(profile: dict[str, object] | None) -> CookingPreferences:
    if not profile:
        return CookingPreferences()
    raw = profile.get("cooking_preferences")
    if raw is None:
        return CookingPreferences()
    if isinstance(raw, CookingPreferences):
        return raw
    if isinstance(raw, dict):
        if "prefer_faster_meals" not in raw:
            return CookingPreferences()
        value = raw.get("prefer_faster_meals")
        if value is None:
            return CookingPreferences(prefer_faster_meals=None)
        if isinstance(value, bool):
            return CookingPreferences(prefer_faster_meals=value)
    return CookingPreferences()


def cooking_preferences_from_json(raw: str | None) -> CookingPreferences:
    if not raw:
        return CookingPreferences()
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return CookingPreferences()
    if not isinstance(parsed, dict):
        return CookingPreferences()
    if "prefer_faster_meals" not in parsed:
        return CookingPreferences()
    value = parsed.get("prefer_faster_meals")
    if value is None:
        return CookingPreferences(prefer_faster_meals=None)
    if isinstance(value, bool):
        return CookingPreferences(prefer_faster_meals=value)
    return CookingPreferences()


def serialize_cooking_preferences_json(preferences: CookingPreferences) -> str | None:
    """Serializes explicit true/false preferences (legacy helper)."""
    if preferences.prefer_faster_meals is None:
        return None
    return json.dumps(
        {"prefer_faster_meals": preferences.prefer_faster_meals},
        ensure_ascii=False,
    )


def cooking_preferences_to_db_json(profile: dict[str, object]) -> str | None:
    """Persists cooking preferences from a profile dict, including explicit null."""
    raw = profile.get("cooking_preferences")
    if raw is None:
        return None
    if isinstance(raw, dict) and "prefer_faster_meals" in raw:
        value = raw["prefer_faster_meals"]
        if value is not None and not isinstance(value, bool):
            return None
        return json.dumps({"prefer_faster_meals": value}, ensure_ascii=False)
    return None


def cooking_preferences_to_response_dict(raw: str | None) -> dict[str, object] | None:
    """Maps stored JSON to API response; NULL column stays absent (legacy)."""
    if not raw:
        return None
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return None
    if isinstance(parsed, dict) and "prefer_faster_meals" in parsed:
        value = parsed.get("prefer_faster_meals")
        if isinstance(value, bool) or value is None:
            return {"prefer_faster_meals": value}
    return None


def cooking_preferences_dict(
    preferences: CookingPreferences,
    *,
    present: bool = True,
) -> dict[str, object] | None:
    if not present:
        return None
    return {"prefer_faster_meals": preferences.prefer_faster_meals}
