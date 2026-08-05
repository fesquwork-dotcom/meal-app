# Recipe Quality Report (Sprint 10.7 / 10.8)

## 1. Executive Summary

- Audited **80** recipes (audit `quality_audit_v1`, mode `apply`).
- Creation mix: **agent_generated**=30, **source_adapted**=50.
- Recipes with recorded sources: **65** (source_verified status count: **65**).
- Computational checks do **not** prove taste, kitchen timing, or storage safety.
- Nutrition snapshots were **not** recalculated from ingredients (ingredient nutrition database is empty).
- Kitchen testing is **absent**.
- **Approved** recipes: **0** (automatic approval is forbidden).
- Passed: 0, with warnings: 80, failed: 0.
- Average confidence: **0.499**.

## 2. Quality Status Distribution

- `computationally_checked`: 15
- `source_verified`: 65

## 3. Creation Methods

- `agent_generated`: 30
- `source_adapted`: 50

## 4. Source Verification

- source_verified recipes: **65**
- Remaining without source_verified: **15** (computationally_checked only; still agent_generated seeds pending further source review).

## 5. Computational Checks

Checks run: nutrition snapshot, yield, time, proportions, pattern derivation.
- Suggested computationally_checked candidates without blocking errors: 80

## 6. Nutrition Warnings

### recipe_baked_chicken_veg_001
- `NUTRITION_INGREDIENT_DATA_INCOMPLETE` (warning): ingredient_nutrition table incomplete; cannot recalculate recipe macros from ingredients

### recipe_baked_fish_potato_001
- `NUTRITION_INGREDIENT_DATA_INCOMPLETE` (warning): ingredient_nutrition table incomplete; cannot recalculate recipe macros from ingredients

### recipe_baked_oat_apple_001
- `NUTRITION_INGREDIENT_DATA_INCOMPLETE` (warning): ingredient_nutrition table incomplete; cannot recalculate recipe macros from ingredients

### recipe_bean_spinach_dinner_001
- `NUTRITION_INGREDIENT_DATA_INCOMPLETE` (warning): ingredient_nutrition table incomplete; cannot recalculate recipe macros from ingredients

### recipe_bean_veg_rice_lunch_001
- `NUTRITION_INGREDIENT_DATA_INCOMPLETE` (warning): ingredient_nutrition table incomplete; cannot recalculate recipe macros from ingredients

### recipe_beans_tomato_egg_lunch_001
- `NUTRITION_INGREDIENT_DATA_INCOMPLETE` (warning): ingredient_nutrition table incomplete; cannot recalculate recipe macros from ingredients

### recipe_beef_cabbage_skillet_lunch_001
- `NUTRITION_INGREDIENT_DATA_INCOMPLETE` (warning): ingredient_nutrition table incomplete; cannot recalculate recipe macros from ingredients

### recipe_beef_onion_pepper_dinner_001
- `NUTRITION_MACRO_KCAL_MISMATCH` (warning): Macro-estimated kcal 140.0 differs from snapshot 110.0 (tolerance 25.0)
- `NUTRITION_INGREDIENT_DATA_INCOMPLETE` (warning): ingredient_nutrition table incomplete; cannot recalculate recipe macros from ingredients

### recipe_beef_pepper_rice_lunch_001
- `NUTRITION_MACRO_KCAL_MISMATCH` (warning): Macro-estimated kcal 140.0 differs from snapshot 110.0 (tolerance 25.0)
- `NUTRITION_INGREDIENT_DATA_INCOMPLETE` (warning): ingredient_nutrition table incomplete; cannot recalculate recipe macros from ingredients

### recipe_beef_potato_stew_001
- `NUTRITION_INGREDIENT_DATA_INCOMPLETE` (warning): ingredient_nutrition table incomplete; cannot recalculate recipe macros from ingredients

### recipe_beef_tomato_pasta_lunch_001
- `NUTRITION_MACRO_KCAL_MISMATCH` (warning): Macro-estimated kcal 140.0 differs from snapshot 110.0 (tolerance 25.0)
- `NUTRITION_INGREDIENT_DATA_INCOMPLETE` (warning): ingredient_nutrition table incomplete; cannot recalculate recipe macros from ingredients

### recipe_beef_zucchini_dinner_001
- `NUTRITION_MACRO_KCAL_MISMATCH` (warning): Macro-estimated kcal 140.0 differs from snapshot 110.0 (tolerance 25.0)
- `NUTRITION_INGREDIENT_DATA_INCOMPLETE` (warning): ingredient_nutrition table incomplete; cannot recalculate recipe macros from ingredients

### recipe_buckwheat_chicken_veg_001
- `NUTRITION_INGREDIENT_DATA_INCOMPLETE` (warning): ingredient_nutrition table incomplete; cannot recalculate recipe macros from ingredients

### recipe_buckwheat_milk_001
- `NUTRITION_INGREDIENT_DATA_INCOMPLETE` (warning): ingredient_nutrition table incomplete; cannot recalculate recipe macros from ingredients

