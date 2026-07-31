"""Allowlisted QA scenario names (Sprint 9.5)."""

from __future__ import annotations

from typing import Literal

QaScenarioName = Literal[
    "fresh_user",
    "profile_ready",
    "active_week",
    "completed_history",
    "learning_candidate",
    "learned_preference_active",
    "learned_preference_insufficient",
    "learned_preference_emerging",
    "learned_preference_effective",
    "learned_preference_ineffective",
    "review_dismissed",
    "review_new_generation",
    "legacy_partial_data",
]

QA_SCENARIO_NAMES: frozenset[str] = frozenset(
    {
        "fresh_user",
        "profile_ready",
        "active_week",
        "completed_history",
        "learning_candidate",
        "learned_preference_active",
        "learned_preference_insufficient",
        "learned_preference_emerging",
        "learned_preference_effective",
        "learned_preference_ineffective",
        "review_dismissed",
        "review_new_generation",
        "legacy_partial_data",
    }
)
