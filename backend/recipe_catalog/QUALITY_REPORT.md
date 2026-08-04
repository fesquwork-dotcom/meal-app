# Recipe Quality Report (Sprint 10.7)

## 1. Executive Summary

- Audited **30** recipes (audit `quality_audit_v1`, mode `apply`).
- All current seed recipes were created as **agent_generated** structured data.
- Real culinary sources are **not** recorded (`source_count = 0`).
- Computational checks do **not** prove taste, kitchen timing, or storage safety.
- Nutrition snapshots were **not** recalculated from ingredients (ingredient nutrition database is empty).
- Kitchen testing is **absent**.
- **Approved** recipes: **0** (automatic approval is forbidden).
- Passed: 0, with warnings: 30, failed: 0.
- Average confidence: **0.306**.

## 2. Quality Status Distribution

- `computationally_checked`: 30

## 3. Creation Methods

- `agent_generated`: 30

## 4. Source Verification

- source_verified recipes: **0**
- Recipes without sources: all current seed recipes.
- `source_verified = false` for the entire seed catalog.

## 5. Computational Checks

Checks run: nutrition snapshot, yield, time, proportions, pattern derivation.
- Suggested computationally_checked candidates without blocking errors: 30

## 6. Nutrition Warnings

### recipe_baked_chicken_veg_001
- `NUTRITION_INGREDIENT_DATA_INCOMPLETE` (warning): ingredient_nutrition table incomplete; cannot recalculate recipe macros from ingredients

### recipe_baked_fish_potato_001
- `NUTRITION_INGREDIENT_DATA_INCOMPLETE` (warning): ingredient_nutrition table incomplete; cannot recalculate recipe macros from ingredients

### recipe_beef_potato_stew_001
- `NUTRITION_INGREDIENT_DATA_INCOMPLETE` (warning): ingredient_nutrition table incomplete; cannot recalculate recipe macros from ingredients

### recipe_buckwheat_chicken_veg_001
- `NUTRITION_INGREDIENT_DATA_INCOMPLETE` (warning): ingredient_nutrition table incomplete; cannot recalculate recipe macros from ingredients

### recipe_buckwheat_milk_001
- `NUTRITION_INGREDIENT_DATA_INCOMPLETE` (warning): ingredient_nutrition table incomplete; cannot recalculate recipe macros from ingredients

### recipe_buckwheat_mushroom_egg_001
- `NUTRITION_INGREDIENT_DATA_INCOMPLETE` (warning): ingredient_nutrition table incomplete; cannot recalculate recipe macros from ingredients

### recipe_chicken_cutlets_veg_001
- `NUTRITION_INGREDIENT_DATA_INCOMPLETE` (warning): ingredient_nutrition table incomplete; cannot recalculate recipe macros from ingredients

### recipe_chicken_noodle_soup_001
- `NUTRITION_INGREDIENT_DATA_INCOMPLETE` (warning): ingredient_nutrition table incomplete; cannot recalculate recipe macros from ingredients

### recipe_cottage_casserole_001
- `NUTRITION_INGREDIENT_DATA_INCOMPLETE` (warning): ingredient_nutrition table incomplete; cannot recalculate recipe macros from ingredients

### recipe_cottage_yogurt_fruit_001
- `NUTRITION_INGREDIENT_DATA_INCOMPLETE` (warning): ingredient_nutrition table incomplete; cannot recalculate recipe macros from ingredients

### recipe_fish_rice_veg_001
- `NUTRITION_INGREDIENT_DATA_INCOMPLETE` (warning): ingredient_nutrition table incomplete; cannot recalculate recipe macros from ingredients

### recipe_fried_eggs_veg_001
- `NUTRITION_INGREDIENT_DATA_INCOMPLETE` (warning): ingredient_nutrition table incomplete; cannot recalculate recipe macros from ingredients

### recipe_lavash_egg_cheese_001
- `NUTRITION_INGREDIENT_DATA_INCOMPLETE` (warning): ingredient_nutrition table incomplete; cannot recalculate recipe macros from ingredients

### recipe_lentil_soup_001
- `NUTRITION_INGREDIENT_DATA_INCOMPLETE` (warning): ingredient_nutrition table incomplete; cannot recalculate recipe macros from ingredients

### recipe_lentils_veg_egg_001
- `NUTRITION_INGREDIENT_DATA_INCOMPLETE` (warning): ingredient_nutrition table incomplete; cannot recalculate recipe macros from ingredients

### recipe_meatballs_buckwheat_001
- `NUTRITION_INGREDIENT_DATA_INCOMPLETE` (warning): ingredient_nutrition table incomplete; cannot recalculate recipe macros from ingredients