### recipe_buckwheat_mushroom_egg_001
- `NUTRITION_INGREDIENT_DATA_INCOMPLETE` (warning): ingredient_nutrition table incomplete; cannot recalculate recipe macros from ingredients

### recipe_chicken_cabbage_skillet_lunch_001
- `NUTRITION_MACRO_KCAL_MISMATCH` (warning): Macro-estimated kcal 140.0 differs from snapshot 110.0 (tolerance 25.0)
- `NUTRITION_INGREDIENT_DATA_INCOMPLETE` (warning): ingredient_nutrition table incomplete; cannot recalculate recipe macros from ingredients

### recipe_chicken_cutlets_veg_001
- `NUTRITION_INGREDIENT_DATA_INCOMPLETE` (warning): ingredient_nutrition table incomplete; cannot recalculate recipe macros from ingredients

### recipe_chicken_mushroom_dinner_001
- `NUTRITION_MACRO_KCAL_MISMATCH` (warning): Macro-estimated kcal 140.0 differs from snapshot 110.0 (tolerance 25.0)
- `NUTRITION_INGREDIENT_DATA_INCOMPLETE` (warning): ingredient_nutrition table incomplete; cannot recalculate recipe macros from ingredients

### recipe_chicken_noodle_soup_001
- `NUTRITION_INGREDIENT_DATA_INCOMPLETE` (warning): ingredient_nutrition table incomplete; cannot recalculate recipe macros from ingredients

### recipe_chicken_peas_carrot_dinner_001
- `NUTRITION_MACRO_KCAL_MISMATCH` (warning): Macro-estimated kcal 140.0 differs from snapshot 110.0 (tolerance 25.0)
- `NUTRITION_INGREDIENT_DATA_INCOMPLETE` (warning): ingredient_nutrition table incomplete; cannot recalculate recipe macros from ingredients

### recipe_chicken_rice_bowl_lunch_001
- `NUTRITION_MACRO_KCAL_MISMATCH` (warning): Macro-estimated kcal 140.0 differs from snapshot 110.0 (tolerance 25.0)
- `NUTRITION_INGREDIENT_DATA_INCOMPLETE` (warning): ingredient_nutrition table incomplete; cannot recalculate recipe macros from ingredients

### recipe_chicken_veg_lunch_skillet_001
- `NUTRITION_INGREDIENT_DATA_INCOMPLETE` (warning): ingredient_nutrition table incomplete; cannot recalculate recipe macros from ingredients

### recipe_chicken_zucchini_dinner_skillet_001
- `NUTRITION_INGREDIENT_DATA_INCOMPLETE` (warning): ingredient_nutrition table incomplete; cannot recalculate recipe macros from ingredients

### recipe_chickpea_couscous_lunch_001
- `NUTRITION_INGREDIENT_DATA_INCOMPLETE` (warning): ingredient_nutrition table incomplete; cannot recalculate recipe macros from ingredients

### recipe_chickpea_hummus_toast_001
- `NUTRITION_INGREDIENT_DATA_INCOMPLETE` (warning): ingredient_nutrition table incomplete; cannot recalculate recipe macros from ingredients

### recipe_chickpea_pepper_dinner_001
- `NUTRITION_INGREDIENT_DATA_INCOMPLETE` (warning): ingredient_nutrition table incomplete; cannot recalculate recipe macros from ingredients

### recipe_chickpea_spinach_dinner_001
- `NUTRITION_INGREDIENT_DATA_INCOMPLETE` (warning): ingredient_nutrition table incomplete; cannot recalculate recipe macros from ingredients

### recipe_chickpea_tomato_skillet_001
- `NUTRITION_INGREDIENT_DATA_INCOMPLETE` (warning): ingredient_nutrition table incomplete; cannot recalculate recipe macros from ingredients

### recipe_chickpea_yogurt_bowl_flex_001
- `NUTRITION_INGREDIENT_DATA_INCOMPLETE` (warning): ingredient_nutrition table incomplete; cannot recalculate recipe macros from ingredients

### recipe_cottage_berries_bowl_001
- `NUTRITION_MACRO_KCAL_MISMATCH` (warning): Macro-estimated kcal 140.0 differs from snapshot 110.0 (tolerance 25.0)
- `NUTRITION_INGREDIENT_DATA_INCOMPLETE` (warning): ingredient_nutrition table incomplete; cannot recalculate recipe macros from ingredients

### recipe_cottage_casserole_001
- `NUTRITION_INGREDIENT_DATA_INCOMPLETE` (warning): ingredient_nutrition table incomplete; cannot recalculate recipe macros from ingredients

### recipe_cottage_lavash_roll_bf_001
- `NUTRITION_MACRO_KCAL_MISMATCH` (warning): Macro-estimated kcal 140.0 differs from snapshot 110.0 (tolerance 25.0)
- `NUTRITION_INGREDIENT_DATA_INCOMPLETE` (warning): ingredient_nutrition table incomplete; cannot recalculate recipe macros from ingredients

