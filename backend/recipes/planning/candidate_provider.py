"""Candidate provider — always delegates to RecipeCandidateSelector."""

from __future__ import annotations

from dataclasses import dataclass, field

from recipes.enums import MealType, RecipeRole, TagType
from recipes.models import Recipe
from recipes.planning.context import WeeklyPlanningContext
from recipes.planning.slots import WeeklyMealSlot
from recipes.quality.enums import QualityStatus
from recipes.repository import RecipeRepository
from recipes.selection.context import CandidateSelectionContext
from recipes.selection.models import RecipeCandidate, RecipeSelectionResult
from recipes.selection.selector import RecipeCandidateSelector

QUALITY_RANK: dict[str, int] = {
    QualityStatus.UNREVIEWED.value: 0,
    QualityStatus.SCHEMA_VALIDATED.value: 1,
    QualityStatus.COMPUTATIONALLY_CHECKED.value: 2,
    QualityStatus.SOURCE_VERIFIED.value: 3,
    QualityStatus.HUMAN_REVIEWED.value: 4,
    QualityStatus.KITCHEN_TESTED.value: 5,
    QualityStatus.APPROVED.value: 6,
    QualityStatus.REJECTED.value: -1,
}


@dataclass
class SlotCandidatePool:
    slot_id: str
    candidates: list[RecipeCandidate] = field(default_factory=list)
    selection_result: RecipeSelectionResult | None = None
    filter_stats: dict[str, int] = field(default_factory=dict)


class PlanningCandidateProvider:
    """Builds per-slot CandidateSelectionContext and calls Selector."""

    def __init__(
        self,
        *,
        selector: RecipeCandidateSelector | None = None,
        repository: RecipeRepository | None = None,
        quality_by_recipe: dict[str, str] | None = None,
    ) -> None:
        self.repository = repository or RecipeRepository()
        self.selector = selector or RecipeCandidateSelector(repository=self.repository)
        self.quality_by_recipe = quality_by_recipe or {}

    async def load_quality_map(self) -> dict[str, str]:
        if self.quality_by_recipe:
            return self.quality_by_recipe
        import aiosqlite

        mapping: dict[str, str] = {}
        async with aiosqlite.connect(self.repository.db_path) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute(
                "SELECT recipe_id, quality_status FROM recipe_provenance"
            )
            for row in await cur.fetchall():
                mapping[str(row["recipe_id"])] = str(row["quality_status"])
        self.quality_by_recipe = mapping
        return mapping

    def build_slot_context(
        self,
        planning: WeeklyPlanningContext,
        slot: WeeklyMealSlot,
        *,
        avoid_extra: set[str] | None = None,
    ) -> CandidateSelectionContext:
        desired_roles: list[RecipeRole] = []
        if planning.prefer_batch_friendly and slot.meal_type != MealType.BREAKFAST:
            desired_roles.append(RecipeRole.BATCH_BASE)
            if planning.leftovers_enabled:
                desired_roles.append(RecipeRole.LEFTOVER_SOURCE)

        preferred_tags: set[tuple[str, str]] = set()
        if planning.prefer_faster_meals:
            preferred_tags.add(("usage", "quick"))

        avoid = set(planning.avoided_recipe_ids) | set(planning.recent_recipe_ids)
        if avoid_extra:
            avoid |= avoid_extra

        return CandidateSelectionContext(
            meal_type=slot.meal_type,
            limit=planning.config.candidate_pool_size,
            goal=planning.goal,
            allowed_budget_classes=planning.allowed_budget_classes,
            max_total_time_minutes=planning.max_cooking_time,
            excluded_ingredient_ids=set(planning.excluded_ingredient_ids),
            excluded_protein_sources=set(planning.excluded_protein_sources),
            preferred_protein_sources=set(planning.preferred_proteins),
            required_tags=set(planning.required_tags),
            excluded_tags=set(planning.excluded_tags),
            preferred_tags=preferred_tags,
            desired_roles=desired_roles,
            avoid_recipe_ids=avoid,
            allow_leftovers=planning.leftovers_enabled,
            prefer_batch_friendly=planning.prefer_batch_friendly
            and slot.meal_type != MealType.BREAKFAST,
            family_mode=planning.family_mode,
            minimum_quality_status=planning.minimum_quality_status,
        )

    def _passes_quality(self, recipe_id: str, minimum: QualityStatus | None) -> bool:
        if minimum is None:
            return True
        status = self.quality_by_recipe.get(recipe_id)
        if status is None:
            return False
        if status == QualityStatus.REJECTED.value:
            return False
        return QUALITY_RANK.get(status, -1) >= QUALITY_RANK.get(minimum.value, 0)

    async def candidates_for_slot(
        self,
        planning: WeeklyPlanningContext,
        slot: WeeklyMealSlot,
        *,
        recipe_pool: list[Recipe] | None = None,
        avoid_extra: set[str] | None = None,
    ) -> SlotCandidatePool:
        await self.load_quality_map()
        ctx = self.build_slot_context(planning, slot, avoid_extra=avoid_extra)
        result = await self.selector.select(ctx, recipe_pool=recipe_pool)
        filtered: list[RecipeCandidate] = []
        for cand in result.candidates:
            if self._passes_quality(cand.recipe.id, planning.minimum_quality_status):
                filtered.append(cand)
        # Deterministic order: score desc, recipe_id asc
        filtered.sort(key=lambda c: (-c.score, c.recipe.id))
        return SlotCandidatePool(
            slot_id=slot.slot_id,
            candidates=filtered,
            selection_result=result,
            filter_stats=dict(result.filter_stats.removed),
        )


def primary_protein(recipe: Recipe) -> str | None:
    for tag in recipe.tags:
        if tag.tag_type == TagType.PROTEIN_SOURCE:
            return tag.tag_value
    return None


def recipe_ingredient_ids(recipe: Recipe) -> set[str]:
    return {
        ri.ingredient_id
        for ri in recipe.ingredients
        if not ri.is_optional and ri.ingredient_id
    }
