"""Rule-based recipe addition / metadata review recommendations."""

from __future__ import annotations

from recipes.enums import GoalType, MealType, RecipeRole, TagType
from recipes.evaluation.models import (
    CatalogGapCluster,
    EvaluationScenario,
    EvaluationScenarioResult,
    GapSeverity,
    RecommendationType,
    RecipeAdditionRecommendation,
    ScenarioCoverageStatus,
)
from recipes.models import Recipe

_PROTEIN_LABEL_RU = {
    "chicken": "курицей",
    "turkey": "индейкой",
    "beef": "говядиной",
    "fish": "рыбой",
    "eggs": "яйцами",
    "legumes": "бобовыми",
    "dairy": "творогом",
}


def _suggest_name(cluster: CatalogGapCluster) -> str:
    meal = cluster.meal_types[0] if cluster.meal_types else "блюдо"
    meal_ru = {"breakfast": "завтрак", "lunch": "обед", "dinner": "ужин"}.get(
        meal, meal
    )
    protein = cluster.preferred_protein_sources[0] if cluster.preferred_protein_sources else None
    if not protein:
        excluded = set(cluster.excluded_protein_sources)
        for candidate in ("turkey", "chicken", "legumes", "eggs", "beef"):
            if candidate not in excluded:
                protein = candidate
                break
    protein_ru = _PROTEIN_LABEL_RU.get(protein or "", "овощами")
    quick = any(t and t <= 30 for t in cluster.time_limits)
    prefix = "Быстрый лёгкий" if quick else "Новый"
    return f"{prefix} {meal_ru} с {protein_ru}"


def _near_duplicate(
    cluster: CatalogGapCluster,
    recipes: list[Recipe],
) -> Recipe | None:
    """Find an existing recipe that roughly matches gap constraints."""
    meal = cluster.meal_types[0] if cluster.meal_types else None
    if not meal:
        return None
    time_limit = min(cluster.time_limits) if cluster.time_limits else None
    excluded_proteins = set(cluster.excluded_protein_sources)
    preferred = set(cluster.preferred_protein_sources)
    budget_ok = set(cluster.budget_classes) if cluster.budget_classes else None

    candidates: list[Recipe] = []
    for recipe in recipes:
        meals = {m.meal_type.value for m in recipe.meal_types} | {
            recipe.primary_meal_type.value
        }
        if meal not in meals:
            continue
        if time_limit is not None and recipe.total_time_minutes > time_limit:
            continue
        if budget_ok is not None and recipe.budget_class.value not in budget_ok:
            continue
        proteins = {
            t.tag_value
            for t in recipe.tags
            if t.tag_type == TagType.PROTEIN_SOURCE
        }
        if proteins & excluded_proteins:
            continue
        if preferred and not (proteins & preferred):
            continue
        candidates.append(recipe)

    if not candidates:
        return None
    # Prefer recipes missing goal score / role as metadata fix candidates
    goal = cluster.goals[0] if cluster.goals else None
    for recipe in candidates:
        goals = {g.goal.value for g in recipe.goal_scores}
        if goal and goal not in goals:
            return recipe
    return candidates[0]