### recipe_cottage_veg_lunch_bowl_001
- `NUTRITION_MACRO_KCAL_MISMATCH` (warning): Macro-estimated kcal 140.0 differs from snapshot 110.0 (tolerance 25.0)
- `NUTRITION_INGREDIENT_DATA_INCOMPLETE` (warning): ingredient_nutrition table incomplete; cannot recalculate recipe macros from ingredients

### recipe_cottage_yogurt_fruit_001
- `NUTRITION_INGREDIENT_DATA_INCOMPLETE` (warning): ingredient_nutrition table incomplete; cannot recalculate recipe macros from ingredients

### recipe_couscous_milk_breakfast_001
- `NUTRITION_INGREDIENT_DATA_INCOMPLETE` (warning): ingredient_nutrition table incomplete; cannot recalculate recipe macros from ingredients

### recipe_egg_potato_skillet_lunch_001
- `NUTRITION_MACRO_KCAL_MISMATCH` (warning): Macro-estimated kcal 140.0 differs from snapshot 110.0 (tolerance 25.0)
- `NUTRITION_INGREDIENT_DATA_INCOMPLETE` (warning): ingredient_nutrition table incomplete; cannot recalculate recipe macros from ingredients

### recipe_egg_spinach_scramble_lunch_001
- `NUTRITION_INGREDIENT_DATA_INCOMPLETE` (warning): ingredient_nutrition table incomplete; cannot recalculate recipe macros from ingredients

### recipe_egg_tomato_skillet_dinner_001
- `NUTRITION_MACRO_KCAL_MISMATCH` (warning): Macro-estimated kcal 140.0 differs from snapshot 110.0 (tolerance 25.0)
- `NUTRITION_INGREDIENT_DATA_INCOMPLETE` (warning): ingredient_nutrition table incomplete; cannot recalculate recipe macros from ingredients

### recipe_egg_veg_rice_bowl_flex_001
- `NUTRITION_MACRO_KCAL_MISMATCH` (warning): Macro-estimated kcal 140.0 differs from snapshot 110.0 (tolerance 25.0)
- `NUTRITION_INGREDIENT_DATA_INCOMPLETE` (warning): ingredient_nutrition table incomplete; cannot recalculate recipe macros from ingredients

### recipe_egg_veg_wrap_flex_001
- `NUTRITION_INGREDIENT_DATA_INCOMPLETE` (warning): ingredient_nutrition table incomplete; cannot recalculate recipe macros from ingredients

### recipe_eggs_veg_toast_001
- `NUTRITION_MACRO_KCAL_MISMATCH` (warning): Macro-estimated kcal 140.0 differs from snapshot 110.0 (tolerance 25.0)
- `NUTRITION_INGREDIENT_DATA_INCOMPLETE` (warning): ingredient_nutrition table incomplete; cannot recalculate recipe macros from ingredients

### recipe_fish_rice_veg_001
- `NUTRITION_INGREDIENT_DATA_INCOMPLETE` (warning): ingredient_nutrition table incomplete; cannot recalculate recipe macros from ingredients

### recipe_fish_veg_skillet_dinner_001
- `NUTRITION_MACRO_KCAL_MISMATCH` (warning): Macro-estimated kcal 140.0 differs from snapshot 110.0 (tolerance 25.0)
- `NUTRITION_INGREDIENT_DATA_INCOMPLETE` (warning): ingredient_nutrition table incomplete; cannot recalculate recipe macros from ingredients

### recipe_fried_eggs_veg_001
- `NUTRITION_INGREDIENT_DATA_INCOMPLETE` (warning): ingredient_nutrition table incomplete; cannot recalculate recipe macros from ingredients

### recipe_lavash_egg_cheese_001
- `NUTRITION_INGREDIENT_DATA_INCOMPLETE` (warning): ingredient_nutrition table incomplete; cannot recalculate recipe macros from ingredients

### recipe_lentil_soup_001
- `NUTRITION_INGREDIENT_DATA_INCOMPLETE` (warning): ingredient_nutrition table incomplete; cannot recalculate recipe macros from ingredients

### recipe_lentil_veg_dinner_skillet_001
- `NUTRITION_INGREDIENT_DATA_INCOMPLETE` (warning): ingredient_nutrition table incomplete; cannot recalculate recipe macros from ingredients

### recipe_lentils_veg_egg_001
- `NUTRITION_INGREDIENT_DATA_INCOMPLETE` (warning): ingredient_nutrition table incomplete; cannot recalculate recipe macros from ingredients

### recipe_meatballs_buckwheat_001
- `NUTRITION_INGREDIENT_DATA_INCOMPLETE` (warning): ingredient_nutrition table incomplete; cannot recalculate recipe macros from ingredients

### recipe_millet_milk_porridge_001
- `NUTRITION_INGREDIENT_DATA_INCOMPLETE` (warning): ingredient_nutrition table incomplete; cannot recalculate recipe macros from ingredients

