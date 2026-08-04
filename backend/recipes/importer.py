"""Recipe Catalog importer: dry_run / validate_only / upsert / replace_catalog."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

import aiosqlite
import yaml

import config
import database
from menu_models import normalize_meal_name
from recipes.db import clear_catalog_tables, ensure_recipe_catalog_tables
from recipes.schemas import (
    IngredientsFileSchema,
    RecipeCardSchema,
    RecipeRelationSchema,
    RelationsFileSchema,
    reason_codes_to_json,
    utc_now_iso,
)
from recipes.validator import RecipeCatalogValidator, ValidationIssue, ValidationReport

logger = logging.getLogger(__name__)

ImportMode = Literal["dry_run", "validate_only", "upsert", "replace_catalog"]

DEFAULT_CATALOG_ROOT = Path(__file__).resolve().parents[1] / "recipe_catalog"


@dataclass
class ImportReport:
    mode: ImportMode
    recipes_read: int = 0
    ingredients_read: int = 0
    relations_read: int = 0
    recipes_written: int = 0
    ingredients_written: int = 0
    relations_written: int = 0
    validation: ValidationReport = field(default_factory=ValidationReport)
    messages: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.validation.ok

    def to_dict(self) -> dict[str, Any]:
        return {
            "mode": self.mode,
            "ok": self.ok,
            "recipes_read": self.recipes_read,
            "ingredients_read": self.ingredients_read,
            "relations_read": self.relations_read,
            "recipes_written": self.recipes_written,
            "ingredients_written": self.ingredients_written,
            "relations_written": self.relations_written,
            "errors": [
                {"code": e.code, "message": e.message, "path": e.path}
                for e in self.validation.errors
            ],
            "warnings": [
                {"code": w.code, "message": w.message, "path": w.path}
                for w in self.validation.warnings
            ],
            "messages": self.messages,
        }


def _load_yaml(path: Path) -> Any:
    with path.open(encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def load_catalog_files(catalog_root: Path) -> tuple[
    list[RecipeCardSchema],
    IngredientsFileSchema,
    list[RecipeRelationSchema],
]:
    ingredients_path = catalog_root / "ingredients" / "ingredients.yaml"
    relations_path = catalog_root / "relations" / "relations.yaml"

    ingredients_raw = _load_yaml(ingredients_path) or {"ingredients": []}
    ingredients_file = IngredientsFileSchema.model_validate(ingredients_raw)

    recipes: list[RecipeCardSchema] = []
    recipes_dir = catalog_root / "recipes"
    for meal_dir in ("breakfast", "lunch", "dinner", "snack"):
        folder = recipes_dir / meal_dir
        if not folder.is_dir():
            continue
        for path in sorted(folder.glob("*.yaml")):
            raw = _load_yaml(path)
            recipes.append(RecipeCardSchema.model_validate(raw))

    relations: list[RecipeRelationSchema] = []
    if relations_path.is_file():
        rel_raw = _load_yaml(relations_path) or {"relations": []}
        relations = RelationsFileSchema.model_validate(rel_raw).relations

    return recipes, ingredients_file, relations


class RecipeCatalogImporter:
    def __init__(
        self,
        catalog_root: Path | None = None,
        db_path: Path | str | None = None,
    ) -> None:
        self.catalog_root = catalog_root or DEFAULT_CATALOG_ROOT
        self.db_path = Path(db_path) if db_path else database.resolve_database_path()
        self.validator = RecipeCatalogValidator()

    async def import_catalog(self, mode: ImportMode = "upsert") -> ImportReport:
        report = ImportReport(mode=mode)
        try:
            recipes, ingredients_file, relations = load_catalog_files(self.catalog_root)
        except Exception as exc:  # noqa: BLE001 — surface file/schema errors
            report.validation.errors.append(
                ValidationIssue("LOAD_FAILED", str(exc))
            )
            report.messages.append(f"Failed to load catalog: {exc}")
            return report

        report.recipes_read = len(recipes)
        report.ingredients_read = len(ingredients_file.ingredients)
        report.relations_read = len(relations)

        ingredient_ids = {i.id for i in ingredients_file.ingredients}
        report.validation = self.validator.validate_catalog(
            recipes, ingredient_ids, relations
        )

        if mode in ("dry_run", "validate_only"):
            report.messages.append(f"{mode}: no database writes")
            return report

        if not report.validation.ok:
            report.messages.append("Import aborted due to validation errors")
            return report

        if mode == "replace_catalog":
            if config.ENVIRONMENT not in ("development", "test", "qa"):
                report.validation.errors.append(
                    ValidationIssue(
                        "REPLACE_FORBIDDEN",
                        "replace_catalog allowed only in development/test/qa",
                    )
                )
                return report

        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        async with aiosqlite.connect(self.db_path) as db:
            await ensure_recipe_catalog_tables(db)
            if mode == "replace_catalog":
                await clear_catalog_tables(db)
                report.messages.append("Cleared catalog tables only")

            now = utc_now_iso()
            for ingredient in ingredients_file.ingredients:
                await self._upsert_ingredient(db, ingredient, now)
                report.ingredients_written += 1

            for recipe in recipes:
                await self._upsert_recipe(db, recipe, now)
                report.recipes_written += 1

            for rel in relations:
                await self._upsert_relation(db, rel)
                report.relations_written += 1

            await db.commit()

        report.messages.append(f"Import complete ({mode})")
        return report

    async def _upsert_ingredient(self, db: aiosqlite.Connection, ingredient, now: str) -> None:
        await db.execute(
            """
            INSERT INTO ingredients (
                id, canonical_name, display_name, category, default_unit,
                piece_weight_g, density_g_per_ml, is_pantry_staple, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                canonical_name=excluded.canonical_name,
                display_name=excluded.display_name,
                category=excluded.category,
                default_unit=excluded.default_unit,
                piece_weight_g=excluded.piece_weight_g,
                density_g_per_ml=excluded.density_g_per_ml,
                is_pantry_staple=excluded.is_pantry_staple,
                updated_at=excluded.updated_at
            """,
            (
                ingredient.id,
                ingredient.canonical_name,
                ingredient.display_name,
                ingredient.category,
                ingredient.default_unit.value,
                ingredient.piece_weight_g,
                ingredient.density_g_per_ml,
                int(ingredient.is_pantry_staple),
                now,
                now,
            ),
        )
        await db.execute(
            "DELETE FROM ingredient_aliases WHERE ingredient_id = ?", (ingredient.id,)
        )
        for idx, alias in enumerate(ingredient.aliases, start=1):
            alias_id = f"{ingredient.id}_alias_{idx:03d}"
            normalized = normalize_meal_name(alias)
            await db.execute(
                """
                INSERT INTO ingredient_aliases (id, ingredient_id, alias, normalized_alias)
                VALUES (?, ?, ?, ?)
                """,
                (alias_id, ingredient.id, alias, normalized),
            )

    async def _upsert_recipe(
        self, db: aiosqlite.Connection, recipe: RecipeCardSchema, now: str
    ) -> None:
        await db.execute(
            """
            INSERT INTO recipes (
                id, slug, name, description, status, version, primary_meal_type,
                base_servings, yield_weight_g, recommended_portion_min_g,
                recommended_portion_max_g, scaling_mode, min_batch_servings,
                max_batch_servings, prep_time_minutes, cook_time_minutes,
                active_time_minutes, total_time_minutes, difficulty, requires_cooking,
                batch_friendly, leftover_friendly, storage_days, freezing_supported,
                budget_class, energy_density, protein_level, fiber_level, satiety_level,
                calories_per_100g, protein_g_per_100g, fat_g_per_100g, carbs_g_per_100g,
                image_key, created_at, updated_at
            ) VALUES (
                ?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?
            )
            ON CONFLICT(id) DO UPDATE SET
                slug=excluded.slug,
                name=excluded.name,
                description=excluded.description,
                status=excluded.status,
                version=excluded.version,
                primary_meal_type=excluded.primary_meal_type,
                base_servings=excluded.base_servings,
                yield_weight_g=excluded.yield_weight_g,
                recommended_portion_min_g=excluded.recommended_portion_min_g,
                recommended_portion_max_g=excluded.recommended_portion_max_g,
                scaling_mode=excluded.scaling_mode,
                min_batch_servings=excluded.min_batch_servings,
                max_batch_servings=excluded.max_batch_servings,
                prep_time_minutes=excluded.prep_time_minutes,
                cook_time_minutes=excluded.cook_time_minutes,
                active_time_minutes=excluded.active_time_minutes,
                total_time_minutes=excluded.total_time_minutes,
                difficulty=excluded.difficulty,
                requires_cooking=excluded.requires_cooking,
                batch_friendly=excluded.batch_friendly,
                leftover_friendly=excluded.leftover_friendly,
                storage_days=excluded.storage_days,
                freezing_supported=excluded.freezing_supported,
                budget_class=excluded.budget_class,
                energy_density=excluded.energy_density,
                protein_level=excluded.protein_level,
                fiber_level=excluded.fiber_level,
                satiety_level=excluded.satiety_level,
                calories_per_100g=excluded.calories_per_100g,
                protein_g_per_100g=excluded.protein_g_per_100g,
                fat_g_per_100g=excluded.fat_g_per_100g,
                carbs_g_per_100g=excluded.carbs_g_per_100g,
                image_key=excluded.image_key,
                updated_at=excluded.updated_at
            """,
            (
                recipe.id,
                recipe.slug,
                recipe.name,
                recipe.description,
                recipe.status.value,
                recipe.version,
                recipe.primary_meal_type.value,
                recipe.base_servings,
                recipe.yield_weight_g,
                recipe.recommended_portion_min_g,
                recipe.recommended_portion_max_g,
                recipe.scaling_mode.value,
                recipe.min_batch_servings,
                recipe.max_batch_servings,
                recipe.prep_time_minutes,
                recipe.cook_time_minutes,
                recipe.active_time_minutes,
                recipe.total_time_minutes,
                recipe.difficulty.value,
                int(recipe.requires_cooking),
                int(recipe.batch_friendly),
                int(recipe.leftover_friendly),
                recipe.storage_days,
                int(recipe.freezing_supported),
                recipe.budget_class.value,
                recipe.energy_density.value,
                recipe.protein_level.value,
                recipe.fiber_level.value,
                recipe.satiety_level.value,
                recipe.calories_per_100g,
                recipe.protein_g_per_100g,
                recipe.fat_g_per_100g,
                recipe.carbs_g_per_100g,
                recipe.image_key,
                now,
                now,
            ),
        )

        # Replace child rows for idempotent upsert.
        for table in (
            "recipe_step_ingredients",
            "recipe_steps",
            "recipe_ingredients",
            "recipe_meal_types",
            "recipe_cooking_methods",
            "recipe_equipment",
            "recipe_roles",
            "recipe_goal_scores",
            "recipe_tags",
        ):
            if table == "recipe_step_ingredients":
                await db.execute(
                    """
                    DELETE FROM recipe_step_ingredients WHERE recipe_step_id IN (
                        SELECT id FROM recipe_steps WHERE recipe_id = ?
                    )
                    """,
                    (recipe.id,),
                )
            else:
                await db.execute(f"DELETE FROM {table} WHERE recipe_id = ?", (recipe.id,))

        for mt in recipe.meal_types:
            await db.execute(
                """
                INSERT INTO recipe_meal_types (recipe_id, meal_type, is_primary)
                VALUES (?, ?, ?)
                """,
                (recipe.id, mt.meal_type.value, int(mt.is_primary)),
            )

        sort_to_id: dict[int, str] = {}
        for ing in recipe.ingredients:
            rid = ing.id or f"{recipe.id}_ing_{ing.sort_order:02d}"
            sort_to_id[ing.sort_order] = rid
            await db.execute(
                """
                INSERT INTO recipe_ingredients (
                    id, recipe_id, ingredient_id, quantity, unit, quantity_grams,
                    preparation, is_optional, ingredient_group, sort_order,
                    scaling_factor, rounding_increment
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    rid,
                    recipe.id,
                    ing.ingredient_id,
                    ing.quantity,
                    ing.unit.value,
                    ing.quantity_grams,
                    ing.preparation,
                    int(ing.is_optional),
                    ing.ingredient_group.value,
                    ing.sort_order,
                    ing.scaling_factor,
                    ing.rounding_increment,
                ),
            )

        for step in recipe.steps:
            sid = step.id or f"{recipe.id}_step_{step.step_number:02d}"
            await db.execute(
                """
                INSERT INTO recipe_steps (
                    id, recipe_id, step_number, instruction,
                    duration_minutes, active_minutes, temperature_c
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    sid,
                    recipe.id,
                    step.step_number,
                    step.instruction,
                    step.duration_minutes,
                    step.active_minutes,
                    step.temperature_c,
                ),
            )
            for ref in step.ingredient_refs:
                # ref may be recipe_ingredient id or sort_order as string/int
                target = ref
                if ref.isdigit():
                    target = sort_to_id.get(int(ref), ref)
                elif ref in sort_to_id.values():
                    target = ref
                else:
                    # try match by generated id pattern
                    for so, iid in sort_to_id.items():
                        if ref == iid or ref == str(so):
                            target = iid
                            break
                await db.execute(
                    """
                    INSERT OR IGNORE INTO recipe_step_ingredients
                    (recipe_step_id, recipe_ingredient_id) VALUES (?, ?)
                    """,
                    (sid, target),
                )

        for method in recipe.cooking_methods:
            await db.execute(
                """
                INSERT INTO recipe_cooking_methods (recipe_id, cooking_method)
                VALUES (?, ?)
                """,
                (recipe.id, method.value),
            )

        for eq in recipe.equipment:
            await db.execute(
                """
                INSERT INTO recipe_equipment (recipe_id, equipment, required)
                VALUES (?, ?, ?)
                """,
                (recipe.id, eq.equipment.value, int(eq.required)),
            )

        for role in recipe.roles:
            await db.execute(
                """
                INSERT INTO recipe_roles (recipe_id, role, score, reason)
                VALUES (?, ?, ?, ?)
                """,
                (recipe.id, role.role.value, role.score, role.reason),
            )

        for goal in recipe.goal_scores:
            await db.execute(
                """
                INSERT INTO recipe_goal_scores (recipe_id, goal, score, reason_codes_json)
                VALUES (?, ?, ?, ?)
                """,
                (
                    recipe.id,
                    goal.goal.value,
                    goal.score,
                    reason_codes_to_json(goal.reason_codes),
                ),
            )

        for tag in recipe.tags:
            await db.execute(
                """
                INSERT INTO recipe_tags (recipe_id, tag_type, tag_value)
                VALUES (?, ?, ?)
                """,
                (recipe.id, tag.tag_type.value, tag.tag_value),
            )

    async def _upsert_relation(
        self, db: aiosqlite.Connection, rel: RecipeRelationSchema
    ) -> None:
        meta = json.dumps(rel.metadata, ensure_ascii=False) if rel.metadata else None
        await db.execute(
            """
            INSERT INTO recipe_relations (
                id, source_recipe_id, target_recipe_id, relation_type,
                score, reason, metadata_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                source_recipe_id=excluded.source_recipe_id,
                target_recipe_id=excluded.target_recipe_id,
                relation_type=excluded.relation_type,
                score=excluded.score,
                reason=excluded.reason,
                metadata_json=excluded.metadata_json
            """,
            (
                rel.id,
                rel.source_recipe_id,
                rel.target_recipe_id,
                rel.relation_type.value,
                rel.score,
                rel.reason,
                meta,
            ),
        )
        # Also handle unique (source, target, type) when id changes
        await db.execute(
            """
            DELETE FROM recipe_relations
            WHERE source_recipe_id = ? AND target_recipe_id = ?
              AND relation_type = ? AND id != ?
            """,
            (
                rel.source_recipe_id,
                rel.target_recipe_id,
                rel.relation_type.value,
                rel.id,
            ),
        )
