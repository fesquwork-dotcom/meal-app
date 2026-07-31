import asyncio

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

import config
import database
import main
from meal_types import (
    DEFAULT_MEAL_TYPES,
    meal_types_from_count,
    normalize_days_plan_payload,
    resolve_meal_types,
)
from menu_models import MenuPlan
from menu_validation import MenuValidationRequest, validate_menu_plan
from tests.menu_fixtures import build_valid_menu_dict, clone_menu
from tests.profile_test_helpers import generate_with_token, issue_preview_token, save_profile


def _validate(menu_dict: dict[str, object], **request_overrides):
    menu_plan = MenuPlan.model_validate(menu_dict)
    request = MenuValidationRequest(
        days=request_overrides.pop("days", 3),
        budget=request_overrides.pop("budget", 3000.0),
        meal_types=request_overrides.pop("meal_types", ["breakfast", "lunch", "dinner"]),
        meals_per_day=request_overrides.pop("meals_per_day", 3),
        persons=request_overrides.pop("persons", 2),
        cooktime=request_overrides.pop("cooktime", "medium"),
        allergies=request_overrides.pop("allergies", "нет"),
        **request_overrides,
    )
    return validate_menu_plan(menu_plan, request)


def test_breakfast_lunch_dinner_valid():
    result = _validate(build_valid_menu_dict(meal_types=["breakfast", "lunch", "dinner"]))
    assert result.is_valid is True


def test_breakfast_dinner_valid():
    menu = build_valid_menu_dict(days=2, meal_types=["breakfast", "dinner"])
    result = _validate(menu, days=2, meal_types=["breakfast", "dinner"], meals_per_day=2)
    assert result.is_valid is True


def test_dinner_only_valid():
    menu = build_valid_menu_dict(days=1, meal_types=["dinner"])
    result = _validate(menu, days=1, meal_types=["dinner"], meals_per_day=1)
    assert result.is_valid is True


def test_snack_valid():
    menu = build_valid_menu_dict(days=1, meal_types=["snack"])
    result = _validate(menu, days=1, meal_types=["snack"], meals_per_day=1)
    assert result.is_valid is True


def test_snack_missing_when_requested_fails():
    legacy_day = [{"day": "День 1", "breakfast": "Овсянка", "lunch": "Борщ", "dinner": "Рыба"}]
    normalized = normalize_days_plan_payload(legacy_day, ["breakfast", "lunch", "dinner", "snack"])
    menu = build_valid_menu_dict(days=1, meal_types=["breakfast", "lunch", "dinner", "snack"])
    menu["days_plan"] = normalized
    result = _validate(
        menu,
        days=1,
        meal_types=["breakfast", "lunch", "dinner", "snack"],
        meals_per_day=4,
    )
    assert not result.is_valid
    assert any(issue.code == "MEAL_TYPE_MISSING" for issue in result.errors)


def test_unexpected_lunch_fails():
    menu = build_valid_menu_dict(days=1, meal_types=["breakfast", "dinner"])
    menu["days_plan"][0]["meals"].append({"type": "lunch", "recipe_name": "Борщ"})
    result = _validate(menu, days=1, meal_types=["breakfast", "dinner"], meals_per_day=2)
    assert not result.is_valid
    assert any(issue.code == "MEAL_TYPE_UNEXPECTED" for issue in result.errors)


def test_duplicate_breakfast_fails():
    menu = build_valid_menu_dict(days=1, meal_types=["breakfast", "dinner"])
    menu["days_plan"][0]["meals"].append(
        {"type": "breakfast", "recipe_name": menu["days_plan"][0]["meals"][0]["recipe_name"]}
    )
    result = _validate(menu, days=1, meal_types=["breakfast", "dinner"], meals_per_day=2)
    assert not result.is_valid
    assert any(issue.code == "MEAL_TYPE_DUPLICATE" for issue in result.errors)


def test_unknown_type_schema_error():
    menu = clone_menu(build_valid_menu_dict(days=1))
    menu["days_plan"][0]["meals"][0]["type"] = "brunch"
    with pytest.raises(ValidationError):
        MenuPlan.model_validate(menu)


def test_old_profile_fallback_resolve_meal_types():
    assert resolve_meal_types(None, 2) == ["breakfast", "dinner"]
    assert resolve_meal_types(None, 3) == list(DEFAULT_MEAL_TYPES)
    assert resolve_meal_types(None, None) == list(DEFAULT_MEAL_TYPES)


def test_meal_types_from_count_mapping():
    assert meal_types_from_count(1) == ["breakfast"]
    assert meal_types_from_count(4) == ["breakfast", "lunch", "dinner", "snack"]


