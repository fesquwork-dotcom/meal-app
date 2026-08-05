# Recipe Catalog Coverage Report

Generated: `2026-08-04T21:15:41+00:00`
Catalog recipes: **80**
Schema version: `1`

## Executive Summary

- Scenarios: **90**
- Covered: **84**
- Weak: **0**
- Critical: **1**
- Expected empty: **5**
- Weighted coverage: **99.7%**

## Coverage by Meal Type

| Meal type | Coverage |
|-----------|----------|
| breakfast | 100.0% |
| dinner | 100.0% |
| lunch | 99.2% |

## Coverage by Goal

| Goal | Coverage |
|------|----------|
| balanced | 100.0% |
| budget | 100.0% |
| family | 100.0% |
| muscle_gain | 100.0% |
| quick_cooking | 100.0% |
| weight_loss | 100.0% |
| weight_maintenance | 100.0% |

## Coverage by Scenario Group

| Group | Coverage |
|-------|----------|
| baseline | 100.0% |
| budget | 100.0% |
| combined | 100.0% |
| equipment | 100.0% |
| goal | 100.0% |
| protein | 100.0% |
| stress | 87.5% |
| time | 100.0% |

## Weak Scenarios


## Critical Scenarios

- `stress_lunch_very_budget_20_no_chicken`: expected 1, filters=BUDGET_CLASS_NOT_ALLOWED, TIME_LIMIT_EXCEEDED, EXCLUDED_PROTEIN_SOURCE

## Common Filter Reasons

| Reason | Recipes removed (sum) | Scenarios hit |
|--------|----------------------|---------------|
| `TIME_LIMIT_EXCEEDED` | 270 | 21 |
| `BUDGET_CLASS_NOT_ALLOWED` | 191 | 10 |
| `EXCLUDED_PROTEIN_SOURCE` | 128 | 13 |
| `EXCLUDED_INGREDIENT` | 52 | 3 |
| `REQUIRED_EQUIPMENT_UNAVAILABLE` | 49 | 4 |

## Gap Clusters

### gap_000_lunch: lunch / ≤20m / no_chicken

- Severity: `low`
- Scenarios: `stress_lunch_very_budget_20_no_chicken`
- Missing candidates (sum deficit): 1
- Dominant filters: BUDGET_CLASS_NOT_ALLOWED, TIME_LIMIT_EXCEEDED, EXCLUDED_PROTEIN_SOURCE


## Recommended Recipe Additions

_None_

## Metadata Review Recommendations

- [add_meal_type] Add dinner meal type: Лаваш с яйцом и овощами (recipe=`recipe_egg_veg_wrap_flex_001`)
- [review_goal_score] Review goal scores: Паста с тунцом и томатами (recipe=`recipe_pasta_tuna_tomato_001`)

## Sprint 10.9 notes

- Baseline: 40 recipes, dinner_quick_no_egg=weak_4_of_5, weighted≈98.8%, critical=2, weak=2.
- After: 80 recipes, dinner_quick_no_egg=**covered**, weighted≈99.7%, critical=1 (stress_lunch_very_budget_20_no_chicken), weak=0.
- Known mismatch: lentil soup seed time 45 vs sources 15–20 (not auto-fixed).
