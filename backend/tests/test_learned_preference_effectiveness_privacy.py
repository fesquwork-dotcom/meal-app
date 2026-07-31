"""Privacy contract for Learned Preference effectiveness wire payloads."""

from __future__ import annotations

import json
from datetime import date, timedelta

from learned_preferences.effectiveness import (
    evaluate_learned_preference_effectiveness,
)
from learned_preferences.effectiveness_models import (
    LearnedPreferencePlanObservation,
)
from learned_preferences.effectiveness_presentation import present_effectiveness


_FORBIDDEN_FRAGMENTS = (
    "strategy_id",
    "menu_plan_id",
    "event_id",
    "recommendation_id",
    "decision_key",
    "user_id",
    "trace",
    "raw_evidence",
    "secret-",
)


def _obs(i: int, **kwargs):
    defaults = {
        "plan_date": date(2026, 2, 1) + timedelta(days=i * 7),
        "preference_applied": True,
        "replacement_count": 0,
        "planned_meal_count": 10,
        "meal_suited_count": 2,
        "meal_cooked_count": 1,
        "plan_completed": True,
        "decision_outcome": "successful",
    }
    defaults.update(kwargs)
    return LearnedPreferencePlanObservation(**defaults)


def _walk(value, path="$"):
    if isinstance(value, dict):
        for key, item in value.items():
            yield f"{path}.{key}", key, item
            yield from _walk(item, f"{path}.{key}")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            yield from _walk(item, f"{path}[{index}]")
    else:
        yield path, None, value


def test_effectiveness_response_has_no_internal_identifiers():
    result = evaluate_learned_preference_effectiveness(
        "prefer_familiar_meals", [_obs(i) for i in range(4)]
    )
    payload = present_effectiveness(result).model_dump()
    text = json.dumps(payload, ensure_ascii=False).lower()
    for fragment in _FORBIDDEN_FRAGMENTS:
        assert fragment not in text, fragment
    for _, key, value in _walk(payload):
        if isinstance(key, str):
            assert key not in {
                "strategy_id",
                "menu_plan_id",
                "event_ids",
                "positive_evidence_count",
                "negative_evidence_count",
            }
        if isinstance(value, str):
            lowered = value.lower()
            assert "uuid" not in lowered
            assert "strategy-" not in lowered
