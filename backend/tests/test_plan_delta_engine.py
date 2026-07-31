"""Pure Plan Delta Engine: extraction, honesty gates, determinism."""

import pathlib

from plan_delta.engine import build_plan_delta
from plan_delta.extract import (
    extract_characteristics,
    parse_calories,
    parse_cook_time_minutes,
    parse_kbju,
)
from tests.menu_fixtures import build_valid_menu_dict, clone_menu


def _metric(delta, metric_id):
    return next(metric for metric in delta.metrics if metric.id == metric_id)


def test_parse_cook_time_minutes():
    assert parse_cook_time_minutes("30 мин") == 30
    assert parse_cook_time_minutes("1 ч") == 60
    assert parse_cook_time_minutes("1 ч 20 мин") == 80
    assert parse_cook_time_minutes("быстро") is None
    assert parse_cook_time_minutes("") is None
    assert parse_cook_time_minutes(None) is None


def test_parse_calories():
    assert parse_calories("350 ккал") == 350
    assert parse_calories("420") == 420
    assert parse_calories("много") is None
    assert parse_calories(None) is None


def test_parse_kbju_requires_all_components():
    assert parse_kbju("Б:20г Ж:10г У:30г") == {
        "protein": 20,
        "fat": 10,
        "carbs": 30,
    }
    assert parse_kbju("Б:20г Ж:10г") is None
    assert parse_kbju("") is None


def test_identical_plans_produce_unchanged_available_metrics():
    menu = build_valid_menu_dict(days=3)
    delta = build_plan_delta(menu, clone_menu(menu))

    for metric_id in ("total_cost", "basket_cost", "cooking_time_minutes",
                      "protein_grams", "fat_grams", "carbs_grams"):
        metric = _metric(delta, metric_id)
        assert metric.status == "available", metric_id
        assert metric.delta == 0
        assert metric.direction == "unchanged"

    changed = _metric(delta, "changed_meals")
    assert changed.status == "available"
    assert changed.delta == 0

    # Fixture recipes have no calories_per_portion: honestly unavailable.
    assert _metric(delta, "calories").status == "unavailable"
    # Fixture meals carry no cooking metadata: honestly unavailable.
    assert _metric(delta, "cooking_sessions").status == "unavailable"


def test_cost_delta_after_cheaper_replacement():
    original = build_valid_menu_dict(days=3)
    current = clone_menu(original)
    current["total_cost"] = float(original["total_cost"]) - 250.0
    current["days_plan"][1]["meals"][2]["recipe_name"] = "Новая запеканка"

    delta = build_plan_delta(original, current)

    cost = _metric(delta, "total_cost")
    assert cost.delta == -250.0
    assert cost.direction == "decreased"
    assert cost.original == float(original["total_cost"])
    assert cost.current == float(original["total_cost"]) - 250.0

    changed = _metric(delta, "changed_meals")
    assert changed.delta == 1
    assert changed.direction == "increased"


def test_unparseable_cook_time_disables_metric_for_both_variants():
    original = build_valid_menu_dict(days=3)
    current = clone_menu(original)
    current["recipes"][0]["cook_time"] = "быстро"

    delta = build_plan_delta(original, current)
    assert _metric(delta, "cooking_time_minutes").status == "unavailable"

    # The original alone is still parseable.
    characteristics = extract_characteristics(original)
    assert characteristics.cooking_time_minutes is not None


def test_structural_slot_mismatch_disables_changed_meals():
    original = build_valid_menu_dict(days=3)
    current = build_valid_menu_dict(days=2)
    delta = build_plan_delta(original, current)
    assert _metric(delta, "changed_meals").status == "unavailable"


def test_cooking_sessions_counted_from_metadata():
    original = build_valid_menu_dict(days=3)
    for day in original["days_plan"]:
        for meal in day["meals"]:
            meal["requires_cooking"] = False
    original["days_plan"][0]["meals"][0].update(
        {"requires_cooking": True, "cooking_instance_id": "cook_a"}
    )
    original["days_plan"][1]["meals"][0].update(
        {"requires_cooking": True, "cooking_instance_id": "cook_b"}
    )
    current = clone_menu(original)
    current["days_plan"][1]["meals"][0]["requires_cooking"] = False
    del current["days_plan"][1]["meals"][0]["cooking_instance_id"]

    delta = build_plan_delta(original, current)
    sessions = _metric(delta, "cooking_sessions")
    assert sessions.status == "available"
    assert sessions.original == 2
    assert sessions.current == 1
    assert sessions.delta == -1
    assert sessions.direction == "decreased"


def test_malformed_pieces_degrade_metric_not_whole_delta():
    original = build_valid_menu_dict(days=3)
    current = clone_menu(original)
    current["basket"] = "not a basket"

    delta = build_plan_delta(original, current)
    assert _metric(delta, "basket_cost").status == "unavailable"
    assert _metric(delta, "total_cost").status == "available"


def test_engine_is_deterministic():
    original = build_valid_menu_dict(days=3)
    current = clone_menu(original)
    current["total_cost"] = 100.0
    first = build_plan_delta(original, current)
    second = build_plan_delta(original, current)
    assert first.model_dump() == second.model_dump()


def test_plan_delta_layer_is_pure_and_isolated():
    package_dir = pathlib.Path(__file__).resolve().parents[1] / "plan_delta"
    for module in ("engine.py", "extract.py", "models.py"):
        source = (package_dir / module).read_text(encoding="utf-8")
        for forbidden in ("aiosqlite", "import database", "datetime.now", "import random"):
            assert forbidden not in source, f"{module} must stay pure: {forbidden}"

    backend_dir = pathlib.Path(__file__).resolve().parents[1]
    for package in ("decision", "learning", "strategy", "trends"):
        for path in (backend_dir / package).glob("*.py"):
            source = path.read_text(encoding="utf-8")
            assert "plan_delta" not in source, f"{path} must not depend on plan_delta"
