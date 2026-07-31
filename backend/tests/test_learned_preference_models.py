"""Learned Preference models, allowlists, and closed-contract guarantees."""

from __future__ import annotations

from typing import get_args

import pytest
from pydantic import ValidationError

from learned_preferences.models import (
    LEARNED_PREFERENCE_VERSION,
    LearnedPreference,
    LearnedPreferenceEvidence,
    LearnedPreferenceType,
)
from learned_preferences.presentation import (
    LEARNED_PREFERENCE_BASIS,
    LEARNED_PREFERENCE_SUMMARIES,
    LEARNED_PREFERENCE_TITLES,
)


def _preference(**overrides) -> LearnedPreference:
    base = dict(
        id="v1:prefer_familiar_meals",
        type="prefer_familiar_meals",
        status="candidate",
        source="decision_learning",
        confidence="strong",
        title="t",
        summary="s",
        evidence=LearnedPreferenceEvidence(
            source="decision_learning", confidence="strong", basis="b"
        ),
    )
    base.update(overrides)
    return LearnedPreference(**base)


def test_presentation_allowlists_cover_every_type():
    types = set(get_args(LearnedPreferenceType))
    assert set(LEARNED_PREFERENCE_TITLES) == types
    assert set(LEARNED_PREFERENCE_SUMMARIES) == types
    assert set(LEARNED_PREFERENCE_BASIS) == types


def test_v1_declares_five_types():
    assert set(get_args(LearnedPreferenceType)) == {
        "prefer_familiar_meals",
        "avoid_unavailable_products",
        "prefer_fast_meals",
        "stable_cook_days",
        "stable_shopping_days",
    }


def test_default_version_is_one():
    assert _preference().version == LEARNED_PREFERENCE_VERSION == 1


def test_models_are_frozen_and_reject_unknown_fields():
    preference = _preference()
    with pytest.raises(ValidationError):
        _preference(unexpected=1)
    with pytest.raises(ValidationError):
        preference.status = "active"  # type: ignore[misc]
    with pytest.raises(ValidationError):
        LearnedPreferenceEvidence(
            source="decision_learning",
            confidence="strong",
            basis="b",
            secret="leak",  # type: ignore[call-arg]
        )


def test_invalid_type_and_status_are_rejected():
    with pytest.raises(ValidationError):
        _preference(type="calorie_target")
    with pytest.raises(ValidationError):
        _preference(status="deleted")


def test_evidence_never_accepts_identifier_fields():
    # The evidence model has no field for identifiers, so any is rejected.
    for forbidden in ("strategy_id", "decision_id", "event_id", "user_id"):
        with pytest.raises(ValidationError):
            LearnedPreferenceEvidence(
                source="decision_learning",
                confidence="strong",
                basis="b",
                **{forbidden: "x"},  # type: ignore[arg-type]
            )
