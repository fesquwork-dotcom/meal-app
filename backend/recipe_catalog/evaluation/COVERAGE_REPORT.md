# Recipe Catalog Coverage Report

Generated: `2026-08-04T16:55:52+00:00`
Catalog recipes: **30**
Schema version: `1`

## Executive Summary

- Scenarios: **90**
- Covered: **74**
- Weak: **5**
- Critical: **6**
- Expected empty: **5**
- Weighted coverage: **91.9%**

## Coverage by Meal Type

| Meal type | Coverage |
|-----------|----------|
| breakfast | 98.8% |
| dinner | 96.2% |
| lunch | 82.5% |

## Coverage by Goal

| Goal | Coverage |
|------|----------|
| balanced | 100.0% |
| budget | 76.8% |
| family | 100.0% |
| muscle_gain | 100.0% |
| quick_cooking | 100.0% |
| weight_loss | 80.7% |
| weight_maintenance | 100.0% |

## Coverage by Scenario Group

| Group | Coverage |
|-------|----------|
| baseline | 100.0% |
| budget | 92.6% |
| combined | 83.8% |
| equipment | 100.0% |
| goal | 100.0% |
| protein | 100.0% |
| stress | 75.0% |
| time | 77.8% |

## Weak Scenarios

- `budget_dinner_very_budget_only`: 2/3 (ratio=0.67)
- `budget_lunch_very_budget_only`: 2/3 (ratio=0.67)
- `dinner_quick_no_egg`: 2/5 (ratio=0.40)
- `dinner_weight_loss_quick_no_fish`: 4/5 (ratio=0.80)
- `lunch_budget_no_chicken`: 2/5 (ratio=0.40)

## Critical Scenarios

- `lunch_quick_budget`: expected 5, filters=TIME_LIMIT_EXCEEDED, BUDGET_CLASS_NOT_ALLOWED
- `lunch_weight_loss_30`: expected 5, filters=TIME_LIMIT_EXCEEDED
- `stress_breakfast_no_dairy_10`: expected 1, filters=EXCLUDED_INGREDIENT, TIME_LIMIT_EXCEEDED
- `stress_lunch_very_budget_20_no_chicken`: expected 1, filters=TIME_LIMIT_EXCEEDED, BUDGET_CLASS_NOT_ALLOWED, EXCLUDED_PROTEIN_SOURCE
- `time_lunch_le_20`: expected 3, filters=TIME_LIMIT_EXCEEDED
- `time_lunch_le_30`: expected 5, filters=TIME_LIMIT_EXCEEDED

## Common Filter Reasons

| Reason | Recipes removed (sum) | Scenarios hit |
|--------|----------------------|---------------|
| `TIME_LIMIT_EXCEEDED` | 165 | 21 |
| `BUDGET_CLASS_NOT_ALLOWED` | 68 | 10 |
| `EXCLUDED_PROTEIN_SOURCE` | 54 | 13 |
| `REQUIRED_EQUIPMENT_UNAVAILABLE` | 29 | 4 |
| `EXCLUDED_INGREDIENT` | 27 | 3 |

## Gap Clusters

### gap_004_lunch: lunch / budget / ≤30m

- Severity: `high`
- Scenarios: `lunch_quick_budget`
- Missing candidates (sum deficit): 5
- Dominant filters: TIME_LIMIT_EXCEEDED, BUDGET_CLASS_NOT_ALLOWED

### gap_006_lunch: lunch / weight_loss / ≤30m

- Severity: `high`
- Scenarios: `lunch_weight_loss_30`
- Missing candidates (sum deficit): 5
- Dominant filters: TIME_LIMIT_EXCEEDED

### gap_009_lunch: lunch / ≤30m

- Severity: `high`
- Scenarios: `time_lunch_le_30`
- Missing candidates (sum deficit): 5
- Dominant filters: TIME_LIMIT_EXCEEDED

### gap_008_lunch: lunch / ≤20m