### recipe_mushroom_egg_scramble_bf_001
- `NUTRITION_MACRO_KCAL_MISMATCH` (warning): Macro-estimated kcal 140.0 differs from snapshot 110.0 (tolerance 25.0)
- `NUTRITION_INGREDIENT_DATA_INCOMPLETE` (warning): ingredient_nutrition table incomplete; cannot recalculate recipe macros from ingredients

### recipe_oatmeal_apple_cinnamon_001
- `NUTRITION_INGREDIENT_DATA_INCOMPLETE` (warning): ingredient_nutrition table incomplete; cannot recalculate recipe macros from ingredients

### recipe_oatmeal_banana_001
- `NUTRITION_INGREDIENT_DATA_INCOMPLETE` (warning): ingredient_nutrition table incomplete; cannot recalculate recipe macros from ingredients

### recipe_omelet_chicken_veg_001
- `NUTRITION_INGREDIENT_DATA_INCOMPLETE` (warning): ingredient_nutrition table incomplete; cannot recalculate recipe macros from ingredients

### recipe_omelet_tomato_cheese_001
- `NUTRITION_INGREDIENT_DATA_INCOMPLETE` (warning): ingredient_nutrition table incomplete; cannot recalculate recipe macros from ingredients

### recipe_overnight_oats_classic_001
- `NUTRITION_INGREDIENT_DATA_INCOMPLETE` (warning): ingredient_nutrition table incomplete; cannot recalculate recipe macros from ingredients

### recipe_pasta_chicken_tomato_001
- `NUTRITION_INGREDIENT_DATA_INCOMPLETE` (warning): ingredient_nutrition table incomplete; cannot recalculate recipe macros from ingredients

### recipe_pasta_peas_cheese_lunch_001
- `NUTRITION_INGREDIENT_DATA_INCOMPLETE` (warning): ingredient_nutrition table incomplete; cannot recalculate recipe macros from ingredients

### recipe_pasta_tuna_tomato_001
- `NUTRITION_INGREDIENT_DATA_INCOMPLETE` (warning): ingredient_nutrition table incomplete; cannot recalculate recipe macros from ingredients

### recipe_plov_chicken_001
- `NUTRITION_INGREDIENT_DATA_INCOMPLETE` (warning): ingredient_nutrition table incomplete; cannot recalculate recipe macros from ingredients

### recipe_red_lentil_tomato_quick_001
- `NUTRITION_INGREDIENT_DATA_INCOMPLETE` (warning): ingredient_nutrition table incomplete; cannot recalculate recipe macros from ingredients

### recipe_rice_chicken_veg_001
- `NUTRITION_INGREDIENT_DATA_INCOMPLETE` (warning): ingredient_nutrition table incomplete; cannot recalculate recipe macros from ingredients

### recipe_rice_porridge_001
- `NUTRITION_INGREDIENT_DATA_INCOMPLETE` (warning): ingredient_nutrition table incomplete; cannot recalculate recipe macros from ingredients

### recipe_savory_cottage_cucumber_001
- `NUTRITION_MACRO_KCAL_MISMATCH` (warning): Macro-estimated kcal 140.0 differs from snapshot 110.0 (tolerance 25.0)
- `NUTRITION_INGREDIENT_DATA_INCOMPLETE` (warning): ingredient_nutrition table incomplete; cannot recalculate recipe macros from ingredients

### recipe_spinach_cottage_frittata_001
- `NUTRITION_MACRO_KCAL_MISMATCH` (warning): Macro-estimated kcal 140.0 differs from snapshot 110.0 (tolerance 25.0)
- `NUTRITION_INGREDIENT_DATA_INCOMPLETE` (warning): ingredient_nutrition table incomplete; cannot recalculate recipe macros from ingredients

### recipe_stewed_beans_veg_001
- `NUTRITION_INGREDIENT_DATA_INCOMPLETE` (warning): ingredient_nutrition table incomplete; cannot recalculate recipe macros from ingredients

### recipe_syrniki_001
- `NUTRITION_INGREDIENT_DATA_INCOMPLETE` (warning): ingredient_nutrition table incomplete; cannot recalculate recipe macros from ingredients

### recipe_tuna_bean_salad_lunch_001
- `NUTRITION_INGREDIENT_DATA_INCOMPLETE` (warning): ingredient_nutrition table incomplete; cannot recalculate recipe macros from ingredients

### recipe_tuna_rice_bowl_lunch_001
- `NUTRITION_MACRO_KCAL_MISMATCH` (warning): Macro-estimated kcal 140.0 differs from snapshot 110.0 (tolerance 25.0)
- `NUTRITION_INGREDIENT_DATA_INCOMPLETE` (warning): ingredient_nutrition table incomplete; cannot recalculate recipe macros from ingredients

### recipe_tuna_zucchini_dinner_001
- `NUTRITION_MACRO_KCAL_MISMATCH` (warning): Macro-estimated kcal 140.0 differs from snapshot 110.0 (tolerance 25.0)
- `NUTRITION_INGREDIENT_DATA_INCOMPLETE` (warning): ingredient_nutrition table incomplete; cannot recalculate recipe macros from ingredients

