"""Time plausibility checks (rule-based, not kitchen-verified)."""

from __future__ import annotations

from typing import Any

from recipes.enums import CookingMethod
from recipes.models import Recipe
from recipes.quality.config import DEFAULT_QUALITY_THRESHOLDS, QualityThresholds
from recipes.quality.models import CheckSummary, QualityIssue


class RecipeTimeChecker:
    def __init__(self, thresholds: QualityThresholds | None = None) -> None:
        self.thresholds = thresholds or DEFAULT_QUALITY_THRESHOLDS

    def check(self, recipe: Recipe) -> CheckSummary:
        issues: list[QualityIssue] = []
        metrics: dict[str, Any] = {
            "prep_time_minutes": recipe.prep_time_minutes,
            "cook_time_minutes": recipe.cook_time_minutes,
            "active_time_minutes": recipe.active_time_minutes,
            "total_time_minutes": recipe.total_time_minutes,
        }

        if recipe.active_time_minutes > recipe.total_time_minutes:
            issues.append(
                QualityIssue(
                    code="ACTIVE_TIME_INCONSISTENT",
                    message="active_time_minutes exceeds total_time_minutes",
                    severity="error",
                )
            )

        step_duration_sum = sum(
            s.duration_minutes or 0 for s in recipe.steps if s.duration_minutes
        )
        step_active_sum = sum(
            s.active_minutes or 0 for s in recipe.steps if s.active_minutes
        )
        metrics["step_duration_sum"] = step_duration_sum
        metrics["step_active_sum"] = step_active_sum

        if step_duration_sum > recipe.total_time_minutes * 1.5 + 10:
            issues.append(
                QualityIssue(
                    code="STEP_DURATION_EXCEEDS_TOTAL",
                    message=(
                        f"Sum of step durations ({step_duration_sum}) greatly "
                        f"exceeds total_time ({recipe.total_time_minutes})"
                    ),
                    severity="warning",
                )
            )

        methods = set(recipe.cooking_methods)
        if CookingMethod.BAKING in methods or CookingMethod.ROASTING in methods:
            if recipe.cook_time_minutes < self.thresholds.baking_min_cook_minutes:
                issues.append(
                    QualityIssue(
                        code="COOKING_METHOD_TIME_SUSPICIOUS",
                        message="Baking/roasting with cook_time < 10 minutes",
                        severity="warning",
                        details={"cook_time_minutes": recipe.cook_time_minutes},
                    )
                )
            has_temp = any(s.temperature_c is not None for s in recipe.steps)
            if not has_temp:
                issues.append(
                    QualityIssue(
                        code="TEMPERATURE_MISSING_FOR_BAKING",
                        message="Baking/roasting steps lack temperature_c",
                        severity="warning",
                    )
                )

        if CookingMethod.SLOW_COOKING in methods:
            if recipe.total_time_minutes < self.thresholds.slow_cooking_min_total_minutes:
                issues.append(
                    QualityIssue(
                        code="COOKING_METHOD_TIME_SUSPICIOUS",
                        message="slow_cooking with total_time < 30 minutes",
                        severity="warning",
                    )
                )

        texture_liquid = any(
            t.tag_type.value == "texture" and t.tag_value == "liquid"
            for t in recipe.tags
        )
        is_soupish = texture_liquid or "soup" in recipe.slug or "soup" in recipe.id
        if is_soupish and recipe.total_time_minutes < self.thresholds.soup_min_total_minutes:
            issues.append(
                QualityIssue(
                    code="COOKING_METHOD_TIME_SUSPICIOUS",
                    message="Soup-like recipe with total_time < 15 minutes",
                    severity="warning",
                )
            )

        if recipe.requires_cooking:
            cooking_methods_real = methods - {CookingMethod.NO_COOK}
            has_process_hint = bool(cooking_methods_real) or any(
                (s.duration_minutes or 0) > 0 or s.temperature_c is not None
                for s in recipe.steps
            )
            if not has_process_hint:
                issues.append(
                    QualityIssue(
                        code="COOKING_STEP_MISSING",
                        message="requires_cooking=true but no cooking process signals",
                        severity="warning",
                    )
                )

        issues.append(
            QualityIssue(
                code="TIME_REQUIRES_HUMAN_REVIEW",
                message="Time checks are structural only; kitchen timing not verified",
                severity="info",
            )
        )

        has_error = any(i.severity == "error" for i in issues)
        has_warning = any(i.severity == "warning" for i in issues)
        status = "failed" if has_error else ("warning" if has_warning else "passed")
        return CheckSummary(
            name="time_plausibility",
            status=status,
            issues=issues,
            metrics=metrics,
        )
