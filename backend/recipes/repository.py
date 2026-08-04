"""Recipe Catalog repository (SQLite via aiosqlite)."""

from __future__ import annotations

import json
from contextlib import asynccontextmanager
from decimal import Decimal
from pathlib import Path
from typing import Any, AsyncIterator, Iterable

import aiosqlite

import database
from recipes.db import ensure_recipe_catalog_tables
from recipes.enums import (
    BudgetClass,
    CookingMethod,
    Difficulty,
    EnergyDensity,
    EquipmentType,
    FiberLevel,
    GoalType,
    IngredientGroup,
    IngredientUnit,
    MealType,
    ProteinLevel,
    RecipeRole,
    RecipeStatus,
    RelationType,
    SatietyLevel,
    ScalingMode,
    TagType,
)
from recipes.models import (
    Ingredient,
    IngredientAlias,
    Recipe,
    RecipeEquipmentItem,
    RecipeGoalScore,
    RecipeIngredient,
    RecipeMealTypeLink,
    RecipeRelation,
    RecipeRoleItem,
    RecipeStep,
    RecipeTag,
)
from recipes.schemas import parse_reason_codes_json


def _db_path(path: Path | str | None = None) -> Path:
    if path is not None:
        return Path(path)
    return database.resolve_database_path()


def _bool(value: Any) -> bool:
    return bool(value)


def _dec(value: Any) -> Decimal:
    return Decimal(str(value))


def _dec_opt(value: Any) -> Decimal | None:
    if value is None:
        return None
    return Decimal(str(value))


