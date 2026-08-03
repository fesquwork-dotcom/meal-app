"""
Асинхронное хранилище профилей на SQLite (aiosqlite).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import aiosqlite

import config
from meal_types import resolve_meal_types

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS profiles (
    user_id     INTEGER PRIMARY KEY,
    first_name  TEXT,
    budget      REAL,
    days        INTEGER,
    persons     INTEGER,
    proteins    TEXT,
    goal        TEXT,
    cooktime    TEXT,
    allergies   TEXT,
    store       TEXT,
    updated_at  TEXT DEFAULT CURRENT_TIMESTAMP
);
"""

CREATE_WEEKLY_STRATEGIES_SQL = """
CREATE TABLE IF NOT EXISTS weekly_strategies (
    id TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL,
    strategy_version INTEGER NOT NULL CHECK (strategy_version >= 1),
    status TEXT NOT NULL CHECK (status IN ('active', 'completed', 'superseded')),
    plan_start_date TEXT NOT NULL,
    plan_days INTEGER NOT NULL CHECK (plan_days >= 1),
    strategy_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    completed_at TEXT,
    superseded_at TEXT
);
"""

WEEKLY_STRATEGIES_INDEXES_SQL = (
    "CREATE INDEX IF NOT EXISTS idx_weekly_strategies_user_id ON weekly_strategies(user_id);",
    "CREATE INDEX IF NOT EXISTS idx_weekly_strategies_user_status ON weekly_strategies(user_id, status);",
    "CREATE INDEX IF NOT EXISTS idx_weekly_strategies_plan_start_date ON weekly_strategies(plan_start_date);",
    "CREATE UNIQUE INDEX IF NOT EXISTS idx_weekly_strategies_one_active_per_user "
    "ON weekly_strategies(user_id) WHERE status = 'active';",
)

# Memory Engine (Sprint 5.13): raw feedback events and aggregated preference signals.
# No foreign keys to strategies — a memory event is a durable user fact even if the
# related strategy is later removed. meal_id is only meaningful together with strategy_id.
CREATE_MEMORY_EVENTS_SQL = """
CREATE TABLE IF NOT EXISTS memory_events (
    id TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL,
    event_type TEXT NOT NULL,
    event_key TEXT NOT NULL,
    strategy_id TEXT,
    meal_id TEXT,
    recipe_id TEXT,
    reason_code TEXT,
    target_type TEXT,
    target_value TEXT,
    target_label TEXT,
    metadata_json TEXT,
    created_at TEXT NOT NULL
);
"""

CREATE_PREFERENCE_SIGNALS_SQL = """
CREATE TABLE IF NOT EXISTS preference_signals (
    id TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL,
    signal_type TEXT NOT NULL,
    target_value TEXT NOT NULL DEFAULT '',
    target_label TEXT,
    status TEXT NOT NULL CHECK (status IN ('observed', 'confirmed', 'dismissed')),
    confidence REAL NOT NULL DEFAULT 0.0,
    evidence_count INTEGER NOT NULL DEFAULT 0,
    first_observed_at TEXT,
    last_observed_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    dismissed_at TEXT
);
"""

MEMORY_INDEXES_SQL = (
    "CREATE UNIQUE INDEX IF NOT EXISTS idx_memory_events_event_key ON memory_events(event_key);",
    "CREATE INDEX IF NOT EXISTS idx_memory_events_user_id ON memory_events(user_id);",
    "CREATE INDEX IF NOT EXISTS idx_memory_events_user_type ON memory_events(user_id, event_type);",
    "CREATE INDEX IF NOT EXISTS idx_memory_events_user_reason_target "
    "ON memory_events(user_id, reason_code, target_value);",
    "CREATE INDEX IF NOT EXISTS idx_memory_events_created_at ON memory_events(created_at);",
    "CREATE INDEX IF NOT EXISTS idx_preference_signals_user_id ON preference_signals(user_id);",
    "CREATE UNIQUE INDEX IF NOT EXISTS idx_preference_signals_user_type_target "
    "ON preference_signals(user_id, signal_type, target_value);",
)

