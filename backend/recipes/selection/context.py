"""CandidateSelectionContext — requirements for one meal slot."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator

from recipes.enums import (
    BudgetClass,
    EquipmentType,
    GoalType,
    MealType,
    ProteinSourceTag,
    RecipeRole,
)
from recipes.quality.enums import QualityStatus


class CandidateSelectionContext(BaseModel):
    """Selection requirements for a single meal slot.

    Hard constraints (filters) vs soft preferences (scoring) are documented
    per field in hard_filter / scorer modules. Only ``meal_type`` and ``limit``
    are required.

    ``minimum_quality_status`` is reserved for a future filter. When ``None``
    (default), Selector behaviour is unchanged and no quality filtering runs.
    """

    model_config = ConfigDict(extra="forbid")

    meal_type: MealType
    limit: int = Field(default=5, ge=1, le=50)

    goal: GoalType | None = None
    allowed_budget_classes: list[BudgetClass] | None = None
    max_total_time_minutes: int | None = Field(default=None, ge=1)

    preferred_ingredient_ids: set[str] = Field(default_factory=set)
    excluded_ingredient_ids: set[str] = Field(default_factory=set)
    avoid_ingredient_ids: set[str] = Field(default_factory=set)

    required_tags: set[tuple[str, str]] = Field(
        default_factory=set,
        description="Pairs of (tag_type, tag_value) that must all be present",
    )
    excluded_tags: set[tuple[str, str]] = Field(default_factory=set)
    preferred_tags: set[tuple[str, str]] = Field(default_factory=set)

    available_equipment: set[EquipmentType] | None = None
    desired_roles: list[RecipeRole] = Field(default_factory=list)
    avoid_recipe_ids: set[str] = Field(default_factory=set)

    preferred_protein_sources: set[ProteinSourceTag] = Field(default_factory=set)
    excluded_protein_sources: set[ProteinSourceTag] = Field(default_factory=set)

    allow_leftovers: bool = False
    prefer_batch_friendly: bool = False
    family_mode: bool = False

    # Future use only — Selector ignores this in Sprint 10.7.
    minimum_quality_status: QualityStatus | None = None

    @field_validator(
        "preferred_ingredient_ids",
        "excluded_ingredient_ids",
        "avoid_ingredient_ids",
        "avoid_recipe_ids",
        mode="before",
    )
    @classmethod
    def _coerce_str_set(cls, value: object) -> object:
        if value is None:
            return set()
        if isinstance(value, (list, tuple, set, frozenset)):
            return {str(item) for item in value if item is not None and str(item).strip()}
        return value

    @field_validator(
        "preferred_protein_sources",
        "excluded_protein_sources",
        mode="before",
    )
    @classmethod
    def _coerce_protein_set(cls, value: object) -> object:
        if value is None:
            return set()
        if isinstance(value, (list, tuple, set, frozenset)):
            return {ProteinSourceTag(str(item)) for item in value}
        return value

    @field_validator("available_equipment", mode="before")
    @classmethod
    def _coerce_equipment(cls, value: object) -> object:
        if value is None:
            return None
        if isinstance(value, (list, tuple, set, frozenset)):
            return {EquipmentType(str(item)) for item in value}
        return value

    @field_validator("allowed_budget_classes", mode="before")
    @classmethod
    def _coerce_budgets(cls, value: object) -> object:
        if value is None:
            return None
        if isinstance(value, (list, tuple, set, frozenset)):
            return [BudgetClass(str(item)) for item in value]
        return value

    @field_validator("desired_roles", mode="before")
    @classmethod
    def _coerce_roles(cls, value: object) -> object:
        if value is None:
            return []
        if isinstance(value, (list, tuple, set, frozenset)):
            return [RecipeRole(str(item)) for item in value]
        return value

    @field_validator("required_tags", "excluded_tags", "preferred_tags", mode="before")
    @classmethod
    def _coerce_tag_pairs(cls, value: object) -> object:
        if value is None:
            return set()
        if isinstance(value, (list, tuple, set, frozenset)):
            pairs: set[tuple[str, str]] = set()
            for item in value:
                if isinstance(item, (list, tuple)) and len(item) == 2:
                    pairs.add((str(item[0]), str(item[1])))
                elif isinstance(item, dict):
                    pairs.add((str(item["tag_type"]), str(item["tag_value"])))
            return pairs
        return value
