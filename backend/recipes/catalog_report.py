"""Coverage report for Recipe Catalog."""

from __future__ import annotations

import json
import logging
from collections import Counter
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import aiosqlite

import database
from recipes.db import ensure_recipe_catalog_tables
from recipes.enums import RecipeStatus
from recipes.importer import DEFAULT_CATALOG_ROOT, load_catalog_files
from recipes.validator import RecipeCatalogValidator

logger = logging.getLogger(__name__)


@dataclass
class CatalogCoverageReport:
    total_recipes: int = 0
    active_recipes: int = 0
    draft_recipes: int = 0
    recipes_by_primary_meal_type: dict[str, int] = field(default_factory=dict)
    recipes_by_all_meal_types: dict[str, int] = field(default_factory=dict)
    recipes_by_budget_class: dict[str, int] = field(default_factory=dict)
    recipes_by_goal: dict[str, int] = field(default_factory=dict)
    recipes_by_role: dict[str, int] = field(default_factory=dict)
    recipes_by_protein_source: dict[str, int] = field(default_factory=dict)
    quick_recipes: int = 0
    batch_friendly_recipes: int = 0
    leftover_friendly_recipes: int = 0
    recipes_without_images: int = 0
    recipes_without_relations: int = 0
    recipes_without_goal_scores: int = 0
    ingredients_count: int = 0
    unused_ingredients: list[str] = field(default_factory=list)
    unknown_references: list[str] = field(default_factory=list)
    validation_errors: list[dict[str, Any]] = field(default_factory=list)
    validation_warnings: list[dict[str, Any]] = field(default_factory=list)
    relations_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=indent)


async def build_catalog_report(
    db_path: Path | str | None = None,
    catalog_root: Path | None = None,
) -> CatalogCoverageReport:
    path = Path(db_path) if db_path else database.resolve_database_path()
    root = catalog_root or DEFAULT_CATALOG_ROOT
    report = CatalogCoverageReport()

    # File-level validation (even if DB empty)
    try:
        recipes, ingredients_file, relations = load_catalog_files(root)
        ingredient_ids = {i.id for i in ingredients_file.ingredients}
        validation = RecipeCatalogValidator().validate_catalog(
            recipes, ingredient_ids, relations
        )
        report.validation_errors = [
            {"code": e.code, "message": e.message, "path": e.path}
            for e in validation.errors
        ]
        report.validation_warnings = [
            {"code": w.code, "message": w.message, "path": w.path}
            for w in validation.warnings
        ]
    except Exception as exc:  # noqa: BLE001
        report.validation_errors.append(
            {"code": "LOAD_FAILED", "message": str(exc), "path": None}
        )

    if not path.exists():
        return report

    async with aiosqlite.connect(path) as db:
        db.row_factory = aiosqlite.Row
        await ensure_recipe_catalog_tables(db)

        cur = await db.execute("SELECT * FROM recipes")
        recipes = await cur.fetchall()
        report.total_recipes = len(recipes)
        report.active_recipes = sum(
            1 for r in recipes if r["status"] == RecipeStatus.ACTIVE.value
        )
        report.draft_recipes = sum(
            1 for r in recipes if r["status"] == RecipeStatus.DRAFT.value
        )

        primary = Counter(r["primary_meal_type"] for r in recipes)
        report.recipes_by_primary_meal_type = dict(primary)
        budget = Counter(r["budget_class"] for r in recipes)
        report.recipes_by_budget_class = dict(budget)
        report.batch_friendly_recipes = sum(1 for r in recipes if r["batch_friendly"])
        report.leftover_friendly_recipes = sum(
            1 for r in recipes if r["leftover_friendly"]
        )
        report.recipes_without_images = sum(1 for r in recipes if not r["image_key"])
        report.quick_recipes = sum(1 for r in recipes if r["total_time_minutes"] <= 30)

        cur = await db.execute(
            "SELECT meal_type, COUNT(*) AS c FROM recipe_meal_types GROUP BY meal_type"
        )
        report.recipes_by_all_meal_types = {
            r["meal_type"]: r["c"] for r in await cur.fetchall()
        }

        cur = await db.execute(
            "SELECT goal, COUNT(*) AS c FROM recipe_goal_scores GROUP BY goal"
        )
        report.recipes_by_goal = {r["goal"]: r["c"] for r in await cur.fetchall()}

        cur = await db.execute(
            "SELECT role, COUNT(*) AS c FROM recipe_roles GROUP BY role"
        )
        report.recipes_by_role = {r["role"]: r["c"] for r in await cur.fetchall()}

        cur = await db.execute(
            """
            SELECT tag_value, COUNT(*) AS c FROM recipe_tags
            WHERE tag_type = 'protein_source' GROUP BY tag_value
            """
        )
        report.recipes_by_protein_source = {
            r["tag_value"]: r["c"] for r in await cur.fetchall()
        }

        cur = await db.execute("SELECT COUNT(*) AS c FROM recipe_relations")
        report.relations_count = int((await cur.fetchone())["c"])

        related = set()
        cur = await db.execute(
            "SELECT source_recipe_id, target_recipe_id FROM recipe_relations"
        )
        for row in await cur.fetchall():
            related.add(row["source_recipe_id"])
            related.add(row["target_recipe_id"])
        report.recipes_without_relations = sum(
            1 for r in recipes if r["id"] not in related
        )

        cur = await db.execute("SELECT DISTINCT recipe_id FROM recipe_goal_scores")
        with_goals = {r["recipe_id"] for r in await cur.fetchall()}
        report.recipes_without_goal_scores = sum(
            1 for r in recipes if r["id"] not in with_goals
        )

        cur = await db.execute("SELECT id FROM ingredients")
        all_ings = [r["id"] for r in await cur.fetchall()]
        report.ingredients_count = len(all_ings)

        cur = await db.execute("SELECT DISTINCT ingredient_id FROM recipe_ingredients")
        used = {r["ingredient_id"] for r in await cur.fetchall()}
        report.unused_ingredients = sorted(set(all_ings) - used)

        cur = await db.execute(
            """
            SELECT DISTINCT ri.ingredient_id FROM recipe_ingredients ri
            LEFT JOIN ingredients i ON i.id = ri.ingredient_id
            WHERE i.id IS NULL
            """
        )
        report.unknown_references = [r["ingredient_id"] for r in await cur.fetchall()]

    return report


def log_catalog_report(report: CatalogCoverageReport) -> None:
    logger.info("Recipe catalog coverage:\n%s", report.to_json())
