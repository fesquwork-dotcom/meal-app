from learned_preferences.models import (
    LearnedPreference,
    LearnedPreferenceEvidence,
)
from decision.learned_preferences_context import (
    LearnedPreferencesContext,
    build_learned_preferences_context,
)


def _preference(kind: str, status: str = "active", version: int = 1):
    return LearnedPreference(
        id=f"private:{kind}",
        type=kind,
        status=status,
        source="decision_learning",
        confidence="strong",
        title="t",
        summary="s",
        evidence=LearnedPreferenceEvidence(
            source="decision_learning", confidence="strong", basis="b"
        ),
        version=version,
    )


def test_flag_off_returns_privacy_safe_empty_context():
    context = build_learned_preferences_context(
        [_preference("prefer_familiar_meals")], enabled=False
    )
    assert context == LearnedPreferencesContext.empty(enabled=False)
    assert "private:" not in repr(context)


def test_only_active_supported_types_are_mapped_in_stable_order():
    context = build_learned_preferences_context(
        [
            _preference("prefer_fast_meals"),
            _preference("stable_cook_days"),
            _preference("prefer_familiar_meals", "revoked"),
            _preference("prefer_familiar_meals"),
            _preference("prefer_fast_meals", "candidate"),
        ],
        enabled=True,
    )
    assert context.prefer_familiar_meals is True
    assert context.prefer_faster_meals is True
    assert [item.preference_type for item in context.source_preferences] == [
        "prefer_familiar_meals",
        "prefer_fast_meals",
    ]


def test_duplicate_type_is_deterministically_deduplicated():
    context = build_learned_preferences_context(
        [
            _preference("prefer_fast_meals", version=1),
            _preference("prefer_fast_meals", version=2),
        ],
        enabled=True,
    )
    assert len(context.source_preferences) == 1
    assert context.source_preferences[0].preference_version == 1
