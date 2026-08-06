# Sprint 10.11.6 — Strategy Consistency & Preview Feasibility

## Root Cause

`resolve_cook_days` and `resolve_leftovers_enabled` used independent goal sets:

| Set | Goals |
|--|--|
| `LEFTOVERS_GOALS` | home, healthy, budget, weightloss |
| `BATCH_COOK_GOALS` | home, budget, **muscle** |

`goal=muscle` produced `leftovers=false` + sparse `cook_days=[1,3,5]` + `batch_allowed=true`.

Strategy rules allowed it; catalog feasibility did not (`NON_COOK_DAY_UNCOVERED` on day2/day4 dinner). Preview never ran feasibility → `warning_count=0`.

## Old Strategy Behavior

```
muscle + days=5 + medium
→ leftovers=false
→ cook_days=[1,3,5]
→ batch_allowed=true
→ Preview: ready, warnings=0
→ Generation: STRATEGY_INFEASIBLE
```

## New Consistency Rule

Chosen architecture: **A — `resolve_cook_days(context, leftovers_enabled=...)`**

1. Resolve leftovers first (unchanged goal sets).
2. Pass leftovers into cook-days resolver.
3. If `leftovers_enabled=false` → return all planning days.
4. Do **not** auto-enable leftovers for muscle.

DecisionEngine order:

```
leftovers = resolve_leftovers_enabled(context)
cook_days = resolve_cook_days(context, leftovers_enabled=leftovers)
batch_allowed = (cook_days != all_days) or leftovers
```

## Goal Matrix (days=5, cooktime=medium unless noted)

| Goal | leftovers | cook_days | batch_allowed |
|--|--|--|--|
| home | true | [1,3,5] | true |
| budget | true | [1,3,5] | true |
| healthy | true | [1,2,3,4,5] | true* |
| weightloss | true | [1,2,3,4,5] | true* |
| **muscle** | **false** | **[1,2,3,4,5]** | **false** |
| restaurant | false | [1,2,3,4,5] | false |
| home + fast | true | [1,2,3,4,5] | true* |

\* `batch_allowed` true because leftovers_enabled (formula: sparse OR leftovers).

## DecisionTrace Changes

New applied rule when leftovers=false forces daily cook:

- `COOK_DAYS_DAILY_NO_LEFTOVERS` / reason `COOK_DAYS_DAILY_NO_LEFTOVERS`
- Rejected: `COOK_DAYS_BATCH_GOAL` / `COOK_DAYS_REQUIRES_LEFTOVERS`

User-facing copy (no «заготовки» when leftovers=false):

> Поскольку блюда на следующий день не используются, приготовление распределено по каждому дню.

## Preview Feasibility Integration

```
Profile → DecisionEngine/StrategyBuilder
       → profile/memory conflict warnings
       → StrategyFeasibilityAnalyzer (existing)
       → Preview (feasibility_* populated)
```

- `StrategyPreviewService.build_preview` is **async** (catalog load).
- Generation still rechecks feasibility before Planner.
- Preview does **not** run beam search.
- Feasibility warning codes are distinct:
  - `STRATEGY_FEASIBILITY_INFEASIBLE`
  - `STRATEGY_FEASIBILITY_RELAXATION`

## Muscle Production Case

| Step | Result |
|--|--|
| Strategy | leftovers=false, cook_days=[1..5], batch_allowed=false |
| Feasibility | FEASIBLE |
| Generation | SUCCESS, 15 meals, relaxation_used=false |

## Home / Budget Regression

| Goal | leftovers | cook_days | Notes |
|--|--|--|--|
| home days=5 | true | [1,3,5] | FEASIBLE; leftovers used |
| budget days=7 | true | [1,3,5,7] | unchanged |

## Preview Warning Examples

| Status | warning_count | Copy |
|--|--|--|
| FEASIBLE | no feasibility warning | — |
| FEASIBLE_WITH_RELAXATION | +1 | «План можно составить, но может потребоваться один дополнительный день готовки.» |
| INFEASIBLE | +1 | «С текущими настройками меню нельзя составить без дополнительной готовки…» |

## Performance

Muscle preview smoke with catalog import warm path: structural analyzer only; measured under 5s in tests (no hard CI budget).

## Known Limitations

- Consistency rule is binary (leftovers off → daily). Future: allow sparse without leftovers if catalog proves sufficient no-cook dinner coverage.
- Preview feasibility uses the same catalog DB as generation; stale catalog between preview and confirm remains a race (generation rechecks).
- Preview token payload unchanged (feasibility not hashed into token).
