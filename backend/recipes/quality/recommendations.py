"""Metadata consistency recommendations (never auto-applied)."""

from __future__ import annotations

from recipes.enums import GoalType, RecipeRole, TagType, UsageTag
from recipes.models import Recipe
from recipes.quality.enums import MetadataRecommendationType, PatternType
from recipes.quality.models import (
    MetadataRecommendation,
    PatternDerivationResult,
    QualityIssue,
)


def build_recommendations(
    recipe: Recipe,
    patterns: PatternDerivationResult,
    issues: list[QualityIssue],
    *,
    source_count: int = 0,
) -> list[MetadataRecommendation]:
    recs: list[MetadataRecommendation] = []
    evidence_by = {e.pattern_type: e for e in patterns.evidence}

    quick = evidence_by.get(PatternType.QUICK_MEAL)
    has_quick_tag = any(
        t.tag_type == TagType.USAGE and t.tag_value == UsageTag.QUICK.value
        for t in recipe.tags
    )
    if quick and quick.value_bool is False and has_quick_tag:
        recs.append(
            MetadataRecommendation(
                recipe_id=recipe.id,
                recommendation_type=MetadataRecommendationType.REMOVE_UNSUPPORTED_TAG,
                field="tags.usage.quick",
                current_value="quick",
                derived_value=None,
                evidence=quick.evidence_json,
                severity="warning",
                reason_code="TAG_QUICK_NOT_SUPPORTED",
                message="Remove or review quick usage tag",
            )
        )
    if quick and quick.value_bool is True and not has_quick_tag:
        recs.append(
            MetadataRecommendation(
                recipe_id=recipe.id,
                recommendation_type=MetadataRecommendationType.ADD_DERIVED_TAG,
                field="tags.usage.quick",
                current_value=None,
                derived_value="quick",
                evidence=quick.evidence_json,
                severity="info",
                reason_code="DERIVED_QUICK_TAG_MISSING",
                message="Consider adding usage=quick",
            )
        )

    batch = evidence_by.get(PatternType.BATCH_FRIENDLY)
    if batch and recipe.batch_friendly and batch.value_bool is False:
        recs.append(
            MetadataRecommendation(
                recipe_id=recipe.id,
                recommendation_type=MetadataRecommendationType.REVIEW_ROLE,
                field="batch_friendly",
                current_value=True,
                derived_value=False,
                evidence=batch.evidence_json,
                severity="warning",
                reason_code="BATCH_FLAG_NOT_SUPPORTED",
            )
        )

    for issue in issues:
        if issue.code == "ENERGY_DENSITY_MISMATCH":
            ed = evidence_by.get(PatternType.LOW_ENERGY_DENSITY)
            recs.append(
                MetadataRecommendation(
                    recipe_id=recipe.id,
                    recommendation_type=MetadataRecommendationType.REVIEW_NUTRITION,
                    field="energy_density",
                    current_value=recipe.energy_density.value,
                    derived_value=(ed.evidence_json.get("derived_band") if ed else None),
                    evidence=issue.details,
                    severity="warning",
                    reason_code=issue.code,
                )
            )
        if issue.code in {
            "WEIGHT_LOSS_SCORE_WEAKLY_SUPPORTED",
            "MUSCLE_GAIN_SCORE_WEAKLY_SUPPORTED",
        }:
            goal = (
                GoalType.WEIGHT_LOSS
                if "WEIGHT_LOSS" in issue.code
                else GoalType.MUSCLE_GAIN
            )
            current = next((g.score for g in recipe.goal_scores if g.goal == goal), None)
            recs.append(
                MetadataRecommendation(
                    recipe_id=recipe.id,
                    recommendation_type=MetadataRecommendationType.REVIEW_GOAL_SCORE,
                    field=f"goal_scores.{goal.value}",
                    current_value=current,
                    derived_value=issue.details.get("structural"),
                    evidence=issue.details,
                    severity="warning",
                    reason_code=issue.code,
                )
            )
        if issue.code.startswith("NUTRITION_"):
            recs.append(
                MetadataRecommendation(
                    recipe_id=recipe.id,
                    recommendation_type=MetadataRecommendationType.REVIEW_NUTRITION,
                    field="nutrition_snapshot",
                    current_value=None,
                    derived_value=None,
                    evidence=issue.details,
                    severity=issue.severity if issue.severity != "info" else "warning",
                    reason_code=issue.code,
                    message=issue.message,
                )
            )
        if issue.code.startswith("YIELD_") or issue.code == "BASE_PORTION_OUTSIDE_RECOMMENDED_RANGE":
            recs.append(
                MetadataRecommendation(
                    recipe_id=recipe.id,
                    recommendation_type=MetadataRecommendationType.REVIEW_YIELD,
                    field="yield_weight_g",
                    current_value=float(recipe.yield_weight_g),
                    derived_value=None,
                    evidence=issue.details,
                    severity="warning",
                    reason_code=issue.code,
                    message=issue.message,
                )
            )
        if issue.code in {
            "STEP_DURATION_EXCEEDS_TOTAL",
            "COOKING_METHOD_TIME_SUSPICIOUS",
            "ACTIVE_TIME_INCONSISTENT",
        }:
            recs.append(
                MetadataRecommendation(
                    recipe_id=recipe.id,
                    recommendation_type=MetadataRecommendationType.REVIEW_TIME,
                    field="total_time_minutes",
                    current_value=recipe.total_time_minutes,
                    derived_value=None,
                    evidence=issue.details,
                    severity="warning" if issue.severity != "error" else "error",
                    reason_code=issue.code,
                    message=issue.message,
                )
            )

    if source_count == 0:
        recs.append(
            MetadataRecommendation(
                recipe_id=recipe.id,
                recommendation_type=MetadataRecommendationType.SOURCE_VERIFICATION_REQUIRED,
                field="recipe_sources",
                current_value=0,
                derived_value=None,
                evidence={},
                severity="warning",
                reason_code="SOURCE_VERIFICATION_REQUIRED",
                message="No real culinary sources recorded",
            )
        )
    recs.append(
        MetadataRecommendation(
            recipe_id=recipe.id,
            recommendation_type=MetadataRecommendationType.HUMAN_REVIEW_REQUIRED,
            field="quality_status",
            current_value=None,
            derived_value=None,
            evidence={},
            severity="info",
            reason_code="HUMAN_REVIEW_REQUIRED",
            message="Catalog recipe still needs human culinary review before approval",
        )
    )
    # Kitchen test for batch / leftover / freezer claims
    if recipe.batch_friendly or recipe.leftover_friendly or recipe.freezing_supported:
        recs.append(
            MetadataRecommendation(
                recipe_id=recipe.id,
                recommendation_type=MetadataRecommendationType.KITCHEN_TEST_RECOMMENDED,
                field="storage_claims",
                current_value={
                    "batch_friendly": recipe.batch_friendly,
                    "leftover_friendly": recipe.leftover_friendly,
                    "freezing_supported": recipe.freezing_supported,
                },
                derived_value=None,
                evidence={},
                severity="info",
                reason_code="KITCHEN_TEST_RECOMMENDED",
                message="Storage/batch claims should be kitchen-tested",
            )
        )

    # Family role without strong evidence
    if any(r.role == RecipeRole.FAMILY_MEAL for r in recipe.roles):
        fam = evidence_by.get(PatternType.FAMILY_FRIENDLY)
        if fam and (fam.score or 0) < 0.7:
            recs.append(
                MetadataRecommendation(
                    recipe_id=recipe.id,
                    recommendation_type=MetadataRecommendationType.REVIEW_ROLE,
                    field="roles.family_meal",
                    current_value=True,
                    derived_value=fam.score,
                    evidence=fam.evidence_json,
                    severity="info",
                    reason_code="FAMILY_CONFIDENCE_CAPPED",
                )
            )

    # De-duplicate by reason_code+field
    seen: set[tuple[str, str]] = set()
    unique: list[MetadataRecommendation] = []
    for r in recs:
        key = (r.reason_code, r.field)
        if key in seen:
            continue
        seen.add(key)
        unique.append(r)
    return unique
