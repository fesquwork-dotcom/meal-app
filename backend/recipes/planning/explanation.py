"""Week-level explanation builder."""

from __future__ import annotations

from collections import Counter
from typing import Any

from recipes.planning.codes import planner_reason_text_ru
from recipes.planning.context import WeeklyPlanningContext
from recipes.planning.models import WeeklyRecipePlan


def build_week_explanation(
    plan: WeeklyRecipePlan,
    context: WeeklyPlanningContext,
) -> dict[str, Any]:
    leftovers = [m for m in plan.meals if m.is_leftover]
    cooks = [m for m in plan.meals if not m.is_leftover]

    protein_note = (
        "Protein diversity is soft-scored across lunch/dinner; "
        "breakfast egg/dairy repeats are softened."
    )
    leftover_note = (
        f"{len(leftovers)} leftover meal(s) linked to cooking instances."
        if leftovers
        else "No leftover meals in this plan."
    )
    batch_note = (
        f"{sum(1 for c in plan.cooking_instances if c.servings_cooked > 1)} "
        "batch cooking instance(s) prepared extra servings."
    )

    # Cases where selector rank > 1 was chosen
    rank_overrides = [
        {
            "slot_id": m.slot_id,
            "selected": m.recipe_id,
            "selector_rank": m.selector_rank,
            "alternatives": m.alternatives,
        }
        for m in plan.meals
        if m.selector_rank is not None and m.selector_rank > 1
    ]

    top_reasons = Counter()
    for m in plan.meals:
        top_reasons.update(m.planner_reasons)

    return {
        "summary_ru": (
            f"План на {plan.days} дн., статус={plan.status.value}, "
            f"score={plan.score:.3f}, блюд={len(plan.meals)}, "
            f"остатков={len(leftovers)}, готовить={len(cooks)}."
        ),
        "leftovers": leftover_note,
        "batch": batch_note,
        "protein_policy": protein_note,
        "cook_days": list(context.cook_days),
        "selector_overrides": rank_overrides[:12],
        "top_planner_reasons": [
            {"code": code, "count": count, "text_ru": planner_reason_text_ru(code)}
            for code, count in top_reasons.most_common(8)
        ],
        "score_breakdown": plan.score_breakdown.as_dict(),
    }