# Behavior Engine (Sprint 5.25A): durable observations from memory events.
CREATE_BEHAVIOR_INSIGHTS_SQL = """
CREATE TABLE IF NOT EXISTS behavior_insights (
    id TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL,
    insight_key TEXT NOT NULL,
    insight_type TEXT NOT NULL,
    target_key TEXT,
    target_label TEXT,
    status TEXT NOT NULL,
    confidence REAL NOT NULL,
    evidence_count INTEGER NOT NULL,
    evidence_window_days INTEGER NOT NULL,
    rule_version INTEGER NOT NULL,
    first_seen_at TEXT NOT NULL,
    last_seen_at TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    confirmed_at TEXT,
    dismissed_at TEXT,
    expires_at TEXT
);
"""

BEHAVIOR_INDEXES_SQL = (
    "CREATE UNIQUE INDEX IF NOT EXISTS idx_behavior_insights_user_key "
    "ON behavior_insights(user_id, insight_key);",
    "CREATE INDEX IF NOT EXISTS idx_behavior_insights_user_id ON behavior_insights(user_id);",
    "CREATE INDEX IF NOT EXISTS idx_behavior_insights_user_status "
    "ON behavior_insights(user_id, status);",
    "CREATE INDEX IF NOT EXISTS idx_behavior_insights_user_type "
    "ON behavior_insights(user_id, insight_type);",
    "CREATE INDEX IF NOT EXISTS idx_behavior_insights_expires_at ON behavior_insights(expires_at);",
)

# Decision Learning (Sprint 6.6): durable, human-approved recommendation history.
# Only aggregate provenance and an allowlisted profile patch are persisted.
CREATE_LEARNING_RECOMMENDATIONS_SQL = """
CREATE TABLE IF NOT EXISTS learning_recommendations (
    id TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL,
    recommendation_key TEXT NOT NULL,
    recommendation_type TEXT NOT NULL,
    decision_key TEXT NOT NULL,
    status TEXT NOT NULL CHECK (
        status IN ('candidate', 'accepted', 'dismissed', 'expired')
    ),
    confidence TEXT NOT NULL CHECK (confidence IN ('moderate', 'strong')),
    rule_version INTEGER NOT NULL,
    source_strategy_id TEXT NOT NULL,
    profile_patch_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    accepted_at TEXT,
    dismissed_at TEXT,
    expired_at TEXT
);
"""

LEARNING_INDEXES_SQL = (
    "CREATE UNIQUE INDEX IF NOT EXISTS idx_learning_user_key "
    "ON learning_recommendations(user_id, recommendation_key);",
    "CREATE INDEX IF NOT EXISTS idx_learning_user_status "
    "ON learning_recommendations(user_id, status);",
)

# Durable MenuPlan (Sprint 7.2): the backend becomes the authoritative store
# for generated menus. `menu_plans` keeps the immutable original snapshot;
# `menu_plan_revisions` is a strictly append-only history of validated states.
CREATE_MENU_PLANS_SQL = """
CREATE TABLE IF NOT EXISTS menu_plans (
    id TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL,
    strategy_id TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('active', 'superseded')),
    current_revision INTEGER NOT NULL CHECK (current_revision >= 1),
    original_plan_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    superseded_at TEXT
);
"""

CREATE_MENU_PLAN_REVISIONS_SQL = """
CREATE TABLE IF NOT EXISTS menu_plan_revisions (
    menu_plan_id TEXT NOT NULL,
    revision INTEGER NOT NULL CHECK (revision >= 1),
    change_type TEXT NOT NULL CHECK (
        change_type IN ('initial', 'meal_replacement', 'basket_rebuild')
    ),
    plan_json TEXT NOT NULL,
    changed_meal_ids_json TEXT,
    created_at TEXT NOT NULL,
    PRIMARY KEY (menu_plan_id, revision)
);
"""

