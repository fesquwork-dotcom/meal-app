"""Deterministic confidence score for recipe quality verification."""

from __future__ import annotations

from recipes.quality.enums import QualityStatus
from recipes.quality.models import QualityIssue, RecipeQualityResult


class RecipeQualityConfidenceCalculator:
    """Confidence in data verification — not taste quality."""

    CAPS: dict[QualityStatus, float] = {
        QualityStatus.UNREVIEWED: 0.15,
        QualityStatus.SCHEMA_VALIDATED: 0.30,
        QualityStatus.COMPUTATIONALLY_CHECKED: 0.50,
        QualityStatus.SOURCE_VERIFIED: 0.70,
        QualityStatus.HUMAN_REVIEWED: 0.85,
        QualityStatus.KITCHEN_TESTED: 0.95,
        QualityStatus.APPROVED: 1.0,
        QualityStatus.REJECTED: 0.05,
    }

    def calculate(
        self,
        *,
        quality_status: QualityStatus,
        source_count: int,
        blocking_errors: list[QualityIssue],
        warnings: list[QualityIssue],
        has_human_review: bool = False,
        has_kitchen_test: bool = False,
    ) -> float:
        base = self.CAPS.get(quality_status, 0.15)
        if blocking_errors:
            return min(base, 0.20)
        score = base * 0.7
        if quality_status in {
            QualityStatus.SCHEMA_VALIDATED,
            QualityStatus.COMPUTATIONALLY_CHECKED,
        }:
            # Agent recipes without sources stay capped
            if source_count == 0:
                score = min(score, 0.45 if quality_status == QualityStatus.COMPUTATIONALLY_CHECKED else 0.28)
        score += min(0.15, 0.05 * source_count)
        if has_human_review:
            score += 0.1
        if has_kitchen_test:
            score += 0.1
        warning_penalty = min(0.15, 0.01 * len([w for w in warnings if w.severity == "warning"]))
        score -= warning_penalty
        return round(max(0.0, min(self.CAPS[quality_status], score)), 3)

    def from_result(self, result: RecipeQualityResult) -> float:
        return self.calculate(
            quality_status=result.suggested_quality_status,
            source_count=int(result.source_summary.get("source_count") or 0),
            blocking_errors=result.blocking_errors,
            warnings=result.warnings,
            has_human_review="human_reviewed" in result.approval_blockers
            or result.current_quality_status
            in {QualityStatus.HUMAN_REVIEWED, QualityStatus.APPROVED, QualityStatus.KITCHEN_TESTED},
            has_kitchen_test=result.current_quality_status
            in {QualityStatus.KITCHEN_TESTED, QualityStatus.APPROVED},
        )