### recipe_turkey_bean_lunch_001
- `NUTRITION_MACRO_KCAL_MISMATCH` (warning): Macro-estimated kcal 140.0 differs from snapshot 110.0 (tolerance 25.0)
- `NUTRITION_INGREDIENT_DATA_INCOMPLETE` (warning): ingredient_nutrition table incomplete; cannot recalculate recipe macros from ingredients

### recipe_turkey_cabbage_dinner_001
- `NUTRITION_MACRO_KCAL_MISMATCH` (warning): Macro-estimated kcal 140.0 differs from snapshot 110.0 (tolerance 25.0)
- `NUTRITION_INGREDIENT_DATA_INCOMPLETE` (warning): ingredient_nutrition table incomplete; cannot recalculate recipe macros from ingredients

### recipe_turkey_couscous_lunch_001
- `NUTRITION_MACRO_KCAL_MISMATCH` (warning): Macro-estimated kcal 140.0 differs from snapshot 110.0 (tolerance 25.0)
- `NUTRITION_INGREDIENT_DATA_INCOMPLETE` (warning): ingredient_nutrition table incomplete; cannot recalculate recipe macros from ingredients

### recipe_turkey_veg_lunch_skillet_001
- `NUTRITION_INGREDIENT_DATA_INCOMPLETE` (warning): ingredient_nutrition table incomplete; cannot recalculate recipe macros from ingredients

### recipe_turkey_veg_skillet_001
- `NUTRITION_INGREDIENT_DATA_INCOMPLETE` (warning): ingredient_nutrition table incomplete; cannot recalculate recipe macros from ingredients

### recipe_veg_casserole_cheese_001
- `NUTRITION_INGREDIENT_DATA_INCOMPLETE` (warning): ingredient_nutrition table incomplete; cannot recalculate recipe macros from ingredients

### recipe_veg_cheese_skillet_dinner_001
- `NUTRITION_INGREDIENT_DATA_INCOMPLETE` (warning): ingredient_nutrition table incomplete; cannot recalculate recipe macros from ingredients

### recipe_white_fish_couscous_lunch_001
- `NUTRITION_MACRO_KCAL_MISMATCH` (warning): Macro-estimated kcal 140.0 differs from snapshot 110.0 (tolerance 25.0)
- `NUTRITION_INGREDIENT_DATA_INCOMPLETE` (warning): ingredient_nutrition table incomplete; cannot recalculate recipe macros from ingredients

### recipe_yogurt_oats_banana_001
- `NUTRITION_INGREDIENT_DATA_INCOMPLETE` (warning): ingredient_nutrition table incomplete; cannot recalculate recipe macros from ingredients

### recipe_yogurt_oats_berries_001
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

- `recipe_baked_oat_apple_001` `TEMPERATURE_MISSING_FOR_BAKING`: Baking/roasting steps lack temperature_c
- `recipe_spinach_cottage_frittata_001` `TEMPERATURE_MISSING_FOR_BAKING`: Baking/roasting steps lack temperature_c

## 9. Proportion Warnings

### recipe_baked_fish_potato_001
- `SEASONING_QUANTITY_SUSPICIOUS` (warning): Seasoning mass share 5.1% looks high

### recipe_cottage_casserole_001
- `SEASONING_QUANTITY_SUSPICIOUS` (warning): Seasoning mass share 5.4% looks high

### recipe_syrniki_001
- `SEASONING_QUANTITY_SUSPICIOUS` (warning): Seasoning mass share 6.2% looks high

### recipe_tuna_bean_salad_lunch_001
- `SEASONING_QUANTITY_SUSPICIOUS` (warning): Seasoning mass share 6.7% looks high

## 9b. Other Proportion Codes