MENU_PLAN_INDEXES_SQL = (
    "CREATE UNIQUE INDEX IF NOT EXISTS idx_menu_plans_strategy "
    "ON menu_plans(user_id, strategy_id);",
    "CREATE INDEX IF NOT EXISTS idx_menu_plans_user_status "
    "ON menu_plans(user_id, status);",
)

# Learned Preferences (Sprint 9.1): system-owned knowledge the user explicitly
# accepted. Separate from Profile/Memory/Behavior. Content columns are written
# once; only status and lifecycle timestamps transition (append-only lifecycle,
# never a content UPDATE).
CREATE_LEARNED_PREFERENCES_SQL = """
CREATE TABLE IF NOT EXISTS learned_preferences (
    id TEXT NOT NULL,
    user_id INTEGER NOT NULL,
    type TEXT NOT NULL,
    status TEXT NOT NULL CHECK (
        status IN ('candidate', 'accepted', 'active', 'revoked', 'archived')
    ),
    source TEXT NOT NULL,
    version INTEGER NOT NULL CHECK (version >= 1),
    evidence_json TEXT NOT NULL,
    preference_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    accepted_at TEXT,
    revoked_at TEXT,
    archived_at TEXT,
    last_review_generation INTEGER,
    PRIMARY KEY (user_id, id)
);
"""

LEARNED_PREFERENCES_INDEXES_SQL = (
    "CREATE INDEX IF NOT EXISTS idx_learned_preferences_user_status "
    "ON learned_preferences(user_id, status);",
)

# Async generation jobs (Sprint 10.6): durable status for background menu runs.
CREATE_GENERATION_JOBS_SQL = """
CREATE TABLE IF NOT EXISTS generation_jobs (
    job_id TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('queued','running','succeeded','failed','cancelled')),
    stage TEXT NOT NULL DEFAULT 'queued',
    progress_percent INTEGER,
    attempt INTEGER,
    max_attempts INTEGER,
    message_code TEXT,
    days INTEGER,
    persons INTEGER,
    plan_start_date TEXT,
    strategy_id TEXT,
    menu_plan_id TEXT,
    error_code TEXT,
    safe_message TEXT,
    internal_request_id TEXT,
    duration_ms INTEGER,
    request_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    started_at TEXT,
    completed_at TEXT
);
"""

GENERATION_JOBS_INDEXES_SQL = (
    "CREATE INDEX IF NOT EXISTS idx_generation_jobs_user_status "
    "ON generation_jobs(user_id, status);",
    "CREATE INDEX IF NOT EXISTS idx_generation_jobs_created_at "
    "ON generation_jobs(created_at);",
    "CREATE UNIQUE INDEX IF NOT EXISTS idx_generation_jobs_one_active_per_user "
    "ON generation_jobs(user_id) WHERE status IN ('queued', 'running');",
)


def resolve_database_path() -> Path:
    """Resolves configured SQLite path without creating connections at import time."""
    return Path(config.DATABASE_PATH).expanduser().resolve()


async def _ensure_revision_column(db: aiosqlite.Connection) -> None:
    cursor = await db.execute("PRAGMA table_info(profiles)")
    columns = await cursor.fetchall()
    await cursor.close()

    column_names = {row[1] for row in columns}
    if "revision" not in column_names:
        await db.execute(
            "ALTER TABLE profiles ADD COLUMN revision INTEGER NOT NULL DEFAULT 1"
        )


async def _ensure_meal_types_column(db: aiosqlite.Connection) -> None:
    cursor = await db.execute("PRAGMA table_info(profiles)")
    columns = await cursor.fetchall()
    await cursor.close()

    column_names = {row[1] for row in columns}
    if "meal_types" not in column_names:
        await db.execute("ALTER TABLE profiles ADD COLUMN meal_types TEXT")


