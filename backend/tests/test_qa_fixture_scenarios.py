"""Alias coverage file for Sprint 9.5 scenario list."""

from __future__ import annotations

from dev_tools.scenarios import QA_SCENARIO_NAMES


def test_required_phase9_scenarios_present():
    required = {
        "fresh_user",
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
    assert required.issubset(QA_SCENARIO_NAMES)