- `recipe_baked_oat_apple_001` `MAIN_INGREDIENT_SHARE_SUSPICIOUS`: Main ingredient ing_cinnamon is only 0.4% of mass
- `recipe_bean_spinach_dinner_001` `MAIN_INGREDIENT_SHARE_SUSPICIOUS`: Main ingredient ing_oil is only 1.1% of mass
- `recipe_bean_veg_rice_lunch_001` `MAIN_INGREDIENT_SHARE_SUSPICIOUS`: Main ingredient ing_oil is only 1.5% of mass
- `recipe_beef_cabbage_skillet_lunch_001` `MAIN_INGREDIENT_SHARE_SUSPICIOUS`: Main ingredient ing_garlic is only 1.2% of mass
- `recipe_beef_onion_pepper_dinner_001` `MAIN_INGREDIENT_SHARE_SUSPICIOUS`: Main ingredient ing_oil is only 1.1% of mass
- `recipe_beef_pepper_rice_lunch_001` `MAIN_INGREDIENT_SHARE_SUSPICIOUS`: Main ingredient ing_oil is only 1.2% of mass
- `recipe_beef_tomato_pasta_lunch_001` `MAIN_INGREDIENT_SHARE_SUSPICIOUS`: Main ingredient ing_oil is only 0.9% of mass
- `recipe_beef_zucchini_dinner_001` `MAIN_INGREDIENT_SHARE_SUSPICIOUS`: Main ingredient ing_oil is only 0.9% of mass
- `recipe_chicken_cabbage_skillet_lunch_001` `MAIN_INGREDIENT_SHARE_SUSPICIOUS`: Main ingredient ing_oil is only 1.1% of mass
- `recipe_chicken_mushroom_dinner_001` `MAIN_INGREDIENT_SHARE_SUSPICIOUS`: Main ingredient ing_oil is only 1.2% of mass
- `recipe_chicken_peas_carrot_dinner_001` `MAIN_INGREDIENT_SHARE_SUSPICIOUS`: Main ingredient ing_oil is only 1.2% of mass
- `recipe_chicken_rice_bowl_lunch_001` `MAIN_INGREDIENT_SHARE_SUSPICIOUS`: Main ingredient ing_oil is only 1.6% of mass
- `recipe_chicken_zucchini_dinner_skillet_001` `MAIN_INGREDIENT_SHARE_SUSPICIOUS`: Main ingredient ing_garlic is only 1.2% of mass
- `recipe_chickpea_couscous_lunch_001` `MAIN_INGREDIENT_SHARE_SUSPICIOUS`: Main ingredient ing_oil is only 1.3% of mass
- `recipe_chickpea_pepper_dinner_001` `MAIN_INGREDIENT_SHARE_SUSPICIOUS`: Main ingredient ing_oil is only 1.0% of mass
- `recipe_chickpea_spinach_dinner_001` `MAIN_INGREDIENT_SHARE_SUSPICIOUS`: Main ingredient ing_garlic is only 1.1% of mass
- `recipe_chickpea_tomato_skillet_001` `MAIN_INGREDIENT_SHARE_SUSPICIOUS`: Main ingredient ing_garlic is only 1.2% of mass
- `recipe_egg_potato_skillet_lunch_001` `MAIN_INGREDIENT_SHARE_SUSPICIOUS`: Main ingredient ing_oil is only 1.4% of mass
- `recipe_egg_tomato_skillet_dinner_001` `MAIN_INGREDIENT_SHARE_SUSPICIOUS`: Main ingredient ing_oil is only 1.2% of mass
- `recipe_egg_veg_rice_bowl_flex_001` `MAIN_INGREDIENT_SHARE_SUSPICIOUS`: Main ingredient ing_oil is only 1.7% of mass
- `recipe_eggs_veg_toast_001` `MAIN_INGREDIENT_SHARE_SUSPICIOUS`: Main ingredient ing_oil is only 1.4% of mass
- `recipe_fish_veg_skillet_dinner_001` `MAIN_INGREDIENT_SHARE_SUSPICIOUS`: Main ingredient ing_oil is only 1.4% of mass
- `recipe_lentil_soup_001` `MAIN_INGREDIENT_SHARE_SUSPICIOUS`: Main ingredient ing_garlic is only 0.5% of mass
- `recipe_lentil_veg_dinner_skillet_001` `MAIN_INGREDIENT_SHARE_SUSPICIOUS`: Main ingredient ing_oil is only 1.2% of mass
- `recipe_mushroom_egg_scramble_bf_001` `MAIN_INGREDIENT_SHARE_SUSPICIOUS`: Main ingredient ing_oil is only 1.9% of mass
- `recipe_pasta_chicken_tomato_001` `MAIN_INGREDIENT_SHARE_SUSPICIOUS`: Main ingredient ing_garlic is only 1.0% of mass
- `recipe_pasta_peas_cheese_lunch_001` `MAIN_INGREDIENT_SHARE_SUSPICIOUS`: Main ingredient ing_oil is only 1.4% of mass
- `recipe_pasta_tuna_tomato_001` `MAIN_INGREDIENT_SHARE_SUSPICIOUS`: Main ingredient ing_garlic is only 1.4% of mass
- `recipe_plov_chicken_001` `MAIN_INGREDIENT_SHARE_SUSPICIOUS`: Main ingredient ing_garlic is only 0.2% of mass
- `recipe_red_lentil_tomato_quick_001` `MAIN_INGREDIENT_SHARE_SUSPICIOUS`: Main ingredient ing_oil is only 1.5% of mass
- `recipe_spinach_cottage_frittata_001` `MAIN_INGREDIENT_SHARE_SUSPICIOUS`: Main ingredient ing_oil is only 1.0% of mass
- `recipe_stewed_beans_veg_001` `MAIN_INGREDIENT_SHARE_SUSPICIOUS`: Main ingredient ing_garlic is only 1.0% of mass
- `recipe_tuna_rice_bowl_lunch_001` `MAIN_INGREDIENT_SHARE_SUSPICIOUS`: Main ingredient ing_oil is only 1.4% of mass
- `recipe_tuna_zucchini_dinner_001` `MAIN_INGREDIENT_SHARE_SUSPICIOUS`: Main ingredient ing_oil is only 0.9% of mass
- `recipe_turkey_bean_lunch_001` `MAIN_INGREDIENT_SHARE_SUSPICIOUS`: Main ingredient ing_oil is only 1.0% of mass
- `recipe_turkey_cabbage_dinner_001` `MAIN_INGREDIENT_SHARE_SUSPICIOUS`: Main ingredient ing_oil is only 1.0% of mass
- `recipe_turkey_couscous_lunch_001` `MAIN_INGREDIENT_SHARE_SUSPICIOUS`: Main ingredient ing_oil is only 1.5% of mass
- `recipe_veg_cheese_skillet_dinner_001` `MAIN_INGREDIENT_SHARE_SUSPICIOUS`: Main ingredient ing_oil is only 1.1% of mass
- `recipe_white_fish_couscous_lunch_001` `MAIN_INGREDIENT_SHARE_SUSPICIOUS`: Main ingredient ing_oil is only 1.2% of mass

