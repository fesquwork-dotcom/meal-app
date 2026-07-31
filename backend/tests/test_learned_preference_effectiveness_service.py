"""Service-level coverage for Learned Preference effectiveness."""

from __future__ import annotations

import asyncio
from datetime import date, timedelta

from learned_preferences.effectiveness_models import (
    LearnedPreferencePlanObservation,
)
from learned_preferences.effectiveness_service import (
    LearnedPreferenceEffectivenessService,
)


def _obs(i: int, **kwargs):
    defaults = {
        "plan_date": date(2026, 1, 1) + timedelta(days=i * 7),
        "preference_applied": True,
        "replacement_count": 0,
        "planned_meal_count": 10,
        "meal_suited_count": 2,
        "meal_cooked_count": 0,
        "plan_completed": True,
        "decision_outcome": "successful",
    }
    defaults.update(kwargs)
    return LearnedPreferencePlanObservation(**defaults)


class _Repo:
    def __init__(self, observations):
        self._observations = observations
        self.calls = 0

    async def load_applied_plan_observations(self, *_args, **_kwargs):
        self.calls += 1
        return list(self._observations)


def test_service_presents_effective_result():
    repo = _Repo([_obs(i) for i in range(4)])
    service = LearnedPreferenceEffectivenessService(
        observation_repository=repo  # type: ignore[arg-type]
    )
    payload = asyncio.run(service.get_effectiveness(1, "prefer_familiar_meals"))
    assert payload is not None
    assert payload.status == "effective"
    assert payload.confidence == "established"
    assert "устойчиво" in payload.title.lower() or "положительн" in payload.title


def test_service_returns_none_on_repository_failure():
    class Boom:
        async def load_applied_plan_observations(self, *_args, **_kwargs):
            raise RuntimeError("db down")

    service = LearnedPreferenceEffectivenessService(
        observation_repository=Boom()  # type: ignore[arg-type]
    )
    assert (
        asyncio.run(service.get_effectiveness(1, "prefer_familiar_meals"))
        is None
    )


def test_get_all_skips_unsupported_types():
    repo = _Repo([_obs(i) for i in range(2)])
    service = LearnedPreferenceEffectivenessService(
        observation_repository=repo  # type: ignore[arg-type]
    )
    result = asyncio.run(
        service.get_all_effectiveness(
            1, ["prefer_familiar_meals", "stable_cook_days"]  # type: ignore[list-item]
        )
    )
    assert result["prefer_familiar_meals"] is not None
    assert result["stable_cook_days"] is None
    assert repo.calls == 1
