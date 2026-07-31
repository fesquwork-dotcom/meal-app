"""Pipeline: preview/generate build identical traces; parity matrix for rules."""

from decision.engine import DecisionEngine
from strategy import StrategyBuilder
from trace_fixtures import behavior_availability, memory_avoid, memory_faster


def test_same_inputs_produce_identical_trace():
    profile = {"goal": "budget", "days": 7, "cooktime": "medium", "budget": 3500.0}
    first = DecisionEngine().evaluate(profile, memory_faster(), behavior_availability("киноа"))
    second = DecisionEngine().evaluate(profile, memory_faster(), behavior_availability("киноа"))

    assert first.trace == second.trace
    assert first.trace.to_json() == second.trace.to_json()


def test_facade_build_exposes_trace_in_build_result():
    build_result = StrategyBuilder().build_with_reasons_from_inputs(
        {"goal": "home", "days": 5}
    )
    assert build_result.decision_trace is not None
    assert build_result.decision_trace.trace_version == 1
    assert len(build_result.decision_trace.entries) >= 14


def test_trace_metadata_does_not_affect_strategy_output():
    profile = {"goal": "budget", "days": 7, "cooktime": "medium"}
    via_engine = DecisionEngine().evaluate(profile)
    via_facade = StrategyBuilder().build_with_reasons_from_inputs(profile)

    assert via_engine.strategy.model_dump() == via_facade.strategy.model_dump()
    assert via_engine.reason_codes == via_facade.reason_codes


PARITY_MATRIX = [
    ("home", {"goal": "home", "days": 7, "cooktime": "medium"}, None, None),
    ("budget", {"goal": "budget", "days": 7, "cooktime": "medium", "budget": 3000.0}, None, None),
    ("healthy", {"goal": "healthy", "days": 5, "cooktime": "medium"}, None, None),
    (
        "explicit_cooking",
        {"goal": "home", "days": 5, "cooktime": "fast",
         "cooking_preferences": {"prefer_faster_meals": True}},
        None,
        None,
    ),
    ("memory_faster", {"goal": "home", "days": 5, "cooktime": ""}, "faster", None),
    ("behavior_availability", {"goal": "home", "days": 5}, None, "availability"),
    (
        "familiar_meals",
        {"goal": "home", "days": 5, "planning_preferences": {"prefer_familiar_meals": True}},
        None,
        None,
    ),
    ("exclusions", {"goal": "home", "days": 5, "allergies": "орехи"}, "avoid", None),
    ("legacy_profile", {}, None, None),
]


def _contexts(memory_kind, behavior_kind):
    memory = None
    if memory_kind == "faster":
        memory = memory_faster()
    elif memory_kind == "avoid":
        memory = memory_avoid("гречка")
    behavior = behavior_availability("киноа") if behavior_kind == "availability" else None
    return memory, behavior


def test_parity_strategy_output_unchanged_by_trace_integration():
    """Rule outcomes stay identical: trace generation is observation-only."""
    for name, profile, memory_kind, behavior_kind in PARITY_MATRIX:
        memory, behavior = _contexts(memory_kind, behavior_kind)

        engine_result = DecisionEngine().evaluate(profile, memory, behavior)
        facade_result = StrategyBuilder().build_with_reasons_from_inputs(
            profile, memory, behavior
        )

        assert engine_result.strategy.model_dump() == facade_result.strategy.model_dump(), name
        assert engine_result.reason_codes == facade_result.reason_codes, name
        assert engine_result.trace is not None, name
        assert engine_result.trace == facade_result.decision_trace, name


def test_parity_known_rule_outcomes():
    budget = DecisionEngine().evaluate(
        {"goal": "budget", "days": 7, "cooktime": "medium"}
    ).strategy
    assert budget.cook_days == [1, 3, 5, 7]
    assert budget.leftovers_enabled is True
    assert len(budget.shopping_days) > 1

    fast = DecisionEngine().evaluate({"goal": "home", "days": 5, "cooktime": "fast"}).strategy
    assert fast.cook_days == [1, 2, 3, 4, 5]
    assert fast.cooking_time_limit == 20

    healthy = DecisionEngine().evaluate({"goal": "healthy", "days": 5}).strategy
    assert healthy.cooking_time_limit == 45
