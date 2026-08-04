"""SQLite schema for Recipe Catalog. Idempotent CREATE IF NOT EXISTS."""

from __future__ import annotations

import aiosqlite

CATALOG_TABLES: tuple[str, ...] = (
    "recipe_step_ingredients",
    "recipe_steps",
    "recipe_ingredients",
    "recipe_meal_types",
    "recipe_cooking_methods",
    "recipe_equipment",
    "recipe_roles",
    "recipe_goal_scores",
    "recipe_relations",
    "recipe_tags",
    "ingredient_aliases",
    "ingredients",
    "recipes",
)

CREATE_RECIPES_SQL = """
CREATE TABLE IF NOT EXISTS recipes (
    id TEXT PRIMARY KEY,
    slug TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    description TEXT NOT NULL,
    status TEXT NOT NULL,
    version INTEGER NOT NULL DEFAULT 1,
    primary_meal_type TEXT NOT NULL,
    base_servings REAL NOT NULL,
    yield_weight_g REAL NOT NULL,
    recommended_portion_min_g REAL NOT NULL,
    recommended_portion_max_g REAL NOT NULL,
    scaling_mode TEXT NOT NULL,
    min_batch_servings REAL NOT NULL,
    max_batch_servings REAL NOT NULL,
    prep_time_minutes INTEGER NOT NULL,
    cook_time_minutes INTEGER NOT NULL,
    active_time_minutes INTEGER NOT NULL,
    total_time_minutes INTEGER NOT NULL,
    difficulty TEXT NOT NULL,
    requires_cooking INTEGER NOT NULL,
    batch_friendly INTEGER NOT NULL,
    leftover_friendly INTEGER NOT NULL,
    storage_days INTEGER,
    freezing_supported INTEGER NOT NULL,
    budget_class TEXT NOT NULL,
    energy_density TEXT NOT NULL,
    protein_level TEXT NOT NULL,
    fiber_level TEXT NOT NULL,
    satiety_level TEXT NOT NULL,
    calories_per_100g REAL NOT NULL,
    protein_g_per_100g REAL NOT NULL,
    fat_g_per_100g REAL NOT NULL,
    carbs_g_per_100g REAL NOT NULL,
    image_key TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
"""

CREATE_RECIPE_MEAL_TYPES_SQL = """
CREATE TABLE IF NOT EXISTS recipe_meal_types (
    recipe_id TEXT NOT NULL,
    meal_type TEXT NOT NULL,
    is_primary INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (recipe_id, meal_type),
    FOREIGN KEY (recipe_id) REFERENCES recipes(id) ON DELETE CASCADE
);
"""

CREATE_INGREDIENTS_SQL = """
CREATE TABLE IF NOT EXISTS ingredients (
    id TEXT PRIMARY KEY,
    canonical_name TEXT NOT NULL UNIQUE,
    display_name TEXT NOT NULL,
    category TEXT NOT NULL,
    default_unit TEXT NOT NULL,
    piece_weight_g REAL,
    density_g_per_ml REAL,
    is_pantry_staple INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
"""

CREATE_INGREDIENT_ALIASES_SQL = """
CREATE TABLE IF NOT EXISTS ingredient_aliases (
    id TEXT PRIMARY KEY,
    ingredient_id TEXT NOT NULL,
    alias TEXT NOT NULL,
    normalized_alias TEXT NOT NULL,
    UNIQUE (ingredient_id, normalized_alias),
    FOREIGN KEY (ingredient_id) REFERENCES ingredients(id) ON DELETE CASCADE
);
"""

CREATE_RECIPE_INGREDIENTS_SQL = """
CREATE TABLE IF NOT EXISTS recipe_ingredients (
    id TEXT PRIMARY KEY,
    recipe_id TEXT NOT NULL,
    ingredient_id TEXT NOT NULL,
    quantity REAL NOT NULL,
    unit TEXT NOT NULL,
    quantity_grams REAL,
    preparation TEXT,
    is_optional INTEGER NOT NULL DEFAULT 0,
    ingredient_group TEXT NOT NULL,
    sort_order INTEGER NOT NULL,
    scaling_factor REAL NOT NULL DEFAULT 1.0,
    rounding_increment REAL,
    UNIQUE (recipe_id, sort_order),
    FOREIGN KEY (recipe_id) REFERENCES recipes(id) ON DELETE CASCADE,
    FOREIGN KEY (ingredient_id) REFERENCES ingredients(id)
);
"""

CREATE_RECIPE_STEPS_SQL = """
CREATE TABLE IF NOT EXISTS recipe_steps (
    id TEXT PRIMARY KEY,
    recipe_id TEXT NOT NULL,
    step_number INTEGER NOT NULL,
    instruction TEXT NOT NULL,
    duration_minutes INTEGER,
    active_minutes INTEGER,
    temperature_c INTEGER,
    UNIQUE (recipe_id, step_number),
    FOREIGN KEY (recipe_id) REFERENCES recipes(id) ON DELETE CASCADE
);
"""

CREATE_RECIPE_STEP_INGREDIENTS_SQL = """
CREATE TABLE IF NOT EXISTS recipe_step_ingredients (
    recipe_step_id TEXT NOT NULL,
    recipe_ingredient_id TEXT NOT NULL,
    PRIMARY KEY (recipe_step_id, recipe_ingredient_id),
    FOREIGN KEY (recipe_step_id) REFERENCES recipe_steps(id) ON DELETE CASCADE,
    FOREIGN KEY (recipe_ingredient_id) REFERENCES recipe_ingredients(id) ON DELETE CASCADE
);
"""

