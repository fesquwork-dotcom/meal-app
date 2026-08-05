"""Recipe quality & provenance enums (Sprint 10.7)."""

from __future__ import annotations

from enum import StrEnum


class CreationMethod(StrEnum):
    AGENT_GENERATED = "agent_generated"
    SOURCE_ADAPTED = "source_adapted"
    HUMAN_AUTHORED = "human_authored"
    IMPORTED_STRUCTURED = "imported_structured"
    KITCHEN_TESTED_VERSION = "kitchen_tested_version"


class QualityStatus(StrEnum):
    UNREVIEWED = "unreviewed"
    SCHEMA_VALIDATED = "schema_validated"
    COMPUTATIONALLY_CHECKED = "computationally_checked"
    SOURCE_VERIFIED = "source_verified"
    HUMAN_REVIEWED = "human_reviewed"
    KITCHEN_TESTED = "kitchen_tested"
    APPROVED = "approved"
    REJECTED = "rejected"


class SourceType(StrEnum):
    CULINARY_WEBSITE = "culinary_website"
    COOKBOOK = "cookbook"
    MANUFACTURER_INSTRUCTION = "manufacturer_instruction"
    NUTRITION_DATABASE = "nutrition_database"
    HUMAN_EXPERT = "human_expert"
    INTERNAL_TEST = "internal_test"
    OTHER = "other"


class ReviewType(StrEnum):
    SCHEMA = "schema"
    NUTRITION = "nutrition"
    CULINARY = "culinary"
    SOURCE = "source"
    METADATA = "metadata"
    KITCHEN_TEST = "kitchen_test"


class ReviewOutcome(StrEnum):
    PASSED = "passed"
    PASSED_WITH_WARNINGS = "passed_with_warnings"
    FAILED = "failed"
    NEEDS_REVIEW = "needs_review"


class ReviewerType(StrEnum):
    SYSTEM = "system"
    AGENT = "agent"
    HUMAN = "human"
    EXPERT = "expert"
    KITCHEN_TEST = "kitchen_test"


class EvidenceType(StrEnum):
    DERIVED = "derived"
    DECLARED = "declared"
    SOURCE_SUPPORTED = "source_supported"
    HUMAN_CONFIRMED = "human_confirmed"
    KITCHEN_CONFIRMED = "kitchen_confirmed"
    INSUFFICIENT_DATA = "insufficient_data"


class PatternType(StrEnum):
    QUICK_MEAL = "quick_meal"
    BATCH_FRIENDLY = "batch_friendly"
    LEFTOVER_FRIENDLY = "leftover_friendly"
    HIGH_PROTEIN = "high_protein"
    HIGH_FIBER = "high_fiber"
    LOW_ENERGY_DENSITY = "low_energy_density"
    BUDGET_FRIENDLY = "budget_friendly"
    WEIGHT_LOSS_COMPATIBLE = "weight_loss_compatible"
    MUSCLE_GAIN_COMPATIBLE = "muscle_gain_compatible"
    FAMILY_FRIENDLY = "family_friendly"
    PORTABLE_MEAL = "portable_meal"
    FREEZER_FRIENDLY = "freezer_friendly"


class MetadataRecommendationType(StrEnum):
    REMOVE_UNSUPPORTED_TAG = "remove_unsupported_tag"
    ADD_DERIVED_TAG = "add_derived_tag"
    REVIEW_ROLE = "review_role"
    REVIEW_GOAL_SCORE = "review_goal_score"
    REVIEW_TIME = "review_time"
    REVIEW_YIELD = "review_yield"
    REVIEW_NUTRITION = "review_nutrition"
    SOURCE_VERIFICATION_REQUIRED = "source_verification_required"
    HUMAN_REVIEW_REQUIRED = "human_review_required"
    KITCHEN_TEST_RECOMMENDED = "kitchen_test_recommended"
    RECIPE_SOURCE_MISMATCH = "recipe_source_mismatch"


# Quality status ordering for comparisons (higher = more trusted).
QUALITY_STATUS_RANK: dict[QualityStatus, int] = {
    QualityStatus.UNREVIEWED: 0,
    QualityStatus.SCHEMA_VALIDATED: 1,
    QualityStatus.COMPUTATIONALLY_CHECKED: 2,
    QualityStatus.SOURCE_VERIFIED: 3,
    QualityStatus.HUMAN_REVIEWED: 4,
    QualityStatus.KITCHEN_TESTED: 5,
    QualityStatus.APPROVED: 6,
    QualityStatus.REJECTED: -1,
}
