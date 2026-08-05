# Catalog Planner Production Integration — Sprint 10.11

**Goal:** Make `catalog_planner` the default menu generation engine. The app starts and generates menus **without** `ANTHROPIC_API_KEY`. Legacy Claude remains available only when `MEAL_GENERATION_ENGINE=legacy_claude`.

---

## Architecture Before / After

### Before (Sprint ≤ 10.10)

```
Profile → StrategyBuilder → Claude generate_menu → MenuPlan → Basket → API
```

Claude was required for the main path; Catalog Planner existed only as CLI/tests.

### After (Sprint 10.11)

```
Profile → StrategyBuilder → MenuGenerationOrchestrator
                              ├─ catalog_planner (DEFAULT) → WeeklyRecipePlanner → Adapter → finalize → MenuPlan → Basket
                              └─ legacy_claude (explicit only) → claude_service.generate_menu
```

---

## Production pipeline audit (summary)

| Layer | Classification |
|-------|----------------|
| StrategyBuilder / WeeklyStrategy | REUSED |
| RecipeCandidateSelector / WeeklyRecipePlanner | REUSED |
| Job queue / MenuPlanService / Basket Engine | REUSED |
| cooking_identity / menu validation | REUSED |
| MenuGenerationOrchestrator + CatalogMenuGenerationService + Adapter | NEW |
| config MEAL_GENERATION_ENGINE + startup gate | ADAPTED |
| claude_service / MealReplacementService (Claude path) | LEGACY |
| Catalog recipes / Planner weights | UNTOUCHED |

Claude dependencies that blocked LLM-free startup: `startup_validation` required `ANTHROPIC_API_KEY` whenever `ALLOW_DEV_AUTH=false`. Fixed: key required only for `legacy_claude`.

---

## Architecture

```
API / generation_jobs
        │
        ▼
MenuGenerationOrchestrator  (menu_generation/orchestrator.py)
        │
        ├─ catalog_planner (default) ──► CatalogMenuGenerationService
        │                                       │
        │         WeeklyRecipePlanner.plan()
        │                                       │
        │         WeeklyRecipePlanToMenuPlanAdapter
        │                                       │
        │         finalize_catalog_menu_plan()
        │                                       │
        │         MenuPlan dict + metadata
        │
        └─ legacy_claude ──► require credentials ──► claude_service.generate_menu
```

### New package: `menu_generation/`

| Module | Role |
|--------|------|
| `engine.py` | `GenerationEngine`, `resolve_generation_engine()`, credential gate |
| `errors.py` | `CatalogGenerationError` + stable codes |
| `menuplan_adapter.py` | `WeeklyRecipePlan` → `MenuPlan` (meal_id / recipe_id / leftovers) |
| `finalize.py` | Shared domain finalize (IDs, cooking, basket, budget) — no Claude |
| `catalog_service.py` | End-to-end catalog generation + progress stages |
| `orchestrator.py` | Single entry used by `main.py` and `generation_jobs/execute.py` |

### Intentionally unchanged

- WeeklyRecipePlanner beam/weights/pool defaults (`beam_width=8`, `pool=15`, `max_states=4000`)
- Catalog recipes (still **80** active)
- Claude code (not deleted; only behind legacy flag)
- No `ExternalLLMProvider`, no auto-fallback to Claude

### Production config

```python
MEAL_GENERATION_ENGINE = os.getenv("MEAL_GENERATION_ENGINE", "catalog_planner")
```

Startup (`ALLOW_DEV_AUTH=false`):

- **catalog_planner:** Claude key / model **not** required
- **legacy_claude:** `ANTHROPIC_API_KEY` + `CLAUDE_MODEL` required

---

## Mapping rules (adapter)

| Field | Rule |
|-------|------|
| `meal_id` | `meal_{slot_id}` e.g. `meal_day1_breakfast` (stable, not catalog id) |
| `recipe_id` (cook) | Catalog `recipe.id` |
| `recipe_id` (leftover) | `{catalog_id}__leftover` — separate snapshot so `from_source` does not leak onto cook recipes |
| `DayPlan.day` | `День {day_index}` |
| Leftover meal | `requires_cooking=False`, `uses_leftovers=True`, `source_meal_id=meal_{source_slot}` |
| Cook meal | `requires_cooking=True`, `prepared_on_day=day_index` |
| Scaling | `persons * servings_cooked` from cooking instance |
| Basket | Built in finalize via `build_basket_from_menu` |

