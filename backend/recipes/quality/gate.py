"""RecipeQualityGate — evaluate quality without mixing RecipeStatus."""

from __future__ import annotations

from typing import Literal

import aiosqlite

from recipes.models import Recipe
from recipes.quality.confidence import RecipeQualityConfidenceCalculator
from recipes.quality.config import AUDIT_VERSION, DEFAULT_QUALITY_THRESHOLDS, QualityThresholds
from recipes.quality.enums import QualityStatus
from recipes.quality.models import QualityIssue, RecipeQualityResult
from recipes.quality.nutrition import RecipeNutritionCalculator
from recipes.quality.pattern_deriver import RecipePatternDeriver
from recipes.quality.proportion_checker import RecipeProportionChecker
from recipes.quality.provenance import ProvenanceStore
from recipes.quality.recommendations import build_recommendations
from recipes.quality.time_checker import RecipeTimeChecker
from recipes.quality.yield_checker import RecipeYieldChecker

GateMode = Literal["read_only", "apply"]


class RecipeQualityGate:
    """Automatic audit may only raise as far as computationally_checked."""

    AUTO_MAX_STATUS = QualityStatus.COMPUTATIONALLY_CHECKED

    def __init__(self, thresholds: QualityThresholds | None = None) -> None:
        self.thresholds = thresholds or DEFAULT_QUALITY_THRESHOLDS
        self.nutrition = RecipeNutritionCalculator(self.thresholds)
        self.yield_checker = RecipeYieldChecker()
        self.time_checker = RecipeTimeChecker(self.thresholds)
        self.proportion = RecipeProportionChecker(self.thresholds)
        self.patterns = RecipePatternDeriver(self.thresholds)
        self.confidence = RecipeQualityConfidenceCalculator()
        self.store = ProvenanceStore()

    async def evaluate(
        self,
        recipe: Recipe,
        db: aiosqlite.Connection,
        *,
        mode: GateMode = "read_only",
    ) -> RecipeQualityResult:
        provenance = await self.store.get_provenance(db, recipe.id)
        sources = await self.store.list_sources(db, recipe.id)
        source_count = len(sources)

        current_status: QualityStatus | None = None
        creation_method = None
        if provenance:
            current_status = QualityStatus(provenance["quality_status"])
            creation_method = provenance.get("creation_method")
        else:
            current_status = QualityStatus.SCHEMA_VALIDATED

        snap = self.nutrition.check_snapshot(recipe)
        ing = await self.nutrition.calculate_from_ingredients(recipe, db)
        yld = self.yield_checker.check(recipe)
        time_c = self.time_checker.check(recipe)
        prop = self.proportion.check(recipe)
        pattern_result = self.patterns.derive(recipe)

        checks = [snap, ing, yld, time_c, prop]
        blocking: list[QualityIssue] = []
        warnings: list[QualityIssue] = []

        for check in checks:
            for issue in check.issues:
                if issue.severity == "error":
                    blocking.append(issue)
                elif issue.severity == "warning":
                    warnings.append(issue)

        for issue in pattern_result.inconsistencies:
            if issue.severity == "error":
                blocking.append(issue)
            else:
                warnings.append(issue)
        warnings.extend(pattern_result.warnings)

        if provenance is None:
            warnings.append(
                QualityIssue(
                    code="PROVENANCE_MISSING",
                    message="No provenance record; defaulting to schema_validated",
                    severity="warning",
                )
            )

        # Suggested status: never auto-assign trust tiers.
        if blocking:
            suggested = QualityStatus.SCHEMA_VALIDATED
        else:
            suggested = QualityStatus.COMPUTATIONALLY_CHECKED

        # If already higher via human process, keep suggesting that for display
        # but auto apply still capped.
        display_suggested = suggested
        if current_status in {
            QualityStatus.SOURCE_VERIFIED,
            QualityStatus.HUMAN_REVIEWED,
            QualityStatus.KITCHEN_TESTED,
            QualityStatus.APPROVED,
        }:
            display_suggested = current_status

        approval_blockers = [
            "source_verified_required",
            "human_reviewed_or_kitchen_tested_required",
            "human_approval_required",
        ]
        if source_count == 0:
            approval_blockers.insert(0, "no_sources")
        if blocking:
            approval_blockers.insert(0, "blocking_errors")
        if creation_method == "agent_generated":
            approval_blockers.append("agent_generated_not_source_verified")

        recommendations = build_recommendations(
            recipe, pattern_result, blocking + warnings
        )

        result = RecipeQualityResult(
            recipe_id=recipe.id,
            current_quality_status=current_status,
            suggested_quality_status=display_suggested,
            blocking_errors=blocking,
            warnings=[w for w in warnings if w.severity == "warning"],
            checks=checks,
            pattern_evidence=pattern_result.evidence,
            source_summary={
                "source_count": source_count,
                "source_verified": False,
                "sources": [
                    {
                        "source_type": s.get("source_type"),
                        "source_title": s.get("source_title"),
                        "source_reference": s.get("source_reference"),
                    }
                    for s in sources
                ],
            },
            nutrition_summary={
                "snapshot": snap.to_dict(),
                "ingredient_calculation": ing.to_dict(),
            },
            yield_summary=yld.to_dict(),
            time_summary=time_c.to_dict(),
            proportion_summary=prop.to_dict(),
            approval_eligible=False,
            approval_blockers=approval_blockers,
            recommendations=recommendations,
            creation_method=creation_method,
        )
        result.confidence_score = self.confidence.calculate(
            quality_status=suggested if not blocking else QualityStatus.SCHEMA_VALIDATED,
            source_count=source_count,
            blocking_errors=blocking,
            warnings=result.warnings,
        )

        if mode == "apply":
            await self._apply(db, recipe.id, result, suggested, blocking)

        return result

    async def _apply(
        self,
        db: aiosqlite.Connection,
        recipe_id: str,
        result: RecipeQualityResult,
        suggested: QualityStatus,
        blocking: list[QualityIssue],
    ) -> None:
        await self.store.ensure_default_provenance(db, recipe_id)
        # Only elevate to computationally_checked; never trust tiers.
        target = (
            QualityStatus.SCHEMA_VALIDATED
            if blocking
            else QualityStatus.COMPUTATIONALLY_CHECKED
        )
        assert target in {
            QualityStatus.SCHEMA_VALIDATED,
            QualityStatus.COMPUTATIONALLY_CHECKED,
        }
        await self.store.update_quality_status(
            db,
            recipe_id,
            target,
            confidence_score=result.confidence_score,
        )
        await self.store.replace_derived_pattern_evidence(
            db, recipe_id, result.pattern_evidence, AUDIT_VERSION
        )
        result.suggested_quality_status = target
        # Refresh current after apply
        result.current_quality_status = target
