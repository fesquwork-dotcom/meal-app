"""Trace builder: entries, outcomes, applied/rejected rules per decision group."""

from decision.engine import DecisionEngine
from trace_fixtures import behavior_availability, memory_avoid, memory_faster

EXPECTED_KEYS = [
    "budget.weekly",
    "budget.daily",
    "cooking.time_limit",
    "cooking.prefer_faster",
    "cooking.cook_days",
    "cooking.batch_allowed",
    "protein.preferred",
    "protein.excluded",
    "shopping.days",
    "meal.leftovers_enabled",
    "meal.repeat_breakfasts",
    "meal.repeat_lunches",
    "meal.repeat_dinners",
    "exclusions.count",
    "behavior.availability_avoid_products",
    "planning.prefer_familiar_meals",
]


def _entry(trace, key):
    return next(entry for entry in trace.entries if entry.decision_key == key)


def test_trace_covers_all_expected_decision_keys():
    result = DecisionEngine().evaluate({"goal": "budget", "days": 7, "cooktime": "medium"})
    assert [entry.decision_key for entry in result.trace.entries] == EXPECTED_KEYS


def test_trace_outcomes_match_strategy_values():
    result = DecisionEngine().evaluate(
        {"goal": "budget", "days": 7, "cooktime": "medium", "budget": 3500.0}
    )
    strategy = result.strategy
    trace = result.trace

    assert _entry(trace, "budget.weekly").outcome.value == strategy.budget
    assert _entry(trace, "budget.daily").outcome.value == strategy.budget / strategy.days
    assert _entry(trace, "cooking.time_limit").outcome.value == strategy.cooking_time_limit
    assert _entry(trace, "cooking.prefer_faster").outcome.value == strategy.prefer_faster_meals
    assert _entry(trace, "cooking.cook_days").outcome.value == strategy.cook_days
    assert _entry(trace, "shopping.days").outcome.value == strategy.shopping_days
    assert _entry(trace, "meal.leftovers_enabled").outcome.value == strategy.leftovers_enabled
    assert _entry(trace, "protein.preferred").outcome.value == strategy.preferred_proteins
    assert (
        _entry(trace, "planning.prefer_familiar_meals").outcome.value
        == strategy.prefer_familiar_meals
    )


def test_budget_cook_days_trace_has_batch_applied_and_fast_rejected():
    result = DecisionEngine().evaluate({"goal": "budget", "days": 7, "cooktime": "medium"})
    entry = _entry(result.trace, "cooking.cook_days")

    applied_codes = [rule.rule_code for rule in entry.applied_rules]
    rejected_codes = [rule.rule_code for rule in entry.rejected_rules]
    assert applied_codes == ["COOK_DAYS_BATCH_GOAL"]
    assert "COOK_DAYS_DAILY_FAST" in rejected_codes
    assert entry.applied_rules[0].input_summary == {"goal": "budget", "days": 7}
    assert entry.confidence == "deterministic"


def test_fast_cooktime_trace_skips_batch_rule():
    result = DecisionEngine().evaluate({"goal": "budget", "days": 7, "cooktime": "fast"})
    entry = _entry(result.trace, "cooking.cook_days")

    assert entry.applied_rules[0].rule_code == "COOK_DAYS_DAILY_FAST"
    skipped = [rule for rule in entry.rejected_rules if rule.result == "skipped"]
    assert skipped and skipped[0].rule_code == "COOK_DAYS_BATCH_GOAL"


def test_memory_faster_trace_records_time_downgrade():
    result = DecisionEngine().evaluate({"cooktime": ""}, memory_faster())
    entry = _entry(result.trace, "cooking.time_limit")

    # cooktime implicit (medium) + memory faster → downgrade 45 → 20.
    assert entry.outcome.value == 20
    downgrade = [r for r in entry.applied_rules if r.rule_code == "MEMORY_FASTER_TIME_DOWNGRADE"]
    assert downgrade and downgrade[0].input_summary["base_time_limit"] == 45
    assert entry.priority_winner == "memory"
    assert entry.confidence == "inferred"


def test_explicit_cooktime_rejects_memory_downgrade():
    result = DecisionEngine().evaluate({"cooktime": "medium"}, memory_faster())
    entry = _entry(result.trace, "cooking.time_limit")

    assert entry.outcome.value == 45
    rejected = [r for r in entry.rejected_rules if r.rule_code == "MEMORY_FASTER_TIME_DOWNGRADE"]
    assert rejected and rejected[0].reason_code == "PROFILE_COOKTIME_EXPLICIT"
    assert entry.priority_winner == "profile"
    assert entry.confidence == "explicit"


def test_behavior_availability_traced_as_count_only():
    result = DecisionEngine().evaluate(
        {"goal": "home", "days": 5}, None, behavior_availability("киноа")
    )
    entry = _entry(result.trace, "behavior.availability_avoid_products")

    assert entry.outcome.value == 1
    assert entry.priority_winner == "behavior"
    assert entry.confidence == "inferred"
    assert entry.applied_rules[0].input_summary == {"avoid_count": 1}


def test_memory_avoid_traced_in_exclusions_count():
    result = DecisionEngine().evaluate({"allergies": "нет"}, memory_avoid("гречка"))
    entry = _entry(result.trace, "exclusions.count")

    assert entry.outcome.value == 1
    assert entry.applied_rules[0].reason_code == "MEMORY_AVOID_INGREDIENT_APPLIED"
    assert entry.applied_rules[0].input_summary == {"avoid_count": 1}