## 10. Pattern Evidence Summary

- `batch_friendly` true: 55
- `budget_friendly` true: 64
- `family_friendly` true: 17
- `freezer_friendly` true: 9
- `high_protein` true: 76
- `leftover_friendly` true: 57
- `low_energy_density` true: 77
- `muscle_gain_compatible` true: 79
- `portable_meal` true: 11
- `quick_meal` true: 63
- `weight_loss_compatible` true: 80

- `budget_friendly` evidence is **declared** only (`BUDGET_NOT_PRICE_VERIFIED`).
- `high_fiber` is **insufficient_data** without fiber nutrition fields.

## 11. Unsupported Tags and Roles


## 12. Goal Score Review

- No large goal-score gaps flagged beyond informational incompleteness.

## 13. Approval Blockers

No recipe is auto-approved. Typical blockers remain:
- human_reviewed / kitchen_tested required
- human approval record required
- recipes without sources still blocked on source verification
- source_verified is the maximum automatic gate status

No computational blocking errors in this run.

## 14. Recipes Requiring Human Review

All audited seed recipes require human culinary review.
- `recipe_baked_chicken_veg_001`
- `recipe_baked_fish_potato_001`
- `recipe_baked_oat_apple_001`
- `recipe_bean_spinach_dinner_001`
- `recipe_bean_veg_rice_lunch_001`
- `recipe_beans_tomato_egg_lunch_001`
- `recipe_beef_cabbage_skillet_lunch_001`
- `recipe_beef_onion_pepper_dinner_001`
- `recipe_beef_pepper_rice_lunch_001`
- `recipe_beef_potato_stew_001`
- `recipe_beef_tomato_pasta_lunch_001`
- `recipe_beef_zucchini_dinner_001`
- `recipe_buckwheat_chicken_veg_001`
- `recipe_buckwheat_milk_001`
- `recipe_buckwheat_mushroom_egg_001`
- `recipe_chicken_cabbage_skillet_lunch_001`
- `recipe_chicken_cutlets_veg_001`
- `recipe_chicken_mushroom_dinner_001`
- `recipe_chicken_noodle_soup_001`
- `recipe_chicken_peas_carrot_dinner_001`
- `recipe_chicken_rice_bowl_lunch_001`
- `recipe_chicken_veg_lunch_skillet_001`
- `recipe_chicken_zucchini_dinner_skillet_001`
- `recipe_chickpea_couscous_lunch_001`
- `recipe_chickpea_hummus_toast_001`
- `recipe_chickpea_pepper_dinner_001`
- `recipe_chickpea_spinach_dinner_001`
- `recipe_chickpea_tomato_skillet_001`
- `recipe_chickpea_yogurt_bowl_flex_001`
- `recipe_cottage_berries_bowl_001`
- `recipe_cottage_casserole_001`
- `recipe_cottage_lavash_roll_bf_001`
- `recipe_cottage_veg_lunch_bowl_001`
- `recipe_cottage_yogurt_fruit_001`
- `recipe_couscous_milk_breakfast_001`
- `recipe_egg_potato_skillet_lunch_001`
- `recipe_egg_spinach_scramble_lunch_001`
- `recipe_egg_tomato_skillet_dinner_001`
- `recipe_egg_veg_rice_bowl_flex_001`
- `recipe_egg_veg_wrap_flex_001`
- `recipe_eggs_veg_toast_001`
- `recipe_fish_rice_veg_001`
- `recipe_fish_veg_skillet_dinner_001`
- `recipe_fried_eggs_veg_001`
- `recipe_lavash_egg_cheese_001`
- `recipe_lentil_soup_001`
- `recipe_lentil_veg_dinner_skillet_001`
- `recipe_lentils_veg_egg_001`
- `recipe_meatballs_buckwheat_001`
- `recipe_millet_milk_porridge_001`
- `recipe_mushroom_egg_scramble_bf_001`
- `recipe_oatmeal_apple_cinnamon_001`
- `recipe_oatmeal_banana_001`
- `recipe_omelet_chicken_veg_001`
- `recipe_omelet_tomato_cheese_001`
- `recipe_overnight_oats_classic_001`
- `recipe_pasta_chicken_tomato_001`
- `recipe_pasta_peas_cheese_lunch_001`
- `recipe_pasta_tuna_tomato_001`
- `recipe_plov_chicken_001`
- `recipe_red_lentil_tomato_quick_001`
- `recipe_rice_chicken_veg_001`
- `recipe_rice_porridge_001`
- `recipe_savory_cottage_cucumber_001`
- `recipe_spinach_cottage_frittata_001`
- `recipe_stewed_beans_veg_001`
- `recipe_syrniki_001`
- `recipe_tuna_bean_salad_lunch_001`
- `recipe_tuna_rice_bowl_lunch_001`
- `recipe_tuna_zucchini_dinner_001`
- `recipe_turkey_bean_lunch_001`
- `recipe_turkey_cabbage_dinner_001`
- `recipe_turkey_couscous_lunch_001`
- `recipe_turkey_veg_lunch_skillet_001`
- `recipe_turkey_veg_skillet_001`
- `recipe_veg_casserole_cheese_001`
- `recipe_veg_cheese_skillet_dinner_001`
- `recipe_white_fish_couscous_lunch_001`
- `recipe_yogurt_oats_banana_001`
- `recipe_yogurt_oats_berries_001`

