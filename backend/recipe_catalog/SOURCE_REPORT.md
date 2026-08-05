# Source Coverage Report (Sprint 10.9)

## Source Summary

| Metric | Value |
|--------|-------|
| Total recipes | 80 |
| New recipes this sprint | 40 |
| Existing recipes with source review attached | 10 |
| source_adapted (YAML / audit) | 50 |
| agent_generated (remaining seeds without full sources) | variable |
| source_verified (after quality-audit --apply) | **65** |
| human_reviewed | 0 |
| kitchen_tested | 0 |
| approved | **0** (auto-approve forbidden) |
| Relations total | 141 (106 new from rel_036+) |
| New canonical ingredients | ing_bread, ing_berries, ing_millet, ing_couscous |

## Coverage vs BASELINE_SPRINT_10_9.json

| Metric | Before (baseline) | After |
|--------|-------------------|-------|
| Recipes | 40 | 80 |
| source_verified | 15 | 65 |
| Weighted coverage | 98.8% | **99.7%** |
| Critical | 2 | **1** |
| Weak | 2 | **0** |
| dinner_quick_no_egg | weak_4_of_5 | **covered** |

## Known source mismatches (not auto-fixed)

### recipe_lentil_soup_001

| Field | Value |
|-------|-------|
| field | total_time_minutes |
| current | 45 |
| source range | ~15–20 min simmer (BBC-style red lentil soups) |
| severity | medium |
| suggested review action | Human review whether seed time includes soaking/prep or should be lowered; do not auto-mutate |

Other seed recipes may show soft time/proportion warnings under computational audit; nutrition cannot be recalculated while ingredient nutrition DB is empty.

## Existing recipes source-reviewed in 10.9

Body of each seed was **not** auto-mutated. Provenance/sources attached for review.

| Recipe ID |
|-----------|
| recipe_buckwheat_milk_001 |
| recipe_fried_eggs_veg_001 |
| recipe_oatmeal_apple_cinnamon_001 |
| recipe_yogurt_oats_banana_001 |
| recipe_pasta_tuna_tomato_001 |
| recipe_stewed_beans_veg_001 |
| recipe_turkey_veg_skillet_001 |
| recipe_chicken_noodle_soup_001 |
| recipe_pasta_chicken_tomato_001 |
| recipe_rice_chicken_veg_001 |

## New source-backed recipes (40)

Breakfast (12): spinach_cottage_frittata, eggs_veg_toast, mushroom_egg_scramble_bf, cottage_berries_bowl, savory_cottage_cucumber, yogurt_oats_berries, millet_milk_porridge, couscous_milk_breakfast, overnight_oats_classic, chickpea_hummus_toast, cottage_lavash_roll_bf, baked_oat_apple.

Flexible (2): egg_veg_rice_bowl_flex, chickpea_yogurt_bowl_flex.

Lunch (14): turkey_couscous, chicken_rice_bowl, chicken_cabbage_skillet, beef_tomato_pasta, beef_pepper_rice, white_fish_couscous, tuna_rice_bowl, red_lentil_tomato_quick, chickpea_couscous, bean_veg_rice, cottage_veg_lunch_bowl, egg_potato_skillet, turkey_bean, pasta_peas_cheese.

Dinner (12): turkey_cabbage_dinner, beef_zucchini, chicken_mushroom, chickpea_pepper, bean_spinach, fish_veg_skillet, tuna_zucchini, egg_tomato_skillet_dinner, chicken_peas_carrot, lentil_veg_dinner_skillet, beef_onion_pepper, veg_cheese_skillet.

IDs follow `recipe_<name>_001`.

## Quality notes

- quality-audit --apply: recipes=80, failed=0, approved=0, source_verified=65, computationally_checked=15.
- Common warnings: NUTRITION_INGREDIENT_DATA_INCOMPLETE, FIBER_DATA_UNAVAILABLE, BUDGET_NOT_PRICE_VERIFIED (honest; no invented nutrition).