async def _ensure_dietary_constraints_column(db: aiosqlite.Connection) -> None:
    """Additive migration: typed constraints live next to deprecated allergies."""
    cursor = await db.execute("PRAGMA table_info(profiles)")
    columns = await cursor.fetchall()
    await cursor.close()

    column_names = {row[1] for row in columns}
    if "dietary_constraints_json" not in column_names:
        await db.execute("ALTER TABLE profiles ADD COLUMN dietary_constraints_json TEXT")


async def _ensure_cooking_preferences_column(db: aiosqlite.Connection) -> None:
    cursor = await db.execute("PRAGMA table_info(profiles)")
    columns = await cursor.fetchall()
    await cursor.close()

    column_names = {row[1] for row in columns}
    if "cooking_preferences_json" not in column_names:
        await db.execute("ALTER TABLE profiles ADD COLUMN cooking_preferences_json TEXT")


async def _ensure_reason_codes_column(db: aiosqlite.Connection) -> None:
    cursor = await db.execute("PRAGMA table_info(weekly_strategies)")
    columns = await cursor.fetchall()
    await cursor.close()

    column_names = {row[1] for row in columns}
    if "reason_codes_json" not in column_names:
        await db.execute("ALTER TABLE weekly_strategies ADD COLUMN reason_codes_json TEXT")


async def _ensure_applied_memory_column(db: aiosqlite.Connection) -> None:
    cursor = await db.execute("PRAGMA table_info(weekly_strategies)")
    columns = await cursor.fetchall()
    await cursor.close()

    column_names = {row[1] for row in columns}
    if "applied_memory_json" not in column_names:
        await db.execute("ALTER TABLE weekly_strategies ADD COLUMN applied_memory_json TEXT")


async def _ensure_applied_cooking_preferences_column(db: aiosqlite.Connection) -> None:
    cursor = await db.execute("PRAGMA table_info(weekly_strategies)")
    columns = await cursor.fetchall()
    await cursor.close()

    column_names = {row[1] for row in columns}
    if "applied_cooking_preferences_json" not in column_names:
        await db.execute(
            "ALTER TABLE weekly_strategies ADD COLUMN applied_cooking_preferences_json TEXT"
        )


async def _ensure_applied_behavior_column(db: aiosqlite.Connection) -> None:
    cursor = await db.execute("PRAGMA table_info(weekly_strategies)")
    columns = await cursor.fetchall()
    await cursor.close()

    column_names = {row[1] for row in columns}
    if "applied_behavior_json" not in column_names:
        await db.execute("ALTER TABLE weekly_strategies ADD COLUMN applied_behavior_json TEXT")


async def _ensure_planning_preferences_column(db: aiosqlite.Connection) -> None:
    cursor = await db.execute("PRAGMA table_info(profiles)")
    columns = await cursor.fetchall()
    await cursor.close()

    column_names = {row[1] for row in columns}
    if "planning_preferences_json" not in column_names:
        await db.execute("ALTER TABLE profiles ADD COLUMN planning_preferences_json TEXT")


async def _ensure_behavior_recommendation_columns(db: aiosqlite.Connection) -> None:
    cursor = await db.execute("PRAGMA table_info(behavior_insights)")
    columns = await cursor.fetchall()
    await cursor.close()

    column_names = {row[1] for row in columns}
    if "recommendation_applied_at" not in column_names:
        await db.execute("ALTER TABLE behavior_insights ADD COLUMN recommendation_applied_at TEXT")
    if "recommendation_key" not in column_names:
        await db.execute("ALTER TABLE behavior_insights ADD COLUMN recommendation_key TEXT")


async def _ensure_behavior_lifecycle_columns(db: aiosqlite.Connection) -> None:
    cursor = await db.execute("PRAGMA table_info(behavior_insights)")
    columns = await cursor.fetchall()
    await cursor.close()

    column_names = {row[1] for row in columns}
    if "snoozed_at" not in column_names:
        await db.execute("ALTER TABLE behavior_insights ADD COLUMN snoozed_at TEXT")
    if "snoozed_until" not in column_names:
        await db.execute("ALTER TABLE behavior_insights ADD COLUMN snoozed_until TEXT")
    if "revoked_at" not in column_names:
        await db.execute("ALTER TABLE behavior_insights ADD COLUMN revoked_at TEXT")


