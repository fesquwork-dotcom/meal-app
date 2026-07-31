"""API models for profile persistence."""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field

from dietary_constraints import MAX_DIETARY_CONSTRAINTS, DietaryConstraintInput
from cooking_preferences import CookingPreferencesInput
from planning_preferences import PlanningPreferencesInput


class ProfilePayload(BaseModel):
    """Profile PUT payload.

    `dietary_constraints` is the canonical exclusion field. The deprecated raw
    `allergies` string is not accepted as input anymore; the remaining legacy
    values can only be updated through `legacy_allergies` (classification
    flow). When `legacy_allergies` is None the stored legacy list is kept.
    """

    model_config = ConfigDict(extra="ignore")

    first_name: str = ""
    days: int = 5
    budget: float = 3000.0
    meal_types: Optional[List[str]] = None
    meals_per_day: int = 3
    persons: int = 2
    proteins: List[str] = Field(default_factory=list)
    goal: str = "home"
    cooktime: str = "medium"
    dietary_constraints: List[DietaryConstraintInput] = Field(
        default_factory=list, max_length=MAX_DIETARY_CONSTRAINTS
    )
    legacy_allergies: Optional[List[str]] = None
    cooking_preferences: Optional[CookingPreferencesInput] = None
    planning_preferences: Optional[PlanningPreferencesInput] = None
    store: str = "any"


class UpdateProfileRequest(ProfilePayload):
    expected_revision: int = Field(ge=0, le=1_000_000)


class ProfileResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    profile: dict[str, object]
    legacy_constraints: list[str] = Field(default_factory=list)
    requires_constraint_review: bool = False
    revision: int
    updated_at: str | None = None