### recipe_oatmeal_apple_cinnamon_001
- `NUTRITION_INGREDIENT_DATA_INCOMPLETE` (warning): ingredient_nutrition table incomplete; cannot recalculate recipe macros from ingredients

### recipe_oatmeal_banana_001
- `NUTRITION_INGREDIENT_DATA_INCOMPLETE` (warning): ingredient_nutrition table incomplete; cannot recalculate recipe macros from ingredients

### recipe_omelet_chicken_veg_001
- `NUTRITION_INGREDIENT_DATA_INCOMPLETE` (warning): ingredient_nutrition table incomplete; cannot recalculate recipe macros from ingredients

### recipe_omelet_tomato_cheese_001
- `NUTRITION_INGREDIENT_DATA_INCOMPLETE` (warning): ingredient_nutrition table incomplete; cannot recalculate recipe macros from ingredients

### recipe_pasta_chicken_tomato_001
- `NUTRITION_INGREDIENT_DATA_INCOMPLETE` (warning): ingredient_nutrition table incomplete; cannot recalculate recipe macros from ingredients

### recipe_pasta_tuna_tomato_001
- `NUTRITION_INGREDIENT_DATA_INCOMPLETE` (warning): ingredient_nutrition table incomplete; cannot recalculate recipe macros from ingredients

### recipe_plov_chicken_001
- `NUTRITION_INGREDIENT_DATA_INCOMPLETE` (warning): ingredient_nutrition table incomplete; cannot recalculate recipe macros from ingredients

### recipe_rice_chicken_veg_001
- `NUTRITION_INGREDIENT_DATA_INCOMPLETE` (warning): ingredient_nutrition table incomplete; cannot recalculate recipe macros from ingredients

### recipe_rice_porridge_001
- `NUTRITION_INGREDIENT_DATA_INCOMPLETE` (warning): ingredient_nutrition table incomplete; cannot recalculate recipe macros from ingredients

### recipe_stewed_beans_veg_001
- `NUTRITION_INGREDIENT_DATA_INCOMPLETE` (warning): ingredient_nutrition table incomplete; cannot recalculate recipe macros from ingredients

### recipe_syrniki_001
- `NUTRITION_INGREDIENT_DATA_INCOMPLETE` (warning): ingredient_nutrition table incomplete; cannot recalculate recipe macros from ingredients

### recipe_turkey_veg_skillet_001
- `NUTRITION_INGREDIENT_DATA_INCOMPLETE` (warning): ingredient_nutrition table incomplete; cannot recalculate recipe macros from ingredients

### recipe_veg_casserole_cheese_001
- `NUTRITION_INGREDIENT_DATA_INCOMPLETE` (warning): ingredient_nutrition table incomplete; cannot recalculate recipe macros from ingredients

### recipe_yogurt_oats_banana_001
- `NUTRITION_INGREDIENT_DATA_INCOMPLETE` (warning): ingredient_nutrition table incomplete; cannot recalculate recipe macros from ingredients

## 7. Yield Warnings

- None.

## 7b. Portion Range Warnings

- `recipe_buckwheat_chicken_veg_001`: Base portion 225g outside recommended range 280–450g
- `recipe_fried_eggs_veg_001`: Base portion 170g outside recommended range 250–400g
- `recipe_lavash_egg_cheese_001`: Base portion 160g outside recommended range 250–400g
- `recipe_omelet_tomato_cheese_001`: Base portion 180g outside recommended range 250–400g
- `recipe_yogurt_oats_banana_001`: Base portion 210g outside recommended range 250–400g

## 8. Time Warnings

- None.

## 8b. Cooking / Step Time Codes

- None beyond informational notes.

## 9. Proportion Warnings

### recipe_baked_fish_potato_001
- `SEASONING_QUANTITY_SUSPICIOUS` (warning): Seasoning mass share 5.1% looks high

### recipe_cottage_casserole_001
- `SEASONING_QUANTITY_SUSPICIOUS` (warning): Seasoning mass share 5.4% looks high

### recipe_syrniki_001
- `SEASONING_QUANTITY_SUSPICIOUS` (warning): Seasoning mass share 6.2% looks high

## 9b. Other Proportion Codes

