# Sprint 10.12.1 — Catalog Replacement Production Routing Fix

## Root Cause

Production flow:

1. `catalog_menu_generated engine=catalog_planner` — backend generation correct.
2. Durable SQLite JSON **did** store `generation_engine=catalog_planner` inside `menu_plans` / revision `plan_json`.
3. Webapp `normalizeMenuPlan` **dropped** `generation_engine` / `planner_*` (fields absent from TS `MenuPlan` type).
4. `POST /api/menu/replace-meal` sent `menu_plan` with `generation_engine=null`.
5. `MealReplacementService._is_catalog_planner_menu` required the **request** field → `False`.
6. Router fell through to legacy Claude → `POST api.anthropic.com` → credit error.

Persistence was not the primary loss; **client roundtrip stripping** was.

## Persistence Path

```
CatalogMenuGenerationService.finalize
  → payload["generation_engine"]="catalog_planner"
→ MenuPlan.model_validate(result)   # keeps field (MenuPlan model field)
→ durable_plan.model_dump_json()    # includes generation_engine
→ StrategyService.save_active_strategy(menu_plan_json=...)
→ menu_plan_revisions.plan_json     # SQLite TEXT JSON snapshot
→ GET /api/menu/current → plan.generation_engine == catalog_planner
```

No separate DB column; engine lives in plan JSON. Schema OK.

## DB Before / After

| Stage | generation_engine |
|--|--|
| After generate (dict) | `catalog_planner` |
| After `model_validate` + save | `catalog_planner` in `plan_json` |
| After GET current | `catalog_planner` |
| After old webapp normalize | **lost (None)** |
| After new webapp normalize | `catalog_planner` preserved |
| Replace routing (fixed) | uses request **or** durable JSON |

## Router Before / After

**Before:** only `request.menu_plan.generation_engine == catalog_planner` → catalog; else Claude.

**After:**

1. Log `replacement_engine_selected`
2. Effective engine = request engine **or** durable revision JSON engine
3. `catalog_planner` → `CatalogMealReplacementService` (restore field on request if stripped)
4. Catalog markers without authoritative engine → `CATALOG_REPLACEMENT_ROUTING_ERROR` (never Claude)
5. True legacy (no engine, no markers) → Claude path unchanged

## Production-Equivalent Reproduction

Covered by `test_stripped_client_plan_uses_persisted_engine_claude_zero` and `test_api_current_then_replace_stripped_engine`:

generate → persist → strip engine → replace with `menu_plan_id` → catalog path, Claude=0.

## Async Generation Roundtrip

`test_async_job_persist_preserves_engine_for_replace` mirrors `generation_jobs/execute.py`:

`MenuPlan.model_validate(result)` → `model_dump_json()` → save → reload → stripped replace → Claude=0.

## Claude Spy Result

All catalog routing regressions: **0 Claude calls**.

Marker-only corrupt case: **0 Claude calls** + `CATALOG_REPLACEMENT_ROUTING_ERROR`.

## Legacy Compatibility

Menus without `generation_engine` and without catalog markers still use Claude.

## Frontend Fix

`webapp` types + `normalizeMenuPlan` now preserve:

- `generation_engine`
- `planner_version`
- `planner_score`
- `planning_duration_ms`

## Known Limitations

- Primary recovery for already-stripped clients is durable `menu_plan_id` lookup.
- Without `menu_plan_id` and without engine, catalog markers fail closed (no Claude).
