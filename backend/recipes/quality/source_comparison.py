"""Deterministic multi-source comparison (Sprint 10.8)."""

from __future__ import annotations

import re
from collections import Counter

from recipes.quality.source_models import (
    RecipeConcept,
    RecipeSourceComparisonResult,
    RecipeSourceObservation,
)

_LLM_MARKERS = (
    "llm",
    "chatgpt",
    "gpt-",
    "claude",
    "agent-generated",
    "ai generated",
    "language model",
)

_PLACEHOLDER_REFS = {
    "",
    "n/a",
    "na",
    "none",
    "example.com",
    "http://example.com",
    "https://example.com",
}


def normalize_ingredient_name(name: str) -> str:
    cleaned = name.strip().lower()
    cleaned = re.sub(r"[^a-z0-9а-яё\s_+-]", "", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned)
    aliases = {
        "oats": "oats",
        "porridge oats": "oats",
        "oatmeal": "oats",
        "chickpeas": "chickpeas",
        "canned chickpeas": "chickpeas",
        "chickpea": "chickpeas",
        "turkey mince": "turkey",
        "turkey fillet": "turkey",
        "ground turkey": "turkey",
        "chicken breast": "chicken",
        "ground beef": "beef_mince",
        "beef mince": "beef_mince",
        "eggs": "egg",
        "egg": "egg",
        "tuna": "tuna",
        "canned tuna": "tuna",
        "beans": "beans",
        "canned beans": "beans",
        "red lentils": "lentils",
        "lentils": "lentils",
        "tomato": "tomato",
        "tomatoes": "tomato",
        "onion": "onion",
        "garlic": "garlic",
        "oil": "oil",
        "olive oil": "oil",
        "spinach": "spinach",
        "cabbage": "cabbage",
        "bell pepper": "bell_pepper",
        "pepper": "bell_pepper",
        "zucchini": "zucchini",
        "courgette": "zucchini",
        "milk": "milk",
        "salt": "salt",
        "water": "water",
        "rice": "rice",
        "buckwheat": "buckwheat",
        "banana": "banana",
        "cheese": "cheese",
        "yogurt": "yogurt",
    }
    return aliases.get(cleaned, cleaned.replace(" ", "_"))


def is_forbidden_source_reference(reference: str, title: str = "") -> list[str]:
    errors: list[str] = []
    ref = (reference or "").strip()
    lowered = ref.lower()
    if not ref or lowered in _PLACEHOLDER_REFS:
        errors.append("empty_or_placeholder_reference")
    blob = f"{ref} {title}".lower()
    if any(marker in blob for marker in _LLM_MARKERS):
        errors.append("llm_cannot_be_source")
    return errors


def validate_observation(obs: RecipeSourceObservation) -> list[str]:
    errors = is_forbidden_source_reference(obs.source_reference, obs.source_title)
    if not (obs.source_title or "").strip():
        errors.append("empty_source_title")
    if not (obs.source_id or "").strip():
        errors.append("empty_source_id")
    return errors