def _metadata_recs(
    results: list[EvaluationScenarioResult],
    recipes: list[Recipe],
) -> list[RecipeAdditionRecommendation]:
    recs: list[RecipeAdditionRecommendation] = []
    priority = 80
    # Dinner recipes that are quick and high-protein but lack weight_loss goal score
    for recipe in recipes:
        if recipe.primary_meal_type != MealType.DINNER:
            continue
        if recipe.total_time_minutes > 30:
            continue
        goals = {g.goal for g in recipe.goal_scores}
        if GoalType.WEIGHT_LOSS not in goals and recipe.protein_level.value == "high":
            recs.append(
                RecipeAdditionRecommendation(
                    priority=priority,
                    recommendation_type=RecommendationType.REVIEW_GOAL_SCORE,
                    suggested_name=f"Review goal scores: {recipe.name}",
                    primary_meal_type=recipe.primary_meal_type.value,
                    target_goals=["weight_loss"],
                    max_total_time_minutes=recipe.total_time_minutes,
                    addresses_gap_ids=[],
                    estimated_scenario_impact=2,
                    reason_codes=["MISSING_GOAL_SCORE", "POTENTIAL_METADATA_GAP"],
                    related_recipe_id=recipe.id,
                )
            )
            priority += 1

        # Breakfast-capable egg dishes missing dinner primary already have multi meal —
        # flag omelets without portable role when tagged quick
        roles = {r.role for r in recipe.roles}
        if (
            recipe.primary_meal_type == MealType.BREAKFAST
            and RecipeRole.PORTABLE_MEAL not in roles
            and recipe.total_time_minutes <= 15
        ):
            # only once later deduped
            pass

    # Portable breakfast role gaps
    portable_weak = any(
        r.scenario_id == "breakfast_portable"
        and r.status
        in {ScenarioCoverageStatus.WEAK, ScenarioCoverageStatus.CRITICAL}
        for r in results
    )
    if portable_weak:
        for recipe in recipes:
            if recipe.primary_meal_type != MealType.BREAKFAST:
                continue
            if recipe.total_time_minutes > 15:
                continue
            roles = {r.role for r in recipe.roles}
            if RecipeRole.PORTABLE_MEAL not in roles:
                recs.append(
                    RecipeAdditionRecommendation(
                        priority=70,
                        recommendation_type=RecommendationType.ADD_ROLE,
                        suggested_name=f"Add portable_meal role: {recipe.name}",
                        primary_meal_type="breakfast",
                        desired_roles=["portable_meal"],
                        addresses_gap_ids=[],
                        estimated_scenario_impact=1,
                        reason_codes=["MISSING_ROLE"],
                        related_recipe_id=recipe.id,
                    )
                )
                break

    # Multi meal type: dinner omelets already have breakfast — check egg breakfasts for dinner
    for recipe in recipes:
        if recipe.primary_meal_type != MealType.BREAKFAST:
            continue
        proteins = {
            t.tag_value
            for t in recipe.tags
            if t.tag_type == TagType.PROTEIN_SOURCE
        }
        meals = {m.meal_type.value for m in recipe.meal_types}
        if "eggs" in proteins and "dinner" not in meals and recipe.total_time_minutes <= 25:
            recs.append(
                RecipeAdditionRecommendation(
                    priority=75,
                    recommendation_type=RecommendationType.ADD_MEAL_TYPE,
                    suggested_name=f"Add dinner meal type: {recipe.name}",
                    primary_meal_type="breakfast",
                    supported_meal_types=["breakfast", "dinner"],
                    addresses_gap_ids=[],
                    estimated_scenario_impact=2,
                    reason_codes=["MISSING_MEAL_TYPE"],
                    related_recipe_id=recipe.id,
                )
            )
            break

    return recs