class RecipeRepository:
    def __init__(self, db_path: Path | str | None = None) -> None:
        self.db_path = _db_path(db_path)

    @asynccontextmanager
    async def _connection(self) -> AsyncIterator[aiosqlite.Connection]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            await ensure_recipe_catalog_tables(db)
            yield db

    async def get_by_id(self, recipe_id: str) -> Recipe | None:
        async with self._connection() as db:
            cur = await db.execute("SELECT * FROM recipes WHERE id = ?", (recipe_id,))
            row = await cur.fetchone()
            if row is None:
                return None
            return await self._hydrate_recipe(db, dict(row), with_deps=False)

    async def get_by_slug(self, slug: str) -> Recipe | None:
        async with self._connection() as db:
            cur = await db.execute("SELECT * FROM recipes WHERE slug = ?", (slug,))
            row = await cur.fetchone()
            if row is None:
                return None
            return await self._hydrate_recipe(db, dict(row), with_deps=False)

    async def list_active(self) -> list[Recipe]:
        return await self._list_where("status = ?", (RecipeStatus.ACTIVE.value,))

    async def list_by_meal_type(self, meal_type: MealType | str) -> list[Recipe]:
        mt = meal_type.value if isinstance(meal_type, MealType) else meal_type
        async with self._connection() as db:
            cur = await db.execute(
                """
                SELECT r.* FROM recipes r
                JOIN recipe_meal_types m ON m.recipe_id = r.id
                WHERE m.meal_type = ? AND r.status = ?
                ORDER BY r.id
                """,
                (mt, RecipeStatus.ACTIVE.value),
            )
            rows = await cur.fetchall()
            return [await self._hydrate_recipe(db, dict(r), with_deps=False) for r in rows]

    async def list_by_goal(self, goal: GoalType | str, min_score: float = 0.5) -> list[Recipe]:
        g = goal.value if isinstance(goal, GoalType) else goal
        async with self._connection() as db:
            cur = await db.execute(
                """
                SELECT r.* FROM recipes r
                JOIN recipe_goal_scores g ON g.recipe_id = r.id
                WHERE g.goal = ? AND g.score >= ? AND r.status = ?
                ORDER BY g.score DESC, r.id
                """,
                (g, min_score, RecipeStatus.ACTIVE.value),
            )
            rows = await cur.fetchall()
            return [await self._hydrate_recipe(db, dict(r), with_deps=False) for r in rows]

    async def list_by_role(self, role: RecipeRole | str, min_score: float = 0.5) -> list[Recipe]:
        rv = role.value if isinstance(role, RecipeRole) else role
        async with self._connection() as db:
            cur = await db.execute(
                """
                SELECT r.* FROM recipes r
                JOIN recipe_roles rr ON rr.recipe_id = r.id
                WHERE rr.role = ? AND rr.score >= ? AND r.status = ?
                ORDER BY rr.score DESC, r.id
                """,
                (rv, min_score, RecipeStatus.ACTIVE.value),
            )
            rows = await cur.fetchall()
            return [await self._hydrate_recipe(db, dict(r), with_deps=False) for r in rows]

    async def list_by_budget_class(self, budget_class: BudgetClass | str) -> list[Recipe]:
        bc = budget_class.value if isinstance(budget_class, BudgetClass) else budget_class
        return await self._list_where(
            "status = ? AND budget_class = ?",
            (RecipeStatus.ACTIVE.value, bc),
        )

    async def list_by_max_total_time(self, max_total_time_minutes: int) -> list[Recipe]:
        return await self._list_where(
            "status = ? AND total_time_minutes <= ?",
            (RecipeStatus.ACTIVE.value, max_total_time_minutes),
        )

    async def find_candidates(
        self,
        *,
        meal_type: MealType | str | None = None,
        max_total_time_minutes: int | None = None,
        goals: Iterable[GoalType | str] | None = None,
        budget_classes: Iterable[BudgetClass | str] | None = None,
        excluded_ingredient_ids: set[str] | None = None,
        status: RecipeStatus = RecipeStatus.ACTIVE,
    ) -> list[Recipe]:
        """Filtered candidate list without ranking (foundation for future selector)."""
        async with self._connection() as db:
            sql = ["SELECT DISTINCT r.* FROM recipes r"]
            joins: list[str] = []
            where = ["r.status = ?"]
            params: list[Any] = [status.value]

            if meal_type is not None:
                joins.append("JOIN recipe_meal_types m ON m.recipe_id = r.id")
                where.append("m.meal_type = ?")
                params.append(
                    meal_type.value if isinstance(meal_type, MealType) else meal_type
                )

            if max_total_time_minutes is not None:
                where.append("r.total_time_minutes <= ?")
                params.append(max_total_time_minutes)

            if budget_classes:
                bcs = [
                    b.value if isinstance(b, BudgetClass) else b for b in budget_classes
                ]
                placeholders = ",".join("?" for _ in bcs)
                where.append(f"r.budget_class IN ({placeholders})")
                params.extend(bcs)

            if goals:
                joins.append("JOIN recipe_goal_scores g ON g.recipe_id = r.id")
                gs = [g.value if isinstance(g, GoalType) else g for g in goals]
                placeholders = ",".join("?" for _ in gs)
                where.append(f"g.goal IN ({placeholders})")
                params.extend(gs)

            if excluded_ingredient_ids:
                placeholders = ",".join("?" for _ in excluded_ingredient_ids)
                where.append(
                    f"""r.id NOT IN (
                        SELECT ri.recipe_id FROM recipe_ingredients ri
                        WHERE ri.ingredient_id IN ({placeholders})
                    )"""
                )
                params.extend(sorted(excluded_ingredient_ids))

            sql.extend(joins)
            sql.append("WHERE " + " AND ".join(where))
            sql.append("ORDER BY r.id")
            cur = await db.execute("\n".join(sql), params)
            rows = await cur.fetchall()
            return [await self._hydrate_recipe(db, dict(r), with_deps=False) for r in rows]

    async def find_candidate_recipes_with_deps(
        self,
        *,
        meal_type: MealType | str,
        max_total_time_minutes: int | None = None,
        budget_classes: Iterable[BudgetClass | str] | None = None,
        status: RecipeStatus = RecipeStatus.ACTIVE,
    ) -> list[Recipe]:
        """SQL prefilter + bulk dependency load for selector scoring.

        Does not apply ingredient exclusions here — optional vs required is
        evaluated in RecipeHardFilter. Scoring must not hit the DB.
        """
        async with self._connection() as db:
            mt = meal_type.value if isinstance(meal_type, MealType) else meal_type
            sql = [
                "SELECT DISTINCT r.* FROM recipes r",
                "JOIN recipe_meal_types m ON m.recipe_id = r.id",
                "WHERE m.meal_type = ? AND r.status = ?",
            ]
            params: list[Any] = [mt, status.value]
            if max_total_time_minutes is not None:
                sql.append("AND r.total_time_minutes <= ?")
                params.append(max_total_time_minutes)
            if budget_classes:
                bcs = [
                    b.value if isinstance(b, BudgetClass) else b for b in budget_classes
                ]
                placeholders = ",".join("?" for _ in bcs)
                sql.append(f"AND r.budget_class IN ({placeholders})")
                params.extend(bcs)
            sql.append("ORDER BY r.id")
            cur = await db.execute("\n".join(sql), params)
            rows = [dict(r) for r in await cur.fetchall()]
            if not rows:
                return []
            return await self._hydrate_recipes_bulk(db, rows)

    async def get_recipe_with_dependencies(self, recipe_id: str) -> Recipe | None:
        async with self._connection() as db:
            cur = await db.execute("SELECT * FROM recipes WHERE id = ?", (recipe_id,))
            row = await cur.fetchone()
            if row is None:
                return None
            return await self._hydrate_recipe(db, dict(row), with_deps=True)

    async def _hydrate_recipes_bulk(
        self,
        db: aiosqlite.Connection,
        rows: list[dict[str, Any]],
    ) -> list[Recipe]:
        """Load meal types, ingredients, tags, roles, goals, equipment in bulk."""
        recipe_ids = [r["id"] for r in rows]
        placeholders = ",".join("?" for _ in recipe_ids)

        async def _fetch(sql: str) -> list[aiosqlite.Row]:
            cur = await db.execute(sql, recipe_ids)
            return list(await cur.fetchall())

        meal_rows = await _fetch(
            f"SELECT * FROM recipe_meal_types WHERE recipe_id IN ({placeholders})"
        )
        ing_rows = await _fetch(
            f"""
            SELECT * FROM recipe_ingredients
            WHERE recipe_id IN ({placeholders})
            ORDER BY recipe_id, sort_order
            """
        )
        eq_rows = await _fetch(
            f"SELECT * FROM recipe_equipment WHERE recipe_id IN ({placeholders})"
        )
        role_rows = await _fetch(
            f"SELECT * FROM recipe_roles WHERE recipe_id IN ({placeholders})"
        )
        goal_rows = await _fetch(
            f"SELECT * FROM recipe_goal_scores WHERE recipe_id IN ({placeholders})"
        )
        tag_rows = await _fetch(
            f"SELECT * FROM recipe_tags WHERE recipe_id IN ({placeholders})"
        )
        method_rows = await _fetch(
            f"SELECT * FROM recipe_cooking_methods WHERE recipe_id IN ({placeholders})"
        )

        ingredient_ids = sorted({r["ingredient_id"] for r in ing_rows})
        ingredients_by_id: dict[str, Ingredient] = {}
        if ingredient_ids:
            iph = ",".join("?" for _ in ingredient_ids)
            cur = await db.execute(
                f"SELECT * FROM ingredients WHERE id IN ({iph})", ingredient_ids
            )
            for irow in await cur.fetchall():
                ingredients_by_id[irow["id"]] = await self._hydrate_ingredient(
                    db, dict(irow)
                )

        meals_by: dict[str, list[RecipeMealTypeLink]] = {rid: [] for rid in recipe_ids}
        for m in meal_rows:
            meals_by[m["recipe_id"]].append(
                RecipeMealTypeLink(
                    meal_type=MealType(m["meal_type"]),
                    is_primary=_bool(m["is_primary"]),
                )
            )

        ings_by: dict[str, list[RecipeIngredient]] = {rid: [] for rid in recipe_ids}
        for ir in ing_rows:
            ings_by[ir["recipe_id"]].append(
                RecipeIngredient(
                    id=ir["id"],
                    recipe_id=ir["recipe_id"],
                    ingredient_id=ir["ingredient_id"],
                    quantity=_dec(ir["quantity"]),
                    unit=IngredientUnit(ir["unit"]),
                    quantity_grams=_dec_opt(ir["quantity_grams"]),
                    preparation=ir["preparation"],
                    is_optional=_bool(ir["is_optional"]),
                    ingredient_group=IngredientGroup(ir["ingredient_group"]),
                    sort_order=int(ir["sort_order"]),
                    scaling_factor=_dec(ir["scaling_factor"]),
                    rounding_increment=_dec_opt(ir["rounding_increment"]),
                    ingredient=ingredients_by_id.get(ir["ingredient_id"]),
                )
            )

        eq_by: dict[str, list[RecipeEquipmentItem]] = {rid: [] for rid in recipe_ids}
        for r in eq_rows:
            eq_by[r["recipe_id"]].append(
                RecipeEquipmentItem(
                    equipment=EquipmentType(r["equipment"]),
                    required=_bool(r["required"]),
                )
            )

        roles_by: dict[str, list[RecipeRoleItem]] = {rid: [] for rid in recipe_ids}
        for r in role_rows:
            roles_by[r["recipe_id"]].append(
                RecipeRoleItem(
                    role=RecipeRole(r["role"]),
                    score=float(r["score"]),
                    reason=r["reason"],
                )
            )

        goals_by: dict[str, list[RecipeGoalScore]] = {rid: [] for rid in recipe_ids}
        for r in goal_rows:
            goals_by[r["recipe_id"]].append(
                RecipeGoalScore(
                    goal=GoalType(r["goal"]),
                    score=float(r["score"]),
                    reason_codes=tuple(parse_reason_codes_json(r["reason_codes_json"])),
                )
            )

        tags_by: dict[str, list[RecipeTag]] = {rid: [] for rid in recipe_ids}
        for r in tag_rows:
            tags_by[r["recipe_id"]].append(
                RecipeTag(tag_type=TagType(r["tag_type"]), tag_value=r["tag_value"])
            )

        methods_by: dict[str, list[CookingMethod]] = {rid: [] for rid in recipe_ids}
        for r in method_rows:
            methods_by[r["recipe_id"]].append(CookingMethod(r["cooking_method"]))

        recipes: list[Recipe] = []
        for row in rows:
            rid = row["id"]
            recipes.append(
                Recipe(
                    id=row["id"],
                    slug=row["slug"],
                    name=row["name"],
                    description=row["description"],
                    status=RecipeStatus(row["status"]),
                    version=int(row["version"]),
                    primary_meal_type=MealType(row["primary_meal_type"]),
                    base_servings=_dec(row["base_servings"]),
                    yield_weight_g=_dec(row["yield_weight_g"]),
                    recommended_portion_min_g=_dec(row["recommended_portion_min_g"]),
                    recommended_portion_max_g=_dec(row["recommended_portion_max_g"]),
                    scaling_mode=ScalingMode(row["scaling_mode"]),
                    min_batch_servings=_dec(row["min_batch_servings"]),
                    max_batch_servings=_dec(row["max_batch_servings"]),
                    prep_time_minutes=int(row["prep_time_minutes"]),
                    cook_time_minutes=int(row["cook_time_minutes"]),
                    active_time_minutes=int(row["active_time_minutes"]),
                    total_time_minutes=int(row["total_time_minutes"]),
                    difficulty=Difficulty(row["difficulty"]),
                    requires_cooking=_bool(row["requires_cooking"]),
                    batch_friendly=_bool(row["batch_friendly"]),
                    leftover_friendly=_bool(row["leftover_friendly"]),
                    storage_days=row["storage_days"],
                    freezing_supported=_bool(row["freezing_supported"]),
                    budget_class=BudgetClass(row["budget_class"]),
                    energy_density=EnergyDensity(row["energy_density"]),
                    protein_level=ProteinLevel(row["protein_level"]),
                    fiber_level=FiberLevel(row["fiber_level"]),
                    satiety_level=SatietyLevel(row["satiety_level"]),
                    calories_per_100g=float(row["calories_per_100g"]),
                    protein_g_per_100g=float(row["protein_g_per_100g"]),
                    fat_g_per_100g=float(row["fat_g_per_100g"]),
                    carbs_g_per_100g=float(row["carbs_g_per_100g"]),
                    image_key=row["image_key"],
                    created_at=row["created_at"],
                    updated_at=row["updated_at"],
                    meal_types=tuple(meals_by.get(rid, [])),
                    ingredients=tuple(ings_by.get(rid, [])),
                    steps=(),
                    cooking_methods=tuple(methods_by.get(rid, [])),
                    equipment=tuple(eq_by.get(rid, [])),
                    roles=tuple(roles_by.get(rid, [])),
                    goal_scores=tuple(goals_by.get(rid, [])),
                    tags=tuple(tags_by.get(rid, [])),
                )
            )
        return recipes

    async def get_relations(
        self,
        recipe_id: str | None = None,
    ) -> list[RecipeRelation]:
        async with self._connection() as db:
            if recipe_id:
                cur = await db.execute(
                    """
                    SELECT * FROM recipe_relations
                    WHERE source_recipe_id = ? OR target_recipe_id = ?
                    ORDER BY id
                    """,
                    (recipe_id, recipe_id),
                )
            else:
                cur = await db.execute("SELECT * FROM recipe_relations ORDER BY id")
            rows = await cur.fetchall()
            return [self._row_to_relation(dict(r)) for r in rows]

    async def get_ingredient(self, ingredient_id: str) -> Ingredient | None:
        async with self._connection() as db:
            cur = await db.execute(
                "SELECT * FROM ingredients WHERE id = ?", (ingredient_id,)
            )
            row = await cur.fetchone()
            if row is None:
                return None
            return await self._hydrate_ingredient(db, dict(row))

    async def list_ingredients(self) -> list[Ingredient]:
        async with self._connection() as db:
            cur = await db.execute("SELECT * FROM ingredients ORDER BY id")
            rows = await cur.fetchall()
            return [await self._hydrate_ingredient(db, dict(r)) for r in rows]

    async def count_recipes(self, status: RecipeStatus | None = None) -> int:
        async with self._connection() as db:
            if status is None:
                cur = await db.execute("SELECT COUNT(*) AS c FROM recipes")
            else:
                cur = await db.execute(
                    "SELECT COUNT(*) AS c FROM recipes WHERE status = ?",
                    (status.value,),
                )
            row = await cur.fetchone()
            return int(row["c"])

    async def _list_where(self, where: str, params: tuple[Any, ...]) -> list[Recipe]:
        async with self._connection() as db:
            cur = await db.execute(
                f"SELECT * FROM recipes WHERE {where} ORDER BY id", params
            )
            rows = await cur.fetchall()
            return [await self._hydrate_recipe(db, dict(r), with_deps=False) for r in rows]

    async def _hydrate_ingredient(
        self, db: aiosqlite.Connection, row: dict[str, Any]
    ) -> Ingredient:
        cur = await db.execute(
            "SELECT * FROM ingredient_aliases WHERE ingredient_id = ? ORDER BY id",
            (row["id"],),
        )
        aliases = [
            IngredientAlias(
                id=a["id"],
                ingredient_id=a["ingredient_id"],
                alias=a["alias"],
                normalized_alias=a["normalized_alias"],
            )
            for a in await cur.fetchall()
        ]
        return Ingredient(
            id=row["id"],
            canonical_name=row["canonical_name"],
            display_name=row["display_name"],
            category=row["category"],
            default_unit=IngredientUnit(row["default_unit"]),
            piece_weight_g=row["piece_weight_g"],
            density_g_per_ml=row["density_g_per_ml"],
            is_pantry_staple=_bool(row["is_pantry_staple"]),
            aliases=tuple(aliases),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    async def _hydrate_recipe(
        self,
        db: aiosqlite.Connection,
        row: dict[str, Any],
        *,
        with_deps: bool,
    ) -> Recipe:
        recipe_id = row["id"]
        meal_types: tuple[RecipeMealTypeLink, ...] = ()
        ingredients: tuple[RecipeIngredient, ...] = ()
        steps: tuple[RecipeStep, ...] = ()
        cooking_methods: tuple[CookingMethod, ...] = ()
        equipment: tuple[RecipeEquipmentItem, ...] = ()
        roles: tuple[RecipeRoleItem, ...] = ()
        goal_scores: tuple[RecipeGoalScore, ...] = ()
        tags: tuple[RecipeTag, ...] = ()

        if with_deps:
            cur = await db.execute(
                "SELECT * FROM recipe_meal_types WHERE recipe_id = ?", (recipe_id,)
            )
            meal_types = tuple(
                RecipeMealTypeLink(
                    meal_type=MealType(m["meal_type"]),
                    is_primary=_bool(m["is_primary"]),
                )
                for m in await cur.fetchall()
            )

            cur = await db.execute(
                """
                SELECT * FROM recipe_ingredients
                WHERE recipe_id = ? ORDER BY sort_order
                """,
                (recipe_id,),
            )
            ing_rows = await cur.fetchall()
            ing_list: list[RecipeIngredient] = []
            for ir in ing_rows:
                cur_i = await db.execute(
                    "SELECT * FROM ingredients WHERE id = ?", (ir["ingredient_id"],)
                )
                irow = await cur_i.fetchone()
                ingredient = (
                    await self._hydrate_ingredient(db, dict(irow)) if irow else None
                )
                ing_list.append(
                    RecipeIngredient(
                        id=ir["id"],
                        recipe_id=ir["recipe_id"],
                        ingredient_id=ir["ingredient_id"],
                        quantity=_dec(ir["quantity"]),
                        unit=IngredientUnit(ir["unit"]),
                        quantity_grams=_dec_opt(ir["quantity_grams"]),
                        preparation=ir["preparation"],
                        is_optional=_bool(ir["is_optional"]),
                        ingredient_group=IngredientGroup(ir["ingredient_group"]),
                        sort_order=int(ir["sort_order"]),
                        scaling_factor=_dec(ir["scaling_factor"]),
                        rounding_increment=_dec_opt(ir["rounding_increment"]),
                        ingredient=ingredient,
                    )
                )
            ingredients = tuple(ing_list)

            cur = await db.execute(
                "SELECT * FROM recipe_steps WHERE recipe_id = ? ORDER BY step_number",
                (recipe_id,),
            )
            step_rows = await cur.fetchall()
            step_list: list[RecipeStep] = []
            for sr in step_rows:
                cur_l = await db.execute(
                    "SELECT recipe_ingredient_id FROM recipe_step_ingredients WHERE recipe_step_id = ?",
                    (sr["id"],),
                )
                links = tuple(r["recipe_ingredient_id"] for r in await cur_l.fetchall())
                step_list.append(
                    RecipeStep(
                        id=sr["id"],
                        recipe_id=sr["recipe_id"],
                        step_number=int(sr["step_number"]),
                        instruction=sr["instruction"],
                        duration_minutes=sr["duration_minutes"],
                        active_minutes=sr["active_minutes"],
                        temperature_c=sr["temperature_c"],
                        ingredient_ids=links,
                    )
                )
            steps = tuple(step_list)

            cur = await db.execute(
                "SELECT cooking_method FROM recipe_cooking_methods WHERE recipe_id = ?",
                (recipe_id,),
            )
            cooking_methods = tuple(
                CookingMethod(r["cooking_method"]) for r in await cur.fetchall()
            )

            cur = await db.execute(
                "SELECT equipment, required FROM recipe_equipment WHERE recipe_id = ?",
                (recipe_id,),
            )
            equipment = tuple(
                RecipeEquipmentItem(
                    equipment=EquipmentType(r["equipment"]),
                    required=_bool(r["required"]),
                )
                for r in await cur.fetchall()
            )

            cur = await db.execute(
                "SELECT role, score, reason FROM recipe_roles WHERE recipe_id = ?",
                (recipe_id,),
            )
            roles = tuple(
                RecipeRoleItem(
                    role=RecipeRole(r["role"]),
                    score=float(r["score"]),
                    reason=r["reason"],
                )
                for r in await cur.fetchall()
            )

            cur = await db.execute(
                "SELECT goal, score, reason_codes_json FROM recipe_goal_scores WHERE recipe_id = ?",
                (recipe_id,),
            )
            goal_scores = tuple(
                RecipeGoalScore(
                    goal=GoalType(r["goal"]),
                    score=float(r["score"]),
                    reason_codes=tuple(parse_reason_codes_json(r["reason_codes_json"])),
                )
                for r in await cur.fetchall()
            )

            cur = await db.execute(
                "SELECT tag_type, tag_value FROM recipe_tags WHERE recipe_id = ?",
                (recipe_id,),
            )
            tags = tuple(
                RecipeTag(tag_type=TagType(r["tag_type"]), tag_value=r["tag_value"])
                for r in await cur.fetchall()
            )

        return Recipe(
            id=row["id"],
            slug=row["slug"],
            name=row["name"],
            description=row["description"],
            status=RecipeStatus(row["status"]),
            version=int(row["version"]),
            primary_meal_type=MealType(row["primary_meal_type"]),
            base_servings=_dec(row["base_servings"]),
            yield_weight_g=_dec(row["yield_weight_g"]),
            recommended_portion_min_g=_dec(row["recommended_portion_min_g"]),
            recommended_portion_max_g=_dec(row["recommended_portion_max_g"]),
            scaling_mode=ScalingMode(row["scaling_mode"]),
            min_batch_servings=_dec(row["min_batch_servings"]),
            max_batch_servings=_dec(row["max_batch_servings"]),
            prep_time_minutes=int(row["prep_time_minutes"]),
            cook_time_minutes=int(row["cook_time_minutes"]),
            active_time_minutes=int(row["active_time_minutes"]),
            total_time_minutes=int(row["total_time_minutes"]),
            difficulty=Difficulty(row["difficulty"]),
            requires_cooking=_bool(row["requires_cooking"]),
            batch_friendly=_bool(row["batch_friendly"]),
            leftover_friendly=_bool(row["leftover_friendly"]),
            storage_days=row["storage_days"],
            freezing_supported=_bool(row["freezing_supported"]),
            budget_class=BudgetClass(row["budget_class"]),
            energy_density=EnergyDensity(row["energy_density"]),
            protein_level=ProteinLevel(row["protein_level"]),
            fiber_level=FiberLevel(row["fiber_level"]),
            satiety_level=SatietyLevel(row["satiety_level"]),
            calories_per_100g=float(row["calories_per_100g"]),
            protein_g_per_100g=float(row["protein_g_per_100g"]),
            fat_g_per_100g=float(row["fat_g_per_100g"]),
            carbs_g_per_100g=float(row["carbs_g_per_100g"]),
            image_key=row["image_key"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            meal_types=meal_types,
            ingredients=ingredients,
            steps=steps,
            cooking_methods=cooking_methods,
            equipment=equipment,
            roles=roles,
            goal_scores=goal_scores,
            tags=tags,
        )

    @staticmethod
    def _row_to_relation(row: dict[str, Any]) -> RecipeRelation:
        meta = None
        if row.get("metadata_json"):
            meta = json.loads(row["metadata_json"])
        return RecipeRelation(
            id=row["id"],
            source_recipe_id=row["source_recipe_id"],
            target_recipe_id=row["target_recipe_id"],
            relation_type=RelationType(row["relation_type"]),
            score=float(row["score"]),
            reason=row["reason"],
            metadata=meta,
        )
