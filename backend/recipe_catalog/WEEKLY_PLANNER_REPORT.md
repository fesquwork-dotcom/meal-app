# Weekly Planner Report — Sprint 10.10

Deterministic **Weekly Recipe Planner v1** over Profile / WeeklyStrategy / Recipe Catalog / RecipeCandidateSelector / relations.

**Does not** use Claude, generate recipes, mutate the catalog, or touch MenuPlan / Basket.

---

## Architecture

### Reused as-is

| Component | Path |
|-----------|------|
| WeeklyStrategy | `strategy/models.py` |
| StrategyBuilder (untouched) | `strategy/builder.py` |
| ProfileContext | `strategy/context.py` |
| RecipeCandidateSelector | `recipes/selection/selector.py` |
| CandidateSelectionContext | `recipes/selection/context.py` |
| Strategy / Profile adapters | `recipes/selection/*_adapter.py` |
| RecipeRepository + relations | `recipes/repository.py` |
| RelationType / Recipe roles | `recipes/enums.py` |

### Adapted (thin wrappers)

| Piece | Role |
|-------|------|
| `build_planning_context_from_strategy` | WeeklyStrategy → `WeeklyPlanningContext` |
| `PlanningCandidateProvider` | Builds slot context + calls Selector; applies optional quality floor |
| Cook-day / leftover policy | Soft cook-day miss escape; leftovers explicit via cooking instances |

### New

Package: `backend/recipes/planning/`

| Module | Responsibility |
|--------|----------------|
| `models.py` | `WeeklyRecipePlan`, meals, cooking instances, diagnostics |
| `context.py` | `WeeklyPlanningContext` |
| `slots.py` | Stable `dayN_mealtype` slots |
| `candidate_provider.py` | Selector-backed pools |
| `constraints.py` | Hard weekly checks |
| `relations.py` | Relation index |
| `weekly_scorer.py` | Weekly score + breakdown |
| `weights.py` | Planner weights / beam config |
| `planner.py` | Deterministic beam search |
| `validator.py` | Structured violations |
| `explanation.py` | Week + per-meal reasons |
| `evaluator.py` | Post-hoc metrics |
| `diversity.py` | Helpers |
| `codes.py` | Planner reason / violation codes |

CLI: `python -m recipes.cli plan-week`

### Intentionally untouched

- Claude service / generation pipeline
- `MenuPlan` / `menu_plan/`
- Basket engine
- Selector weights / hard filters / evaluation scenarios
- Catalog size (remains **80** recipes)
- Known data issues (lentil soup time, nutrition DB, etc.)

---

## Algorithm

**Deterministic beam search** over ordered slots (`day1_breakfast` → … → `dayN_dinner`).

1. Build `WeeklyPlanningContext` once.
2. Build slots (stable IDs).
3. For each meal type, call **RecipeCandidateSelector** once with `limit = candidate_pool_size` (default 15).
4. For each slot, expand beam states with:
   - leftover actions (from cooking instances with remaining servings);
   - cook actions from Selector pool (hard weekly constraints applied).
5. Keep top `beam_width` states by weekly score; tie-break by assignment tuple / `recipe_id`.
6. Validate, explain, return `WeeklyRecipePlan`.

No LLM, no ML, no random.

### Config defaults

| Key | Default |
|-----|---------|
| `candidate_pool_size` | 15 |
| `beam_width` | 8 |
| `max_states` | 4000 |
| `max_independent_recipe_repeats` | 1 |
| `max_leftovers_per_cook` | 1 |
| `allow_cook_day_miss` | true (soft escape) |

---

## Weekly scoring weights

```
selector_quality     0.35
recipe_diversity     0.12
protein_diversity    0.14
relation_score       0.10
strategy_alignment   0.12
batch_efficiency     0.08
ingredient_reuse     0.05  (capped raw contribution)
```

Penalties: recipe repeat, consecutive protein, similar_meal, cook_day_miss.  
Breakfast diversity penalties scaled by `breakfast_diversity_scale = 0.35`.

Score normalized to **0..1** with breakdown.

Selector score is an **input**, not modified.

---

## Hard constraints

1. Required slots filled (else `partial` / `no_plan`)
2. Meal type supported
3. Selector hard filters (via candidate pool)
4. Excluded ingredients / proteins
5. Time / budget class
6. Avoided recipes
7. `avoid_consecutive_days` on adjacent days
8. Independent recipe repeat ≤ `max_independent_recipe_repeats`
9. Leftover requires source cooking instance, earlier slot, same recipe, remaining servings
10. No leftovers when `leftovers_enabled=false`
11. Optional `minimum_quality_status` (e.g. source_verified_only)