- Severity: `high`
- Scenarios: `time_lunch_le_20`
- Missing candidates (sum deficit): 3
- Dominant filters: TIME_LIMIT_EXCEEDED

### gap_002_dinner: dinner / ≤30m

- Severity: `low`
- Scenarios: `dinner_quick_no_egg`
- Missing candidates (sum deficit): 3
- Dominant filters: EXCLUDED_INGREDIENT, TIME_LIMIT_EXCEEDED

### gap_005_lunch: lunch / budget / no_chicken

- Severity: `low`
- Scenarios: `lunch_budget_no_chicken`
- Missing candidates (sum deficit): 3
- Dominant filters: EXCLUDED_PROTEIN_SOURCE, BUDGET_CLASS_NOT_ALLOWED

### gap_000_breakfast: breakfast / ≤10m

- Severity: `low`
- Scenarios: `stress_breakfast_no_dairy_10`
- Missing candidates (sum deficit): 1
- Dominant filters: EXCLUDED_INGREDIENT, TIME_LIMIT_EXCEEDED

### gap_001_dinner: dinner / weight_loss / ≤30m / no_fish

- Severity: `low`
- Scenarios: `dinner_weight_loss_quick_no_fish`
- Missing candidates (sum deficit): 1
- Dominant filters: TIME_LIMIT_EXCEEDED, EXCLUDED_PROTEIN_SOURCE

### gap_003_dinner: dinner

- Severity: `low`
- Scenarios: `budget_dinner_very_budget_only`
- Missing candidates (sum deficit): 1
- Dominant filters: BUDGET_CLASS_NOT_ALLOWED

### gap_007_lunch: lunch / ≤20m / no_chicken

- Severity: `low`
- Scenarios: `stress_lunch_very_budget_20_no_chicken`
- Missing candidates (sum deficit): 1
- Dominant filters: TIME_LIMIT_EXCEEDED, BUDGET_CLASS_NOT_ALLOWED, EXCLUDED_PROTEIN_SOURCE

### gap_010_lunch: lunch

- Severity: `low`
- Scenarios: `budget_lunch_very_budget_only`
- Missing candidates (sum deficit): 1
- Dominant filters: BUDGET_CLASS_NOT_ALLOWED


## Recommended Recipe Additions

1. **Быстрый лёгкий обед с индейкой** — meal=`lunch`, goals=['budget'], time≤30, budget=`very_budget`, protein=`None`, impact≈2, gaps=['gap_004_lunch', 'gap_008_lunch']
1. **Быстрый лёгкий обед с индейкой** — meal=`lunch`, goals=['weight_loss'], time≤30, budget=`budget`, protein=`None`, impact≈1, gaps=['gap_006_lunch']
1. **Быстрый лёгкий обед с индейкой** — meal=`lunch`, goals=[], time≤30, budget=`budget`, protein=`None`, impact≈1, gaps=['gap_009_lunch']

## Metadata Review Recommendations

- [retag_or_review_existing_recipe] Review existing: Яичница с овощами (recipe=`recipe_fried_eggs_veg_001`)
- [retag_or_review_existing_recipe] Review existing: Чечевичный суп (recipe=`recipe_lentil_soup_001`)
- [review_goal_score] Review existing: Омлет с помидорами и сыром (recipe=`recipe_omelet_tomato_cheese_001`)
- [retag_or_review_existing_recipe] Review existing: Гречка с грибами и яйцом (recipe=`recipe_buckwheat_mushroom_egg_001`)
- [retag_or_review_existing_recipe] Review existing: Чечевичный суп (recipe=`recipe_lentil_soup_001`)
- [add_meal_type] Add dinner meal type: Лаваш с яйцом и сыром (recipe=`recipe_lavash_egg_cheese_001`)
- [review_goal_score] Review goal scores: Паста с тунцом и томатами (recipe=`recipe_pasta_tuna_tomato_001`)
