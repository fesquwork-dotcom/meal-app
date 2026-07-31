"""Version constants for Decision Engine persistence and strategy coupling."""

DECISION_VERSION = 1

# Versioned independently from strategy/decision/explanation versions.
DECISION_TRACE_VERSION = 1

# Public, user-facing rendering contract for DecisionTrace.
DECISION_EXPLANATION_VERSION = 1

# Retrospective, write-once evaluation contract. Independent from decisions,
# traces, and public explanation versions.
DECISION_OUTCOME_VERSION = 1

# WeeklyStrategy.strategy_version stamped when DecisionContext is produced/persisted.
# Existing snapshots remain readable: 1..4 without decision_context_json.
STRATEGY_VERSION_WITH_DECISIONS = 5