async def _ensure_applied_planning_preferences_column(db: aiosqlite.Connection) -> None:
    cursor = await db.execute("PRAGMA table_info(weekly_strategies)")
    columns = await cursor.fetchall()
    await cursor.close()

    column_names = {row[1] for row in columns}
    if "applied_planning_preferences_json" not in column_names:
        await db.execute(
            "ALTER TABLE weekly_strategies ADD COLUMN applied_planning_preferences_json TEXT"
        )


async def _ensure_applied_learned_preferences_column(
    db: aiosqlite.Connection,
) -> None:
    cursor = await db.execute("PRAGMA table_info(weekly_strategies)")
    columns = await cursor.fetchall()
    await cursor.close()
    column_names = {row[1] for row in columns}
    if "applied_learned_preferences_json" not in column_names:
        await db.execute(
            "ALTER TABLE weekly_strategies "
            "ADD COLUMN applied_learned_preferences_json TEXT"
        )


async def _ensure_decision_context_column(db: aiosqlite.Connection) -> None:
    cursor = await db.execute("PRAGMA table_info(weekly_strategies)")
    columns = await cursor.fetchall()
    await cursor.close()

    column_names = {row[1] for row in columns}
    if "decision_context_json" not in column_names:
        await db.execute("ALTER TABLE weekly_strategies ADD COLUMN decision_context_json TEXT")


async def _ensure_decision_trace_column(db: aiosqlite.Connection) -> None:
    cursor = await db.execute("PRAGMA table_info(weekly_strategies)")
    columns = await cursor.fetchall()
    await cursor.close()

    column_names = {row[1] for row in columns}
    if "decision_trace_json" not in column_names:
        await db.execute("ALTER TABLE weekly_strategies ADD COLUMN decision_trace_json TEXT")


async def _ensure_decision_outcomes_column(db: aiosqlite.Connection) -> None:
    cursor = await db.execute("PRAGMA table_info(weekly_strategies)")
    columns = await cursor.fetchall()
    await cursor.close()

    column_names = {row[1] for row in columns}
    if "decision_outcomes_json" not in column_names:
        await db.execute("ALTER TABLE weekly_strategies ADD COLUMN decision_outcomes_json TEXT")


async def _ensure_learning_recommendations_table(
    db: aiosqlite.Connection,
) -> None:
    """Idempotent Sprint 6.6 migration used by init and repositories."""
    await db.execute(CREATE_LEARNING_RECOMMENDATIONS_SQL)
    for index_sql in LEARNING_INDEXES_SQL:
        await db.execute(index_sql)


async def _ensure_menu_plan_tables(db: aiosqlite.Connection) -> None:
    """Idempotent Sprint 7.2 migration used by init and repositories."""
    await db.execute(CREATE_MENU_PLANS_SQL)
    await db.execute(CREATE_MENU_PLAN_REVISIONS_SQL)
    for index_sql in MENU_PLAN_INDEXES_SQL:
        await db.execute(index_sql)


async def _ensure_learned_preferences_table(db: aiosqlite.Connection) -> None:
    """Idempotent Sprint 9.1 migration used by init and repositories."""
    await db.execute(CREATE_LEARNED_PREFERENCES_SQL)
    for index_sql in LEARNED_PREFERENCES_INDEXES_SQL:
        await db.execute(index_sql)
    await _ensure_learned_preference_review_generation_column(db)


async def _ensure_generation_jobs_table(db: aiosqlite.Connection) -> None:
    """Idempotent Sprint 10.6 migration used by init and repositories."""
    await db.execute(CREATE_GENERATION_JOBS_SQL)
    for index_sql in GENERATION_JOBS_INDEXES_SQL:
        await db.execute(index_sql)


