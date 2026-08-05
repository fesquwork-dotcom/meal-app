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
    """Automatic audit may raise to source_verified when sources + checks pass.

    Never auto-assigns human_reviewed, kitchen_tested, or approved.
    """

    AUTO_MAX_STATUS = QualityStatus.SOURCE_VERIFIED
    SOURCE_VERIFIED_MIN_SOURCES = 2

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

        # Suggested status: computational max, or source_verified when sources exist.
        if blocking:
            suggested = QualityStatus.SCHEMA_VALIDATED
        elif source_count >= self.SOURCE_VERIFIED_MIN_SOURCES:
            suggested = QualityStatus.SOURCE_VERIFIED
        else:
            suggested = QualityStatus.COMPUTATIONALLY_CHECKED

        # Preserve higher human/kitchen/approved tiers for display only.
        display_suggested = suggested
        if current_status in {
            QualityStatus.HUMAN_REVIEWED,
            QualityStatus.KITCHEN_TESTED,
            QualityStatus.APPROVED,
        }:
            display_suggested = current_status
        elif (
            current_status == QualityStatus.SOURCE_VERIFIED
            and source_count >= self.SOURCE_VERIFIED_MIN_SOURCES
            and not blocking
        ):
            display_suggested = QualityStatus.SOURCE_VERIFIED

        approval_blockers = [
            "human_reviewed_or_kitchen_tested_required",
            "human_approval_required",
        ]
        if source_count < self.SOURCE_VERIFIED_MIN_SOURCES:
            approval_blockers.insert(0, "source_verified_required")
        if source_count == 0:
            approval_blockers.insert(0, "no_sources")
        if blocking:
            approval_blockers.insert(0, "blocking_errors")
        if (
            creation_method == "agent_generated"
            and source_count < self.SOURCE_VERIFIED_MIN_SOURCES
        ):
            approval_blockers.append("agent_generated_not_source_verified")

        is_source_verified_status = (
            current_status == QualityStatus.SOURCE_VERIFIED
            or suggested == QualityStatus.SOURCE_VERIFIED
        )

        recommendations = build_recommendations(
            recipe,
            pattern_result,
            blocking + warnings,
            source_count=source_count,
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
                "source_verified": bool(
                    is_source_verified_status
                    and source_count >= self.SOURCE_VERIFIED_MIN_SOURCES
                    and not blocking
                ),
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
        conf_status = suggested if not blocking else QualityStatus.SCHEMA_VALIDATED
        result.confidence_score = self.confidence.calculate(
            quality_status=conf_status,
            source_count=source_count,
            blocking_errors=blocking,
            warnings=result.warnings,
        )

        if mode == "apply":
            await self._apply(db, recipe.id, result, suggested, blocking, source_count)

        return result

    async def _apply(
        self,
        db: aiosqlite.Connection,
        recipe_id: str,
        result: RecipeQualityResult,
        suggested: QualityStatus,
        blocking: list[QualityIssue],
        source_count: int,
    ) -> None:
        await self.store.ensure_default_provenance(db, recipe_id)
        # May elevate to source_verified; never human/kitchen/approved.
        if blocking:
            target = QualityStatus.SCHEMA_VALIDATED
        elif source_count >= self.SOURCE_VERIFIED_MIN_SOURCES:
            target = QualityStatus.SOURCE_VERIFIED
        else:
            target = QualityStatus.COMPUTATIONALLY_CHECKED
        assert target in {
            QualityStatus.SCHEMA_VALIDATED,
            QualityStatus.COMPUTATIONALLY_CHECKED,
            QualityStatus.SOURCE_VERIFIED,
        }
        # Do not demote human/kitchen/approved on apply.
        current = result.current_quality_status
        if current in {
            QualityStatus.HUMAN_REVIEWED,
            QualityStatus.KITCHEN_TESTED,
            QualityStatus.APPROVED,
        }:
            target = current
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
        result.current_quality_status = target
        result.source_summary["source_verified"] = (
            target == QualityStatus.SOURCE_VERIFIED
        )
