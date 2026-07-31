"""Deterministic insight identity keys."""

from __future__ import annotations

import hashlib
import uuid

from behavior.constants import BEHAVIOR_RULES_VERSION, BehaviorInsightType


def new_insight_id() -> str:
    return f"bi_{uuid.uuid4().hex}"


def compute_insight_key(
    *,
    user_id: int,
    insight_type: BehaviorInsightType | str,
    target_key: str | None,
    rule_version: int = BEHAVIOR_RULES_VERSION,
) -> str:
    type_value = (
        insight_type.value if isinstance(insight_type, BehaviorInsightType) else str(insight_type)
    )
    target_part = target_key or ""
    payload = f"{user_id}|{type_value}|{target_part}|{rule_version}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
