"""Shared quality check issue / result dataclasses."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal

from recipes.quality.enums import (
    EvidenceType,
    MetadataRecommendationType,
    PatternType,
    QualityStatus,
)


Severity = Literal["error", "warning", "info"]


@dataclass
class QualityIssue:
    code: str
    message: str
    severity: Severity = "warning"
    path: str | None = None
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class CheckSummary:
    name: str
    status: str  # passed | failed | warning | insufficient_data | skipped
    issues: list[QualityIssue] = field(default_factory=list)
    metrics: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "status": self.status,
            "issues": [i.to_dict() for i in self.issues],
            "metrics": self.metrics,
        }


@dataclass
class PatternEvidenceItem:
    pattern_type: PatternType
    evidence_type: EvidenceType
    value_bool: bool | None = None
    score: float | None = None
    rule_code: str | None = None
    evidence_json: dict[str, Any] = field(default_factory=dict)
    manually_overridden: bool = False
    override_reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "pattern_type": self.pattern_type.value,
            "evidence_type": self.evidence_type.value,
            "value_bool": self.value_bool,
            "score": self.score,
            "rule_code": self.rule_code,
            "evidence_json": self.evidence_json,
            "manually_overridden": self.manually_overridden,
            "override_reason": self.override_reason,
        }


@dataclass
class PatternDerivationResult:
    recipe_id: str
    evidence: list[PatternEvidenceItem] = field(default_factory=list)
    inconsistencies: list[QualityIssue] = field(default_factory=list)
    warnings: list[QualityIssue] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "recipe_id": self.recipe_id,
            "evidence": [e.to_dict() for e in self.evidence],
            "inconsistencies": [i.to_dict() for i in self.inconsistencies],
            "warnings": [w.to_dict() for w in self.warnings],
        }


@dataclass
class MetadataRecommendation:
    recipe_id: str
    recommendation_type: MetadataRecommendationType
    field: str
    current_value: Any
    derived_value: Any
    evidence: dict[str, Any]
    severity: Severity
    reason_code: str
    message: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "recipe_id": self.recipe_id,
            "recommendation_type": self.recommendation_type.value,
            "field": self.field,
            "current_value": self.current_value,
            "derived_value": self.derived_value,
            "evidence": self.evidence,
            "severity": self.severity,
            "reason_code": self.reason_code,
            "message": self.message,
        }


@dataclass
class RecipeQualityResult:
    recipe_id: str
    current_quality_status: QualityStatus | None
    suggested_quality_status: QualityStatus
    blocking_errors: list[QualityIssue] = field(default_factory=list)
    warnings: list[QualityIssue] = field(default_factory=list)
    checks: list[CheckSummary] = field(default_factory=list)
    pattern_evidence: list[PatternEvidenceItem] = field(default_factory=list)
    source_summary: dict[str, Any] = field(default_factory=dict)
    nutrition_summary: dict[str, Any] = field(default_factory=dict)
    yield_summary: dict[str, Any] = field(default_factory=dict)
    time_summary: dict[str, Any] = field(default_factory=dict)
    proportion_summary: dict[str, Any] = field(default_factory=dict)
    approval_eligible: bool = False
    approval_blockers: list[str] = field(default_factory=list)
    recommendations: list[MetadataRecommendation] = field(default_factory=list)
    confidence_score: float | None = None
    creation_method: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "recipe_id": self.recipe_id,
            "current_quality_status": (
                self.current_quality_status.value if self.current_quality_status else None
            ),
            "suggested_quality_status": self.suggested_quality_status.value,
            "blocking_errors": [e.to_dict() for e in self.blocking_errors],
            "warnings": [w.to_dict() for w in self.warnings],
            "checks": [c.to_dict() for c in self.checks],
            "pattern_evidence": [p.to_dict() for p in self.pattern_evidence],
            "source_summary": self.source_summary,
            "nutrition_summary": self.nutrition_summary,
            "yield_summary": self.yield_summary,
            "time_summary": self.time_summary,
            "proportion_summary": self.proportion_summary,
            "approval_eligible": self.approval_eligible,
            "approval_blockers": self.approval_blockers,
            "recommendations": [r.to_dict() for r in self.recommendations],
            "confidence_score": self.confidence_score,
            "creation_method": self.creation_method,
        }
