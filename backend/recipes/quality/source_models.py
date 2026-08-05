"""Source workflow models: observations, comparison, drafts (Sprint 10.8)."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from recipes.quality.enums import SourceType


@dataclass
class RecipeConcept:
    """Intent before sources are attached — not a catalog Recipe."""

    concept_id: str
    title: str
    target_meal_types: list[str]
    target_gaps: list[str] = field(default_factory=list)
    primary_protein: str | None = None
    max_total_time_minutes: int | None = None
    budget_class: str | None = None
    notes: str | None = None
    status: str = "research"  # research | pending_source_research | ready | rejected_duplicate

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class IngredientObservation:
    name: str
    quantity: float | None = None
    unit: str | None = None
    quantity_grams: float | None = None
    notes: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class RecipeSourceObservation:
    """Structured facts observed from one real source (manual or assisted)."""

    source_id: str
    source_type: SourceType
    source_title: str
    source_reference: str
    publisher_or_author: str | None = None
    accessed_at: str | None = None
    ingredients: list[IngredientObservation] = field(default_factory=list)
    cooking_method: str | None = None
    prep_time_minutes: int | None = None
    cook_time_minutes: int | None = None
    total_time_minutes: int | None = None
    temperature_c: int | None = None
    yield_servings: float | None = None
    yield_weight_g: float | None = None
    storage_days: int | None = None
    notes: str | None = None
    supports_ingredients: bool = True
    supports_proportions: bool = False
    supports_method: bool = False
    supports_time: bool = False
    supports_yield: bool = False
    supports_storage: bool = False

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["source_type"] = self.source_type.value
        data["ingredients"] = [i.to_dict() for i in self.ingredients]
        return data


@dataclass
class RecipeSourceComparisonResult:
    agreement_fields: list[str] = field(default_factory=list)
    disagreement_fields: list[str] = field(default_factory=list)
    ingredient_consensus: list[str] = field(default_factory=list)
    proportion_ranges: dict[str, dict[str, float | None]] = field(default_factory=dict)
    time_range: dict[str, int | None] = field(default_factory=dict)
    yield_range: dict[str, float | None] = field(default_factory=dict)
    cooking_method_consensus: str | None = None
    unresolved_questions: list[str] = field(default_factory=list)
    confidence: float = 0.0
    recommended_normalization: dict[str, Any] = field(default_factory=dict)
    critical_contradiction: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class NormalizedIngredient:
    ingredient_id: str | None
    name: str
    quantity: float | None = None
    unit: str | None = None
    quantity_grams: float | None = None
    notes: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class SourceBackedRecipeDraft:
    """Normalized draft — not yet a catalog Recipe."""

    concept: RecipeConcept
    source_ids: list[str]
    observations: list[RecipeSourceObservation] = field(default_factory=list)
    comparison: RecipeSourceComparisonResult | None = None
    normalized_ingredients: list[NormalizedIngredient] = field(default_factory=list)
    normalized_method: str | None = None
    normalized_prep_time_minutes: int | None = None
    normalized_cook_time_minutes: int | None = None
    normalized_total_time_minutes: int | None = None
    normalized_yield_servings: float | None = None
    normalized_yield_weight_g: float | None = None
    normalization_notes: list[str] = field(default_factory=list)
    unresolved_questions: list[str] = field(default_factory=list)
    confidence: float = 0.0
    ready_for_catalog_import: bool = False
    blocking_reasons: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "concept": self.concept.to_dict(),
            "source_ids": list(self.source_ids),
            "observations": [o.to_dict() for o in self.observations],
            "comparison": self.comparison.to_dict() if self.comparison else None,
            "normalized_ingredients": [i.to_dict() for i in self.normalized_ingredients],
            "normalized_method": self.normalized_method,
            "normalized_prep_time_minutes": self.normalized_prep_time_minutes,
            "normalized_cook_time_minutes": self.normalized_cook_time_minutes,
            "normalized_total_time_minutes": self.normalized_total_time_minutes,
            "normalized_yield_servings": self.normalized_yield_servings,
            "normalized_yield_weight_g": self.normalized_yield_weight_g,
            "normalization_notes": list(self.normalization_notes),
            "unresolved_questions": list(self.unresolved_questions),
            "confidence": self.confidence,
            "ready_for_catalog_import": self.ready_for_catalog_import,
            "blocking_reasons": list(self.blocking_reasons),
        }
