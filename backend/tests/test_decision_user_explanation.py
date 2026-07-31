"""Allowlisted, deterministic DecisionTrace → user explanation templates."""

from decision.engine import DecisionEngine
from decision.user_explanation import build_decision_explanations
from trace_fixtures import behavior_availability, memory_faster


def _item(collection, key):
    return next(item for item in collection.explanations if item.decision_key == key)


def _build(profile, memory=None, behavior=None):
    result = DecisionEngine().evaluate(profile, memory, behavior)
    return build_decision_explanations(result.trace, strategy=result.strategy)


def test_cook_days_explanation_and_rejected_alternative():
    collection = _build({"goal": "budget", "days": 7, "cooktime": "medium"})
    item = _item(collection, "cooking.cook_days")
    assert item.title == "Дни готовки"
    assert item.outcome == "Дни 1, 3, 5 и 7"
    assert "заготовки" in item.explanation
    assert "Ежедневная готовка не выбрана" in item.alternative_note


def test_fast_daily_cooking_explanation():
    collection = _build({"goal": "home", "days": 5, "cooktime": "fast"})
    item = _item(collection, "cooking.cook_days")
    assert item.outcome == "Каждый день"
    assert "короткий лимит" in item.explanation


def test_explicit_budget_has_profile_provenance():
    collection = _build({"budget": 3500.0, "days": 5})
    item = _item(collection, "budget.weekly")
    assert item.outcome == "Около 3 500 ₽"
    assert item.source_label == "Настройки профиля"
    assert item.confidence_label == "Задано вами"


def test_fallback_budget_explanation():
    collection = _build({"days": 5})
    item = _item(collection, "budget.weekly")
    assert "стандартное значение" in item.explanation
    assert item.confidence_label == "Использовано стандартное значение"


def test_profile_false_wins_memory_without_technical_words():
    collection = _build(
        {
            "cooktime": "medium",
            "cooking_preferences": {"prefer_faster_meals": False},
        },
        memory_faster(),
    )
    item = _item(collection, "cooking.prefer_faster")
    assert item.outcome == "Выключено"
    assert "Настройка профиля имеет приоритет" in item.alternative_note
    assert "skipped" not in item.alternative_note


def test_memory_provenance_explanation():
    collection = _build({"cooktime": "medium"}, memory_faster())
    item = _item(collection, "cooking.prefer_faster")
    assert item.source_label == "Подтверждённые предпочтения"
    assert "прошлых замен" in item.explanation


def test_behavior_availability_explanation():
    collection = _build({}, None, behavior_availability("киноа"))
    item = _item(collection, "behavior.availability_avoid_products")
    assert item.outcome == "Наблюдения учтены"
    assert item.source_label == "Подтверждённые наблюдения"
    assert "киноа" not in item.model_dump_json()


def test_output_stable_and_limited():
    result = DecisionEngine().evaluate({"goal": "budget", "days": 7})
    first = build_decision_explanations(result.trace, strategy=result.strategy)
    second = build_decision_explanations(result.trace, strategy=result.strategy)
    assert first == second
    assert len(first.explanations) <= 8
    assert all(len(item.supporting_points) <= 4 for item in first.explanations)
