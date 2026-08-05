# -*- coding: utf-8 -*-
"""Append Sprint 10.9 recipe relations (>=60 new)."""
from __future__ import annotations

from pathlib import Path

import yaml

REL_PATH = Path("recipe_catalog/relations/relations.yaml")

# Meaningful relations among new + some existing recipes.
# Format: (source, target, type, score, reason)
NEW = [
    # --- similar_meal / avoid_consecutive among egg breakfasts ---
    ("recipe_spinach_cottage_frittata_001", "recipe_mushroom_egg_scramble_bf_001", "similar_meal", 0.75, "Egg skillet breakfasts"),
    ("recipe_spinach_cottage_frittata_001", "recipe_mushroom_egg_scramble_bf_001", "avoid_consecutive_days", 0.8, "Similar egg breakfast structure"),
    ("recipe_eggs_veg_toast_001", "recipe_fried_eggs_veg_001", "similar_meal", 0.8, "Eggs with vegetables"),
    ("recipe_eggs_veg_toast_001", "recipe_fried_eggs_veg_001", "avoid_consecutive_days", 0.75, "Egg+veg breakfast repeat"),
    ("recipe_eggs_veg_toast_001", "recipe_omelet_tomato_cheese_001", "avoid_same_day", 0.7, "Two egg breakfasts same day"),
    ("recipe_mushroom_egg_scramble_bf_001", "recipe_omelet_tomato_cheese_001", "similar_meal", 0.7, "Egg scramble/omelet family"),
    ("recipe_spinach_cottage_frittata_001", "recipe_omelet_tomato_cheese_001", "avoid_consecutive_days", 0.7, "Egg-forward breakfasts"),
    # --- cottage / yogurt / oats breakfasts ---
    ("recipe_cottage_berries_bowl_001", "recipe_cottage_yogurt_fruit_001", "similar_meal", 0.85, "Cottage cheese bowls"),
    ("recipe_cottage_berries_bowl_001", "recipe_cottage_yogurt_fruit_001", "avoid_consecutive_days", 0.8, "Cottage breakfast repeat"),
    ("recipe_cottage_berries_bowl_001", "recipe_savory_cottage_cucumber_001", "shares_ingredients", 0.7, "Shared cottage cheese"),
    ("recipe_savory_cottage_cucumber_001", "recipe_cottage_veg_lunch_bowl_001", "similar_meal", 0.8, "Savory cottage + vegetables"),
    ("recipe_savory_cottage_cucumber_001", "recipe_cottage_veg_lunch_bowl_001", "avoid_same_day", 0.65, "Same cottage-veg pattern"),
    ("recipe_yogurt_oats_berries_001", "recipe_yogurt_oats_banana_001", "similar_meal", 0.9, "Yogurt oats bowls"),
    ("recipe_yogurt_oats_berries_001", "recipe_yogurt_oats_banana_001", "avoid_consecutive_days", 0.85, "Near-identical oat bowls"),
    ("recipe_overnight_oats_classic_001", "recipe_oatmeal_banana_001", "similar_meal", 0.75, "Oat breakfasts"),
    ("recipe_overnight_oats_classic_001", "recipe_yogurt_oats_berries_001", "shares_ingredients", 0.8, "Oats + yogurt/milk dairy"),
    ("recipe_baked_oat_apple_001", "recipe_oatmeal_apple_cinnamon_001", "similar_meal", 0.85, "Oats + apple + cinnamon"),
    ("recipe_baked_oat_apple_001", "recipe_oatmeal_apple_cinnamon_001", "avoid_consecutive_days", 0.8, "Apple oat breakfast repeat"),
    ("recipe_millet_milk_porridge_001", "recipe_buckwheat_milk_001", "similar_meal", 0.75, "Milk porridge breakfasts"),
    ("recipe_millet_milk_porridge_001", "recipe_couscous_milk_breakfast_001", "similar_meal", 0.7, "Grain milk porridge"),
    ("recipe_couscous_milk_breakfast_001", "recipe_rice_porridge_001", "similar_meal", 0.65, "Soft grain porridge"),
    ("recipe_millet_milk_porridge_001", "recipe_couscous_milk_breakfast_001", "avoid_consecutive_days", 0.7, "Porridge-heavy mornings"),
    ("recipe_chickpea_hummus_toast_001", "recipe_eggs_veg_toast_001", "shares_ingredients", 0.55, "Shared bread/toast base"),
    ("recipe_cottage_lavash_roll_bf_001", "recipe_lavash_egg_cheese_001", "similar_meal", 0.7, "Lavash roll breakfasts"),
    ("recipe_cottage_lavash_roll_bf_001", "recipe_egg_veg_wrap_flex_001", "shares_ingredients", 0.6, "Shared lavash wrap format"),
    # --- flex bowls ---
    ("recipe_egg_veg_rice_bowl_flex_001", "recipe_chicken_rice_bowl_lunch_001", "similar_meal", 0.65, "Rice bowl lunch structure"),
    ("recipe_egg_veg_rice_bowl_flex_001", "recipe_tuna_rice_bowl_lunch_001", "similar_meal", 0.6, "Protein + rice bowls"),
    ("recipe_chickpea_yogurt_bowl_flex_001", "recipe_chickpea_hummus_toast_001", "shares_ingredients", 0.7, "Shared chickpeas"),
    ("recipe_chickpea_yogurt_bowl_flex_001", "recipe_savory_cottage_cucumber_001", "good_pair", 0.55, "Light dairy/veg breakfast+lunch alt"),
    # --- lunch similar / avoid ---
    ("recipe_turkey_couscous_lunch_001", "recipe_white_fish_couscous_lunch_001", "shares_ingredients", 0.7, "Shared couscous base"),
    ("recipe_turkey_couscous_lunch_001", "recipe_chickpea_couscous_lunch_001", "similar_meal", 0.7, "Couscous protein bowls"),
    ("recipe_turkey_couscous_lunch_001", "recipe_chickpea_couscous_lunch_001", "avoid_consecutive_days", 0.75, "Couscous lunch repeat"),
    ("recipe_white_fish_couscous_lunch_001", "recipe_chickpea_couscous_lunch_001", "avoid_consecutive_days", 0.7, "Couscous-heavy lunches"),
    ("recipe_chicken_rice_bowl_lunch_001", "recipe_rice_chicken_veg_001", "similar_meal", 0.85, "Chicken rice lunches"),
    ("recipe_chicken_rice_bowl_lunch_001", "recipe_rice_chicken_veg_001", "avoid_consecutive_days", 0.85, "Chicken+rice repeat"),
    ("recipe_chicken_rice_bowl_lunch_001", "recipe_beef_pepper_rice_lunch_001", "shares_ingredients", 0.65, "Shared rice"),
    ("recipe_beef_pepper_rice_lunch_001", "recipe_bean_veg_rice_lunch_001", "shares_ingredients", 0.6, "Shared rice base"),
    ("recipe_beef_pepper_rice_lunch_001", "recipe_beef_tomato_pasta_lunch_001", "avoid_consecutive_days", 0.75, "Beef mince lunches"),
    ("recipe_beef_tomato_pasta_lunch_001", "recipe_pasta_chicken_tomato_001", "similar_meal", 0.7, "Tomato pasta lunches"),
    ("recipe_beef_tomato_pasta_lunch_001", "recipe_pasta_peas_cheese_lunch_001", "shares_ingredients", 0.6, "Shared pasta"),
    ("recipe_chicken_cabbage_skillet_lunch_001", "recipe_turkey_cabbage_dinner_001", "similar_meal", 0.75, "Poultry + cabbage skillet"),
    ("recipe_chicken_cabbage_skillet_lunch_001", "recipe_turkey_cabbage_dinner_001", "avoid_consecutive_days", 0.8, "Cabbage poultry repeat"),
    ("recipe_tuna_rice_bowl_lunch_001", "recipe_fish_rice_veg_001", "similar_meal", 0.7, "Fish/tuna rice bowls"),
    ("recipe_tuna_rice_bowl_lunch_001", "recipe_tuna_bean_salad_lunch_001", "shares_ingredients", 0.65, "Shared tuna"),
    ("recipe_red_lentil_tomato_quick_001", "recipe_lentil_soup_001", "similar_meal", 0.8, "Lentil tomato dishes"),
    ("recipe_red_lentil_tomato_quick_001", "recipe_lentil_soup_001", "avoid_consecutive_days", 0.75, "Lentil lunch repeat"),
    ("recipe_red_lentil_tomato_quick_001", "recipe_lentil_veg_dinner_skillet_001", "similar_meal", 0.7, "Lentil tomato skillet family"),
    ("recipe_chickpea_couscous_lunch_001", "recipe_chickpea_tomato_skillet_001", "shares_ingredients", 0.75, "Shared chickpeas"),
    ("recipe_bean_veg_rice_lunch_001", "recipe_stewed_beans_veg_001", "shares_ingredients", 0.7, "Shared beans"),
    ("recipe_egg_potato_skillet_lunch_001", "recipe_egg_spinach_scramble_lunch_001", "similar_meal", 0.7, "Egg skillet lunches"),
    ("recipe_egg_potato_skillet_lunch_001", "recipe_egg_tomato_skillet_dinner_001", "avoid_consecutive_days", 0.7, "Egg skillet meals"),
    ("recipe_turkey_bean_lunch_001", "recipe_turkey_veg_skillet_001", "shares_ingredients", 0.65, "Shared turkey"),
    ("recipe_turkey_bean_lunch_001", "recipe_stewed_beans_veg_001", "shares_ingredients", 0.6, "Shared beans"),
    ("recipe_pasta_peas_cheese_lunch_001", "recipe_pasta_chicken_tomato_001", "avoid_consecutive_days", 0.65, "Pasta lunch repeat"),
    # --- dinner similar / avoid ---
    ("recipe_beef_zucchini_dinner_001", "recipe_beef_onion_pepper_dinner_001", "similar_meal", 0.8, "Beef mince dinners"),
    ("recipe_beef_zucchini_dinner_001", "recipe_beef_onion_pepper_dinner_001", "avoid_consecutive_days", 0.85, "Beef mince dinner repeat"),
    ("recipe_beef_zucchini_dinner_001", "recipe_chicken_zucchini_dinner_skillet_001", "shares_ingredients", 0.6, "Shared zucchini skillet"),
    ("recipe_chicken_mushroom_dinner_001", "recipe_buckwheat_mushroom_egg_001", "shares_ingredients", 0.55, "Shared mushrooms"),
    ("recipe_chicken_mushroom_dinner_001", "recipe_chicken_zucchini_dinner_skillet_001", "avoid_consecutive_days", 0.7, "Chicken skillet dinners"),
    ("recipe_chickpea_pepper_dinner_001", "recipe_chickpea_spinach_dinner_001", "similar_meal", 0.85, "Chickpea dinners"),
    ("recipe_chickpea_pepper_dinner_001", "recipe_chickpea_spinach_dinner_001", "avoid_consecutive_days", 0.8, "Chickpea dinner repeat"),
    ("recipe_bean_spinach_dinner_001", "recipe_stewed_beans_veg_001", "similar_meal", 0.75, "Bean vegetable dinners"),
    ("recipe_bean_spinach_dinner_001", "recipe_chickpea_pepper_dinner_001", "avoid_consecutive_days", 0.65, "Legume dinners"),
    ("recipe_fish_veg_skillet_dinner_001", "recipe_baked_fish_potato_001", "similar_meal", 0.7, "White fish dinners"),
    ("recipe_fish_veg_skillet_dinner_001", "recipe_baked_fish_potato_001", "avoid_consecutive_days", 0.75, "Fish dinner repeat"),
    ("recipe_tuna_zucchini_dinner_001", "recipe_pasta_tuna_tomato_001", "shares_ingredients", 0.65, "Shared tuna"),
    ("recipe_tuna_zucchini_dinner_001", "recipe_fish_veg_skillet_dinner_001", "avoid_consecutive_days", 0.7, "Fish/seafood dinners"),
    ("recipe_egg_tomato_skillet_dinner_001", "recipe_omelet_chicken_veg_001", "similar_meal", 0.65, "Egg-based dinners"),
    ("recipe_egg_tomato_skillet_dinner_001", "recipe_veg_cheese_skillet_dinner_001", "shares_ingredients", 0.5, "Skillet veg dinner base"),
    ("recipe_chicken_peas_carrot_dinner_001", "recipe_baked_chicken_veg_001", "shares_ingredients", 0.6, "Shared chicken + carrot"),
    ("recipe_chicken_peas_carrot_dinner_001", "recipe_chicken_mushroom_dinner_001", "avoid_consecutive_days", 0.7, "Chicken dinner repeat"),
    ("recipe_lentil_veg_dinner_skillet_001", "recipe_lentils_veg_egg_001", "similar_meal", 0.75, "Lentil vegetable meals"),
    ("recipe_lentil_veg_dinner_skillet_001", "recipe_red_lentil_tomato_quick_001", "avoid_consecutive_days", 0.8, "Lentil day stacking"),
    ("recipe_turkey_cabbage_dinner_001", "recipe_turkey_veg_skillet_001", "similar_meal", 0.75, "Turkey skillet dinners"),
    ("recipe_turkey_cabbage_dinner_001", "recipe_turkey_veg_skillet_001", "avoid_consecutive_days", 0.8, "Turkey dinner repeat"),
    ("recipe_veg_cheese_skillet_dinner_001", "recipe_veg_casserole_cheese_001", "similar_meal", 0.8, "Vegetable cheese dinners"),
    ("recipe_veg_cheese_skillet_dinner_001", "recipe_veg_casserole_cheese_001", "avoid_consecutive_days", 0.75, "Cheese veg dinner repeat"),
    # --- good_pair breakfast+lunch / lunch+dinner ---
    ("recipe_yogurt_oats_berries_001", "recipe_chicken_rice_bowl_lunch_001", "good_pair", 0.75, "Light oats breakfast + filling lunch"),
    ("recipe_cottage_berries_bowl_001", "recipe_turkey_couscous_lunch_001", "good_pair", 0.7, "Protein breakfast + couscous lunch"),
    ("recipe_millet_milk_porridge_001", "recipe_beef_tomato_pasta_lunch_001", "good_pair", 0.65, "Porridge morning + pasta lunch"),
    ("recipe_overnight_oats_classic_001", "recipe_red_lentil_tomato_quick_001", "good_pair", 0.7, "Make-ahead oats + quick lentil lunch"),
    ("recipe_eggs_veg_toast_001", "recipe_chickpea_couscous_lunch_001", "good_pair", 0.7, "Egg toast + legume lunch"),
    ("recipe_spinach_cottage_frittata_001", "recipe_tuna_rice_bowl_lunch_001", "good_pair", 0.7, "Egg breakfast + tuna lunch"),
    ("recipe_savory_cottage_cucumber_001", "recipe_chicken_cabbage_skillet_lunch_001", "good_pair", 0.7, "Light cottage BF + skillet lunch"),
    ("recipe_chickpea_hummus_toast_001", "recipe_fish_veg_skillet_dinner_001", "good_pair", 0.65, "Plant BF + fish dinner"),
    ("recipe_chicken_rice_bowl_lunch_001", "recipe_veg_cheese_skillet_dinner_001", "good_pair", 0.75, "Hearty lunch + light veg dinner"),
    ("recipe_red_lentil_tomato_quick_001", "recipe_chicken_mushroom_dinner_001", "good_pair", 0.7, "Legume lunch + chicken dinner"),
    ("recipe_turkey_couscous_lunch_001", "recipe_bean_spinach_dinner_001", "good_pair", 0.7, "Poultry lunch + bean dinner"),
    ("recipe_beef_pepper_rice_lunch_001", "recipe_fish_veg_skillet_dinner_001", "good_pair", 0.7, "Beef lunch + lighter fish dinner"),
    ("recipe_white_fish_couscous_lunch_001", "recipe_beef_zucchini_dinner_001", "good_pair", 0.65, "Fish lunch + beef dinner rotation"),
    ("recipe_bean_veg_rice_lunch_001", "recipe_turkey_cabbage_dinner_001", "good_pair", 0.7, "Bean lunch + turkey dinner"),
    ("recipe_pasta_peas_cheese_lunch_001", "recipe_tuna_zucchini_dinner_001", "good_pair", 0.7, "Pasta lunch + tuna dinner"),
    ("recipe_egg_potato_skillet_lunch_001", "recipe_chickpea_pepper_dinner_001", "good_pair", 0.65, "Egg lunch + chickpea dinner"),
    ("recipe_cottage_veg_lunch_bowl_001", "recipe_chicken_peas_carrot_dinner_001", "good_pair", 0.7, "Light lunch + chicken dinner"),
    ("recipe_turkey_bean_lunch_001", "recipe_veg_cheese_skillet_dinner_001", "good_pair", 0.7, "Turkey bean lunch + veg dinner"),
    # --- leftovers / component ---
    ("recipe_chicken_rice_bowl_lunch_001", "recipe_egg_veg_rice_bowl_flex_001", "provides_component_for", 0.55, "Cooked rice can feed flex bowl"),
    ("recipe_baked_chicken_veg_001", "recipe_chicken_mushroom_dinner_001", "uses_leftovers_from", 0.5, "Leftover chicken into skillet"),
    ("recipe_chickpea_couscous_lunch_001", "recipe_chickpea_pepper_dinner_001", "provides_component_for", 0.55, "Cooked chickpeas for dinner"),
    ("recipe_turkey_couscous_lunch_001", "recipe_turkey_cabbage_dinner_001", "provides_component_for", 0.5, "Cooked turkey for next meal"),
    ("recipe_red_lentil_tomato_quick_001", "recipe_lentil_veg_dinner_skillet_001", "uses_leftovers_from", 0.55, "Cooked lentils reused"),
    ("recipe_stewed_beans_veg_001", "recipe_bean_spinach_dinner_001", "provides_component_for", 0.6, "Stewed beans as component"),
    ("recipe_bean_veg_rice_lunch_001", "recipe_bean_spinach_dinner_001", "shares_ingredients", 0.65, "Shared beans across meals"),
    # --- balances_nutrition ---
    ("recipe_yogurt_oats_berries_001", "recipe_beef_onion_pepper_dinner_001", "balances_nutrition", 0.6, "Carb dairy morning + meat dinner"),
    ("recipe_cottage_berries_bowl_001", "recipe_beef_pepper_rice_lunch_001", "balances_nutrition", 0.6, "High protein dairy + rice lunch"),
    ("recipe_chickpea_yogurt_bowl_flex_001", "recipe_fish_veg_skillet_dinner_001", "balances_nutrition", 0.55, "Legume lunch + fish dinner"),
    ("recipe_millet_milk_porridge_001", "recipe_turkey_bean_lunch_001", "balances_nutrition", 0.55, "Grain porridge + turkey bean"),
]