def build_recommendations(
    results: list[EvaluationScenarioResult],
    clusters: list[CatalogGapCluster],
    recipes: list[Recipe],
    scenarios_by_id: dict[str, EvaluationScenario],
) -> list[RecipeAdditionRecommendation]:
    recs: list[RecipeAdditionRecommendation] = []
    seen_signatures: set[tuple] = set()

    for priority, cluster in enumerate(clusters, start=1):
        if cluster.severity == GapSeverity.LOW and len(cluster.affected_scenario_ids) == 1:
            # Skip single low stress-like gaps unless critical missing
            sc = scenarios_by_id.get(cluster.affected_scenario_ids[0])
            if sc and sc.weight < 0.5:
                continue

        # Coarse signature: quick lunch gaps share one recipe concept.
        time_bucket = None
        if cluster.time_limits:
            tmin = min(cluster.time_limits)
            time_bucket = "le_30" if tmin <= 30 else ("le_45" if tmin <= 45 else str(tmin))
        signature = (
            tuple(cluster.meal_types),
            time_bucket,
            tuple(cluster.excluded_protein_sources),
            tuple(cluster.preferred_protein_sources[:1]),
            tuple(cluster.excluded_ingredients),
        )
        if signature in seen_signatures:
            for existing in recs:
                same_meal = existing.primary_meal_type in cluster.meal_types
                if same_meal and existing.recommendation_type.value == "add_recipe":
                    if cluster.id not in existing.addresses_gap_ids:
                        existing.addresses_gap_ids.append(cluster.id)
                        existing.estimated_scenario_impact += len(
                            cluster.affected_scenario_ids
                        )
                    break
            continue
        seen_signatures.add(signature)

        near = _near_duplicate(cluster, recipes)
        if near is not None:
            goal = cluster.goals[0] if cluster.goals else None
            has_goal = goal in {g.goal.value for g in near.goal_scores} if goal else True
            if not has_goal:
                rec_type = RecommendationType.REVIEW_GOAL_SCORE
                reason = ["SIMILAR_RECIPE_MISSING_GOAL_SCORE"]
            else:
                rec_type = RecommendationType.RETAG_OR_REVIEW_EXISTING_RECIPE
                reason = ["SIMILAR_RECIPE_EXISTS"]
            recs.append(
                RecipeAdditionRecommendation(
                    priority=priority,
                    recommendation_type=rec_type,
                    suggested_name=f"Review existing: {near.name}",
                    primary_meal_type=cluster.meal_types[0] if cluster.meal_types else None,
                    supported_meal_types=list(cluster.meal_types),
                    target_goals=list(cluster.goals),
                    budget_class=cluster.budget_classes[0] if cluster.budget_classes else None,
                    max_total_time_minutes=(
                        min(cluster.time_limits) if cluster.time_limits else None
                    ),
                    protein_source=(
                        cluster.preferred_protein_sources[0]
                        if cluster.preferred_protein_sources
                        else None
                    ),
                    desired_roles=list(cluster.desired_roles),
                    required_properties=[],
                    avoid_properties=[
                        f"protein:{p}" for p in cluster.excluded_protein_sources
                    ]
                    + [f"ingredient:{i}" for i in cluster.excluded_ingredients],
                    addresses_gap_ids=[cluster.id],
                    estimated_scenario_impact=len(cluster.affected_scenario_ids),
                    reason_codes=reason,
                    related_recipe_id=near.id,
                )
            )
            continue

        protein = (
            cluster.preferred_protein_sources[0]
            if cluster.preferred_protein_sources
            else None
        )
        recs.append(
            RecipeAdditionRecommendation(
                priority=priority,
                recommendation_type=RecommendationType.ADD_RECIPE,
                suggested_name=_suggest_name(cluster),
                primary_meal_type=cluster.meal_types[0] if cluster.meal_types else None,
                supported_meal_types=list(cluster.meal_types),
                target_goals=list(cluster.goals),
                budget_class=(
                    "budget"
                    if not cluster.budget_classes
                    else (
                        "very_budget"
                        if "very_budget" in cluster.budget_classes
                        else cluster.budget_classes[0]
                    )
                ),
                max_total_time_minutes=(
                    min(cluster.time_limits) if cluster.time_limits else None
                ),
                protein_source=protein,
                desired_roles=list(cluster.desired_roles),
                required_properties=[
                    *(["batch_friendly"] if "batch" in cluster.title else []),
                    *(["leftover_friendly"] if cluster.desired_roles else []),
                ],
                avoid_properties=[
                    f"protein:{p}" for p in cluster.excluded_protein_sources
                ]
                + [f"ingredient:{i}" for i in cluster.excluded_ingredients],
                addresses_gap_ids=[cluster.id],
                estimated_scenario_impact=len(cluster.affected_scenario_ids),
                reason_codes=["CATALOG_GAP", *cluster.dominant_filter_reasons[:3]],
            )
        )

    recs.extend(_metadata_recs(results, recipes))
    recs.sort(key=lambda r: (r.priority, r.suggested_name))
    # Re-number priorities stably
    for idx, rec in enumerate(recs, start=1):
        rec.priority = idx
    return recs
