"""Immutable DecisionTrace models — engineering provenance for resolved decisions.

Trace is backend-only metadata: never sent to Claude, never rendered directly
to users, and never accepted from clients. All persisted values pass a
privacy allowlist; sensitive targets are represented as counts.
"""

from __future__ import annotations

import json
import logging
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from decision.versions import DECISION_TRACE_VERSION, DECISION_VERSION

logger = logging.getLogger(__name__)

SafeScalar = str | int | float | bool | None

TraceSource = Literal[
    "profile",
    "learned_preference",
    "memory",
    "behavior",
    "default",
    "rule",
    "runtime",
]
TraceRuleResult = Literal["applied", "rejected", "skipped"]
TraceConfidence = Literal["explicit", "deterministic", "inferred", "fallback"]
TraceDisplayType = Literal["string", "number", "boolean", "list", "null"]

# Lower number = higher precedence, matching effective priority order.
SOURCE_PRECEDENCE: dict[str, int] = {
    "profile": 1,
    "learned_preference": 2,
    "memory": 3,
    "behavior": 4,
    "rule": 5,
    "default": 6,
    "runtime": 7,
}

# Privacy allowlist for DecisionRuleTrace.input_summary keys. Values are
# non-sensitive scalars only: enumerated codes, numeric settings, counts,
# booleans, and day indexes. Free text, targets, and IDs are forbidden.
TRACE_INPUT_ALLOWLIST: frozenset[str] = frozenset(
    {
        "goal",
        "days",
        "budget",
        "weekly_budget",
        "daily_budget",
        "cooktime",
        "cooktime_explicit",
        "time_limit",
        "base_time_limit",
        "prefer_faster",
        "profile_value",
        "memory_value",
        "learned_value",
        "meal_types_count",
        "exclusion_count",
        "avoid_count",
        "applied_count",
        "ignored_count",
        "blocked_count",
        "signal_count",
        "insight_count",
        "cook_days_count",
        "shopping_days_count",
        "leftovers_enabled",
        "batch_allowed",
        "proteins_explicit",
        "preferred_count",
    }
)


def _validate_safe_scalar(value: object) -> bool:
    return value is None or isinstance(value, (str, int, float, bool))


class DecisionTraceValue(BaseModel):
    """Safe, serialization-ready decision outcome."""

    model_config = ConfigDict(frozen=True, extra="ignore")

    display_type: TraceDisplayType
    value: str | int | float | bool | list[str | int | float | bool] | None = None

    @field_validator("value")
    @classmethod
    def validate_value_shape(cls, value: object) -> object:
        if _validate_safe_scalar(value):
            return value
        if isinstance(value, list):
            for item in value:
                if item is None or not _validate_safe_scalar(item):
                    raise ValueError("trace value list items must be non-null safe scalars")
            return value
        raise ValueError("trace value must be a safe scalar or list of safe scalars")

    @classmethod
    def from_value(cls, value: object) -> "DecisionTraceValue":
        if value is None:
            return cls(display_type="null", value=None)
        if isinstance(value, bool):
            return cls(display_type="boolean", value=value)
        if isinstance(value, (int, float)):
            return cls(display_type="number", value=value)
        if isinstance(value, str):
            return cls(display_type="string", value=value)
        if isinstance(value, (list, tuple)):
            return cls(display_type="list", value=list(value))
        raise ValueError(f"unsupported trace value type: {type(value).__name__}")


class DecisionSourceReference(BaseModel):
    """Which input source participated in a decision, without raw payloads."""

    model_config = ConfigDict(frozen=True, extra="ignore")

    source: TraceSource
    field: str | None = None
    precedence: int
    applied: bool


class DecisionRuleTrace(BaseModel):
    """One evaluated rule branch: applied, rejected, or skipped by priority."""

    model_config = ConfigDict(frozen=True, extra="ignore")

    rule_code: str
    result: TraceRuleResult
    reason_code: str
    input_summary: dict[str, SafeScalar] = Field(default_factory=dict)

    @field_validator("input_summary")
    @classmethod
    def validate_input_summary(cls, value: dict[str, object]) -> dict[str, object]:
        for key, item in value.items():
            if key not in TRACE_INPUT_ALLOWLIST:
                raise ValueError(f"trace input key not allowlisted: {key}")
            if not _validate_safe_scalar(item):
                raise ValueError(f"trace input value must be a safe scalar: {key}")
        return value


class DecisionTraceEntry(BaseModel):
    """Full provenance for one decision key."""

    model_config = ConfigDict(frozen=True, extra="ignore")

    decision_key: str
    outcome: DecisionTraceValue
    sources: list[DecisionSourceReference] = Field(default_factory=list)
    applied_rules: list[DecisionRuleTrace] = Field(default_factory=list)
    rejected_rules: list[DecisionRuleTrace] = Field(default_factory=list)
    priority_winner: str | None = None
    confidence: TraceConfidence


class DecisionTrace(BaseModel):
    """Immutable, reproducible trace of one DecisionEngine resolution."""

    model_config = ConfigDict(frozen=True, extra="ignore")

    trace_version: int = DECISION_TRACE_VERSION
    decision_version: int = DECISION_VERSION
    entries: list[DecisionTraceEntry] = Field(default_factory=list)

    def to_json(self) -> str:
        return self.model_dump_json()

    @classmethod
    def from_json(cls, raw: str | None) -> "DecisionTrace | None":
        if not raw:
            return None
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            logger.warning("decision_trace_unavailable reason=malformed_json")
            return None
        if not isinstance(parsed, dict):
            logger.warning("decision_trace_unavailable reason=not_object")
            return None
        version = parsed.get("trace_version")
        if version != DECISION_TRACE_VERSION:
            logger.warning(
                "decision_trace_unavailable reason=unsupported_version trace_version=%s",
                version,
            )
            return None
        try:
            return cls.model_validate(parsed)
        except ValueError:
            logger.warning("decision_trace_unavailable reason=invalid_payload")
            return None


class DecisionTraceSummary(BaseModel):
    """Safe aggregate view for API/observability; contains no rule inputs."""

    model_config = ConfigDict(frozen=True, extra="ignore")

    trace_version: int
    decision_count: int
    source_counts: dict[str, int] = Field(default_factory=dict)
    applied_rule_count: int
    rejected_rule_count: int
    fallback_decision_count: int


def build_trace_summary(trace: DecisionTrace) -> DecisionTraceSummary:
    source_counts: dict[str, int] = {}
    applied = 0
    rejected = 0
    fallback = 0
    for entry in trace.entries:
        applied += len(entry.applied_rules)
        rejected += len(entry.rejected_rules)
        if entry.confidence == "fallback":
            fallback += 1
        for source in entry.sources:
            source_counts[source.source] = source_counts.get(source.source, 0) + 1
    return DecisionTraceSummary(
        trace_version=trace.trace_version,
        decision_count=len(trace.entries),
        source_counts=source_counts,
        applied_rule_count=applied,
        rejected_rule_count=rejected,
        fallback_decision_count=fallback,
    )