- `recipe_lentil_soup_001` `MAIN_INGREDIENT_SHARE_SUSPICIOUS`: Main ingredient ing_garlic is only 0.5% of mass
- `recipe_pasta_chicken_tomato_001` `MAIN_INGREDIENT_SHARE_SUSPICIOUS`: Main ingredient ing_garlic is only 1.0% of mass
- `recipe_pasta_tuna_tomato_001` `MAIN_INGREDIENT_SHARE_SUSPICIOUS`: Main ingredient ing_garlic is only 1.4% of mass
- `recipe_plov_chicken_001` `MAIN_INGREDIENT_SHARE_SUSPICIOUS`: Main ingredient ing_garlic is only 0.2% of mass
- `recipe_stewed_beans_veg_001` `MAIN_INGREDIENT_SHARE_SUSPICIOUS`: Main ingredient ing_garlic is only 1.0% of mass

## 10. Pattern Evidence Summary

- `batch_friendly` true: 20
- `budget_friendly` true: 24
- `family_friendly` true: 14
- `freezer_friendly` true: 9
- `high_protein` true: 26
- `leftover_friendly` true: 20
- `low_energy_density` true: 27
- `muscle_gain_compatible` true: 29
- `quick_meal` true: 13
- `weight_loss_compatible` true: 30

- `budget_friendly` evidence is **declared** only (`BUDGET_NOT_PRICE_VERIFIED`).
- `high_fiber` is **insufficient_data** without fiber nutrition fields.

## 11. Unsupported Tags and Roles


## 12. Goal Score Review

- No large goal-score gaps flagged beyond informational incompleteness.

## 13. Approval Blockers

Every seed recipe is blocked from approval by:
- no real sources
- no human / expert review
- no kitchen test
- no human approval record
- agent_generated provenance

No computational blocking errors in this run.

## 14. Recipes Requiring Human Review

All audited seed recipes require human culinary review.
- `recipe_baked_chicken_veg_001`
- `recipe_baked_fish_potato_001`
- `recipe_beef_potato_stew_001`
- `recipe_buckwheat_chicken_veg_001`
- `recipe_buckwheat_milk_001`
- `recipe_buckwheat_mushroom_egg_001`
- `recipe_chicken_cutlets_veg_001`
- `recipe_chicken_noodle_soup_001`
- `recipe_cottage_casserole_001`
- `recipe_cottage_yogurt_fruit_001`
- `recipe_fish_rice_veg_001`
- `recipe_fried_eggs_veg_001`
- `recipe_lavash_egg_cheese_001`
- `recipe_lentil_soup_001`
- `recipe_lentils_veg_egg_001`
- `recipe_meatballs_buckwheat_001`
- `recipe_oatmeal_apple_cinnamon_001`
- `recipe_oatmeal_banana_001`
- `recipe_omelet_chicken_veg_001`
- `recipe_omelet_tomato_cheese_001`
- `recipe_pasta_chicken_tomato_001`
- `recipe_pasta_tuna_tomato_001`
- `recipe_plov_chicken_001`
- `recipe_rice_chicken_veg_001`
- `recipe_rice_porridge_001`
- `recipe_stewed_beans_veg_001`
- `recipe_syrniki_001`
- `recipe_turkey_veg_skillet_001`
- `recipe_veg_casserole_cheese_001`
- `recipe_yogurt_oats_banana_001`

## 15. Recipes Recommended for Kitchen Testing

- `recipe_baked_chicken_veg_001`
- `recipe_baked_fish_potato_001`
- `recipe_beef_potato_stew_001`
- `recipe_buckwheat_chicken_veg_001`
- `recipe_buckwheat_milk_001`
- `recipe_buckwheat_mushroom_egg_001`
- `recipe_chicken_cutlets_veg_001`
- `recipe_chicken_noodle_soup_001`
- `recipe_cottage_casserole_001`
- `recipe_fish_rice_veg_001`
- `recipe_lentil_soup_001`
- `recipe_lentils_veg_egg_001`
- `recipe_meatballs_buckwheat_001`
- `recipe_pasta_chicken_tomato_001`
- `recipe_plov_chicken_001`
- `recipe_rice_chicken_veg_001`
- `recipe_rice_porridge_001`
- `recipe_stewed_beans_veg_001`
- `recipe_turkey_veg_skillet_001`
- `recipe_veg_casserole_cheese_001`

## 16. Known Limitations

- Agent-generated YAML is schema-valid, not kitchen-proven.
- No invented source URLs or cookbook citations.
- Ingredient nutrition table exists but is empty in this sprint.
- Pattern evidence is structural/declared, not culinary proof.
- Automatic audit cannot assign approved / source_verified / human_reviewed / kitchen_tested.
- Selector weights, hard filters, MenuPlan, Claude pipeline, and Basket Engine are unchanged.

_Generated at 2026-08-04T19:04:48+00:00_