class RecipeSourceComparison:
    """Rule-based comparison of 2..N source observations."""

    MIN_SOURCES = 2
    TIME_DISAGREE_RATIO = 0.4
    YIELD_DISAGREE_RATIO = 0.5

    def compare(
        self,
        concept: RecipeConcept,
        observations: list[RecipeSourceObservation],
    ) -> RecipeSourceComparisonResult:
        errors: list[str] = []
        for obs in observations:
            errors.extend(validate_observation(obs))

        if len(observations) < self.MIN_SOURCES:
            errors.append(f"need_at_least_{self.MIN_SOURCES}_sources")

        refs = [o.source_reference.strip().lower() for o in observations]
        if len(refs) != len(set(refs)):
            errors.append("duplicate_source_reference")

        result = RecipeSourceComparisonResult(unresolved_questions=list(errors))

        if len(observations) < 1:
            result.confidence = 0.0
            result.critical_contradiction = True
            return result

        # Ingredient consensus: names seen in >= half of sources (min 2 sources → both)
        name_sets = []
        for obs in observations:
            names = {normalize_ingredient_name(i.name) for i in obs.ingredients if i.name}
            name_sets.append(names)
        if name_sets:
            threshold = max(1, (len(name_sets) + 1) // 2)
            counts: Counter[str] = Counter()
            for s in name_sets:
                counts.update(s)
            result.ingredient_consensus = sorted(
                name for name, c in counts.items() if c >= threshold
            )

            # Proportions for consensus ingredients when quantities present
            for name in result.ingredient_consensus:
                grams: list[float] = []
                for obs in observations:
                    for ing in obs.ingredients:
                        if normalize_ingredient_name(ing.name) != name:
                            continue
                        if ing.quantity_grams is not None:
                            grams.append(float(ing.quantity_grams))
                        elif ing.quantity is not None and (ing.unit or "").lower() in {
                            "g",
                            "gram",
                            "grams",
                        }:
                            grams.append(float(ing.quantity))
                if grams:
                    result.proportion_ranges[name] = {
                        "min": min(grams),
                        "max": max(grams),
                        "mid": sum(grams) / len(grams),
                    }

        # Methods
        methods = [
            (o.cooking_method or "").strip().lower()
            for o in observations
            if (o.cooking_method or "").strip()
        ]
        if methods:
            method_counts = Counter(methods)
            top_method, top_count = method_counts.most_common(1)[0]
            result.cooking_method_consensus = top_method
            if len(method_counts) > 1 and top_count < len(methods):
                # Soft disagreement unless methods are clearly incompatible
                incompatible = self._methods_incompatible(list(method_counts))
                if incompatible:
                    result.disagreement_fields.append("cooking_method")
                    result.critical_contradiction = True
                else:
                    result.disagreement_fields.append("cooking_method_variant")
            else:
                result.agreement_fields.append("cooking_method")

        # Times
        totals = [o.total_time_minutes for o in observations if o.total_time_minutes is not None]
        cooks = [o.cook_time_minutes for o in observations if o.cook_time_minutes is not None]
        preps = [o.prep_time_minutes for o in observations if o.prep_time_minutes is not None]
        time_values = totals or cooks
        if time_values:
            t_min, t_max = min(time_values), max(time_values)
            result.time_range = {
                "min_total": min(totals) if totals else None,
                "max_total": max(totals) if totals else None,
                "min_cook": min(cooks) if cooks else None,
                "max_cook": max(cooks) if cooks else None,
                "min_prep": min(preps) if preps else None,
                "max_prep": max(preps) if preps else None,
                "recommended_total": int(round(sum(time_values) / len(time_values))),
            }
            mid = (t_min + t_max) / 2 or 1
            if (t_max - t_min) / mid > self.TIME_DISAGREE_RATIO:
                result.disagreement_fields.append("time")
                # Large time gaps are warnings unless one source is < half the other
                if t_min > 0 and t_max / t_min >= 2.5:
                    result.critical_contradiction = True
                    result.unresolved_questions.append(
                        f"critical_time_gap:{t_min}-{t_max}"
                    )
            else:
                result.agreement_fields.append("time")
        else:
            result.unresolved_questions.append("missing_time_observations")

        # Yield
        yields = [o.yield_servings for o in observations if o.yield_servings is not None]
        if yields:
            y_min, y_max = min(yields), max(yields)
            result.yield_range = {
                "min_servings": y_min,
                "max_servings": y_max,
                "recommended_servings": sum(yields) / len(yields),
            }
            mid = (y_min + y_max) / 2 or 1
            if (y_max - y_min) / mid > self.YIELD_DISAGREE_RATIO:
                result.disagreement_fields.append("yield")
            else:
                result.agreement_fields.append("yield")

        # Ingredient support
        if result.ingredient_consensus:
            result.agreement_fields.append("ingredients")
            primary = (concept.primary_protein or "").lower()
            if primary and primary not in {
                normalize_ingredient_name(x) for x in result.ingredient_consensus
            }:
                # Map protein tags loosely
                protein_aliases = {
                    "turkey": {"turkey"},
                    "chicken": {"chicken"},
                    "beef": {"beef", "beef_mince"},
                    "fish": {"fish", "tuna", "white_fish"},
                    "eggs": {"egg"},
                    "legumes": {"lentils", "beans", "chickpeas"},
                    "dairy": {"milk", "yogurt", "cheese", "cottage_cheese"},
                }
                aliases = protein_aliases.get(primary, {primary})
                if not aliases.intersection(result.ingredient_consensus):
                    result.unresolved_questions.append(
                        f"primary_protein_not_in_consensus:{primary}"
                    )
                    result.critical_contradiction = True
        else:
            result.unresolved_questions.append("no_ingredient_consensus")
            result.critical_contradiction = True

        # Confidence
        base = 0.35
        if len(observations) >= 2:
            base += 0.25
        if "ingredients" in result.agreement_fields:
            base += 0.15
        if "cooking_method" in result.agreement_fields:
            base += 0.1
        if "time" in result.agreement_fields:
            base += 0.1
        if result.critical_contradiction:
            base -= 0.35
        if errors:
            base -= 0.2
        result.confidence = max(0.0, min(1.0, base))

        recommended_total = None
        if result.time_range.get("recommended_total") is not None:
            recommended_total = result.time_range["recommended_total"]
        elif concept.max_total_time_minutes is not None:
            recommended_total = concept.max_total_time_minutes

        result.recommended_normalization = {
            "ingredients": result.ingredient_consensus,
            "cooking_method": result.cooking_method_consensus,
            "total_time_minutes": recommended_total,
            "yield_servings": result.yield_range.get("recommended_servings"),
            "proportion_ranges": result.proportion_ranges,
        }
        return result

    @staticmethod
    def _methods_incompatible(methods: list[str]) -> bool:
        families = {
            "boil": {"boil", "boiling", "simmer", "porridge"},
            "fry": {"fry", "frying", "saute", "sauté", "stir_fry", "stir-fry", "skillet"},
            "bake": {"bake", "baking", "roast", "roasting", "oven"},
            "raw": {"raw", "no_cook", "assemble", "salad"},
            "stew": {"stew", "stewing", "braise"},
        }
        found: set[str] = set()
        for method in methods:
            matched = None
            for fam, keys in families.items():
                if any(k in method for k in keys):
                    matched = fam
                    break
            found.add(matched or method)
        # raw vs cook is critical; bake vs fry often OK as variant
        if "raw" in found and len(found) > 1:
            return True
        if "bake" in found and "fry" in found and "boil" not in found:
            return False
        return False