Impossible weeks → **no Claude fallback**; structured diagnostics with `unfilled_slots` + filter causes.

---

## Soft constraints / bonuses

- Protein diversity (lunch/dinner; breakfast softer)
- similar_meal penalty
- good_pair / shares_ingredients bonuses
- Cook-day match vs miss
- Batch + leftover efficiency
- Bounded ingredient reuse
- Preferred proteins (via Selector soft score)

---

## Relations usage

| Relation | Behaviour |
|----------|-----------|
| `avoid_consecutive_days` | Hard |
| `similar_meal` | Soft penalty |
| `shares_ingredients` | Soft bonus |
| `good_pair` | Soft bonus |
| `uses_leftovers_from` / `provides_component_for` | Indexed for future / leftover-friendly pairing; leftover eligibility still requires `leftover_friendly` |

---

## Batch / leftover logic

- Cook of `batch_friendly` + `leftover_friendly` (non-breakfast) with leftovers enabled → cooking instance with `servings_cooked = 1 + max_leftovers_per_cook`.
- Later slot may consume leftover: `is_leftover=true`, `source_slot_id`, same `cooking_instance_id`, `requires_cooking=false`.
- Not a double cook: independent cook count increments only for non-leftover meals.
- Leftovers disabled → all `servings_cooked=1`, zero leftover meals.

---

## Determinism

Same context + catalog → same `plan_id`, recipe IDs, leftover links, scores, reason ordering (except wall-clock `planning_duration_ms`).

Verified by `test_determinism_same_plan_twice`.

---

## Performance

| Metric | Smoke (7×3, leftovers) |
|--------|-------------------------|
| Duration | ~277 ms |
| Target | < 2 s |

Selector called once per meal type (not per slot). Beam bounded by `beam_width` / `max_states`.

---

## Scenario results

| ID | Scenario | Result |
|----|----------|--------|
| A | Balanced 7×3 | success, 21 slots |
| B | Budget / very_budget | success, budget classes respected |
| C | Weight loss | success |
| D | Max time ≤30 | success, cooks ≤30 |
| E | No fish | success, fish=0 |
| F | Prefer poultry | success, not monoculture |
| G | Leftovers off | success, leftovers=0 |
| H | Leftovers + sparse cook days | success / partial OK; leftovers linked |
| I | source_verified_only | success |
| J | Impossible constraints | no_plan or partial + diagnostics |

---

## Example week (CLI smoke)

Status `success`, score ≈ 0.69, leftovers ≈ 4.

| Day | Breakfast | Lunch | Dinner |
|-----|-----------|-------|--------|
| 1 | Cook | Cook | Cook |
| 2 | Cook | Cook | Cook |
| 3 | Cook | Cook | Cook |
| 4 | Cook | Cook | Leftover |
| 5 | Cook | Leftover | Leftover |
| 6 | Cook | Leftover | Cook |
| 7 | Cook | Cook | Cook |

Exact recipe names vary with catalog state; see CLI `--json` for IDs.

---

## Failure diagnostics example

```json
{
  "status": "no_plan",
  "unfilled_slots": ["day1_breakfast", "..."],
  "slot_filter_causes": {
    "day1_breakfast": {
      "TIME_LIMIT_EXCEEDED": 12,
      "BUDGET_CLASS_NOT_ALLOWED": 8
    }
  }
}
```

---

## Known limitations

1. Beam is greedy over partial weekly scores — not globally optimal.
2. Leftover capacity capped at 1 extra meal per cook (v1).
3. Cook-day miss allowed as escape when leftovers cannot fill a slot.
4. Strategy protein vocab lacks `turkey` (catalog tag exists); CLI/tests may set preferred proteins on planning context.
5. Quality floor applied in planner, not inside Selector (`minimum_quality_status` still reserved there).
6. Does not integrate with production MenuPlan / Basket yet.
7. Does not fix catalog data issues (lentil soup time, nutrition DB, orphan relations).

---

## Recommended next step

**Sprint 10.11** — Integrate WeeklyRecipePlan with production MenuPlan/Basket behind a feature flag, without Claude recipe generation for catalog-backed weeks.
