"""Deterministic pattern evidence derivation (no ML / Claude / network)."""

from __future__ import annotations

from recipes.enums import (
    BudgetClass,
    Difficulty,
    EnergyDensity,
    GoalType,
    RecipeRole,
    ScalingMode,
    TagType,
    TasteTag,
    UsageTag,
)
from recipes.models import Recipe
from recipes.quality.config import DEFAULT_QUALITY_THRESHOLDS, QualityThresholds
from recipes.quality.enums import EvidenceType, PatternType
from recipes.quality.models import (
    PatternDerivationResult,
    PatternEvidenceItem,
    QualityIssue,
)


class RecipePatternDeriver:
    def __init__(self, thresholds: QualityThresholds | None = None) -> None:
        self.t = thresholds or DEFAULT_QUALITY_THRESHOLDS

    def derive(self, recipe: Recipe) -> PatternDerivationResult:
        result = PatternDerivationResult(recipe_id=recipe.id)
        result.evidence.append(self._quick(recipe, result))
        result.evidence.append(self._batch(recipe, result))
        result.evidence.append(self._leftover(recipe, result))
        result.evidence.append(self._high_protein(recipe, result))
        result.evidence.append(self._high_fiber(recipe, result))
        result.evidence.append(self._energy_density(recipe, result))
        result.evidence.append(self._budget(recipe, result))
        result.evidence.append(self._weight_loss(recipe, result))
        result.evidence.append(self._muscle_gain(recipe, result))
        result.evidence.append(self._family(recipe, result))
        result.evidence.append(self._portable(recipe, result))
        result.evidence.append(self._freezer(recipe, result))
        return result

    def _has_usage(self, recipe: Recipe, value: str) -> bool:
        return any(
            t.tag_type == TagType.USAGE and t.tag_value == value for t in recipe.tags
        )

    def _has_role(self, recipe: Recipe, role: RecipeRole) -> bool:
        return any(r.role == role for r in recipe.roles)

    def _goal_score(self, recipe: Recipe, goal: GoalType) -> float | None:
        for g in recipe.goal_scores:
            if g.goal == goal:
                return g.score
        return None

    def _quick(self, recipe: Recipe, result: PatternDerivationResult) -> PatternEvidenceItem:
        total = recipe.total_time_minutes
        active = recipe.active_time_minutes
        is_quick = total <= self.t.quick_total_minutes
        evidence = PatternEvidenceItem(
            pattern_type=PatternType.QUICK_MEAL,
            evidence_type=EvidenceType.DERIVED,
            value_bool=is_quick,
            rule_code="TOTAL_TIME_LE_30",
            evidence_json={
                "total_time_minutes": total,
                "active_time_minutes": active,
                "threshold_minutes": self.t.quick_total_minutes,
                "active_threshold_minutes": self.t.quick_active_minutes,
                "very_quick": active <= self.t.quick_active_minutes and is_quick,
                "check_kind": "structural",
            },
        )
        has_quick_tag = self._has_usage(recipe, UsageTag.QUICK.value)
        if has_quick_tag and not is_quick:
            result.warnings.append(
                QualityIssue(
                    code="TAG_QUICK_NOT_SUPPORTED",
                    message="usage=quick tag present but total_time > 30",
                    severity="warning",
                )
            )
        if is_quick and not has_quick_tag:
            result.warnings.append(
                QualityIssue(
                    code="DERIVED_QUICK_TAG_MISSING",
                    message="total_time <= 30 but usage=quick tag missing",
                    severity="warning",
                )
            )
        return evidence

    def _batch(self, recipe: Recipe, result: PatternDerivationResult) -> PatternEvidenceItem:
        scalable = recipe.scaling_mode in {
            ScalingMode.LINEAR,
            ScalingMode.DISCRETE,
            ScalingMode.LIMITED,
        }
        storage_ok = (
            recipe.storage_days is not None
            and recipe.storage_days >= self.t.batch_min_storage_days
        )
        servings_ok = float(recipe.max_batch_servings) >= self.t.batch_min_servings
        structural_ok = servings_ok and scalable and storage_ok
        evidence = PatternEvidenceItem(
            pattern_type=PatternType.BATCH_FRIENDLY,
            evidence_type=EvidenceType.DERIVED,
            value_bool=structural_ok,
            rule_code="BATCH_STORAGE_SCALING_V1",
            evidence_json={
                "max_batch_servings": float(recipe.max_batch_servings),
                "storage_days": recipe.storage_days,
                "scaling_mode": recipe.scaling_mode.value,
                "declared_batch_friendly": recipe.batch_friendly,
                "check_kind": "structural_not_culinary_safety",
            },
        )
        if recipe.batch_friendly and not structural_ok:
            result.warnings.append(
                QualityIssue(
                    code="BATCH_FLAG_NOT_SUPPORTED",
                    message="batch_friendly=true but structural conditions unmet",
                    severity="warning",
                )
            )
        if structural_ok and not recipe.batch_friendly:
            result.warnings.append(
                QualityIssue(
                    code="BATCH_FLAG_MISSING",
                    message="Structural batch conditions met but flag=false",
                    severity="warning",
                )
            )
        return evidence

    def _leftover(
        self, recipe: Recipe, result: PatternDerivationResult
    ) -> PatternEvidenceItem:
        storage = recipe.storage_days
        if recipe.leftover_friendly and storage is None:
            result.inconsistencies.append(
                QualityIssue(
                    code="LEFTOVER_WITHOUT_STORAGE",
                    message="leftover_friendly=true but storage_days is null",
                    severity="error",
                )
            )
        storable = storage is not None and storage >= self.t.leftover_min_storage_days
        structural = recipe.leftover_friendly and storable
        score = self.t.leftover_max_derived_score if structural else 0.0
        return PatternEvidenceItem(
            pattern_type=PatternType.LEFTOVER_FRIENDLY,
            evidence_type=EvidenceType.DERIVED,
            value_bool=structural if recipe.leftover_friendly else False,
            score=score if structural else None,
            rule_code="LEFTOVER_STORAGE_V1",
            evidence_json={
                "storage_days": storage,
                "leftover_friendly": recipe.leftover_friendly,
                "requires_cooking": recipe.requires_cooking,
                "max_derived_score": self.t.leftover_max_derived_score,
                "note": "Reheating suitability not automatically confirmed",
            },
        )

    def _high_protein(
        self, recipe: Recipe, result: PatternDerivationResult
    ) -> PatternEvidenceItem:
        p100 = recipe.protein_g_per_100g
        base_portion = float(recipe.yield_weight_g) / float(recipe.base_servings)
        portion_min = float(recipe.recommended_portion_min_g)
        portion_max = float(recipe.recommended_portion_max_g)
        prot_min = p100 * portion_min / 100.0
        prot_max = p100 * portion_max / 100.0
        prot_typical = p100 * base_portion / 100.0
        cal = recipe.calories_per_100g
        protein_cal_share = (p100 * 4 / cal) if cal > 0 else 0.0
        strong = (
            p100 >= self.t.high_protein_g_per_100g
            or prot_typical >= self.t.high_protein_g_per_portion
            or protein_cal_share >= self.t.high_protein_calorie_share
        )
        evidence = PatternEvidenceItem(
            pattern_type=PatternType.HIGH_PROTEIN,
            evidence_type=EvidenceType.DERIVED,
            value_bool=strong,
            rule_code="HIGH_PROTEIN_V1",
            evidence_json={
                "protein_g_per_100g": p100,
                "protein_g_per_portion_min": round(prot_min, 2),
                "protein_g_per_portion_max": round(prot_max, 2),
                "protein_g_per_typical_portion": round(prot_typical, 2),
                "calories_from_protein_ratio": round(protein_cal_share, 4),
                "thresholds": {
                    "g_per_100g": self.t.high_protein_g_per_100g,
                    "g_per_portion": self.t.high_protein_g_per_portion,
                    "calorie_share": self.t.high_protein_calorie_share,
                },
                "note": "Not a medical claim",
            },
        )
        if recipe.protein_level.value == "high" and not strong:
            result.warnings.append(
                QualityIssue(
                    code="PROTEIN_LEVEL_WEAKLY_SUPPORTED",
                    message="protein_level=high but HIGH_PROTEIN_V1 not met",
                    severity="warning",
                )
            )
        return evidence

    def _high_fiber(
        self, recipe: Recipe, result: PatternDerivationResult
    ) -> PatternEvidenceItem:
        result.warnings.append(
            QualityIssue(
                code="FIBER_DATA_UNAVAILABLE",
                message="No fiber_g_per_100g on recipe or ingredient nutrition",
                severity="warning",
            )
        )
        return PatternEvidenceItem(
            pattern_type=PatternType.HIGH_FIBER,
            evidence_type=EvidenceType.INSUFFICIENT_DATA,
            value_bool=None,
            score=None,
            rule_code="HIGH_FIBER_REQUIRES_FIBER_DATA",
            evidence_json={
                "status": "insufficient_data",
                "declared_fiber_level": recipe.fiber_level.value,
                "note": "Do not infer fiber from vegetables/legumes alone",
            },
        )

    def _energy_density(
        self, recipe: Recipe, result: PatternDerivationResult
    ) -> PatternEvidenceItem:
        kcal = recipe.calories_per_100g
        if kcal <= self.t.low_energy_density_kcal:
            derived = EnergyDensity.LOW
        elif kcal <= self.t.medium_energy_density_kcal:
            derived = EnergyDensity.MEDIUM
        else:
            derived = EnergyDensity.HIGH
        if derived != recipe.energy_density:
            result.warnings.append(
                QualityIssue(
                    code="ENERGY_DENSITY_MISMATCH",
                    message=(
                        f"Declared energy_density={recipe.energy_density.value} "
                        f"but derived={derived.value} from {kcal} kcal/100g"
                    ),
                    severity="warning",
                )
            )
        return PatternEvidenceItem(
            pattern_type=PatternType.LOW_ENERGY_DENSITY,
            evidence_type=EvidenceType.DERIVED,
            value_bool=derived == EnergyDensity.LOW,
            rule_code="ENERGY_DENSITY_KCAL_V1",
            evidence_json={
                "calories_per_100g": kcal,
                "derived_band": derived.value,
                "declared": recipe.energy_density.value,
                "thresholds": {
                    "low": self.t.low_energy_density_kcal,
                    "medium": self.t.medium_energy_density_kcal,
                },
            },
        )

    def _budget(
        self, recipe: Recipe, result: PatternDerivationResult
    ) -> PatternEvidenceItem:
        result.warnings.append(
            QualityIssue(
                code="BUDGET_NOT_PRICE_VERIFIED",
                message="budget_class is declared metadata, not a verified price",
                severity="warning",
            )
        )
        friendly = recipe.budget_class in {BudgetClass.VERY_BUDGET, BudgetClass.BUDGET}
        return PatternEvidenceItem(
            pattern_type=PatternType.BUDGET_FRIENDLY,
            evidence_type=EvidenceType.DECLARED,
            value_bool=friendly,
            rule_code="BUDGET_CLASS_DECLARED",
            evidence_json={
                "budget_class": recipe.budget_class.value,
                "note": "No market prices available",
            },
        )

    def _weight_loss(
        self, recipe: Recipe, result: PatternDerivationResult
    ) -> PatternEvidenceItem:
        kcal = recipe.calories_per_100g
        ed_score = 1.0 if kcal <= 150 else (0.6 if kcal <= 250 else 0.2)
        protein_score = min(1.0, recipe.protein_g_per_100g / 12.0)
        satiety_map = {"low": 0.3, "medium": 0.6, "high": 1.0}
        satiety = satiety_map.get(recipe.satiety_level.value, 0.5)
        portion = float(recipe.yield_weight_g) / float(recipe.base_servings)
        portion_kcal = kcal * portion / 100.0
        portion_score = 1.0 if portion_kcal <= 450 else (0.5 if portion_kcal <= 650 else 0.2)
        # Fiber unavailable → incomplete
        structural = round(
            0.35 * ed_score + 0.25 * protein_score + 0.25 * satiety + 0.15 * portion_score,
            3,
        )
        goal = self._goal_score(recipe, GoalType.WEIGHT_LOSS)
        if goal is None:
            result.warnings.append(
                QualityIssue(
                    code="WEIGHT_LOSS_EVIDENCE_INCOMPLETE",
                    message="No weight_loss goal score to compare",
                    severity="info",
                )
            )
        elif goal - structural >= self.t.weight_loss_goal_gap_warning:
            result.warnings.append(
                QualityIssue(
                    code="WEIGHT_LOSS_SCORE_WEAKLY_SUPPORTED",
                    message=(
                        f"weight_loss goal score {goal:.2f} much higher than "
                        f"structural score {structural:.2f}"
                    ),
                    severity="warning",
                    details={"goal": goal, "structural": structural},
                )
            )
        result.warnings.append(
            QualityIssue(
                code="WEIGHT_LOSS_EVIDENCE_INCOMPLETE",
                message="Fiber and oil contribution not fully available",
                severity="info",
            )
        )
        return PatternEvidenceItem(
            pattern_type=PatternType.WEIGHT_LOSS_COMPATIBLE,
            evidence_type=EvidenceType.DERIVED,
            value_bool=structural >= 0.55,
            score=structural,
            rule_code="STRUCTURAL_WEIGHT_LOSS_COMPATIBILITY_V1",
            evidence_json={
                "structural_weight_loss_compatibility": structural,
                "energy_density_component": ed_score,
                "protein_component": round(protein_score, 3),
                "satiety_component": satiety,
                "portion_kcal": round(portion_kcal, 1),
                "declared_goal_score": goal,
                "note": "Not a medical recommendation",
            },
        )

    def _muscle_gain(
        self, recipe: Recipe, result: PatternDerivationResult
    ) -> PatternEvidenceItem:
        base_portion = float(recipe.yield_weight_g) / float(recipe.base_servings)
        prot = recipe.protein_g_per_100g * base_portion / 100.0
        protein_score = min(1.0, prot / 30.0)
        scale_score = min(1.0, float(recipe.max_batch_servings) / 6.0)
        energy = min(1.0, recipe.calories_per_100g / 200.0)
        structural = round(0.5 * protein_score + 0.25 * scale_score + 0.25 * energy, 3)
        goal = self._goal_score(recipe, GoalType.MUSCLE_GAIN)
        if goal is not None and goal - structural >= self.t.muscle_gain_goal_gap_warning:
            result.warnings.append(
                QualityIssue(
                    code="MUSCLE_GAIN_SCORE_WEAKLY_SUPPORTED",
                    message=(
                        f"muscle_gain goal score {goal:.2f} much higher than "
                        f"structural score {structural:.2f}"
                    ),
                    severity="warning",
                )
            )
        return PatternEvidenceItem(
            pattern_type=PatternType.MUSCLE_GAIN_COMPATIBLE,
            evidence_type=EvidenceType.DERIVED,
            value_bool=structural >= 0.55,
            score=structural,
            rule_code="STRUCTURAL_MUSCLE_GAIN_COMPATIBILITY_V1",
            evidence_json={
                "structural_muscle_gain_compatibility": structural,
                "protein_g_per_typical_portion": round(prot, 2),
                "max_batch_servings": float(recipe.max_batch_servings),
                "calories_per_100g": recipe.calories_per_100g,
                "declared_goal_score": goal,
            },
        )

    def _family(
        self, recipe: Recipe, result: PatternDerivationResult
    ) -> PatternEvidenceItem:
        has_family_tag = self._has_usage(recipe, UsageTag.FAMILY.value)
        has_family_role = self._has_role(recipe, RecipeRole.FAMILY_MEAL)
        taste_ok = not any(
            t.tag_type == TagType.TASTE and t.tag_value == TasteTag.SPICY.value
            for t in recipe.tags
        )
        difficulty_ok = recipe.difficulty in {Difficulty.EASY, Difficulty.MEDIUM}
        scalable = float(recipe.max_batch_servings) >= 4
        declared = has_family_tag or has_family_role
        signals = sum([declared, taste_ok, difficulty_ok, scalable])
        score = min(
            self.t.family_max_confidence_without_human,
            0.15 * signals,
        )
        if declared:
            score = min(self.t.family_max_confidence_without_human, 0.4 + 0.1 * signals)
        return PatternEvidenceItem(
            pattern_type=PatternType.FAMILY_FRIENDLY,
            evidence_type=EvidenceType.DECLARED if declared else EvidenceType.DERIVED,
            value_bool=declared and taste_ok and difficulty_ok,
            score=round(score, 3),
            rule_code="FAMILY_DECLARED_CAPPED_V1",
            evidence_json={
                "family_tag": has_family_tag,
                "family_role": has_family_role,
                "taste_ok": taste_ok,
                "difficulty": recipe.difficulty.value,
                "scalable": scalable,
                "confidence_cap": self.t.family_max_confidence_without_human,
                "note": "Full family suitability needs human review",
            },
        )

    def _portable(
        self, recipe: Recipe, result: PatternDerivationResult
    ) -> PatternEvidenceItem:
        has_role = self._has_role(recipe, RecipeRole.PORTABLE_MEAL)
        liquid = any(
            t.tag_type == TagType.TEXTURE and t.tag_value == "liquid" for t in recipe.tags
        )
        oven_hot = any(m.value in {"baking", "roasting"} for m in recipe.cooking_methods)
        storage_ok = recipe.storage_days is not None and recipe.storage_days >= 1
        if not has_role and liquid is False and not oven_hot:
            result.warnings.append(
                QualityIssue(
                    code="PORTABLE_REQUIRES_MANUAL_REVIEW",
                    message="Insufficient form/texture data for portable_meal",
                    severity="info",
                )
            )
        ok = has_role and not liquid and storage_ok
        return PatternEvidenceItem(
            pattern_type=PatternType.PORTABLE_MEAL,
            evidence_type=EvidenceType.DECLARED if has_role else EvidenceType.DERIVED,
            value_bool=ok if has_role else None,
            score=0.5 if ok else None,
            rule_code="PORTABLE_ROLE_STRUCTURAL_V1",
            evidence_json={
                "portable_role": has_role,
                "liquid_texture": liquid,
                "oven_service_likely": oven_hot,
                "storage_days": recipe.storage_days,
                "note": "manual review required when form data insufficient",
            },
        )

    def _freezer(
        self, recipe: Recipe, result: PatternDerivationResult
    ) -> PatternEvidenceItem:
        return PatternEvidenceItem(
            pattern_type=PatternType.FREEZER_FRIENDLY,
            evidence_type=EvidenceType.DECLARED,
            value_bool=recipe.freezing_supported,
            score=0.4 if recipe.freezing_supported else 0.0,
            rule_code="FREEZER_DECLARED_ONLY",
            evidence_json={
                "freezing_supported": recipe.freezing_supported,
                "usage_tag": self._has_usage(recipe, UsageTag.FREEZER_FRIENDLY.value),
                "note": "Requires human/source/kitchen confirmation for high confidence",
            },
        )