## 15. Recipes Recommended for Kitchen Testing

- `recipe_baked_chicken_veg_001`
- `recipe_baked_fish_potato_001`
- `recipe_baked_oat_apple_001`
- `recipe_bean_spinach_dinner_001`
- `recipe_bean_veg_rice_lunch_001`
- `recipe_beans_tomato_egg_lunch_001`
- `recipe_beef_cabbage_skillet_lunch_001`
- `recipe_beef_onion_pepper_dinner_001`
- `recipe_beef_pepper_rice_lunch_001`
- `recipe_beef_potato_stew_001`
- `recipe_beef_tomato_pasta_lunch_001`
- `recipe_beef_zucchini_dinner_001`
- `recipe_buckwheat_chicken_veg_001`
- `recipe_buckwheat_milk_001`
- `recipe_buckwheat_mushroom_egg_001`
- `recipe_chicken_cabbage_skillet_lunch_001`
- `recipe_chicken_cutlets_veg_001`
- `recipe_chicken_mushroom_dinner_001`
- `recipe_chicken_noodle_soup_001`
- `recipe_chicken_peas_carrot_dinner_001`
- `recipe_chicken_rice_bowl_lunch_001`
- `recipe_chicken_veg_lunch_skillet_001`
- `recipe_chicken_zucchini_dinner_skillet_001`
- `recipe_chickpea_couscous_lunch_001`
- `recipe_chickpea_pepper_dinner_001`
- `recipe_chickpea_spinach_dinner_001`
- `recipe_chickpea_tomato_skillet_001`
- `recipe_cottage_casserole_001`
- `recipe_egg_potato_skillet_lunch_001`
- `recipe_egg_tomato_skillet_dinner_001`
- `recipe_egg_veg_rice_bowl_flex_001`
- `recipe_fish_rice_veg_001`
- `recipe_fish_veg_skillet_dinner_001`
- `recipe_lentil_soup_001`
- `recipe_lentil_veg_dinner_skillet_001`
- `recipe_lentils_veg_egg_001`
- `recipe_meatballs_buckwheat_001`
- `recipe_millet_milk_porridge_001`
- `recipe_overnight_oats_classic_001`
- `recipe_pasta_chicken_tomato_001`
- `recipe_pasta_peas_cheese_lunch_001`
- `recipe_plov_chicken_001`
- `recipe_red_lentil_tomato_quick_001`
- `recipe_rice_chicken_veg_001`
- `recipe_rice_porridge_001`
- `recipe_spinach_cottage_frittata_001`
- `recipe_stewed_beans_veg_001`
- `recipe_tuna_bean_salad_lunch_001`
- `recipe_tuna_rice_bowl_lunch_001`
- `recipe_tuna_zucchini_dinner_001`
- `recipe_turkey_bean_lunch_001`
- `recipe_turkey_cabbage_dinner_001`
- `recipe_turkey_couscous_lunch_001`
- `recipe_turkey_veg_lunch_skillet_001`
- `recipe_turkey_veg_skillet_001`
- `recipe_veg_casserole_cheese_001`
- `recipe_veg_cheese_skillet_dinner_001`
- `recipe_white_fish_couscous_lunch_001`

## 16. Known Limitations

- Agent-generated YAML is schema-valid, not kitchen-proven.
- No invented source URLs or cookbook citations.
- Ingredient nutrition table exists but is empty in this sprint.
- Pattern evidence is structural/declared, not culinary proof.
- Automatic audit may assign up to `source_verified` when ≥2 sources and checks pass; never approved / human_reviewed / kitchen_tested.
- Selector weights, hard filters, MenuPlan, Claude pipeline, and Basket Engine are unchanged.

_Generated at 2026-08-04T21:15:02+00:00_
