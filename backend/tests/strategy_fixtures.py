"""Reusable weekly strategy fixtures for persistence tests."""

from __future__ import annotations

from strategy.builder import StrategyBuilder


def build_test_profile(**overrides: object) -> dict:
    profile = {
        "goal": "home",
        "days": 3,
        "budget": 3000.0,
        "meal_types": ["breakfast", "lunch", "dinner"],
        "meals_per_day": 3,
        "proteins": ["any"],
        "cooktime": "medium",
        "allergies": "нет",
        "store": "any",
    }
    profile.update(overrides)
    return profile


def build_test_strategy(**profile_overrides: object):
    return StrategyBuilder().build(build_test_profile(**profile_overrides))