async def _ensure_learned_preference_review_generation_column(
    db: aiosqlite.Connection,
) -> None:
    """Sprint 9.4: persist dismissed review cohort without changing LP lifecycle."""
    cursor = await db.execute("PRAGMA table_info(learned_preferences)")
    columns = await cursor.fetchall()
    await cursor.close()
    column_names = {row[1] for row in columns}
    if "last_review_generation" not in column_names:
        await db.execute(
            "ALTER TABLE learned_preferences "
            "ADD COLUMN last_review_generation INTEGER"
        )


async def _ensure_confirmation_source_column(db: aiosqlite.Connection) -> None:
    cursor = await db.execute("PRAGMA table_info(preference_signals)")
    columns = await cursor.fetchall()
    await cursor.close()

    column_names = {row[1] for row in columns}
    if "confirmation_source" not in column_names:
        await db.execute("ALTER TABLE preference_signals ADD COLUMN confirmation_source TEXT")


async def _ensure_promotion_columns(db: aiosqlite.Connection) -> None:
    cursor = await db.execute("PRAGMA table_info(preference_signals)")
    columns = await cursor.fetchall()
    await cursor.close()

    column_names = {row[1] for row in columns}
    if "promoted_at" not in column_names:
        await db.execute("ALTER TABLE preference_signals ADD COLUMN promoted_at TEXT")
    if "promoted_constraint_id" not in column_names:
        await db.execute(
            "ALTER TABLE preference_signals ADD COLUMN promoted_constraint_id TEXT"
        )


def _parse_meal_types(raw: str | None) -> list[str] | None:
    if not raw:
        return None

    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return None

    if not isinstance(parsed, list):
        return None

    return [item for item in parsed if isinstance(item, str)]


def _parse_dietary_constraints(raw: str | None) -> list[dict]:
    from dietary_constraints import parse_constraints_json

    return [constraint.model_dump(mode="json") for constraint in parse_constraints_json(raw)]


def _parse_cooking_preferences(raw: str | None) -> dict[str, object] | None:
    from cooking_preferences import cooking_preferences_to_response_dict

    return cooking_preferences_to_response_dict(raw)


def _parse_planning_preferences(raw: str | None) -> dict[str, object] | None:
    from planning_preferences import planning_preferences_to_response_dict

    return planning_preferences_to_response_dict(raw)


def _normalize_profile_row(row: aiosqlite.Row) -> dict:
    from profile_limits import clamp_legacy_budget, clamp_legacy_days

    meal_types = resolve_meal_types(_parse_meal_types(row["meal_types"]))
    meals_per_day = len(meal_types)

    row_keys = row.keys()
    dietary_raw = (
        row["dietary_constraints_json"] if "dietary_constraints_json" in row_keys else None
    )
    cooking_raw = (
        row["cooking_preferences_json"] if "cooking_preferences_json" in row_keys else None
    )
    planning_raw = (
        row["planning_preferences_json"] if "planning_preferences_json" in row_keys else None
    )

    return {
        "user_id": row["user_id"],
        "first_name": row["first_name"],
        "budget": clamp_legacy_budget(row["budget"], default=3000.0),
        "days": clamp_legacy_days(row["days"], default=5),
        "persons": row["persons"],
        "proteins": json.loads(row["proteins"]) if row["proteins"] else [],
        "goal": row["goal"],
        "cooktime": row["cooktime"],
        "allergies": row["allergies"],
        "dietary_constraints": _parse_dietary_constraints(dietary_raw),
        "cooking_preferences": _parse_cooking_preferences(cooking_raw),
        "planning_preferences": _parse_planning_preferences(planning_raw),
        "store": row["store"],
        "meal_types": meal_types,
        "meals_per_day": meals_per_day,
        "updated_at": row["updated_at"],
        "revision": int(row["revision"]) if row["revision"] is not None else 1,
    }


