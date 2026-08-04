"""Centralized thresholds for Recipe Quality checks (Sprint 10.7)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class QualityThresholds:
    quick_total_minutes: int = 30
    quick_active_minutes: int = 20
    batch_min_servings: float = 4.0
    batch_min_storage_days: int = 2
    leftover_min_storage_days: int = 1
    high_protein_g_per_100g: float = 10.0
    high_protein_g_per_portion: float = 25.0
    high_protein_calorie_share: float = 0.20
    low_energy_density_kcal: float = 150.0
    medium_energy_density_kcal: float = 250.0
    nutrition_kcal_relative_tolerance: float = 0.20
    nutrition_kcal_absolute_tolerance: float = 25.0
    suspicious_protein_g_per_100g: float = 40.0
    suspicious_fat_g_per_100g: float = 50.0
    suspicious_carbs_g_per_100g: float = 90.0
    seasoning_mass_share_warning: float = 0.05
    oil_mass_share_warning: float = 0.12
    baking_min_cook_minutes: int = 10
    slow_cooking_min_total_minutes: int = 30
    soup_min_total_minutes: int = 15
    family_max_confidence_without_human: float = 0.7
    leftover_max_derived_score: float = 0.7
    weight_loss_goal_gap_warning: float = 0.25
    muscle_gain_goal_gap_warning: float = 0.25


DEFAULT_QUALITY_THRESHOLDS = QualityThresholds()

AUDIT_VERSION = "quality_audit_v1"

SEED_PROVENANCE_NOTES = (
    "Seed recipe created as structured catalog data; "
    "culinary and source verification not yet completed."
)
