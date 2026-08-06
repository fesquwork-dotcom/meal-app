# Sprint 10.11.4 — Strategy Feasibility Guard

## Architecture

```
Profile → StrategyBuilder → WeeklyStrategy
                              ↓
                   StrategyFeasibilityAnalyzer  (catalog structural check)
                              ↓
              FEASIBLE | FEASIBLE_WITH_RELAXATION | INFEASIBLE
                              ↓
                   WeeklyRecipePlanner (only if not INFEASIBLE)
```

Package: `strategy/feasibility/`
- `models.py` — status, issues, suggestions, catalog gaps
- `analyzer.py` — `StrategyFeasibilityAnalyzer`

Integration: `CatalogMenuGenerationService.generate` runs feasibility **before** beam search.
On `INFEASIBLE` raises `CatalogGenerationError(STRATEGY_INFEASIBLE)` without mutating strategy/profile.

## Feasibility model

| Status | Meaning |
|--|--|
| `FEASIBLE` | Non-cook lunch/dinner slots covered by batch+leftover or no-cook under CTL |
| `FEASIBLE_WITH_RELAXATION` | Gaps ≤ `max_extra_cook_days` (still 1) |
| `INFEASIBLE` | More gaps than allowed extra cook days / no structural coverage |

## Non-cook day analysis

For `cook_days=[1,3,5]`, non-cook days `{2,4}`.
Each lunch/dinner slot checks:

1. preceding cook day has batch+leftover candidates after profile+time filters, or
2. no-cook alternative under CTL, else
3. marks gap (needs extra cook / infeasible).

Breakfast/snack treated as soft (not leftover-chain critical for v1).

## CTL=20 production-like

`days=5`, `cook_days=[1,3,5]`, leftovers, CTL=20 → **INFEASIBLE**

Typical issues:

- `TIME_LIMIT_REMOVES_REQUIRED_BATCH_CANDIDATES` and/or `NO_BATCH_LEFTOVER_CANDIDATE`
- targets include `day2_dinner` / `day4_dinner`
- catalog gap: `{meal_type: dinner, required_properties: [batch_friendly, leftover_friendly], max_time: 20}`

Planner is **not** started.

## CTL=45 control

Same cook_days, CTL=45 → **FEASIBLE**; catalog generation succeeds (15 meals).

## Suggested adjustments

- `RELAX_TIME_LIMIT` with catalog-derived `minimum_supported`
- `ADD_COOK_DAY` for uncovered non-cook days
- `CATALOG_COVERAGE_REQUIRED` when no batch+lo exists even without time filter
- `ALLOW_EXTRA_COOK_DAY` when status is `FEASIBLE_WITH_RELAXATION`

## Catalog gap example

```json
{
  "meal_type": "dinner",
  "required_properties": ["batch_friendly", "leftover_friendly"],
  "max_time": 20,
  "needed_for": "non_cook_day",
  "source_cook_day": 3,
  "target_slot": "day4_dinner"
}
```

## Logging

- `strategy_feasibility_checked status=… cook_days=… time_limit=… issue_count=…`
- `strategy_infeasible issue_codes=… affected_slots=… suggested_adjustments=…`

## Unchanged

- Planner beam/weights/pool/`max_leftovers_per_cook=1`/`max_extra_cook_days=1`
- Catalog 80 recipes
- Persisted WeeklyStrategy / profile
- `TerminationReason.MAX_EXTRA_COOK_DAYS` regression kept

## Limitations

- Structural only (not a full leftover inventory simulation across multiple meals sharing one cook).
- Breakfast coverage is soft.
- Preview API exposes optional `feasibility_*` fields; population is generation-path primary in v1.