async def init_db() -> Path:
    """Creates database file and tables idempotently. Returns resolved DB path."""
    db_path = resolve_database_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)

    async with aiosqlite.connect(db_path) as db:
        await db.execute("PRAGMA journal_mode=WAL;")
        await db.execute(CREATE_TABLE_SQL)
        await _ensure_meal_types_column(db)
        await _ensure_revision_column(db)
        await _ensure_dietary_constraints_column(db)
        await _ensure_cooking_preferences_column(db)
        await _ensure_planning_preferences_column(db)
        await db.execute(CREATE_WEEKLY_STRATEGIES_SQL)
        await _ensure_reason_codes_column(db)
        await _ensure_applied_memory_column(db)
        await _ensure_applied_cooking_preferences_column(db)
        await _ensure_applied_behavior_column(db)
        await _ensure_applied_planning_preferences_column(db)
        await _ensure_applied_learned_preferences_column(db)
        await _ensure_decision_context_column(db)
        await _ensure_decision_trace_column(db)
        await _ensure_decision_outcomes_column(db)
        for index_sql in WEEKLY_STRATEGIES_INDEXES_SQL:
            await db.execute(index_sql)
        await db.execute(CREATE_MEMORY_EVENTS_SQL)
        await db.execute(CREATE_PREFERENCE_SIGNALS_SQL)
        await _ensure_confirmation_source_column(db)
        await _ensure_promotion_columns(db)
        for index_sql in MEMORY_INDEXES_SQL:
            await db.execute(index_sql)
        await db.execute(CREATE_BEHAVIOR_INSIGHTS_SQL)
        await _ensure_behavior_recommendation_columns(db)
        await _ensure_behavior_lifecycle_columns(db)
        for index_sql in BEHAVIOR_INDEXES_SQL:
            await db.execute(index_sql)
        await _ensure_learning_recommendations_table(db)
        await _ensure_menu_plan_tables(db)
        await _ensure_learned_preferences_table(db)
        await _ensure_generation_jobs_table(db)
        await db.commit()

    return db_path


async def check_database_ready() -> bool:
    """Checks that the database file is readable and responds to queries."""
    db_path = resolve_database_path()

    try:
        async with aiosqlite.connect(db_path) as db:
            cursor = await db.execute("SELECT 1")
            row = await cursor.fetchone()
            await cursor.close()
        return row == (1,)
    except Exception:
        return False


async def save_profile(user_id: int, profile: dict) -> dict | None:
    """Internal profile save using current revision (conflict resolution path)."""
    stored = await get_profile(user_id)
    expected_revision = int(stored["revision"]) if stored else 0
    result = await save_profile_with_revision(user_id, profile, expected_revision)
    if not result.success:
        return None
    return result.profile