CREATE_RECIPE_COOKING_METHODS_SQL = """
CREATE TABLE IF NOT EXISTS recipe_cooking_methods (
    recipe_id TEXT NOT NULL,
    cooking_method TEXT NOT NULL,
    PRIMARY KEY (recipe_id, cooking_method),
    FOREIGN KEY (recipe_id) REFERENCES recipes(id) ON DELETE CASCADE
);
"""

CREATE_RECIPE_EQUIPMENT_SQL = """
CREATE TABLE IF NOT EXISTS recipe_equipment (
    recipe_id TEXT NOT NULL,
    equipment TEXT NOT NULL,
    required INTEGER NOT NULL DEFAULT 1,
    PRIMARY KEY (recipe_id, equipment),
    FOREIGN KEY (recipe_id) REFERENCES recipes(id) ON DELETE CASCADE
);
"""

CREATE_RECIPE_ROLES_SQL = """
CREATE TABLE IF NOT EXISTS recipe_roles (
    recipe_id TEXT NOT NULL,
    role TEXT NOT NULL,
    score REAL NOT NULL,
    reason TEXT,
    PRIMARY KEY (recipe_id, role),
    FOREIGN KEY (recipe_id) REFERENCES recipes(id) ON DELETE CASCADE
);
"""

CREATE_RECIPE_GOAL_SCORES_SQL = """
CREATE TABLE IF NOT EXISTS recipe_goal_scores (
    recipe_id TEXT NOT NULL,
    goal TEXT NOT NULL,
    score REAL NOT NULL,
    reason_codes_json TEXT NOT NULL DEFAULT '[]',
    PRIMARY KEY (recipe_id, goal),
    FOREIGN KEY (recipe_id) REFERENCES recipes(id) ON DELETE CASCADE
);
"""

CREATE_RECIPE_RELATIONS_SQL = """
CREATE TABLE IF NOT EXISTS recipe_relations (
    id TEXT PRIMARY KEY,
    source_recipe_id TEXT NOT NULL,
    target_recipe_id TEXT NOT NULL,
    relation_type TEXT NOT NULL,
    score REAL NOT NULL,
    reason TEXT,
    metadata_json TEXT,
    UNIQUE (source_recipe_id, target_recipe_id, relation_type),
    FOREIGN KEY (source_recipe_id) REFERENCES recipes(id) ON DELETE CASCADE,
    FOREIGN KEY (target_recipe_id) REFERENCES recipes(id) ON DELETE CASCADE
);
"""

CREATE_RECIPE_TAGS_SQL = """
CREATE TABLE IF NOT EXISTS recipe_tags (
    recipe_id TEXT NOT NULL,
    tag_type TEXT NOT NULL,
    tag_value TEXT NOT NULL,
    PRIMARY KEY (recipe_id, tag_type, tag_value),
    FOREIGN KEY (recipe_id) REFERENCES recipes(id) ON DELETE CASCADE
);
"""

CATALOG_INDEXES_SQL: tuple[str, ...] = (
    "CREATE INDEX IF NOT EXISTS idx_recipes_status ON recipes(status);",
    "CREATE INDEX IF NOT EXISTS idx_recipes_primary_meal_type ON recipes(primary_meal_type);",
    "CREATE INDEX IF NOT EXISTS idx_recipes_budget_class ON recipes(budget_class);",
    "CREATE INDEX IF NOT EXISTS idx_recipes_total_time ON recipes(total_time_minutes);",
    "CREATE INDEX IF NOT EXISTS idx_recipe_meal_types_meal ON recipe_meal_types(meal_type);",
    "CREATE INDEX IF NOT EXISTS idx_recipe_goal_scores_goal ON recipe_goal_scores(goal);",
    "CREATE INDEX IF NOT EXISTS idx_recipe_roles_role ON recipe_roles(role);",
    "CREATE INDEX IF NOT EXISTS idx_ingredient_aliases_norm ON ingredient_aliases(normalized_alias);",
    "CREATE INDEX IF NOT EXISTS idx_recipe_ingredients_ingredient ON recipe_ingredients(ingredient_id);",
    "CREATE INDEX IF NOT EXISTS idx_recipe_relations_source ON recipe_relations(source_recipe_id);",
    "CREATE INDEX IF NOT EXISTS idx_recipe_relations_target ON recipe_relations(target_recipe_id);",
)


async def ensure_recipe_catalog_tables(db: aiosqlite.Connection) -> None:
    """Creates catalog tables and indexes if missing. Safe to call repeatedly."""
    await db.execute(CREATE_INGREDIENTS_SQL)
    await db.execute(CREATE_INGREDIENT_ALIASES_SQL)
    await db.execute(CREATE_RECIPES_SQL)
    await db.execute(CREATE_RECIPE_MEAL_TYPES_SQL)
    await db.execute(CREATE_RECIPE_INGREDIENTS_SQL)
    await db.execute(CREATE_RECIPE_STEPS_SQL)
    await db.execute(CREATE_RECIPE_STEP_INGREDIENTS_SQL)
    await db.execute(CREATE_RECIPE_COOKING_METHODS_SQL)
    await db.execute(CREATE_RECIPE_EQUIPMENT_SQL)
    await db.execute(CREATE_RECIPE_ROLES_SQL)
    await db.execute(CREATE_RECIPE_GOAL_SCORES_SQL)
    await db.execute(CREATE_RECIPE_RELATIONS_SQL)
    await db.execute(CREATE_RECIPE_TAGS_SQL)
    for index_sql in CATALOG_INDEXES_SQL:
        await db.execute(index_sql)


async def clear_catalog_tables(db: aiosqlite.Connection) -> None:
    """Deletes all catalog rows. Does not touch users, menus, strategies, baskets."""
    await db.execute("PRAGMA foreign_keys = OFF;")
    for table in CATALOG_TABLES:
        await db.execute(f"DELETE FROM {table};")
    await db.execute("PRAGMA foreign_keys = ON;")
