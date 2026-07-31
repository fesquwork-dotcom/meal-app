"""Planning preferences domain model (Sprint 5.27)."""

from __future__ import annotations

import json

from pydantic import BaseModel, ConfigDict

PREFER_FAMILIAR_MEALS_RECOMMENDATION_KEY = "prefer_familiar_meals"


class PlanningPreferences(BaseModel):
    """Permanent planning preferences owned by the profile."""

    model_config = ConfigDict(extra="ignore")

    prefer_familiar_meals: bool | None = None


class PlanningPreferencesInput(BaseModel):
    """Planning preferences accepted from Profile PUT."""

    model_config = ConfigDict(extra="forbid")

    prefer_familiar_meals: bool | None = None


def parse_planning_preferences(profile: dict[str, object] | None) -> PlanningPreferences:
    if not profile:
        return PlanningPreferences()
    raw = profile.get("planning_preferences")
    if raw is None:
        return PlanningPreferences()
    if isinstance(raw, PlanningPreferences):
        return raw
    if isinstance(raw, dict):
        if "prefer_familiar_meals" not in raw:
            return PlanningPreferences()
        value = raw.get("prefer_familiar_meals")
        if value is None:
            return PlanningPreferences(prefer_familiar_meals=None)
        if isinstance(value, bool):
            return PlanningPreferences(prefer_familiar_meals=value)
    return PlanningPreferences()


def planning_preferences_from_json(raw: str | None) -> PlanningPreferences:
    if not raw:
        return PlanningPreferences()
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return PlanningPreferences()
    if not isinstance(parsed, dict):
        return PlanningPreferences()
    if "prefer_familiar_meals" not in parsed:
        return PlanningPreferences()
    value = parsed.get("prefer_familiar_meals")
    if value is None:
        return PlanningPreferences(prefer_familiar_meals=None)
    if isinstance(value, bool):
        return PlanningPreferences(prefer_familiar_meals=value)
    return PlanningPreferences()


def planning_preferences_to_db_json(profile: dict[str, object]) -> str | None:
    """Persists planning preferences from a profile dict, including explicit null."""
    raw = profile.get("planning_preferences")
    if raw is None:
        return None
    if isinstance(raw, dict) and "prefer_familiar_meals" in raw:
        value = raw["prefer_familiar_meals"]
        if value is not None and not isinstance(value, bool):
            return None
        return json.dumps({"prefer_familiar_meals": value}, ensure_ascii=False)
    return None


def planning_preferences_to_response_dict(raw: str | None) -> dict[str, object] | None:
    """Maps stored JSON to API response; NULL column stays absent (legacy)."""
    if not raw:
        return None
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return None
    if isinstance(parsed, dict) and "prefer_familiar_meals" in parsed:
        value = parsed.get("prefer_familiar_meals")
        if isinstance(value, bool) or value is None:
            return {"prefer_familiar_meals": value}
    return None


def planning_preferences_dict(
    preferences: PlanningPreferences,
    *,
    present: bool = True,
) -> dict[str, object] | None:
    if not present:
        return None
    return {"prefer_familiar_meals": preferences.prefer_familiar_meals}


def serialize_planning_preferences_json(preferences: PlanningPreferences) -> str:
    return json.dumps(
        {"prefer_familiar_meals": preferences.prefer_familiar_meals},
        ensure_ascii=False,
    )