async def save_profile_with_revision(
    user_id: int,
    profile: dict,
    expected_revision: int,
) -> "ProfileSaveResult":
    """Atomically saves profile when expected_revision matches."""
    from profile_persistence import ProfileSaveResult

    db_path = resolve_database_path()
    meal_types = resolve_meal_types(profile.get("meal_types"), profile.get("meals_per_day"))
    proteins_json = json.dumps(profile.get("proteins", []), ensure_ascii=False)
    meal_types_json = json.dumps(meal_types, ensure_ascii=False)
    dietary_constraints = profile.get("dietary_constraints")
    dietary_constraints_json = (
        json.dumps(dietary_constraints, ensure_ascii=False)
        if isinstance(dietary_constraints, list)
        else None
    )
    from cooking_preferences import cooking_preferences_to_db_json
    from planning_preferences import planning_preferences_to_db_json

    cooking_preferences_json = cooking_preferences_to_db_json(profile)
    planning_preferences_json = planning_preferences_to_db_json(profile)

    async with aiosqlite.connect(db_path) as db:
        await _ensure_meal_types_column(db)
        await _ensure_revision_column(db)
        await _ensure_dietary_constraints_column(db)
        await _ensure_cooking_preferences_column(db)
        await _ensure_planning_preferences_column(db)
        db.row_factory = aiosqlite.Row

        if expected_revision == 0:
            cursor = await db.execute(
                "SELECT user_id FROM profiles WHERE user_id = ?",
                (user_id,),
            )
            exists = await cursor.fetchone()
            await cursor.close()
            if exists is not None:
                current = await _fetch_profile_row(db, user_id)
                return ProfileSaveResult(
                    success=False,
                    stale=True,
                    current_profile=current,
                    current_revision=int(current["revision"]) if current else None,
                )

            await db.execute(
                """
                INSERT INTO profiles
                    (user_id, first_name, budget, days, persons, proteins, goal,
                     cooktime, allergies, dietary_constraints_json, cooking_preferences_json,
                     planning_preferences_json, store, meal_types, updated_at, revision)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, 1)
                """,
                (
                    user_id,
                    profile.get("first_name", ""),
                    profile.get("budget"),
                    profile.get("days"),
                    profile.get("persons"),
                    proteins_json,
                    profile.get("goal"),
                    profile.get("cooktime"),
                    profile.get("allergies"),
                    dietary_constraints_json,
                    cooking_preferences_json,
                    planning_preferences_json,
                    profile.get("store"),
                    meal_types_json,
                ),
            )
            await db.commit()
            saved = await _fetch_profile_row(db, user_id)
            return ProfileSaveResult(
                success=True,
                profile=saved,
                revision=1,
            )

        cursor = await db.execute(
            """
            UPDATE profiles
            SET
                first_name = ?,
                budget = ?,
                days = ?,
                persons = ?,
                proteins = ?,
                goal = ?,
                cooktime = ?,
                allergies = ?,
                dietary_constraints_json = ?,
                cooking_preferences_json = ?,
                planning_preferences_json = ?,
                store = ?,
                meal_types = ?,
                updated_at = CURRENT_TIMESTAMP,
                revision = revision + 1
            WHERE user_id = ? AND revision = ?
            """,
            (
                profile.get("first_name", ""),
                profile.get("budget"),
                profile.get("days"),
                profile.get("persons"),
                proteins_json,
                profile.get("goal"),
                profile.get("cooktime"),
                profile.get("allergies"),
                dietary_constraints_json,
                cooking_preferences_json,
                planning_preferences_json,
                profile.get("store"),
                meal_types_json,
                user_id,
                expected_revision,
            ),
        )
        updated_rows = cursor.rowcount
        await cursor.close()

        if updated_rows == 1:
            await db.commit()
            saved = await _fetch_profile_row(db, user_id)
            return ProfileSaveResult(
                success=True,
                profile=saved,
                revision=int(saved["revision"]) if saved else None,
            )

        current = await _fetch_profile_row(db, user_id)
        await db.commit()
        return ProfileSaveResult(
            success=False,
            stale=True,
            current_profile=current,
            current_revision=int(current["revision"]) if current else None,
        )


async def _fetch_profile_row(db: aiosqlite.Connection, user_id: int) -> dict | None:
    cursor = await db.execute("SELECT * FROM profiles WHERE user_id = ?", (user_id,))
    row = await cursor.fetchone()
    await cursor.close()
    if row is None:
        return None
    return _normalize_profile_row(row)


async def get_profile_revision(user_id: int) -> int:
    """Returns persisted revision or 0 when profile does not exist."""
    profile = await get_profile(user_id)
    if profile is None:
        return 0
    return int(profile.get("revision", 1))


async def get_profile(user_id: int) -> Optional[dict]:
    """Returns saved profile or None."""
    db_path = resolve_database_path()

    async with aiosqlite.connect(db_path) as db:
        await _ensure_meal_types_column(db)
        await _ensure_revision_column(db)
        await _ensure_dietary_constraints_column(db)
        await _ensure_cooking_preferences_column(db)
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM profiles WHERE user_id = ?", (user_id,))
        row = await cursor.fetchone()
        await cursor.close()

        if row is None:
            return None

        return _normalize_profile_row(row)
