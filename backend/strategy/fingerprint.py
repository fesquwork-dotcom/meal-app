"""Deterministic hashes for signed preview token binding."""

from __future__ import annotations

import hashlib
import json

from strategy.behavior_context import StrategyBehaviorContext
from strategy.memory_context import StrategyMemoryContext
from decision.learned_preferences_context import LearnedPreferencesContext

PROFILE_HASH_LENGTH = 32
MEMORY_HASH_LENGTH = 32
BEHAVIOR_HASH_LENGTH = 32
LEARNED_PREFERENCES_HASH_LENGTH = 32


def _stable_json(payload: dict[str, object]) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode(
        "utf-8"
    )


def _constraints_for_hash(raw: object) -> list[str]:
    if not isinstance(raw, list):
        return []
    parts: list[str] = []
    for entry in raw:
        if isinstance(entry, dict):
            kind = str(entry.get("kind") or "")
            canonical = str(entry.get("canonical_value") or entry.get("value") or "")
            if canonical:
                parts.append(f"{kind}:{canonical}")
    return sorted(parts)


def normalize_profile_for_hash(profile: dict[str, object]) -> dict[str, object]:
    meal_types = profile.get("meal_types")
    proteins = profile.get("proteins")
    return {
        "goal": profile.get("goal"),
        "days": profile.get("days"),
        "budget": profile.get("budget"),
        "persons": profile.get("persons"),
        "meal_types": sorted(meal_types) if isinstance(meal_types, list) else meal_types,
        "meals_per_day": profile.get("meals_per_day"),
        "proteins": sorted(proteins) if isinstance(proteins, list) else proteins,
        "cooktime": profile.get("cooktime"),
        "cooking_preferences": profile.get("cooking_preferences"),
        "planning_preferences": profile.get("planning_preferences"),
        "allergies": profile.get("allergies"),
        "dietary_constraints": _constraints_for_hash(profile.get("dietary_constraints")),
        "store": profile.get("store"),
    }


def compute_profile_hash(profile: dict[str, object]) -> str:
    digest = hashlib.sha256(_stable_json(normalize_profile_for_hash(profile))).hexdigest()
    return digest[:PROFILE_HASH_LENGTH]


def compute_memory_hash(
    memory_context: StrategyMemoryContext,
    *,
    memory_unavailable: bool = False,
) -> str:
    signal_parts = sorted(
        f"{signal.signal_id}:{signal.updated_at}:{signal.signal_type}:"
        f"{signal.confirmation_source}:{signal.target_value}"
        for signal in memory_context.signals
    )
    payload = {
        "signals": signal_parts,
        "memory_unavailable": memory_unavailable,
    }
    digest = hashlib.sha256(_stable_json(payload)).hexdigest()
    return digest[:MEMORY_HASH_LENGTH]


def _target_hash(target_key: str | None) -> str:
    if not target_key:
        return ""
    return hashlib.sha256(target_key.encode("utf-8")).hexdigest()[:16]


def compute_behavior_hash(
    behavior_context: StrategyBehaviorContext,
    *,
    behavior_unavailable: bool = False,
) -> str:
    insight_parts = sorted(
        f"{insight.insight_id}:{insight.insight_type.value}:confirmed:"
        f"{insight.rule_version}:{insight.updated_at}:{_target_hash(insight.target_key)}"
        for insight in behavior_context.insights
    )
    payload = {
        "insights": insight_parts,
        "behavior_unavailable": behavior_unavailable,
    }
    digest = hashlib.sha256(_stable_json(payload)).hexdigest()
    return digest[:BEHAVIOR_HASH_LENGTH]


def compute_learned_preferences_hash(
    context: LearnedPreferencesContext,
    *,
    unavailable: bool = False,
) -> str:
    """Bind only effective supported inputs and rollout state; never IDs/evidence."""
    payload = {
        "enabled": context.enabled,
        "context_version": context.version,
        "preferences": [
            {
                "type": item.preference_type,
                "version": item.preference_version,
                "active": True,
            }
            for item in context.source_preferences
        ],
        "unavailable": unavailable,
    }
    digest = hashlib.sha256(_stable_json(payload)).hexdigest()
    return digest[:LEARNED_PREFERENCES_HASH_LENGTH]


def compute_preview_fingerprint(
    profile: dict[str, object],
    memory_context: StrategyMemoryContext,
    *,
    memory_unavailable: bool = False,
) -> str:
    """Deprecated compatibility helper — prefer signed preview tokens."""
    return compute_profile_hash(profile)[:16] + compute_memory_hash(
        memory_context, memory_unavailable=memory_unavailable
    )[:16]
