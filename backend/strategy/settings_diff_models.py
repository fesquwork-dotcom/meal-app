"""Typed models for strategy settings diff (Sprint 5.24)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

STRATEGY_SETTINGS_DIFF_VERSION = 1

ComparisonQuality = Literal["exact", "partial", "unavailable"]
ChangeType = Literal["changed", "added", "removed", "source_changed"]


class StrategySettingValue(BaseModel):
    model_config = ConfigDict(extra="ignore")

    display_value: str
    raw_value: str | int | float | bool | list[str] | None = None
    source: str | None = None


class StrategySettingChange(BaseModel):
    model_config = ConfigDict(extra="ignore")

    key: str
    category: str
    change_type: ChangeType
    title: str
    description: str
    current: StrategySettingValue | None = None
    next: StrategySettingValue | None = None
    priority: int


class StrategySettingsDiff(BaseModel):
    model_config = ConfigDict(extra="ignore")

    version: int = STRATEGY_SETTINGS_DIFF_VERSION
    has_changes: bool
    changes: list[StrategySettingChange] = Field(default_factory=list)
    unchanged_count: int = 0
    comparison_quality: ComparisonQuality = "exact"
