"""Backend-only decision trace comparison (foundation for Sprint 6.3/6.4)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from decision.trace_models import DecisionTrace, DecisionTraceEntry


class DecisionTraceEntryChange(BaseModel):
    model_config = ConfigDict(frozen=True, extra="ignore")

    decision_key: str
    value_changed: bool = False
    winner_changed: bool = False
    applied_rules_changed: bool = False
    confidence_changed: bool = False


class DecisionTraceDiff(BaseModel):
    model_config = ConfigDict(frozen=True, extra="ignore")

    current_trace_available: bool
    next_trace_available: bool
    changed_keys: list[str] = Field(default_factory=list)
    changes: list[DecisionTraceEntryChange] = Field(default_factory=list)

    @property
    def has_changes(self) -> bool:
        return bool(self.changed_keys)


def _entries_by_key(trace: DecisionTrace) -> dict[str, DecisionTraceEntry]:
    return {entry.decision_key: entry for entry in trace.entries}


def _applied_rule_codes(entry: DecisionTraceEntry) -> tuple[str, ...]:
    return tuple(sorted(rule.rule_code for rule in entry.applied_rules))


def _compare_entries(
    key: str,
    current: DecisionTraceEntry,
    nxt: DecisionTraceEntry,
) -> DecisionTraceEntryChange | None:
    value_changed = current.outcome != nxt.outcome
    winner_changed = current.priority_winner != nxt.priority_winner
    applied_changed = _applied_rule_codes(current) != _applied_rule_codes(nxt)
    confidence_changed = current.confidence != nxt.confidence

    if not (value_changed or winner_changed or applied_changed or confidence_changed):
        return None
    return DecisionTraceEntryChange(
        decision_key=key,
        value_changed=value_changed,
        winner_changed=winner_changed,
        applied_rules_changed=applied_changed,
        confidence_changed=confidence_changed,
    )


def compare_decision_traces(
    current: DecisionTrace | None,
    next_trace: DecisionTrace | None,
) -> DecisionTraceDiff:
    """Compares by decision key; ordering differences never produce a diff."""
    if current is None or next_trace is None:
        return DecisionTraceDiff(
            current_trace_available=current is not None,
            next_trace_available=next_trace is not None,
        )

    current_entries = _entries_by_key(current)
    next_entries = _entries_by_key(next_trace)

    changes: list[DecisionTraceEntryChange] = []
    for key in sorted(set(current_entries) | set(next_entries)):
        current_entry = current_entries.get(key)
        next_entry = next_entries.get(key)
        if current_entry is None or next_entry is None:
            changes.append(
                DecisionTraceEntryChange(
                    decision_key=key,
                    value_changed=True,
                    winner_changed=True,
                    applied_rules_changed=True,
                )
            )
            continue
        change = _compare_entries(key, current_entry, next_entry)
        if change is not None:
            changes.append(change)

    return DecisionTraceDiff(
        current_trace_available=True,
        next_trace_available=True,
        changed_keys=[change.decision_key for change in changes],
        changes=changes,
    )
