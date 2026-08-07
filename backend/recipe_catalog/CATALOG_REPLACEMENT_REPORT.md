# Sprint 10.12 — Catalog-Aware Replace Meal v1

## Architecture Audit

| Piece | Classification | Notes |
|--|--|--|
| `POST /api/menu/replace-meal` | REUSE | Same request/response contract |
| `ReplaceMealRequest` / `ReplaceMealResponse` | ADAPT | Optional explainability fields added |
| `ReplacementReasonCode` wire vocab | REUSE | Mapped to local catalog reasons |
| `MealReplacementService` Claude path | LEGACY | Intact for non-catalog menus |
| Catalog 501 gate | ADAPT | Routes to `CatalogMealReplacementService` |
| `build_replacement_context` | REUSE | Target + downstream discovery |
| `merge_replacement` (preserves recipe_id) | UNTOUCHED | Claude-only; catalog uses `apply_catalog_repair` |
| `build_basket_from_menu` | REUSE | Full rebuild after repair |
| `RecipeCandidateSelector` | REUSE | Candidate source; weights unchanged |
| `RecipeScaler` / adapter `_build_snapshot` | REUSE | Nutrition + portions |
| Cooking identity / leftovers contract | REUSE | No parallel identity model |
| `WeeklyRecipePlanner` / beam / weights | UNTOUCHED | |
| StrategyBuilder / FeasibilityAnalyzer | UNTOUCHED | |
| Catalog recipes (86) | UNTOUCHED | |

## Replacement Flow

```
MenuPlan (catalog_planner)
→ build_replacement_context
→ resolve CatalogReplacementReason
→ resolve RepairMode
→ RecipeCandidateSelector (avoid current + week duplicates)
→ local replacement scorer
→ apply_catalog_repair
→ validate_menu_plan + strategy + cooking contract
→ rebuild Basket
→ persist revision (CAS) / memory
→ ReplaceMealResponse
```

## Engine Routing

- `generation_engine == catalog_planner` → `CatalogMealReplacementService` (Claude never called)
- otherwise → legacy `MealReplacementService` Claude loop
- Catalog failure → `CATALOG_REPLACEMENT_NOT_FOUND` (422), never Claude fallback

## Candidate Selection

- `StrategyToCandidateContextAdapter` + `RecipeCandidateSelector.select`
- Always excludes current catalog recipe id (`__leftover` stripped)
- Excludes other same-type week recipes when repeats are disabled
- Limit 40 candidates; local scorer re-ranks

## Reason Semantics

Wire codes preserved (`faster`, `dislike_ingredient`, `ingredient_unavailable`, …).

Local layer:

| Local reason | Behavior |
|--|--|
| TOO_LONG | Prefer `total_time` &lt; current |
| TOO_EXPENSIVE | Prefer cheaper `budget_class` |
| INGREDIENT_UNAVAILABLE | Hard-exclude candidates containing target ingredient |
| DONT_LIKE | Exclude target ingredient; prefer structural difference |
| WANT_VARIETY | Boost diversity / different protein |
| GENERIC | Selector + weekly compatibility |

## Weekly Compatibility

Structural checks without beam search:

- current recipe excluded
- no consecutive same recipe (same meal type)
- no cooking recipe on non-cook day when force_no_cook
- full `validate_menu_plan` / `validate_menu_against_strategy` / `validate_cooking_contract` after repair

## Cooking Identity

Repair modes:

1. **SINGLE_SLOT** — cooked meal without dependents: only target slot changes
2. **SOURCE_CHAIN** — source with dependents OR leftover on non-cook / last leftover: update source + leftovers together (shared `cooking_instance_id`, leftover `__leftover` snapshot)
3. **LEFTOVER_TO_INDEPENDENT** — leftover on cook day when other leftovers remain: convert target to independent meal; clear `source_meal_id`

## Leftover Repair

Policy v1 (documented):

- Prefer independent leftover replacement only when strategy leftovers remain satisfied and day is a cook day.
- Otherwise repair the cooking group as one chain so orphans cannot appear.
- Basket always rebuilt from the full MenuPlan (instance dedupe handles servings).

## Basket Rebuild

`build_basket_from_menu(..., require_all_prices=False)` — same as catalog finalize. Source of truth = full rebuild. Presentation delta deferred.

## Explainability

Template-based `explanation` + machine `replacement_reasons` + `replacement_engine=catalog_selector`. No LLM text.

## Failure Model

| Case | Result |
|--|--|
| No candidate | `CATALOG_REPLACEMENT_NOT_FOUND` + details |
| Invalid meal_id | existing `MEAL_NOT_FOUND` 404 |
| Validation fail after pick | no persist (atomic) |
| Catalog menu | never 501 after this sprint |

## Determinism

Same MenuPlan + Profile/Strategy + meal_id + reason + Catalog → same `recipe_id` (tie-break `recipe_id` ascending).

## Performance

Local replacement ≪ weekly beam. Typical smoke in tests: seconds including catalog generate setup; replacement itself is selector + validation + basket.

## Claude Call Verification

Spy tests: catalog success and catalog NOT_FOUND → Claude calls = 0.

## Production-like Cases

Covered in `tests/test_catalog_replacement.py`:

- breakfast / lunch / dinner replace
- leftover chain + source replace
- reason variants
- determinism
- API 200 for catalog menus

## Known Limitations

- No optimistic concurrency beyond existing `expected_revision` CAS when `menu_plan_id` is set.
- Basket delta (`added`/`removed`/`changed`) not returned yet (rebuild only).
- Leftover→independent on non-cook dinner days falls back to SOURCE_CHAIN (few no-cook dinners in catalog).
- Claude `merge_replacement` still preserves recipe_id (legacy identity); catalog path intentionally changes catalog recipe_id.
- Does not re-run StrategyFeasibilityAnalyzer (strategy already fixed).
