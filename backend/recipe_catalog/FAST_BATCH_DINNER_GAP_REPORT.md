# Sprint 10.11.5 — Fast Batch Dinner Catalog Gap Report

## Baseline Gap

| Metric | Before |
|--------|--------|
| Catalog recipes | 80 |
| Dinner recipes | 24 |
| Dinner ≤20 + batch + leftover | **0** |
| CTL=20, cook_days=[1,3,5], leftovers | **INFEASIBLE** (`NO_BATCH_LEFTOVER_CANDIDATE`) |
| CTL=45 same strategy | FEASIBLE + planner success |

Root cause: day3 dinner had no batch+leftover candidates under CTL=20, so day4 dinner could not be closed by leftover, and a second extra cook day is forbidden (`max_extra_cook_days=1`).

## New Recipes

Exactly **6** dinner recipes added → catalog **86**.

| ID | Slug | Protein | Time | Budget |
|----|------|---------|------|--------|
| `recipe_chicken_bean_pepper_skillet_001` | chicken-bean-pepper-skillet | chicken | 20 | budget |
| `recipe_turkey_bean_corn_skillet_001` | turkey-bean-corn-skillet | turkey | 20 | budget |
| `recipe_white_fish_tomato_beans_001` | white-fish-tomato-beans | fish | 20 | standard |
| `recipe_bean_corn_tomato_skillet_001` | bean-corn-tomato-skillet | legumes | 17 | very_budget |
| `recipe_egg_bean_spinach_skillet_001` | egg-bean-spinach-skillet | eggs | 20 | budget |
| `recipe_beef_bean_tomato_skillet_001` | beef-bean-tomato-skillet | beef | 20 | standard |

All: `batch_friendly=true`, `leftover_friendly=true`, `storage_days≥2`, `max_batch_servings≥4`, `creation_method=source_adapted`, ≥2 sources, Quality Gate blocking errors = 0.

## Sources

| Recipe | Source 1 | Source 2 |
|--------|----------|----------|
| Chicken bean pepper | [Warmfeast 15-min salsa bean chicken](https://warmfeast.com/15-minute-salsa-and-black-bean-chicken-skillet/) (storage 3–4d) | [BBC Food quick chicken chilli](https://www.bbc.co.uk/food/recipes/quick_chicken_chilli_70026) |
| Turkey bean corn | [Real Food Whole Life turkey taco skillet](https://realfoodwholelife.com/recipes/turkey-taco-skillet/) | [Family Food turkey taco rice skillet](https://www.familyfoodonthetable.com/turkey-taco-rice-skillet/) (rice omitted) |
| White fish tomato beans | [What's Gaby Cooking fish + tomato beans](https://whatsgabycooking.com/white-fish-with-tomato-basil-beans/) (2–3d) | [BBC Good Food fish + spicy beans](https://www.bbcgoodfood.com/recipes/white-fish-spicy-beans-and-chorizo) (chorizo omitted) |
| Bean corn tomato | [BBC Good Food quick chilli bean wraps](https://www.bbcgoodfood.com/recipes/quick-chilli-bean-wraps) | [BBC Good Food tomato pepper bean one pot](https://www.bbcgoodfood.com/recipes/tomato-pepper-bean-one-pot) (fridge 3–4d) |
| Egg bean spinach | [BBC Good Food smoky beans & baked eggs](https://www.bbcgoodfood.com/recipes/smoky-beans-baked-eggs) (bean base freezable) | [BBC Good Food saucy bean baked eggs](https://www.bbcgoodfood.com/recipes/saucy-bean-baked-eggs) |
| Beef bean tomato | [BBC Good Food super speedy chilli](https://www.bbcgoodfood.com/recipes/super-speedy-chilli) | [BBC Good Food Mexican bean chilli](https://www.bbcgoodfood.com/recipes/mexican-bean-chilli) |

## Duplicate Rejections

| Rejected concept | Reason |
|------------------|--------|
| Turkey + couscous dinner | Near-duplicate of `turkey-couscous-lunch` |
| Chickpea + tomato + spinach dinner ≤20 | Near-duplicate of `chickpea-spinach-dinner` |
| Faster fish+veg skillet | Near-duplicate of `fish-veg-skillet-dinner` |
| Tuna + zucchini batch rewrite | Near-duplicate of `tuna-zucchini-dinner` |
| Chicken + mushroom ≤20 | Near-duplicate of `chicken-mushroom-dinner` |
| Beef + zucchini ≤20 | Near-duplicate of `beef-zucchini-dinner` |

See also `REJECTED_DUPLICATES_10_11_5.md`.

## Protein Distribution

chicken, turkey, fish, legumes, eggs, beef — one each among the six new dinners.

## Budget Distribution

- very_budget / budget: 4 (`bean-corn`, `chicken`, `turkey`, `egg`)
- standard: 2 (`fish`, `beef`)
- premium: 0

## Batch / Leftover Evidence

- Scale: `max_batch_servings=8` on all six; one-pan / one-pot stewing or skillet methods.
- Storage: source notes support ≥2 days fridge for chilli/skillet styles; egg card uses **fully set eggs** (not runny yolks) and `storage_days=2`.
- Pattern Evidence / Quality Audit: failed_count=0; warnings remain honest nutrition incompleteness (no invented macros).

## Relations

Added `rel_142`–`rel_155` (14 relations): `avoid_consecutive_days`, `shares_ingredients`, `similar_meal`, `good_pair`.

Total relations: **155**.

## Feasibility Before / After

| CTL | Before | After |
|-----|--------|-------|
| 20 | INFEASIBLE (`NO_BATCH_LEFTOVER_CANDIDATE`) | **FEASIBLE** |
| 45 | FEASIBLE | FEASIBLE |

## Planner Before / After

| CTL | Before | After |
|-----|--------|-------|
| 20 | Not started (feasibility block) | **SUCCESS** 15 meals, leftovers ≥1, strict pass |
| 45 | SUCCESS | SUCCESS |

`max_leftovers_per_cook=1`, `max_extra_cook_days=1`, beam/weights/pool unchanged.

## Leftover Chain Example (CTL=20)

Observed strict plan:

- `day1_dinner` `recipe_turkey_bean_corn_skillet_001` → `day2_dinner` leftover same recipe
- `day3_dinner` `recipe_chicken_bean_pepper_skillet_001` → `day4_dinner` leftover same recipe

## Coverage Impact

| Metric | After |
|--------|-------|
| Weighted coverage | **99.7%** (unchanged vs 10.9) |
| Critical | 1 (unchanged) |
| Weak | 0 (unchanged) |
| Planner readiness | `ready_for_v1` |
| Fast Batch Dinner Coverage | **6** |

## Catalog Counts

| Metric | Value |
|--------|-------|
| Total | 86 |
| Dinner | 30 |
| Dinner ≤20 | 8 (includes 2 prior non-batch) |
| Dinner ≤20 + batch + leftover | **6** |

## Known Limitations

- Structural feasibility ≠ full multi-meal leftover inventory simulation.
- Egg leftovers require fully set eggs; runny-yolk baked eggs were intentionally avoided.
- Ingredient nutrition DB still incomplete — approximate recipe snapshots only.
- Some non-cook breakfast/lunch slots still rely on no-cook / quick recipes under CTL=20.

## Recommended Next Step

Optional: expand fast batch **lunch** under CTL=20 for sparse cook days, or add 1–2 more fish/seafood fast batch dinners for protein variety under heavy poultry preference.