Persisted on `MenuPlan` (optional fields): `generation_engine`, `planner_score`, `planner_version`, `planning_duration_ms`.

---

## Failure modes

| Code | When |
|------|------|
| `PLANNER_NO_PLAN` | Planner returns `no_plan` |
| `PLANNER_PARTIAL_PLAN` | Planner returns `partial` (**no Claude fallback**) |
| `MENUPLAN_VALIDATION_FAILED` | Identity / cooking / strategy / budget validation |
| `BASKET_BUILD_FAILED` | Basket rebuild exception |
| `CATALOG_RECIPE_NOT_FOUND` | Catalog id missing from DB |
| `CATALOG_REPLACE_NOT_IMPLEMENTED` | Replace-meal on catalog-generated menu |
| `GENERATION_ENGINE_UNAVAILABLE` | Legacy Claude without credentials |

---

## Replace-meal status

**Not implemented** for catalog-generated menus.

- When `MenuPlan.generation_engine == "catalog_planner"`, `MealReplacementService` raises `CatalogGenerationError(CATALOG_REPLACE_NOT_IMPLEMENTED)` **without** calling Claude.
- Legacy Claude menus (`generation_engine` absent / null) remain replaceable via the existing Claude path.
- API returns **501** with code `CATALOG_REPLACE_NOT_IMPLEMENTED`.

---

## Observability

Logged / returned fields:

- `generation_engine`, `planner_version` (`10.10`), `planner_score`, `planning_duration_ms`
- `catalog_recipe_count`, `meal_count`, `leftover_count`, `cooking_instance_count`, `unique_recipe_count`
- Budget utilization wire fields (same as Claude finalize path)

Progress stages reuse `JobStage` strings: `preparing`, `generating`, `validating` (+ job `saving` in execute).

---

## Performance smoke

On a seeded 80-recipe catalog DB (typical laptop):

| Scenario | Expected |
|----------|----------|
| Balanced 7×3 | Planner + adapt + finalize typically under a few seconds |
| Sparse cook days + leftovers | Leftovers present; basket dedupes by cooking instance |
| Impossible constraints | Fast `CatalogGenerationError`, Claude never called |

Exact timings depend on host; integration tests assert correctness, not hard latency budgets.

---

## Known limitations

1. **Replace-meal** for catalog menus is stubbed (`CATALOG_REPLACE_NOT_IMPLEMENTED`).
2. Leftover MenuPlan recipes use `{id}__leftover` snapshots to satisfy the ingredient contribution contract (cook vs leftover cannot share one recipe row with `from_source`).
3. No auto-fallback to Claude on planner failure.
4. Budget / price quality still depends on Basket Engine price resolution (may be sparse for some ingredients).
5. `source_verified_only` may yield `PLANNER_NO_PLAN` if the catalog lacks enough verified recipes for the requested week shape.
6. Planner config for production sets `allow_cook_day_miss=False` (strategy cooking compliance); beam/pool/max_states unchanged.

---

## Tests

Primary: `tests/test_catalog_planner_production_integration.py`

- Default engine, Claude spy not called
- Balanced 7×3, weight-loss, budgets, leftovers, leftovers off
- Impossible → error, Claude not called
- MenuPlan JSON roundtrip of `generation_engine` / meal_ids
- Catalog still 80 recipes

Startup: `tests/test_startup_validation.py` — Claude key required only for `legacy_claude`.

Packaging: `menu_generation` added to `REQUIRED_RUNTIME_PACKAGES`.

---

## How to run

```powershell
$env:PYTHONIOENCODING='utf-8'; $env:ENVIRONMENT='test'
python -m pytest tests/test_catalog_planner_production_integration.py tests/test_startup_validation.py -q --tb=short
python -m pytest -q --tb=line
```

Legacy Claude:

```powershell
$env:MEAL_GENERATION_ENGINE='legacy_claude'
# requires ANTHROPIC_API_KEY + CLAUDE_MODEL
```
