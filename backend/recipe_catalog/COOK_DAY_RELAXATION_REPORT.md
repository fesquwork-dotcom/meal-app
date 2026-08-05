# Sprint 10.11.2 — Controlled Cook-Day Relaxation

## Goal

Eliminate production `COOK_DAY_CONFLICT` deadlocks without mutating `WeeklyStrategy.cook_days`
and without broadly weakening planner constraints.

## Behavior

1. **Strict pass** — `WeeklyPlannerConfig(allow_cook_day_miss=False)`.
2. If `success` → return plan (`relaxation_used=false`).
3. **Relaxation gate** (all required):
   - status `partial` / `no_plan`
   - `termination_reason=COOK_DAY_CONFLICT`
   - failed slot had candidates after hard filters
   - weekly removals (or aggregate stats) show cook-day conflict
4. **Relaxed pass** — `allow_cook_day_miss=True`, `max_extra_cook_days=1`,
   strong `extra_cook_day_penalty=0.30` (weights defaults unchanged).
5. Weekly constraint tracks unique extra cook days; blocks `MAX_EXTRA_COOK_DAYS`.
6. Finalize / compliance use **original** strategy; extra cook day → warning
   `EXTRA_COOK_DAY_REQUIRED` + RU explanation (not a silent rewrite of cook_days).

## Metadata on MenuPlan payload

- `strict_pass_status`
- `relaxation_used`
- `extra_cook_days`
- `original_failed_slot`
- `original_diagnostics`
- `strategy_cook_days` (unchanged preferred days)
- `warnings` / `explanations` / `cook_day_relaxation`

## Files

- `menu_generation/cook_day_relaxation.py` — gate + configs + metadata helpers
- `menu_generation/catalog_service.py` — two-pass orchestration
- `menu_generation/finalize.py` — soft warnings, version `10.11.2`
- `recipes/planning/weights.py` — `max_extra_cook_days`, `extra_cook_day_penalty`
- `recipes/planning/constraints.py` — extra-day cap when miss allowed
- `recipes/planning/planner.py` — `extra_cook_days` on beam state
- `recipes/planning/weekly_scorer.py` — config penalty override
- `strategy/cooking_compliance.py` / `compliance.py` — valid-with-warning path
- `tests/test_cook_day_relaxation.py` — cases 18–21

## Tests

Full backend suite: **1487 passed**.