@pytest.fixture
def client():
    return TestClient(main.app)


@pytest.fixture(autouse=True)
def _configure_auth_and_db(tmp_path, monkeypatch):
    db_path = tmp_path / "meal-types-api.db"
    monkeypatch.setattr(config, "DATABASE_PATH", str(db_path))
    asyncio.run(database.init_db())
    monkeypatch.setattr(config, "TELEGRAM_BOT_TOKEN", "token")
    monkeypatch.setattr(config, "ALLOW_DEV_AUTH", True)
    monkeypatch.setattr(config, "DEV_TELEGRAM_USER_ID", 42)


def test_sqlite_migration_adds_meal_types_column(tmp_path, monkeypatch):
    db_path = tmp_path / "profiles.db"
    monkeypatch.setattr(config, "DATABASE_PATH", str(db_path))

    async def run() -> set[str]:
        await database.init_db()
        async with database.aiosqlite.connect(db_path) as db:
            cursor = await db.execute("PRAGMA table_info(profiles)")
            columns = {row[1] for row in await cursor.fetchall()}
            await cursor.close()
        return columns

    columns = asyncio.run(run())
    assert "meal_types" in columns


def test_sqlite_profile_roundtrip_with_meal_types(tmp_path, monkeypatch):
    db_path = tmp_path / "profiles.db"
    monkeypatch.setattr(config, "DATABASE_PATH", str(db_path))

    async def run() -> dict | None:
        await database.init_db()
        await database.save_profile(
            7,
            {
                "first_name": "Test",
                "budget": 2500,
                "days": 5,
                "persons": 2,
                "proteins": ["chicken"],
                "goal": "home",
                "cooktime": "medium",
                "allergies": "нет",
                "store": "any",
                "meal_types": ["breakfast", "dinner"],
            },
        )
        return await database.get_profile(7)

    profile = asyncio.run(run())
    assert profile is not None
    assert profile["meal_types"] == ["breakfast", "dinner"]
    assert profile["meals_per_day"] == 2


def test_meals_per_day_recalculated_from_meal_types():
    assert len(resolve_meal_types(["breakfast", "snack"], meals_per_day=3)) == 2


def test_snack_meal_recipe_consistency():
    menu = build_valid_menu_dict(days=1, meal_types=["snack"])
    result = _validate(menu, days=1, meal_types=["snack"], meals_per_day=1)
    assert result.is_valid is True
    snack_meal = result.menu_plan.days_plan[0].meals[0]
    assert snack_meal.type == "snack"
    assert snack_meal.recipe_name


def test_budget_and_allergies_still_work_with_meal_types():
    menu = clone_menu(build_valid_menu_dict(days=1, meal_types=["breakfast", "dinner"]))
    menu["total_cost"] = 5000
    for item in menu["basket"][0]["items"]:
        item["price"] = 5000
    result = _validate(
        menu,
        days=1,
        meal_types=["breakfast", "dinner"],
        meals_per_day=2,
        budget=3000,
    )
    assert not result.is_valid
    assert any(issue.code == "BUDGET_EXCEEDED" for issue in result.errors)

    menu = clone_menu(build_valid_menu_dict(days=1, meal_types=["dinner"]))
    menu["recipes"][0]["ingredients"][0]["name"] = "молоко"
    result = _validate(
        menu,
        days=1,
        meal_types=["dinner"],
        meals_per_day=1,
        allergies="молоко",
    )
    assert not result.is_valid
    assert any(issue.code == "ALLERGY_VIOLATION" for issue in result.errors)


def test_api_uses_persisted_meal_types(client, monkeypatch):
    captured: dict[str, object] = {}

    async def fake_generate_menu(**kwargs):
        captured.update(kwargs)
        return build_valid_menu_dict(days=1, meal_types=kwargs["meal_types"])

    monkeypatch.setattr(main, "generate_menu", fake_generate_menu)

    save_profile(
        client,
        expected_revision=0,
        days=1,
        meal_types=["breakfast", "dinner"],
        meals_per_day=2,
    )
    token = issue_preview_token(client)
    response = generate_with_token(client, token)

    assert response.status_code == 200
    assert captured["meal_types"] == ["breakfast", "dinner"]
    assert captured["meals_per_day"] == 2


def test_api_auth_still_required_without_dev_auth(monkeypatch):
    monkeypatch.setattr(config, "ALLOW_DEV_AUTH", False)
    monkeypatch.setattr(config, "TELEGRAM_BOT_TOKEN", "token")

    client = TestClient(main.app)
    response = client.post("/api/generate-menu", json={"preview_token": "token"})
    assert response.status_code == 401