def main() -> None:
    data = yaml.safe_load(REL_PATH.read_text(encoding="utf-8"))
    existing = data.get("relations") or []
    existing_ids = {r["id"] for r in existing}
    pairs = {(r["source_recipe_id"], r["target_recipe_id"], r["relation_type"]) for r in existing}
    # find next id
    max_n = 0
    for r in existing:
        rid = r["id"]
        if rid.startswith("rel_"):
            try:
                max_n = max(max_n, int(rid.split("_", 1)[1]))
            except ValueError:
                pass
    added = []
    for src, tgt, rtype, score, reason in NEW:
        key = (src, tgt, rtype)
        if key in pairs or (tgt, src, rtype) in pairs and rtype in {
            "similar_meal", "shares_ingredients", "avoid_same_day",
            "avoid_consecutive_days", "good_pair", "balances_nutrition",
        }:
            # still allow directed leftovers/component even if reverse exists
            if rtype in {"uses_leftovers_from", "provides_component_for"}:
                if key in pairs:
                    continue
            else:
                if key in pairs:
                    continue
                # skip undirected dupes
                if (tgt, src, rtype) in pairs:
                    continue
        max_n += 1
        rid = f"rel_{max_n:03d}"
        while rid in existing_ids:
            max_n += 1
            rid = f"rel_{max_n:03d}"
        row = {
            "id": rid,
            "source_recipe_id": src,
            "target_recipe_id": tgt,
            "relation_type": rtype,
            "score": score,
            "reason": reason,
        }
        existing.append(row)
        existing_ids.add(rid)
        pairs.add(key)
        added.append(row)
    data["relations"] = existing
    REL_PATH.write_text(
        yaml.safe_dump(data, allow_unicode=True, sort_keys=False, default_flow_style=False),
        encoding="utf-8",
    )
    print(f"added={len(added)} total={len(existing)} last_id=rel_{max_n:03d}")
    from collections import Counter
    print(dict(Counter(r["relation_type"] for r in added)))

if __name__ == "__main__":
    main()
