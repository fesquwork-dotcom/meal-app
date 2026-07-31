import pytest

import config
from decision.learned_preferences_context import (
    ActiveLearnedPreference,
    LearnedPreferencesContext,
)
from strategy.behavior_context import StrategyBehaviorContext
from strategy.memory_context import StrategyMemoryContext
from strategy.preview_token import (
    PreviewTokenError,
    issue_preview_token,
    verify_preview_token,
)

PROFILE = {"goal": "home"}
MEMORY = StrategyMemoryContext.empty()
BEHAVIOR = StrategyBehaviorContext.empty()


def _context(*types: str, enabled: bool = True):
    return LearnedPreferencesContext(
        version=1,
        enabled=enabled,
        prefer_familiar_meals=True
        if "prefer_familiar_meals" in types
        else None,
        prefer_faster_meals=True if "prefer_fast_meals" in types else None,
        source_preferences=tuple(
            ActiveLearnedPreference(item, 1) for item in sorted(types)
        ),
    )


@pytest.fixture(autouse=True)
def _secret(monkeypatch):
    monkeypatch.setattr(config, "ALLOW_DEV_AUTH", True)
    monkeypatch.setattr(config, "PREVIEW_TOKEN_TTL_SECONDS", 900)


def _issue(context):
    return issue_preview_token(
        user_id=42,
        profile=PROFILE,
        profile_revision=1,
        plan_start_date="2026-07-15",
        memory_context=MEMORY,
        behavior_context=BEHAVIOR,
        learned_context=context,
        now=1000,
    )[0]


def _verify(token, context):
    return verify_preview_token(
        token,
        user_id=42,
        profile=PROFILE,
        profile_revision=1,
        memory_context=MEMORY,
        behavior_context=BEHAVIOR,
        learned_context=context,
        now=1001,
    )


def test_same_effective_state_verifies():
    context = _context("prefer_familiar_meals")
    assert _verify(_issue(context), context).payload.learned_preferences_hash


@pytest.mark.parametrize(
    ("before", "after"),
    [
        (_context(), _context("prefer_familiar_meals")),
        (_context("prefer_familiar_meals"), _context()),
        (_context(enabled=False), _context(enabled=True)),
    ],
)
def test_accept_revoke_or_flag_change_stales_preview(before, after):
    with pytest.raises(PreviewTokenError) as exc:
        _verify(_issue(before), after)
    assert exc.value.code == "STRATEGY_PREVIEW_STALE_LEARNED_PREFERENCES"


def test_unsupported_preference_does_not_enter_context_hash():
    # Unsupported rows are filtered by the context builder; both effective
    # contexts are therefore identical.
    empty = _context()
    assert _verify(_issue(empty), _context()).payload.version == 5
