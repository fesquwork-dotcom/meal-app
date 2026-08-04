"""Generate evaluation scenario YAML files. Run from backend/:

    python recipes/evaluation/generate_scenarios.py
"""

from __future__ import annotations

from pathlib import Path

import yaml

OUT = Path(__file__).resolve().parents[2] / "recipe_catalog" / "evaluation"
GOALS = [
    "balanced",
    "weight_loss",
    "weight_maintenance",
    "muscle_gain",
    "budget",
    "quick_cooking",
    "family",
]
MEALS = ["breakfast", "lunch", "dinner"]


def dump(path: Path, scenarios: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        yaml.safe_dump(
            {"scenarios": scenarios},
            fh,
            allow_unicode=True,
            sort_keys=False,
            default_flow_style=False,
        )


def sc(
    sid: str,
    name: str,
    group: str,
    context: dict,
    expected: int,
    *,
    weight: float = 1.0,
    description: str = "",
    enabled: bool = True,
) -> dict:
    ctx = {"limit": context.get("limit", 10), **context}
    if "limit" not in context:
        ctx["limit"] = max(expected, 5) if expected else 10
    return {
        "id": sid,
        "name": name,
        "description": description or name,
        "scenario_group": group,
        "expected_min_candidates": expected,
        "weight": weight,
        "enabled": enabled,
        "context": ctx,
    }


def build_baseline() -> list[dict]:
    out = []
    for meal in MEALS:
        out.append(
            sc(
                f"baseline_{meal}",
                f"Baseline {meal}",
                "baseline",
                {"meal_type": meal, "limit": 10},
                8,
                weight=1.5,
                description=f"Unrestricted {meal} catalog depth",
            )
        )
    return out


def build_goal() -> list[dict]:
    out = []
    for meal in MEALS:
        for goal in GOALS:
            out.append(
                sc(
                    f"goal_{meal}_{goal}",
                    f"{meal.title()} for {goal}",
                    "goal",
                    {"meal_type": meal, "goal": goal, "limit": 10},
                    5,
                    weight=1.0,
                )
            )
    return out


def build_time() -> list[dict]:
    specs = [
        ("breakfast", 10, 3),
        ("breakfast", 15, 5),
        ("breakfast", 20, 5),
        ("lunch", 20, 3),
        ("lunch", 30, 5),
        ("lunch", 45, 5),
        ("dinner", 20, 3),
        ("dinner", 30, 5),
        ("dinner", 45, 5),
    ]
    out = []
    for meal, minutes, expected in specs:
        out.append(
            sc(
                f"time_{meal}_le_{minutes}",
                f"{meal.title()} ≤{minutes} min",
                "time",
                {
                    "meal_type": meal,
                    "max_total_time_minutes": minutes,
                    "limit": 10,
                },
                expected,
            )
        )
    return out


def build_budget() -> list[dict]:
    bands = [
        ("very_budget_only", ["very_budget"], 3),
        ("very_budget_budget", ["very_budget", "budget"], 5),
        ("up_to_standard", ["very_budget", "budget", "standard"], 7),
    ]
    out = []
    for meal in MEALS:
        for key, classes, expected in bands:
            out.append(
                sc(
                    f"budget_{meal}_{key}",
                    f"{meal.title()} budget {key}",
                    "budget",
                    {
                        "meal_type": meal,
                        "allowed_budget_classes": classes,
                        "limit": 10,
                    },
                    expected,
                )
            )
    return out


def build_protein() -> list[dict]:
    out = []
    preferred = ["chicken", "beef", "turkey", "fish", "eggs", "legumes"]
    for meal in ("lunch", "dinner"):
        for protein in preferred:
            out.append(
                sc(
                    f"protein_{meal}_prefer_{protein}",
                    f"{meal.title()} prefer {protein}",
                    "protein",
                    {
                        "meal_type": meal,
                        "preferred_protein_sources": [protein],
                        "limit": 10,
                    },
                    3,
                    weight=0.8,
                )
            )
        out.append(
            sc(
                f"protein_{meal}_exclude_fish",
                f"{meal.title()} exclude fish",
                "protein",
                {
                    "meal_type": meal,
                    "excluded_protein_sources": ["fish"],
                    "limit": 10,
                },
                5,
            )
        )
        out.append(
            sc(
                f"protein_{meal}_exclude_chicken",
                f"{meal.title()} exclude chicken",
                "protein",
                {
                    "meal_type": meal,
                    "excluded_protein_sources": ["chicken"],
                    "limit": 10,
                },
                5,
            )
        )
        out.append(
            sc(
                f"protein_{meal}_exclude_meat",
                f"{meal.title()} exclude meat sources",
                "protein",
                {
                    "meal_type": meal,
                    "excluded_protein_sources": [
                        "chicken",
                        "beef",
                        "pork",
                        "turkey",
                    ],
                    "limit": 10,
                },
                3,
                weight=0.8,
            )
        )
    return out


def build_combined() -> list[dict]:
    return [
        sc(
            "dinner_weight_loss_quick_no_fish",
            "Быстрый ужин для снижения веса без рыбы",
            "combined",
            {
                "meal_type": "dinner",
                "goal": "weight_loss",
                "max_total_time_minutes": 30,
                "allowed_budget_classes": ["very_budget", "budget", "standard"],
                "excluded_protein_sources": ["fish"],
                "limit": 10,
            },
            5,
            weight=1.5,
            description="Ужин до 30 минут, без рыбы, бюджет до standard",
        ),
        sc(
            "breakfast_budget_quick",
            "Budget quick breakfast",
            "combined",
            {
                "meal_type": "breakfast",
                "goal": "budget",
                "max_total_time_minutes": 15,
                "allowed_budget_classes": ["very_budget", "budget"],
                "limit": 10,
            },
            5,
            weight=1.2,
        ),
        sc(
            "lunch_muscle_batch",
            "Muscle gain batch lunch",
            "combined",
            {
                "meal_type": "lunch",
                "goal": "muscle_gain",
                "prefer_batch_friendly": True,
                "preferred_protein_sources": ["chicken", "beef", "turkey"],
                "limit": 10,
            },
            5,
            weight=1.2,
        ),
        sc(
            "dinner_family_no_oven",
            "Family dinner without oven",
            "combined",
            {
                "meal_type": "dinner",
                "goal": "family",
                "family_mode": True,
                "available_equipment": ["stove", "frying_pan", "pot"],
                "limit": 10,
            },
            5,
            weight=1.2,
        ),
        sc(
            "lunch_budget_no_chicken",
            "Budget lunch without chicken",
            "combined",
            {
                "meal_type": "lunch",
                "goal": "budget",
                "excluded_protein_sources": ["chicken"],
                "allowed_budget_classes": ["very_budget", "budget"],
                "limit": 10,
            },
            5,
            weight=1.2,
        ),
        sc(
            "breakfast_weight_loss_no_dairy",
            "Weight loss breakfast without dairy",
            "combined",
            {
                "meal_type": "breakfast",
                "goal": "weight_loss",
                "excluded_ingredient_ids": [
                    "ing_milk",
                    "ing_yogurt",
                    "ing_cottage_cheese",
                    "ing_cheese",
                ],
                "limit": 10,
            },
            3,
            weight=1.0,
        ),
        sc(
            "dinner_quick_no_egg",
            "Quick dinner without eggs",
            "combined",
            {
                "meal_type": "dinner",
                "max_total_time_minutes": 30,
                "excluded_ingredient_ids": ["ing_egg"],
                "limit": 10,
            },
            5,
            weight=1.0,
        ),
        sc(
            "dinner_legumes_budget",
            "Dinner with legumes",
            "combined",
            {
                "meal_type": "dinner",
                "goal": "budget",
                "preferred_protein_sources": ["legumes"],
                "limit": 10,
            },
            3,
            weight=1.0,
        ),
        sc(
            "lunch_leftover_roles",
            "Lunch suitable for leftovers",
            "combined",
            {
                "meal_type": "lunch",
                "allow_leftovers": True,
                "desired_roles": ["leftover_source", "batch_base"],
                "limit": 10,
            },
            5,
            weight=1.0,
        ),
        sc(
            "breakfast_portable",
            "Portable breakfast",
            "combined",
            {
                "meal_type": "breakfast",
                "desired_roles": ["portable_meal"],
                "limit": 10,
            },
            3,
            weight=1.0,
        ),
        # Extra combined to reach 20+
        sc(
            "dinner_muscle_quick",
            "Quick muscle dinner",
            "combined",
            {
                "meal_type": "dinner",
                "goal": "muscle_gain",
                "max_total_time_minutes": 30,
                "preferred_protein_sources": ["chicken", "turkey", "eggs"],
                "limit": 10,
            },
            5,
        ),
        sc(
            "lunch_weight_loss_30",
            "Weight loss lunch ≤30",
            "combined",
            {
                "meal_type": "lunch",
                "goal": "weight_loss",
                "max_total_time_minutes": 30,
                "limit": 10,
            },
            5,
        ),
        sc(
            "breakfast_family",
            "Family breakfast",
            "combined",
            {
                "meal_type": "breakfast",
                "goal": "family",
                "family_mode": True,
                "limit": 10,
            },
            5,
        ),
        sc(
            "dinner_batch_leftover",
            "Batch leftover dinner",
            "combined",
            {
                "meal_type": "dinner",
                "prefer_batch_friendly": True,
                "allow_leftovers": True,
                "desired_roles": ["batch_base"],
                "limit": 10,
            },
            5,
        ),
        sc(
            "lunch_quick_budget",
            "Quick budget lunch",
            "combined",
            {
                "meal_type": "lunch",
                "goal": "budget",
                "max_total_time_minutes": 30,
                "allowed_budget_classes": ["very_budget", "budget"],
                "limit": 10,
            },
            5,
        ),
        sc(
            "dinner_no_chicken_standard",
            "Dinner without chicken up to standard",
            "combined",
            {
                "meal_type": "dinner",
                "excluded_protein_sources": ["chicken"],
                "allowed_budget_classes": ["very_budget", "budget", "standard"],
                "limit": 10,
            },
            5,
        ),
        sc(
            "breakfast_quick_cooking_10",
            "Quick cooking breakfast ≤10",
            "combined",
            {
                "meal_type": "breakfast",
                "goal": "quick_cooking",
                "max_total_time_minutes": 10,
                "limit": 10,
            },
            3,
        ),
        sc(
            "lunch_balanced_45",
            "Balanced lunch ≤45",
            "combined",
            {
                "meal_type": "lunch",
                "goal": "balanced",
                "max_total_time_minutes": 45,
                "limit": 10,
            },
            5,
        ),
        sc(
            "dinner_eggs_prefer",
            "Dinner prefer eggs",
            "combined",
            {
                "meal_type": "dinner",
                "preferred_protein_sources": ["eggs"],
                "goal": "muscle_gain",
                "limit": 10,
            },
            3,
        ),
        sc(
            "lunch_exclude_beef_fish",
            "Lunch exclude beef and fish",
            "combined",
            {
                "meal_type": "lunch",
                "excluded_protein_sources": ["beef", "fish"],
                "goal": "balanced",
                "limit": 10,
            },
            5,
        ),
        sc(
            "dinner_stove_only_batch",
            "Stove-only batch dinner",
            "equipment",
            {
                "meal_type": "dinner",
                "prefer_batch_friendly": True,
                "available_equipment": ["stove", "pot", "frying_pan", "saucepan"],
                "limit": 10,
            },
            5,
        ),
        sc(
            "breakfast_light_meal_role",
            "Breakfast light meal role",
            "combined",
            {
                "meal_type": "breakfast",
                "desired_roles": ["light_meal", "quick_meal"],
                "limit": 10,
            },
            5,
        ),
    ]


def build_stress() -> list[dict]:
    return [
        sc(
            "stress_dinner_ultra_restrictive",
            "Ultra-restrictive weight-loss dinner",
            "stress",
            {
                "meal_type": "dinner",
                "goal": "weight_loss",
                "max_total_time_minutes": 15,
                "allowed_budget_classes": ["very_budget"],
                "excluded_protein_sources": ["fish", "eggs", "chicken"],
                "limit": 10,
            },
            0,
            weight=0.25,
        ),
        sc(
            "stress_breakfast_no_dairy_10",
            "Breakfast ≤10 no dairy",
            "stress",
            {
                "meal_type": "breakfast",
                "max_total_time_minutes": 10,
                "excluded_ingredient_ids": [
                    "ing_milk",
                    "ing_yogurt",
                    "ing_cottage_cheese",
                    "ing_cheese",
                    "ing_egg",
                ],
                "limit": 10,
            },
            1,
            weight=0.25,
        ),
        sc(
            "stress_lunch_premium_only",
            "Lunch premium only",
            "stress",
            {
                "meal_type": "lunch",
                "allowed_budget_classes": ["premium"],
                "limit": 10,
            },
            0,
            weight=0.25,
        ),
        sc(
            "stress_dinner_microwave_only",
            "Dinner microwave-only equipment",
            "stress",
            {
                "meal_type": "dinner",
                "available_equipment": ["microwave"],
                "limit": 10,
            },
            0,
            weight=0.25,
        ),
        sc(
            "stress_lunch_no_proteins",
            "Lunch exclude all protein tags",
            "stress",
            {
                "meal_type": "lunch",
                "excluded_protein_sources": [
                    "chicken",
                    "turkey",
                    "beef",
                    "pork",
                    "fish",
                    "eggs",
                    "dairy",
                    "legumes",
                    "mixed",
                    "none",
                ],
                "limit": 10,
            },
            0,
            weight=0.25,
        ),
        sc(
            "stress_dinner_5min",
            "Dinner ≤5 minutes",
            "stress",
            {
                "meal_type": "dinner",
                "max_total_time_minutes": 5,
                "limit": 10,
            },
            0,
            weight=0.25,
        ),
        sc(
            "stress_breakfast_oven_required_only",
            "Breakfast with oven equipment only",
            "stress",
            {
                "meal_type": "breakfast",
                "available_equipment": ["oven", "baking_dish"],
                "limit": 10,
            },
            1,
            weight=0.25,
        ),
        sc(
            "stress_lunch_very_budget_20_no_chicken",
            "Lunch very_budget ≤20 no chicken",
            "stress",
            {
                "meal_type": "lunch",
                "max_total_time_minutes": 20,
                "allowed_budget_classes": ["very_budget"],
                "excluded_protein_sources": ["chicken"],
                "limit": 10,
            },
            1,
            weight=0.25,
        ),
    ]


def main() -> None:
    baseline = build_baseline() + build_goal()
    restrictive = (
        build_time()
        + build_budget()
        + build_protein()
        + build_combined()
        + build_stress()
    )
    dump(OUT / "baseline_scenarios.yaml", baseline)
    dump(OUT / "restrictive_scenarios.yaml", restrictive)
    total = len(baseline) + len(restrictive)
    print(f"Wrote {len(baseline)} baseline+goal, {len(restrictive)} restrictive, total={total}")


if __name__ == "__main__":
    main()
